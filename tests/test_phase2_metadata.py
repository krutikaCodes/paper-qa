"""Phase 2 groundwork: OpenAlex affiliations, picking metadata clients, 429 handling.

All tests here are offline: no API keys and no network calls.
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from lmi import LiteLLMModel
from pydantic import ValidationError

from paperqa import Settings
from paperqa.docs import Docs, _parse_front_matter_institutions
from paperqa.clients import (
    CLIENTS_BY_NAME,
    DEFAULT_CLIENTS,
    get_clients_by_name,
)
from paperqa.clients.client_models import DOIOrTitleBasedProvider
from paperqa.clients.journal_quality import JournalQualityPostProcessor
from paperqa.clients.openalex import (
    OpenAlexProvider,
    get_first_author_affiliations,
    parse_openalex_to_doc_details,
    to_openalex_select_fields,
)
from paperqa.trust import score_trust
from paperqa.types import Context, Doc, DocDetails, ParsedMetadata, PQASession, Text
from paperqa.university_rankings import (
    THE_WORLD_UNIVERSITY_RANKINGS_TOP_100,
    top_university_matches,
)


def _authorship(name: str, insts: list[tuple[str, str | None]]) -> dict[str, Any]:
    """Build one OpenAlex 'authorships' entry: (institution name, country code)."""
    return {
        "raw_author_name": name,
        "institutions": [{"display_name": n, "country_code": c} for n, c in insts],
        "countries": sorted({c for _, c in insts if c}),
    }


AUTHORSHIPS = [
    _authorship("Ashish Vaswani", [("Google (United States)", "US")]),
    _authorship("Noam Shazeer", [("Google (United States)", "US")]),
    _authorship(
        "Niki Parmar",
        [("University of Southern California", "US"), ("University of Toronto", "CA")],
    ),
    # 4th author: must be ignored, we only look at the first 3
    _authorship("Jakob Uszkoreit", [("ETH Zurich", "CH")]),
]


@pytest.mark.parametrize(
    ("source_quality", "expected"),
    [
        ("low", 0.225),
        ("fair", 0.405),
        ("good", 0.513),
        ("excellent", 0.585),
        (0, 0.225),
        (1, 0.405),
        (2, 0.513),
        (3, 0.585),
    ],
)
def test_score_trust_normalizes_general_source_quality(
    source_quality: str | int, expected: float
) -> None:
    record = {
        "source_quality": source_quality,
        "citation_count": 0,
        "year": 2024,
        "is_retracted": False,
    }

    score = score_trust(record)

    assert score == pytest.approx(expected)
    assert record["trust_score"] == score


@pytest.mark.parametrize(
    ("journal_quality", "expected"),
    [
        ("poor quality", 0.225),
        ("peer-reviewed", 0.405),
        ("domain leading peer-reviewed", 0.513),
        ("highest quality peer-reviewed", 0.585),
    ],
)
def test_score_trust_keeps_journal_quality_compatibility(
    journal_quality: str, expected: float
) -> None:
    assert score_trust(
        {
            "journal_quality": journal_quality,
            "citation_count": 0,
            "year": 2024,
            "is_retracted": False,
        }
    ) == pytest.approx(expected)


def test_affiliations_first_three_authors_deduplicated() -> None:
    institutions, countries = get_first_author_affiliations(AUTHORSHIPS)
    assert institutions == [
        "Google (United States)",
        "University of Southern California",
        "University of Toronto",
    ], "Expected distinct institutions of authors 1-3, in order"
    assert countries == ["US", "CA"], "Expected distinct countries, 4th author ignored"


def test_score_trust_stores_normalized_score_on_doc_details() -> None:
    doc = DocDetails(
        docname="test",
        dockey="test",
        citation="Test paper",
        source_quality=2,
        citation_count=0,
        year=2024,
        is_retracted=False,
    )

    score = score_trust(doc)

    assert 0.0 <= score <= 1.0
    assert doc.trust_score == score


def test_score_trust_does_not_assume_unknown_sources_are_unretracted() -> None:
    record: dict[str, Any] = {}

    assert score_trust(record) == 0.0
    assert record["trust_score"] == 0.0


def test_score_trust_adds_ten_percent_for_top_university_affiliation() -> None:
    record = {
        "source_quality": 2,
        "citation_count": 0,
        "year": 2024,
        "is_retracted": False,
        "institutions": ["MIT"],
    }

    assert score_trust(record) == pytest.approx(0.613)
    assert record["top_university_affiliations"] == [
        "Massachusetts Institute of Technology"
    ]
    assert record["top_university_rank"] == 2


def test_top_university_matches_use_exact_normalized_names_and_aliases() -> None:
    assert len(THE_WORLD_UNIVERSITY_RANKINGS_TOP_100) == 100
    assert top_university_matches(["EPFL", "University of Oxford"]) == [
        ("University of Oxford", 1),
        ("École Polytechnique Fédérale de Lausanne", 36),
    ]
    assert top_university_matches(["University of California"]) == []


def test_front_matter_affiliation_response_is_normalized() -> None:
    assert _parse_front_matter_institutions(
        '```json\n{"institutions": ["University of Oxford", " University of Oxford "]}\n```'
    ) == ["University of Oxford"]


@pytest.mark.asyncio
async def test_docs_aadd_uses_front_matter_affiliations_as_fallback(
    tmp_path, monkeypatch
) -> None:
    paper = tmp_path / "paper.txt"
    paper.write_text("paper contents", encoding="utf-8")
    captured: dict[str, Any] = {}

    class MetadataClient:
        async def upgrade_doc_to_doc_details(self, doc: Doc, **kwargs) -> DocDetails:
            return DocDetails(
                **doc.model_dump(),
                title="A paper",
                doi="10.1234/example",
            )

    async def fake_call_single(self, messages, **kwargs):  # noqa: ARG001
        captured["prompt"] = messages[0].content
        return SimpleNamespace(text='{"institutions": ["University of Oxford"]}')

    # A real LiteLLMModel (the type checker rejects other classes), with no API call
    monkeypatch.setattr(LiteLLMModel, "call_single", fake_call_single)

    async def fake_read_doc(path, doc, **kwargs):
        text = Text(
            name="paper chunk",
            text="Author affiliation: University of Oxford. " * 3,
            doc=doc,
        )
        return [
            text
        ], ParsedMetadata(
            parsing_libraries=["test"],
            total_parsed_text_length=len(text.text),
        )

    async def fake_aadd_texts(self, texts, doc, settings=None, embedding_model=None):
        captured["doc"] = doc
        captured["text_doc"] = texts[0].doc
        return True

    monkeypatch.setattr("paperqa.docs.read_doc", fake_read_doc)
    monkeypatch.setattr(Docs, "aadd_texts", fake_aadd_texts)

    await Docs().aadd(
        paper,
        citation="A paper citation",
        title="A paper",
        doi="10.1234/example",
        settings=Settings(
            parsing={
                "extract_author_affiliations_from_front_matter": True,
            }
        ),
        llm_model=LiteLLMModel(name="fake-model"),
        metadata_client=MetadataClient(),
    )

    assert "opening text" in captured["prompt"]
    assert captured["doc"].institutions == ["University of Oxford"]
    assert captured["text_doc"] is captured["doc"]


@pytest.mark.parametrize("authorships", [None, [], [None], [{"institutions": None}]])
def test_affiliations_missing_data_is_none(authorships: Any) -> None:
    assert get_first_author_affiliations(authorships) == (None, None)


def test_affiliations_country_without_institution() -> None:
    institutions, countries = get_first_author_affiliations(
        [{"raw_author_name": "A", "institutions": [], "countries": ["GB"]}]
    )
    assert institutions is None
    assert countries == ["GB"]


def test_parse_openalex_sets_institutions_and_countries() -> None:
    details = parse_openalex_to_doc_details({
        "title": "Attention Is All You Need",
        "publication_year": 2017,
        "cited_by_count": 100,
        "type": "article",
        "authorships": AUTHORSHIPS,
    })
    assert details.year == 2017
    assert details.institutions is not None
    assert len(details.institutions) == 3
    assert details.countries == ["US", "CA"]


@pytest.mark.parametrize(
    ("source", "expected_quality"),
    [
        ({"type": "journal", "is_core": True, "is_in_doaj": True}, 3),
        ({"type": "journal", "is_in_doaj": True}, 2),
        ({"type": "journal", "is_core": False, "is_in_doaj": False}, 1),
        ({"type": "repository", "is_core": False, "is_in_doaj": False}, None),
        ({"type": "other"}, None),
    ],
)
def test_parse_openalex_source_quality_from_curated_flags(
    source: dict[str, Any], expected_quality: int | None
) -> None:
    details = parse_openalex_to_doc_details({
        "title": "A publication",
        "primary_location": {"source": source},
    })

    assert details.source_quality == expected_quality


def test_parse_openalex_source_quality_uses_best_location() -> None:
    details = parse_openalex_to_doc_details({
        "title": "A publication",
        "primary_location": {
            "source": {"type": "repository", "is_core": False, "is_in_doaj": False}
        },
        "locations": [
            {"source": {"type": "repository", "is_core": False, "is_in_doaj": False}},
            {"source": {"type": "conference", "is_core": True}},
        ],
    })

    assert details.source_quality == 3


def test_docdetails_merge_keeps_affiliations() -> None:
    # e.g. Crossref (no affiliations) + OpenAlex (with affiliations)
    crossref = DocDetails(title="T", doi="10.1/x")
    openalex = DocDetails(
        title="T", doi="10.1/x", institutions=["MIT"], countries=["US"]
    )
    for merged in (crossref + openalex, openalex + crossref):
        assert merged.institutions == ["MIT"]
        assert merged.countries == ["US"]


def test_docdetails_merge_does_not_replace_known_source_quality_with_unknown() -> None:
    openalex = DocDetails(source_quality=2)
    journal_quality_unknown = DocDetails(
        source_quality=DocDetails.UNDEFINED_JOURNAL_QUALITY
    )

    assert (openalex + journal_quality_unknown).source_quality == 2
    assert (journal_quality_unknown + openalex).source_quality == 2


def test_get_clients_by_name() -> None:
    assert get_clients_by_name(["openalex", "journal_quality"]) == (
        OpenAlexProvider,
        JournalQualityPostProcessor,
    )
    assert set(CLIENTS_BY_NAME) >= {"crossref", "semantic_scholar", "retractions"}
    with pytest.raises(ValueError, match="Unknown metadata client"):
        get_clients_by_name(["open_alex"])


def test_metadata_clients_setting() -> None:
    assert Settings().parsing.metadata_clients is None, "Default must stay unchanged"
    s = Settings(parsing={"metadata_clients": ["openalex", "journal_quality"]})
    assert s.parsing.metadata_clients == ["openalex", "journal_quality"]
    with pytest.raises(ValidationError, match="Unknown metadata client"):
        Settings(parsing={"metadata_clients": ["opnealex"]})
    assert DEFAULT_CLIENTS, "Original default clients still available"


def test_phase2_switches_default() -> None:
    # All Phase 2 switches are off by default, so "off" means the original behavior
    s = Settings()
    assert s.agent.apply_year_filter is False
    assert s.agent.show_source_diversity is False
    assert s.answer.use_trust_score is False
    assert s.parsing.extract_author_affiliations_from_front_matter is False


@pytest.mark.asyncio
async def test_context_serializer_ranks_by_relevance_and_trust() -> None:
    contexts = [
        Context(
            context="high relevance, low trust",
            score=10,
            text=Text(
                name="low-trust",
                text="",
                doc=DocDetails(
                    docname="low-trust",
                    dockey="low",
                    citation="low",
                    trust_score=0.2,
                ),
            ),
        ),
        Context(
            context="lower relevance, high trust",
            score=5,
            text=Text(
                name="high-trust",
                text="",
                doc=DocDetails(
                    docname="high-trust",
                    dockey="high",
                    citation="high",
                    trust_score=1.0,
                ),
            ),
        ),
    ]

    relevance_only = await Settings(
        answer={"use_trust_score": False}
    ).context_serializer(contexts, question="question", pre_str=None)
    trust_weighted = await Settings(
        answer={"use_trust_score": True}
    ).context_serializer(contexts, question="question", pre_str=None)

    assert relevance_only.index("high relevance, low trust") < relevance_only.index(
        "lower relevance, high trust"
    )
    assert trust_weighted.index("lower relevance, high trust") < trust_weighted.index(
        "high relevance, low trust"
    )
    assert "Source trust score: 1.00/1.00" in trust_weighted
    assert "weigh each source's trust score" in trust_weighted


def test_formatted_references_include_trust_score_when_enabled() -> None:
    session = PQASession(
        question="Question",
        raw_answer="Answer (pqac-a020507f).",
        contexts=[
            Context(
                id="pqac-a020507f",
                context="Evidence",
                text=Text(
                    name="paper",
                    text="Evidence",
                    doc=DocDetails(
                        docname="paper",
                        dockey="paper",
                        citation="Test paper",
                        trust_score=0.73,
                        top_university_affiliations=["University of Oxford"],
                    ),
                ),
            )
        ],
    )

    session.populate_formatted_answers_and_bib_from_raw_answer(
        use_trust_score=True
    )

    assert "Trust score: 0.73/1.00" in session.references
    assert "THE 2027 top-100 affiliation: University of Oxford" in session.references


def test_formatted_answer_lists_cited_papers_by_trust_score() -> None:
    session = PQASession(
        question="Question",
        raw_answer="Answer (pqac-low00001) and (pqac-high0001).",
        contexts=[
            Context(
                id="pqac-low00001",
                context="Low-trust evidence",
                text=Text(
                    name="low-trust",
                    text="Evidence",
                    doc=DocDetails(
                        docname="low-trust",
                        dockey="low",
                        citation="Lower trust paper",
                        title="Lower trust paper",
                        trust_score=0.2,
                    ),
                ),
            ),
            Context(
                id="pqac-high0001",
                context="High-trust evidence",
                text=Text(
                    name="high-trust",
                    text="Evidence",
                    doc=DocDetails(
                        docname="high-trust",
                        dockey="high",
                        citation="Higher trust paper",
                        title="Higher trust paper",
                        trust_score=0.9,
                    ),
                ),
            ),
            Context(
                id="pqac-unused01",
                context="Uncited evidence",
                text=Text(
                    name="uncited",
                    text="Evidence",
                    doc=DocDetails(
                        docname="uncited",
                        dockey="uncited",
                        citation="Uncited paper",
                        title="Uncited paper",
                        trust_score=1.0,
                    ),
                ),
            ),
        ],
    )

    session.populate_formatted_answers_and_bib_from_raw_answer(
        use_trust_score=True
    )

    table = session.formatted_answer.split(
        "Papers cited, ranked by trust score\n\n", maxsplit=1
    )[1].split("\n\nReferences", maxsplit=1)[0]
    assert table.index("Higher trust paper") < table.index("Lower trust paper")
    assert "| 1 | Higher trust paper | 0.90 |" in table
    assert "| 2 | Lower trust paper | 0.20 |" in table
    assert "Uncited paper" not in table


def test_trust_score_comparison_lists_all_indexed_papers() -> None:
    docs = Docs(
        docs={
            "low": DocDetails(
                docname="low",
                dockey="low",
                citation="Lower trust paper",
                title="Lower trust paper",
                trust_score=0.2,
            ),
            "high": DocDetails(
                docname="high",
                dockey="high",
                citation="Higher trust paper",
                title="Higher trust paper",
                trust_score=0.9,
            ),
        }
    )

    session = asyncio.run(
        docs.aquery(
            "How do these papers compare with regards to trust score?",
            settings=Settings(answer={"use_trust_score": True}),
        )
    )

    assert "| 1 | Higher trust paper | 0.90 |" in session.answer
    assert "| 2 | Lower trust paper | 0.20 |" in session.answer
    assert "Papers ranked by trust score" in session.formatted_answer
    assert session.contexts == []


class _RateLimitedProvider(DOIOrTitleBasedProvider):
    """Fake provider that always answers HTTP 429, like Semantic Scholar did."""

    async def _query(self, query: Any) -> DocDetails | None:  # noqa: ARG002
        request = httpx.Request("GET", "https://example.org")
        raise httpx.HTTPStatusError(
            "Too Many Requests",
            request=request,
            response=httpx.Response(429, request=request),
        )


@pytest.mark.asyncio
async def test_http_429_skips_provider_instead_of_crashing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with httpx.AsyncClient() as client:
        result = await _RateLimitedProvider().query(
            {"title": "Attention Is All You Need", "client": client}
        )
    assert result is None, "A 429 should skip the provider, not raise"
    assert "HTTP 429" in caplog.text


def test_openalex_select_fields_translated() -> None:
    # The index builder asks for these names, which OpenAlex rejects with HTTP 400
    selected = to_openalex_select_fields(["author", "journal", "title", "year"])
    assert "author" not in selected
    assert "journal" not in selected
    assert "year" not in selected
    assert {"authorships", "primary_location", "publication_year", "title"} <= set(
        selected
    )
    assert "cited_by_count" in selected, "Citation count is always requested"
    assert len(selected) == len(set(selected)), "No duplicate names"
    # Requests that already use OpenAlex names stay exactly as before
    assert to_openalex_select_fields(["doi", "open_access", "title"]) == [
        "doi",
        "open_access",
        "title",
    ]
