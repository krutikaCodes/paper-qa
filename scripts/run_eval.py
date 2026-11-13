"""Phase 2 evaluation runner: ask a set of questions and record before/after metrics.

Example (baseline for Enhancement 1, original code):
    python scripts/run_eval.py --feature e1 --label before ^
        --questions test_questions/e1_questions.txt --papers test_papers/e1_years ^
        --set parsing.use_doc_details=true

Example (after, with the new year filter on):
    python scripts/run_eval.py --feature e1 --label after ^
        --questions test_questions/e1_questions.txt --papers test_papers/e1_years ^
        --set parsing.use_doc_details=true --set agent.apply_year_filter=true

What it does:
1. Builds (or reuses) a search index named phase2_<feature>_<label>, so the "before"
   and "after" runs never share stale paper metadata.
2. Saves papers.csv: every indexed paper with the year, citation count, journal
   quality, trust score, institutions and countries that PaperQA stored for it.
3. Asks every question --runs times and appends one row per run to results.csv:
   time (s), cost (USD), papers read, searches, cited papers and their years, etc.
4. Saves a full log and the formatted answer for every run under logs/.

Output goes to results/phase2/<feature>/. Needs ANTHROPIC_API_KEY for the questions.
API keys are never written to any output file.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import shutil
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import paperqa.clients
import paperqa.docs
from paperqa import Settings
from paperqa.agents.main import agent_query
from paperqa.agents.search import FAILED_DOCUMENT_ADD_ID, get_directory_index
from paperqa.prompts import CANNOT_ANSWER_PHRASE
from paperqa.settings import get_settings

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

REPO = Path(__file__).resolve().parent.parent
RANGE_RE = re.compile(r"^\[(\d{4})?\s*-\s*(\d{4})?\]\s*(.+)$")

RESULT_COLUMNS = [
    "timestamp", "feature", "label", "question_no", "run", "question",
    "year_min", "year_max", "status", "time_s", "cost_usd",
    "papers_read", "paper_searches", "evidence_calls", "tool_sequence",
    "contexts", "cited_papers", "cited_names", "cited_years",
    "cited_in_range_pct", "papers_read_in_range_pct", "cannot_answer",
    "avg_trust_cited", "cited_retracted", "distinct_institutions_cited",
    "distinct_countries_cited", "log_file",
]
# --clients names -> metadata client classes in paperqa.clients
CLIENT_CLASSES = {
    "crossref": "CrossrefProvider",
    "semantic_scholar": "SemanticScholarProvider",
    "openalex": "OpenAlexProvider",
    "unpaywall": "UnpaywallProvider",
    "journal_quality": "JournalQualityPostProcessor",
    "retractions": "RetractionDataPostProcessor",
}
PAPER_COLUMNS = [
    "file", "status", "docname", "title", "year", "citation_count",
    "source_quality", "is_retracted", "trust_score", "institutions", "countries",
]


# ---------- small helpers ----------


def parse_questions(path: Path) -> list[tuple[int | None, int | None, str]]:
    """Read 'question' or '[MIN-MAX] question' lines, skipping blanks and # comments."""
    questions = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if m := RANGE_RE.match(line):
            lo, hi, text = m.groups()
            questions.append((int(lo) if lo else None, int(hi) if hi else None, text))
        else:
            questions.append((None, None, line))
    if not questions:
        sys.exit(f"No questions found in {path}")
    return questions


def apply_override(settings: Settings, dotted: str) -> None:
    """Apply one --set key=value, e.g. agent.apply_year_filter=true."""
    if "=" not in dotted:
        sys.exit(f"--set needs key=value, got {dotted!r}")
    key, raw_value = dotted.split("=", 1)
    try:
        value: Any = json.loads(raw_value)  # true/false/numbers/lists
    except json.JSONDecodeError:
        value = raw_value  # plain string
    *parents, leaf = key.split(".")
    target: Any = settings
    for part in parents:
        target = getattr(target, part)
    if leaf not in type(target).model_fields:
        sys.exit(
            f"Setting {key!r} does not exist in this version of the code."
            " (Expected on the baseline for settings added in Phase 2.)"
        )
    setattr(target, leaf, value)


