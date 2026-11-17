"""Phase 2 enhancement 2: low-trust warning and retraction status.

Trust-score formula tests are in tests/test_phase2_metadata.py. Everything here is
offline: evidence gathering is faked, so there are no API calls.
"""

from typing import Any

import pytest
from lmi import SparseEmbeddingModel

from paperqa import Docs, Settings
from paperqa.agents.env import settings_to_tools
from paperqa.agents.tools import EnvironmentState, GatherEvidence, low_trust_summary
from paperqa.clients.openalex import (
    parse_openalex_to_doc_details,
    to_openalex_select_fields,
)
from paperqa.trust import LOW_TRUST_THRESHOLD
from paperqa.types import Context, DocDetails, PQASession, Text


def _context(name: str, trust: float, retracted: bool = False, score: int = 8) -> Context:
    doc = DocDetails(
        docname=name,
        dockey=name,
        citation=f"{name} citation",
        trust_score=trust,
        is_retracted=retracted,
    )
    doc.docname = name  # Otherwise generated from (missing) authors, year and title
    text = Text(text=f"{name} text", name=f"{name} pages 1-2", doc=doc)
    return Context(context=f"{name} summary", text=text, score=score)


def test_threshold_is_plan_value() -> None:
    assert LOW_TRUST_THRESHOLD == 0.6


def test_warning_counts_low_trust_among_top_sources() -> None:
    contexts = [
        _context("attention", 0.80),
        _context("preprint", 0.38),
        _context("retracted", 0.0, retracted=True),
        _context("dpr", 0.82),
    ]
    summary = low_trust_summary(contexts, max_sources=5)
    assert summary.startswith(
        "Trust check: 2 of your top 4 source(s) are low-trust (trust score below 0.60):"
    )
    assert "preprint (0.38)" in summary
    assert "retracted (0.00, RETRACTED, do not cite)" in summary
    assert "search for better-supported papers" in summary


def test_warning_checks_only_top_distinct_papers() -> None:
    attention = _context("attention", 0.80)
    contexts = [
        attention,
        Context(context="more", text=attention.text, score=7),  # same paper again
        _context("dpr", 0.82),
        _context("preprint", 0.38),  # 3rd distinct paper, outside the top 2
    ]
    summary = low_trust_summary(contexts, max_sources=2)
    assert summary == (
        "Trust check: all top 2 source(s) are trusted (trust score 0.60 or higher)."
    )


def test_warning_without_sources() -> None:
    assert low_trust_summary([], max_sources=5) == "Trust check: no sources yet."


def _gather_tool(
    use_trust: bool, contexts: list[Context], monkeypatch: pytest.MonkeyPatch
) -> GatherEvidence:
    async def fake_aget_evidence(
        self: Docs, query: PQASession, **kwargs: Any  # noqa: ARG001
    ) -> PQASession:
        query.contexts = contexts
        return query

    monkeypatch.setattr(Docs, "aget_evidence", fake_aget_evidence)
    settings = Settings(embedding="sparse", answer={"use_trust_score": use_trust})
    return GatherEvidence(
        settings=settings,
        summary_llm_model=settings.get_summary_llm(),
        embedding_model=SparseEmbeddingModel(),
    )


def _state_with_a_paper() -> EnvironmentState:
    docs = Docs()
    doc = DocDetails(docname="paper", dockey="paper", citation="c")
    docs.docs[doc.dockey] = doc
    return EnvironmentState(docs=docs, session=PQASession(question="q"))


@pytest.mark.asyncio
async def test_gather_evidence_warns_when_on(monkeypatch: pytest.MonkeyPatch) -> None:
    contexts = [
        _context("preprint", 0.38),
        _context("attention", 0.80),
        _context("irrelevant", 0.10, score=0),  # score 0 = not relevant, not checked
    ]
    result = await _gather_tool(True, contexts, monkeypatch).gather_evidence(
        "q", state=_state_with_a_paper()
    )
    assert "Status: Paper Count=1" in result, "Original status line kept"
    assert "Trust check: 1 of your top 2 source(s) are low-trust" in result
    assert "irrelevant" not in result.split("Trust check:")[1]


@pytest.mark.asyncio
async def test_gather_evidence_unchanged_when_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _gather_tool(
        False, [_context("preprint", 0.38)], monkeypatch
    ).gather_evidence("q", state=_state_with_a_paper())
    assert "Trust check" not in result
    assert "Trust score" not in result


@pytest.mark.parametrize("use_trust", [True, False])
def test_gather_evidence_description_only_changes_when_on(use_trust: bool) -> None:
    settings = Settings(embedding="sparse", answer={"use_trust_score": use_trust})
    (gather,) = [
        t for t in settings_to_tools(settings) if t.info.name == "gather_evidence"
    ]
    assert (GatherEvidence.TRUST_DESCRIPTION in gather.info.description) is use_trust


@pytest.mark.parametrize("retracted", [True, False])
def test_openalex_reads_retraction_status(retracted: bool) -> None:
    details = parse_openalex_to_doc_details(
        {"title": "A paper", "publication_year": 2019, "is_retracted": retracted}
    )
    assert details.is_retracted is retracted


def test_openalex_retraction_unknown_when_not_returned() -> None:
    assert parse_openalex_to_doc_details({"title": "A paper"}).is_retracted is None


def test_openalex_selects_retraction_and_all_venues() -> None:
    # The index builder asks for these fields (see test_phase2_metadata.py)
    selected = to_openalex_select_fields(["title", "author", "journal", "year"])
    assert "is_retracted" in selected
    assert "locations" in selected, "All venues, for the venue quality"


@pytest.mark.asyncio
@pytest.mark.parametrize("with_evidence", [True, False])
async def test_trust_note_only_added_with_evidence(with_evidence: bool) -> None:
    # Regression check: with no evidence the note was the whole context, and the
    # out-of-corpus answer described the note instead of just "I cannot answer"
    contexts = [_context("attention", 0.80)] if with_evidence else []
    context_str = await Settings(
        embedding="sparse", answer={"use_trust_score": True}
    ).context_serializer(contexts, question="q", pre_str=None)
    assert ("weigh each source's trust score" in context_str) is with_evidence
