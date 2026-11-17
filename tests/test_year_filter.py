"""Phase 2 enhancement 1: the paper_search tool's year filter.

Offline: a fake search index stands in for tantivy, and the embedding is sparse
(local), so there are no API calls.
"""

from typing import Any

import pytest
from lmi import SparseEmbeddingModel

from paperqa import Docs, Settings
from paperqa.agents import tools
from paperqa.agents.tools import EnvironmentState, PaperSearch, year_in_range
from paperqa.types import DocDetails, PQASession, Text

# (file name, year) in search-ranking order; None = unknown year
PAPERS: list[tuple[str, int | None]] = [
    ("attention", 2017),
    ("bert", 2018),
    ("toolformer", 2023),
    ("rag", 2020),
    ("cot", 2022),
    ("dpr", 2020),
    ("mystery", None),
    ("webgpt", 2021),
    ("realm", 2020),
    ("paperqa2", 2024),
]


def _result(name: str, year: int | None) -> Docs:
    doc = DocDetails(docname=name, dockey=name, citation=f"{name} citation", year=year)
    result = Docs()
    result.docs[doc.dockey] = doc
    result.texts = [Text(text=f"{name} text", name=f"{name} pages 1-2", doc=doc)]
    return result


class FakeIndex:
    """Returns PAPERS in a fixed ranking order, paged like the tantivy index."""

    fields = ("file_location", "body", "title", "year")

    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    async def query(
        self, query: str, top_n: int, offset: int, **kwargs: Any  # noqa: ARG002
    ) -> list[Docs]:
        self.calls.append((offset, top_n))
        return [_result(n, y) for n, y in PAPERS[offset : offset + top_n]]


@pytest.fixture(name="fake_index")
def fixture_fake_index(monkeypatch: pytest.MonkeyPatch) -> FakeIndex:
    index = FakeIndex()

    async def fake_get_directory_index(**kwargs: Any) -> FakeIndex:  # noqa: ARG001
        return index

    monkeypatch.setattr(tools, "get_directory_index", fake_get_directory_index)
    return index


def _make_tool(apply_year_filter: bool, search_count: int = 3) -> PaperSearch:
    settings = Settings(
        embedding="sparse",
        agent={"apply_year_filter": apply_year_filter, "search_count": search_count},
    )
    return PaperSearch(settings=settings, embedding_model=SparseEmbeddingModel())


def _state() -> EnvironmentState:
    return EnvironmentState(docs=Docs(), session=PQASession(question="q"))


def _years(state: EnvironmentState) -> list[int | None]:
    return [d.year for d in state.docs.docs.values()]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("year", "min_year", "max_year", "expected"),
    [
        (2020, 2020, 2021, True),
        (2021, 2020, 2021, True),
        (2019, 2020, 2021, False),
        (2022, 2020, 2021, False),
        (2023, 2023, None, True),  # "2023 or later"
        (2017, None, 2018, True),  # "before 2019"
        (2019, None, 2018, False),
        (2015, None, None, True),
        (None, 2020, 2021, None),  # unknown year
    ],
)
def test_year_in_range(
    year: int | None, min_year: int | None, max_year: int | None, expected: bool | None
) -> None:
    assert year_in_range(year, min_year, max_year) is expected


@pytest.mark.asyncio
async def test_filter_off_keeps_original_behavior(fake_index: FakeIndex) -> None:
    state = _state()
    status = await _make_tool(apply_year_filter=False).paper_search(
        "retrieval", min_year=2020, max_year=2021, state=state
    )
    assert _years(state) == [2017, 2018, 2023], "Years ignored, as in the original"
    assert "Year filter" not in status
    assert fake_index.calls == [(0, 3)]


@pytest.mark.asyncio
async def test_filter_on_keeps_only_requested_years(fake_index: FakeIndex) -> None:
    state = _state()
    status = await _make_tool(apply_year_filter=True).paper_search(
        "retrieval", min_year=2020, max_year=2021, state=state
    )
    assert _years(state) == [2020, 2020, None, 2021, 2020], (
        "Only 2020-2021 papers added, plus the one whose year is unknown"
    )
    # Had to look through 3 pages of 3 to fill one page with in-range papers
    assert fake_index.calls == [(0, 3), (3, 3), (6, 3)]
    assert (
        "Year filter 2020-2021: kept 4 paper(s) from these years and 1 with unknown"
        " year, skipped 4 outside these years." in status
    )


@pytest.mark.asyncio
async def test_filter_keeps_paper_with_unknown_year(fake_index: FakeIndex) -> None:
    # Regression check: Toolformer's metadata lookup failed (HTTP 429), so its year
    # was unknown, and the agent could never find it when it searched with years
    state = _state()
    await _make_tool(apply_year_filter=True, search_count=10).paper_search(
        "anything", min_year=2023, max_year=None, state=state
    )
    assert None in _years(state), "Unknown year: kept, as without the filter"


@pytest.mark.asyncio
async def test_filter_continuation_starts_after_last_page(
    fake_index: FakeIndex,
) -> None:
    tool = _make_tool(apply_year_filter=True)
    state = _state()
    await tool.paper_search("retrieval", min_year=2020, max_year=2021, state=state)
    await tool.paper_search("retrieval", min_year=2020, max_year=2021, state=state)
    assert fake_index.calls[3] == (9, 3), "Repeat search continues after page 3"
    # All 4 in-range papers found once, none lost between the two searches
    known = sorted(y for y in _years(state) if y is not None)
    assert known == [2020, 2020, 2020, 2021]


@pytest.mark.asyncio
async def test_filter_open_ended_range(fake_index: FakeIndex) -> None:  # noqa: ARG001
    state = _state()
    await _make_tool(apply_year_filter=True, search_count=10).paper_search(
        "tools", min_year=2023, max_year=None, state=state
    )
    assert sorted(y for y in _years(state) if y is not None) == [2023, 2024]


@pytest.mark.asyncio
async def test_filter_no_matches_tells_agent(fake_index: FakeIndex) -> None:
    state = _state()
    status = await _make_tool(apply_year_filter=True).paper_search(
        "anything", min_year=2010, max_year=2012, state=state
    )
    assert _years(state) == [None], "Only the unknown-year paper"
    assert "No papers from these years match this query" in status
    assert len(fake_index.calls) == 4, "Stops when the ranking runs out"


@pytest.mark.asyncio
async def test_filter_on_without_years_is_unchanged(fake_index: FakeIndex) -> None:
    state = _state()
    status = await _make_tool(apply_year_filter=True).paper_search(
        "retrieval", min_year=None, max_year="None", state=state
    )
    assert _years(state) == [2017, 2018, 2023]
    assert "Year filter" not in status
    assert fake_index.calls == [(0, 3)]