def in_range(year: Any, lo: int | None, hi: int | None) -> bool:
    try:
        y = int(year)
    except (TypeError, ValueError):
        return False  # unknown year counts as outside a requested range
    return (lo is None or y >= lo) and (hi is None or y <= hi)


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}" if whole else ""


def doc_field(doc: Any, name: str) -> Any:
    """Read a DocDetails field if this version of the code has it, else None."""
    value = getattr(doc, name, None)
    if value is None and isinstance(getattr(doc, "other", None), dict):
        value = doc.other.get(name)
    return value


def as_list(value: Any) -> list[str]:
    if not value:
        return []
    return [str(v) for v in value] if isinstance(value, list | tuple | set) else [str(value)]


class CountingHandler(logging.Handler):
    """Counts warnings/errors from the metadata clients (failed lookups)."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.count = 0

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1


def add_file_log(path: Path) -> logging.Handler:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    for name in ("paperqa", "lmi", "aviary"):
        logging.getLogger(name).addHandler(handler)
    return handler


def remove_log(handler: logging.Handler) -> None:
    for name in ("paperqa", "lmi", "aviary"):
        logging.getLogger(name).removeHandler(handler)
    handler.close()


# ---------- indexing ----------


async def build_index(settings: Settings, out_dir: Path) -> None:
    """Build the named index once (timed), then save papers.csv."""
    client_errors = CountingHandler()
    logging.getLogger("paperqa.clients").addHandler(client_errors)
    log = add_file_log(out_dir / "logs" / "indexing.log")
    start = time.perf_counter()
    try:
        index = await get_directory_index(settings=settings)
    except Exception as exc:  # record the crash as evidence (e.g. a 429 rate limit)
        cause = exc
        while isinstance(cause, BaseExceptionGroup) and cause.exceptions:
            cause = cause.exceptions[0]
        message = f"{type(cause).__name__}: {cause}".splitlines()[0][:300]
        (out_dir / "indexing_summary.txt").write_text(
            f"index={settings.agent.index.name}\nindexing_crashed=True\nerror={message}\n"
            f"metadata_client_warnings={client_errors.count}\n"
            f"time_before_crash_s={time.perf_counter() - start:.1f}\n",
            encoding="utf-8",
        )
        sys.exit(f"\nIndexing crashed: {message}\n(Recorded in {out_dir / 'indexing_summary.txt'})")
    finally:
        remove_log(log)
        logging.getLogger("paperqa.clients").removeHandler(client_errors)
    elapsed = time.perf_counter() - start

    rows, failed = [], 0
    for file_location, status in sorted((await index.index_files).items()):
        if status == FAILED_DOCUMENT_ADD_ID:
            failed += 1
            rows.append({"file": file_location, "status": "FAILED"})
            continue
        saved = await index.get_saved_object(file_location)
        doc = next(iter(saved.docs.values())) if saved and saved.docs else None
        rows.append({
            "file": file_location,
            "status": "ok",
            "docname": getattr(doc, "docname", ""),
            "title": doc_field(doc, "title") or "",
            "year": doc_field(doc, "year") or "",
            "citation_count": doc_field(doc, "citation_count") if doc_field(doc, "citation_count") is not None else "",
            "source_quality": doc_field(doc, "source_quality") if doc_field(doc, "source_quality") is not None else "",
            "is_retracted": doc_field(doc, "is_retracted") if doc_field(doc, "is_retracted") is not None else "",
            "trust_score": doc_field(doc, "trust_score") if doc_field(doc, "trust_score") is not None else "",
            "institutions": "; ".join(as_list(doc_field(doc, "institutions"))),
            "countries": "; ".join(as_list(doc_field(doc, "countries"))),
        })

    with (out_dir / "papers.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with (out_dir / "indexing_summary.txt").open("w", encoding="utf-8") as f:
        f.write(
            f"index={settings.agent.index.name}\npapers={len(rows)}\nfailed_papers={failed}\n"
            f"metadata_client_warnings={client_errors.count}\nindex_time_s={elapsed:.1f}\n"
        )
    print(
        f"Index {settings.agent.index.name}: {len(rows)} papers, {failed} failed,"
        f" {client_errors.count} metadata warnings, {elapsed:.0f}s."
        f" Paper years: {sorted(str(r.get('year', '')) for r in rows)}"
    )


# ---------- one question ----------


async def run_one(
    settings: Settings, args: argparse.Namespace, q_no: int, run: int,
    lo: int | None, hi: int | None, question: str, out_dir: Path,
) -> dict[str, Any]:
    seen_docs: dict[str, Any] = {}

    async def remember_docs(state: Any) -> None:  # called by the agent's tools
        seen_docs.update({d.dockey: d for d in state.docs.docs.values()})

    settings.agent.callbacks = {
        "gather_evidence_completed": [remember_docs],
        "gen_answer_initialized": [remember_docs],
    }
    log_name = f"{args.label}_q{q_no}_run{run}.log"
    log = add_file_log(out_dir / "logs" / log_name)
    start = time.perf_counter()
    try:
        response = await agent_query(question, settings=settings)
    finally:
        remove_log(log)
    elapsed = time.perf_counter() - start
    session = response.session

    cited_contexts = [c for c in session.contexts if c.id in session.raw_answer]
    cited_docs = {c.text.doc.dockey: c.text.doc for c in cited_contexts}.values()
    cited_years = [doc_field(d, "year") for d in cited_docs]
    has_range = lo is not None or hi is not None
    tools = [name for step in session.tool_history for name in step]
    trusts = [float(t) for d in cited_docs if (t := doc_field(d, "trust_score")) is not None]
    institutions = {i for d in cited_docs for i in as_list(doc_field(d, "institutions"))}
    countries = {c for d in cited_docs for c in as_list(doc_field(d, "countries"))}

    with (out_dir / "logs" / log_name).open("a", encoding="utf-8") as f:
        f.write(f"\n\n===== STATUS: {response.status} =====\n{session.formatted_answer}\n")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "feature": args.feature,
        "label": args.label,
        "question_no": q_no,
        "run": run,
        "question": question,
        "year_min": lo or "",
        "year_max": hi or "",
        "status": str(response.status),
        "time_s": f"{elapsed:.1f}",
        "cost_usd": f"{session.cost:.4f}",
        "papers_read": len(seen_docs),
        "paper_searches": tools.count("paper_search"),
        "evidence_calls": tools.count("gather_evidence"),
        "tool_sequence": " > ".join(tools),
        "contexts": len(session.contexts),
        "cited_papers": len(cited_docs),
        "cited_names": "; ".join(sorted(d.docname for d in cited_docs)),
        "cited_years": "; ".join(str(y) for y in cited_years),
        "cited_in_range_pct": (
            pct(sum(in_range(y, lo, hi) for y in cited_years), len(cited_years)) if has_range else ""
        ),
        "papers_read_in_range_pct": (
            pct(sum(in_range(doc_field(d, "year"), lo, hi) for d in seen_docs.values()), len(seen_docs))
            if has_range else ""
        ),
        "cannot_answer": CANNOT_ANSWER_PHRASE in session.answer,
        "avg_trust_cited": f"{statistics.mean(trusts):.2f}" if trusts else "",
        "cited_retracted": sum(bool(doc_field(d, "is_retracted")) for d in cited_docs),
        "distinct_institutions_cited": len(institutions),
        "distinct_countries_cited": len(countries),
        "log_file": f"logs/{log_name}",
    }


# ---------- main ----------


def summarize(results_csv: Path, label: str) -> None:
    with results_csv.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["label"] == label]
    if not rows:
        return

    def avg(col: str) -> str:
        vals = [float(r[col]) for r in rows if r[col] not in ("", None)]
        return f"{statistics.mean(vals):.2f}" if vals else "n/a"

    print(f"\n=== Summary for label '{label}' ({len(rows)} runs, all rows in {results_csv}) ===")
    for col, unit in [
        ("time_s", "s"), ("cost_usd", "USD"), ("papers_read", "papers"),
        ("paper_searches", "searches"), ("cited_papers", "papers"),
        ("cited_in_range_pct", "%"), ("papers_read_in_range_pct", "%"),
        ("avg_trust_cited", "0-1"), ("distinct_institutions_cited", "count"),
        ("distinct_countries_cited", "count"),
    ]:
        print(f"  avg {col:<28} {avg(col):>8} {unit}")
    print(f"  cannot_answer: {sum(r['cannot_answer'] == 'True' for r in rows)} of {len(rows)} runs")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--feature", required=True, help="e1, e2, e3 or regression")
    parser.add_argument("--label", required=True, help="e.g. before, after, after-off")
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--papers", required=True, type=Path)
    parser.add_argument("--profile", default="claude_cheap")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--only", type=int, nargs="*", help="only these question numbers (1-based)")
    parser.add_argument("--set", dest="overrides", action="append", default=[], help="setting override key=value")
    parser.add_argument("--fresh-index", action="store_true", help="delete and rebuild this run's index")
    parser.add_argument(
        "--clients",
        help="comma-separated metadata services, e.g. crossref,journal_quality"
        f" (choices: {', '.join(CLIENT_CLASSES)}). Default: the code's DEFAULT_CLIENTS",
    )
    parser.add_argument("--index-only", action="store_true", help="build the index and papers.csv, ask no questions (still makes one cheap LLM call per new paper to read its citation)")
    args = parser.parse_args()

    if not args.index_only and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (see MY_SETUP_LOG.md).")

    questions = parse_questions(args.questions)
    out_dir = REPO / "results" / "phase2" / args.feature
    (out_dir / "logs").mkdir(parents=True, exist_ok=True)
    (out_dir / "screenshots").mkdir(exist_ok=True)

    settings = get_settings(args.profile)
    for override in args.overrides:
        apply_override(settings, override)
    if args.clients:
        # Choose which metadata services are asked about each paper, without editing
        # PaperQA's code: Docs.aadd falls back to paperqa.docs.DEFAULT_CLIENTS
        names = [n.strip() for n in args.clients.split(",") if n.strip()]
        if unknown := [n for n in names if n not in CLIENT_CLASSES]:
            sys.exit(f"Unknown --clients {unknown}; choose from {sorted(CLIENT_CLASSES)}")
        paperqa.docs.DEFAULT_CLIENTS = tuple(getattr(paperqa.clients, CLIENT_CLASSES[n]) for n in names)
    settings.agent.index.paper_directory = str(args.papers.resolve())
    settings.agent.index.name = f"phase2_{args.feature}_{args.label}".replace("-", "_")
    if args.fresh_index:
        shutil.rmtree(Path(settings.agent.index.index_directory) / settings.agent.index.name, ignore_errors=True)

    (out_dir / f"run_config_{args.label}.json").write_text(
        json.dumps({
            "profile": args.profile, "overrides": args.overrides,
            "metadata_clients": [c.__name__ for c in paperqa.docs.DEFAULT_CLIENTS], "papers": str(args.papers),
            "questions": str(args.questions), "runs": args.runs, "index": settings.agent.index.name,
            "llm": settings.llm, "agent_llm": settings.agent.agent_llm, "embedding": settings.embedding,
        }, indent=2),
        encoding="utf-8",
    )

    await build_index(settings, out_dir)
    if args.index_only:
        return
    settings.agent.rebuild_index = False  # index is built; keep question timings clean

    results_csv = out_dir / "results.csv"
    new_file = not results_csv.exists()
    for q_no, (lo, hi, question) in enumerate(questions, start=1):
        if args.only and q_no not in args.only:
            continue
        for run in range(1, args.runs + 1):
            print(f"\n[{args.feature}/{args.label}] Q{q_no} run {run}: {question}")
            try:
                row = await run_one(settings, args, q_no, run, lo, hi, question, out_dir)
            except Exception as exc:  # keep going; record the failure
                logging.getLogger(__name__).exception("Run failed")
                row = {c: "" for c in RESULT_COLUMNS} | {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "feature": args.feature, "label": args.label, "question_no": q_no,
                    "run": run, "question": question, "status": f"ERROR: {exc!r}"[:200],
                }
            print(
                f"  -> {row['status']} | {row['time_s']}s | ${row['cost_usd']} | papers read"
                f" {row['papers_read']} | cited {row['cited_names'] or '-'} ({row['cited_years'] or '-'})"
            )
            with results_csv.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=RESULT_COLUMNS)
                if new_file:
                    writer.writeheader()
                    new_file = False
                writer.writerow(row)
    summarize(results_csv, args.label)


if __name__ == "__main__":
    asyncio.run(main())
