"""Phase 2 groundwork: OpenAlex affiliations, picking metadata clients, 429 handling.

All tests here are offline: no API keys and no network calls.
"""

from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from paperqa import Settings
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
from paperqa.types import DocDetails


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


def test_affiliations_first_three_authors_deduplicated() -> None:
    institutions, countries = get_first_author_affiliations(AUTHORSHIPS)
    assert institutions == [
        "Google (United States)",
        "University of Southern California",
        "University of Toronto",
    ], "Expected distinct institutions of authors 1-3, in order"
    assert countries == ["US", "CA"], "Expected distinct countries, 4th author ignored"


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


def test_docdetails_merge_keeps_affiliations() -> None:
    # e.g. Crossref (no affiliations) + OpenAlex (with affiliations)
    crossref = DocDetails(title="T", doi="10.1/x")
    openalex = DocDetails(
        title="T", doi="10.1/x", institutions=["MIT"], countries=["US"]
    )
    for merged in (crossref + openalex, openalex + crossref):
        assert merged.institutions == ["MIT"]
        assert merged.countries == ["US"]


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


def test_phase2_switches_default_off() -> None:
    s = Settings()
    assert s.agent.apply_year_filter is False
    assert s.agent.show_source_diversity is False
    assert s.answer.use_trust_score is False


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
