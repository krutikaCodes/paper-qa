"""Phase 2 enhancement 3: source diversity (institutions and countries) of evidence.

Offline: evidence gathering is faked, so there are no API calls.
"""

from typing import Any

import pytest
from lmi import SparseEmbeddingModel

from paperqa import Docs, Settings
from paperqa.agents.env import settings_to_tools
from paperqa.agents.tools import (
    EnvironmentState,
    GatherEvidence,
    source_diversity_summary,
)
from paperqa.types import Context, DocDetails, PQASession, Text


def _context(
    name: str,
    institutions: list[str] | None,
    countries: list[str] | None,
    score: int = 8,
) -> Context:
    doc = DocDetails(
        docname=name,
        dockey=name,
        citation=f"{name} citation",
        institutions=institutions,
        countries=countries,
    )
    text = Text(text=f"{name} text", name=f"{name} pages 1-2", doc=doc)
    return Context(context=f"{name} summary", text=text, score=score)


FUTUREHOUSE = ["Future House, Inc."]


def test_summary_counts_distinct_institutions_and_countries() -> None:
    paperqa2 = _context("paperqa2", [*FUTUREHOUSE, "University of Rochester"], ["US"])
    # Second piece of evidence from the same paper
    paperqa2_again = Context(context="more", text=paperqa2.text, score=6)
    contexts = [
        paperqa2,
        paperqa2_again,
        _context("selfrag", ["University of Washington", "IBM"], ["US"]),
        _context("rag", ["University College London"], ["GB", "US"]),
        _context("cot", None, None),
    ]
    summary = source_diversity_summary(contexts)
    assert summary.startswith(
        "Source diversity: Institutions=5 | Countries=2 (from 4 relevant paper(s),"
        " 1 without affiliation data)."
    ), "Two contexts from one paper count as one paper"
    assert "consider searching" not in summary, "No institution dominates"


def test_summary_warns_when_one_institution_dominates() -> None:
    contexts = [
        _context("paperqa", FUTUREHOUSE, ["US"]),
        _context("labbench", FUTUREHOUSE, ["US"]),
        _context("aviary", FUTUREHOUSE, ["US"]),
        _context("react", ["Princeton University"], ["US"]),
    ]
    summary = source_diversity_summary(contexts)
    assert "Institutions=2 | Countries=1" in summary
    assert (
        "3 of 4 papers come from Future House, Inc.; consider searching for sources"
        " from other institutions" in summary
    )


def test_summary_no_warning_for_single_paper_or_no_data() -> None:
    assert "consider" not in source_diversity_summary(
        [_context("paperqa", FUTUREHOUSE, ["US"])]
    ), "One paper is not enough to call it dominated"
    empty = source_diversity_summary([])
    assert empty.startswith("Source diversity: Institutions=0 | Countries=0")


def _gather_tool(show: bool, monkeypatch: pytest.MonkeyPatch) -> GatherEvidence:
    contexts = [
        _context("paperqa", FUTUREHOUSE, ["US"]),
        _context("aviary", FUTUREHOUSE, ["US"]),
    ]

    async def fake_aget_evidence(
        self: Docs, query: PQASession, **kwargs: Any  # noqa: ARG001
    ) -> PQASession:
        query.contexts = contexts
        return query

    monkeypatch.setattr(Docs, "aget_evidence", fake_aget_evidence)
    settings = Settings(embedding="sparse", agent={"show_source_diversity": show})
    return GatherEvidence(
        settings=settings,
        summary_llm_model=settings.get_summary_llm(),
        embedding_model=SparseEmbeddingModel(),
    )


def _state_with_a_paper() -> EnvironmentState:
    docs = Docs()
    doc = DocDetails(docname="paperqa", dockey="paperqa", citation="c")
    docs.docs[doc.dockey] = doc
    return EnvironmentState(docs=docs, session=PQASession(question="q"))


@pytest.mark.asyncio
async def test_gather_evidence_shows_diversity_when_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _gather_tool(True, monkeypatch).gather_evidence(
        "q", state=_state_with_a_paper()
    )
    assert "Status: Paper Count=1" in result, "Original status line kept"
    assert "Source diversity: Institutions=1 | Countries=1" in result
    assert "2 of 2 papers come from Future House, Inc." in result


@pytest.mark.asyncio
async def test_gather_evidence_unchanged_when_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = await _gather_tool(False, monkeypatch).gather_evidence(
        "q", state=_state_with_a_paper()
    )
    assert "Status: Paper Count=1" in result
    assert "Source diversity" not in result


@pytest.mark.parametrize("show", [True, False])
def test_gather_evidence_description_only_changes_when_on(show: bool) -> None:
    settings = Settings(embedding="sparse", agent={"show_source_diversity": show})
    (gather,) = [t for t in settings_to_tools(settings) if t.info.name == "gather_evidence"]
    has_note = GatherEvidence.SOURCE_DIVERSITY_DESCRIPTION in gather.info.description
    assert has_note is show
    # Building tools again must not keep adding the note
    (again,) = [t for t in settings_to_tools(settings) if t.info.name == "gather_evidence"]
    assert again.info.description.count("distinct institutions") == int(show)
