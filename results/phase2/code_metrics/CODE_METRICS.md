# Phase 2 code metrics (cloc and lizard)

**Compared:** tag `phase2-baseline` (the original PaperQA2 code plus our Phase 1 setup) vs branch `phase2` (HEAD `339458e`).
**Files measured:** the 19 code files changed in Phase 2 (`changed_files.txt`): `src/`, `tests/`, `scripts/` and the root `trust.py`.
Documentation and result files are not counted.
**Tools:** cloc 2.12 (lines of code) and lizard 1.26.1 (cyclomatic complexity, CCN).

## 1. Lines of code (cloc)

### By area (code lines, without blanks and comments)

| Area | Files changed | New files | Lines added | Lines modified | Lines removed |
|---|---:|---:|---:|---:|---:|
| `src/paperqa` (the agent) | 10 | 2 | **894** | 23 | 21 |
| `tests/` (offline unit tests) | 0 | 4 | **881** | 0 | 0 |
| `scripts/` (evaluation runner, paper download) | 2 | 0 | 96 | 19 | 0 |
| root `trust.py` (import shim) | 0 | 1 | 13 | 0 | 0 |
| **Total** | **12** | **7** | **1,884** | **42** | **21** |

The whole `src/paperqa` package grew from **8,904 to 9,795 code lines (+891, +10%)**.

### By file (`src/paperqa`)

| File | Added | Removed | Enhancement |
|---|---:|---:|---|
| `trust.py` (new) | 196 | 0 | E2: trust score formula |
| `university_rankings.py` (new) | 178 | 0 | E2: THE top-100 list (mostly data) |
| `agents/tools.py` | 138 | 0 | E1 year filter, E2 low-trust warning, E3 diversity summary |
| `types.py` | 96 | 0 | E2 trust fields and table, E3 institutions and countries |
| `docs.py` | 93 | 5 | E2 front-matter affiliations, trust comparison, metadata client choice |
| `clients/openalex.py` | 80 | 0 | E2 venue quality and retraction, E3 affiliations, field translation fix |
| `settings.py` | 68 | 16 | the 3 switches, `metadata_clients`, E2 ranking |
| `clients/__init__.py` | 17 | 0 | choosing metadata clients by name |
| `prompts.py` | 10 | 0 | E2 affiliation prompt |
| `__init__.py` | 8 | 0 | exports |
| `clients/client_models.py` | 6 | 0 | HTTP 429 skips a provider instead of crashing |
| `agents/env.py` | 4 | 0 | E2/E3 tool descriptions |

### What the numbers mean
- **The changes are additive.** 894 lines were added and only 21 removed in `src`, and every
  changed file gained fewer than 140 lines. The core pipeline (indexing, retrieval, the answer prompt) was
  extended, not rewritten, which matches our "small changes, don't rewrite PaperQA's core" rule.
- **About 40% of the new agent code is E2** (`trust.py` + `university_rankings.py` = 374 lines), and
  178 of those lines are a data table of university names rather than logic.
- **Tests are about as large as the new code** (881 test lines for 894 source lines, about 1:1). Every
  enhancement has offline tests, including tests that the agent is unchanged when its switch is off.

## 2. Complexity (lizard)

CCN (cyclomatic complexity) counts the independent paths through a function: 1–10 is simple,
11–15 moderate, and over 15 is hard to test (lizard's default warning level).

### Summary (`src/paperqa` functions in the changed files)

| | Before | After |
|---|---:|---:|
| Functions | 145 | 169 (+24 new) |
| Average CCN | 5.27 | 5.69 |
| Highest CCN | 38 (`DocDetails.__add__`) | 44 (`Docs.aadd`, `DocDetails.__add__`) |
| Functions with CCN > 10 | 22 | 25 |
| Functions with CCN > 15 | 8 | 13 |

Across all measured files, including tests and scripts, the average CCN *fell* from 5.3 to 4.4, because
the 75 new test functions are simple (almost all CCN 1–3).

### New functions with the highest CCN

| Function | CCN | NLOC | Enhancement |
|---|---:|---:|---|
| `openalex.get_first_author_affiliations` | 18 | 20 | E3: affiliations of the first 3 authors |
| `tools.source_diversity_summary` | 11 | 30 | E3 |
| `trust._store_university_matches` | 10 | 15 | E2 |
| `openalex._openalex_source_quality` | 9 | 16 | E2 |
| `trust._normalize_source_quality` | 9 | 48 | E2 |
| `tools.low_trust_summary` | 8 | 27 | E2 |
| `trust.score_trust` | 6 | 44 | E2: the formula itself |
| `tools.year_in_range` | 5 | 8 | E1 |

Most new logic sits in **small helper functions**: of the 24 new `src` functions, only one is over 15.

### Existing functions whose complexity grew most

| Function | CCN before → after | NLOC before → after | Why |
|---|---|---|---|
| `PaperSearch.paper_search` | 11 → **23** | 54 → 97 | E1: the paging loop that fills a page with in-range papers |
| `PQASession.populate_formatted_answers_and_bib_from_raw_answer` | 13 → **25** | 42 → 98 | E2: building the trust-score table |
| `Docs.aadd` | 36 → 44 | 148 → 180 | E2: front-matter affiliations and choosing metadata clients |
| `DocDetails.__add__` | 38 → 44 | 70 → 82 | E2/E3: merging the new fields (trust, institutions) |
| `GatherEvidence.gather_evidence` | 12 → 17 | 60 → 76 | E2 trust check and E3 diversity line |
| `Docs.aquery` | 15 → 18 | 123 → 139 | E2: the trust-score comparison shortcut |

### What the numbers mean
- **The average stayed low** (5.27 → 5.69): most new code is in short, testable helpers.
- **The cost is concentrated in a few existing functions.** `paper_search` and
  `populate_formatted_answers_and_bib_from_raw_answer` roughly doubled, because new behavior was added
  *inside* them behind `if switch:` blocks. That kept each change easy to find and to switch off, but
  it makes these functions harder to read. Five more `src` functions are now above CCN 15 (8 → 13).
- `Docs.aadd` and `DocDetails.__add__` were already the most complex functions in PaperQA2 (36 and 38);
  our changes made them slightly worse.
- **Planned refactor (Phase 3):** move the year-filter loop out of `paper_search` into a helper such
  as `_year_filtered_query`, and the trust table out of `populate_formatted_answers_and_bib_from_raw_answer`
  into `_trust_table`. This would bring both back to about their original CCN without changing behavior.
  The root `trust.py` shim (13 lines) is unused and can be deleted.

## 3. How to reproduce

```powershell
pip install lizard                 # cloc: npx cloc (needs Node.js and Perl; Git for Windows includes Perl)
# Export the changed files at both versions, then:
npx cloc --diff before after
npx cloc --diff --by-file before after
lizard -C 15 before
lizard -C 15 after
```
Raw outputs: `cloc_diff_summary.txt`, `cloc_diff_by_file.txt`, `lizard_before.txt`/`.csv` and
`lizard_after.txt`/`.csv`.
