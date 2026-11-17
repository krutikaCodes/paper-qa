# Team Guide: Run PaperQA2 on Your Windows PC

This guide takes you from nothing to asking AI questions about research papers.
No coding knowledge is needed: copy each command, paste it, press **Enter**,
and check that you see what the guide says you should see.

**Time:** about 30-45 minutes the first time (mostly waiting for downloads).
**Cost:** the free checks cost nothing. Asking questions costs a few cents to
about $1 each on your own Anthropic account.

---

## What is this?

**PaperQA2** is an open-source project by FutureHouse
(original code: https://github.com/Future-House/paper-qa). You give it research
papers (PDFs) and ask questions. It reads the papers, finds the relevant parts,
and writes an answer with the **exact pages** it used, like
`(Skarlinski2024 pages 1-3)`. If the papers don't contain the answer, it says
"I cannot answer" instead of making something up.

This copy uses **Anthropic's Claude** instead of OpenAI. It has two branches:

| Branch | What it has |
|---|---|
| `main` | Phase 1: the **original code unchanged**, plus this guide and helper files |
| `phase2` | Phase 2: **three enhancements** to the agent (year filter, trust score, source diversity), each with an on/off setting. See [Phase 2](#phase-2-the-three-enhancements) |

**Use `phase2`** (Step 2 shows how). With all Phase 2 settings off, it behaves like the original.

---

## Before you start: what you need

| You need | Where to get it |
|---|---|
| A Windows 10 or 11 PC | |
| About 5 GB of free disk space | |
| **Python 3.12** | https://www.python.org/downloads/windows/ (pick the newest **3.12.x** "Windows installer (64-bit)") |
| **Git** | https://git-scm.com/download/win |
| An **Anthropic API key** with at least $5 of credit | https://console.anthropic.com (see Step 6) |

**Important when installing Python:** on the first installer screen, tick the
box **"Add python.exe to PATH"**, then click **Install Now**.
For Git, clicking **Next** on every screen is fine.

---

## Step 1: Open PowerShell

1. Press the **Windows key**, type `PowerShell`, and open **Windows PowerShell**.
2. Allow PowerShell to run the setup scripts (only needed once, ever):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

If it asks a question, type `Y` and press Enter.

3. Check that Python and Git are installed:

```powershell
py -3.12 --version
git --version
```

**You should see:** `Python 3.12.x` and `git version 2.x`.
If you see "not recognized", reinstall that program (and for Python, tick
**"Add python.exe to PATH"**), then close and reopen PowerShell.

---

## Step 2: Download the project

This puts the project in a folder called `paper-qa` inside `C:\Projects`:

```powershell
mkdir C:\Projects -Force
cd C:\Projects
git clone https://github.com/krutikaCodes/paper-qa.git
cd paper-qa
git checkout phase2
```

**You should see:** `Cloning into 'paper-qa'...`, `done`, and then
`Switched to a new branch 'phase2'`.

> **Already cloned it in Phase 1?** Skip the `git clone` line and run
> `cd C:\Projects\paper-qa`, `git fetch origin`, `git checkout phase2` and
> `git pull` instead. Then redo Step 4 (install), because the code changed.

> From now on, **every command must be run inside this `paper-qa` folder.**
> Your PowerShell line should end with `\paper-qa>`. Never `cd` into
> `my_papers`.

---

## Step 3: Create the project's private Python box (one time)

A *virtual environment* is a private box of Python packages just for this
project, so it can't break anything else on your PC.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**You should see:** `(.venv)` at the start of your PowerShell line.

---

## Step 4: Install everything (one time, 10-20 minutes)

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[local]" -r team-requirements.txt
```

This downloads paper-qa and about 100 libraries it needs, including a large
one (`torch`) for local AI search. Wait until the line ends with
`Successfully installed ...`.

**Check it worked:**

```powershell
pqa --help
```

**You should see:** a help menu starting with `usage: pqa`.

---

## Step 5: Download the papers and create the settings (one time)

```powershell
$env:PYTHONUTF8 = 1
.\team_setup.ps1
```

This does two things for you:

1. Downloads 3 free research papers from arXiv:

| Short name | File | Goes into | What it's about |
|---|---|---|---|
| PaperQA2 | `2409.13740v2.pdf` | `my_papers` | The paper about this project |
| ReAct | `2210.03629v3.pdf` | `my_papers` | AI agents that think and use tools |
| Toolformer | `2302.04761v1.pdf` | `papers_later` | AI that learns to use tools (added later, in Test 2) |

2. Saves two settings **profiles** (a profile is a saved set of options, so you
   don't have to type them every time):

| Profile | AI model | Cost per question | Use it for |
|---|---|---|---|
| `claude_cheap` | Claude Haiku (small, fast) | about 1-3 cents | Practice and quick tests |
| `claude_demo` | Claude Sonnet (smarter) | about 30-80 cents | Best-quality answers, demos |

**You should see:** `Setup done. my_papers has PaperQA2 and ReAct; papers_later has Toolformer.`

3. **Phase 2 only:** download the test papers for the three enhancements
   (about 15 papers from arXiv, 1-2 minutes):

```powershell
.\scripts\get_phase2_papers.ps1
```

**You should see:** three sections (`== e1_years ==`, `== e2_trust ==`,
`== e3_diversity ==`), then `Done. Downloaded N new paper(s).`
`e2_trust` gets 4 extra "planted" papers for testing E2: three new preprints with
no citations and one **retracted** paper. They're listed in `test_papers\e2_trust_PLANTED.txt`.

4. **Phase 2 only:** create two more profiles, so you can ask questions like in
   Phase 1 with all enhancements on or all off:

```powershell
python scripts/make_phase2_profiles.py
```

**You should see:** `written ...phase2_all.json` and `written ...phase2_off.json`.

| Profile | Enhancements | Papers |
|---|---|---|
| `phase2_all` | E1, E2 and E3 all **on** | `test_papers\e2_trust` (16 papers) |
| `phase2_off` | all **off** (original behavior) | the same 16 papers |

---

## Step 6: Get your Anthropic API key (one time)

1. Go to https://console.anthropic.com and sign in (or sign up).
2. Go to **Billing** and add credit (about $5 is plenty).
3. Go to **API Keys** (https://console.anthropic.com/settings/keys) and click
   **Create Key**. Copy it right away (it is shown only once).
4. Save it somewhere private, like a password manager.

Your key starts with `sk-ant-api03-`.

> **Keep your key secret.** Never paste it into chat, email, GitHub, or any
> file in this project. Anyone with your key can spend your money.
> A claude.ai Pro/Max subscription is **not** an API key and does not work here.

### Phase 2 only: set your email for the paper databases (one time)

The enhancements look papers up on **OpenAlex** (years, citation counts,
author institutions) and the **Crossref** retraction list. Both ask for an
email address so they know who is sending requests. Any email you check works:

```powershell
setx OPENALEX_MAILTO "you@example.com"
setx CROSSREF_MAILTO "you@example.com"
```

**You should see:** `SUCCESS: Specified value was saved.` twice.
Then **close all PowerShell and VS Code windows** and open a new one:
`setx` only applies to windows opened after it.
An email is not a secret like the API key, but still keep it out of files.

---

## Every time you open a new PowerShell window

Run these 4 lines first (put your real key in the last line):

```powershell
cd C:\Projects\paper-qa
.venv\Scripts\Activate.ps1
$env:PYTHONUTF8 = 1
$env:ANTHROPIC_API_KEY = "sk-ant-api03-...your key..."
```

**Check your key works** (free, uses no credit):

```powershell
try { Invoke-RestMethod "https://api.anthropic.com/v1/models" -Headers @{"x-api-key"=$env:ANTHROPIC_API_KEY; "anthropic-version"="2023-06-01"} | Out-Null; "KEY OK" } catch { "KEY PROBLEM: $($_.ErrorDetails.Message)" }
```

**You should see:** `KEY OK`.

**Phase 2: check your email is set** (should print your email, not an empty line):

```powershell
echo $env:OPENALEX_MAILTO
```

---

## Free checks (no API key needed)

### Check 1: The project's own tests pass

```powershell
python -m pytest tests/test_configs.py tests/test_utils.py --record-mode=none -p no:cacheprovider -q --basetemp C:\pqa_test_tmp
```

**You should see:** `24 passed` (and `97 subtests passed`).

### Check 1b (Phase 2): the enhancements' own tests pass

```powershell
$env:CROSSREF_MAILTO = $null; $env:OPENALEX_MAILTO = $null
python -m pytest tests/test_phase2_metadata.py tests/test_year_filter.py tests/test_trust.py tests/test_diversity.py --record-mode=none -p no:cacheprovider -q --basetemp C:\pqa_test_tmp
```

**You should see:** `82 passed`.
These tests use fake papers, so they need no API key and cost nothing. They also
check that each agent tool is unchanged when its enhancement is off.
The first line clears your email **in this window only**: the tests replay
recorded web answers and fail if an email is set. Open a new window afterwards
to use the enhancements again.

### Check 2: paper-qa can read a PDF

```powershell
python smoke_test.py tests/stub_data/paper.pdf
```

**You should see:** `Chunks read from PDF: 25`.

### Check 3: The settings profiles were saved

```powershell
pqa -s claude_cheap view | Select-String '"llm"|"embedding"|"evidence_k"'
```

**You should see:** `anthropic/claude-haiku-4-5`, `sparse` and `5`.

---

## The test cases (these use your API key)

Run them in this order. Start with `claude_cheap` to practice cheaply. For the
best answers, run them again with `claude_demo` in place of `claude_cheap`.

### Test 1: A question answered by one paper

**Papers in `my_papers`:** PaperQA2, ReAct

```powershell
pqa -s claude_cheap ask "What is PaperQA2?"
```

**You should see:**
- `New file to index` for each paper (only the first time)
- `paper_search`, then `gather_evidence`
- `Current Evidence=` above 0
- An answer with page citations like `(Skarlinski2024 pages 1-3)`

### Test 2: A question that needs several papers (and adding a paper)

First move Toolformer into `my_papers`, then ask:

```powershell
Move-Item papers_later\2302.04761v1.pdf my_papers\
pqa -s claude_cheap ask "Compare how ReAct and Toolformer let language models use tools, and how PaperQA2 uses an agent."
```

**You should see:**
- Only `2302.04761v1.pdf` shows `New file to index` (old papers are not read again)
- Several `gather_evidence` lines, each with a different smaller question
- An answer citing more than one paper

### Test 3: A question the papers can't answer

```powershell
pqa -s claude_cheap ask "How can tool-using AI agents be attacked through indirect prompt injection?"
```

**You should see:** `Current Evidence=0` (or very low), and an answer starting
with **`I cannot answer`**. This is correct: it refuses instead of guessing.

### Test 4: Limited steps ("budget stress")

```powershell
pqa -s claude_cheap --agent.max_timesteps 3 ask "Compare how ReAct and Toolformer let language models use tools, and how PaperQA2 uses an agent."
```

**You should see:** the warning
`Agent didn't finish within 3 timesteps, just answering.`, then an answer anyway.
If the warning doesn't appear, run it again with `2` in place of `3`.

### Test 5: It remembers past answers (free)

```powershell
pqa -s claude_cheap -i answers search "ReAct Toolformer"
```

**You should see:** your earlier questions and answers.

### Test 6 (optional): Using paper-qa from Python

```powershell
python smoke_test.py my_papers/2409.13740v2.pdf "What steps does PaperQA2 use to find answers?"
```

**You should see:** the PDF check, then `Answer:` with references (about 2 cents).

### Reset (to run the tests again from the start)

```powershell
Move-Item my_papers\2302.04761v1.pdf papers_later\ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$HOME\.pqa\indexes" -ErrorAction SilentlyContinue
```

---

## Phase 2: the three enhancements

Each enhancement changes what the AI agent does, and has a setting to turn it on
or off. **All three are off by default**, so the commands above behave like the
original.

| # | Enhancement | Setting | What the agent does differently |
|---|---|---|---|
| E1 | **Year filter** | `agent.apply_year_filter` | When a question asks for certain years, the search keeps only papers from those years and tells the agent how many it skipped |
| E2 | **Trust score** | `answer.use_trust_score` | Gives every paper a trust score from 0 to 1 and ranks evidence by relevance × trust. Warns the agent about sources below 0.60, and marks retracted papers "do not cite". The answer ends with a trust-score table |
| E3 | **Source diversity** | `agent.show_source_diversity` | Tells the agent how many institutions and countries its evidence comes from, and to search wider if one group dominates |

**How the E2 trust score is made** (`src/paperqa/trust.py`):

| Part | Weight | Comes from |
|---|---:|---|
| Venue quality | 36% | OpenAlex: core venue, DOAJ journal, or other journal/conference |
| Citations per year | 31.5% | OpenAlex citation count and year (log scale, capped at 20 per year) |
| Not retracted | 13.5% | OpenAlex `is_retracted` |
| Details complete | 9% | venue, citations, year and retraction status all known |
| Top-100 university | 10% | an author's institution is in the THE 2027 top 100 |

Missing information counts as **0.5 (neutral)**, not as bad. A retracted paper
always scores **0**.

The enhancements need **correct paper details** (years, citations,
institutions). These come from OpenAlex, so they need
`parsing.use_doc_details=true` and the OpenAlex source.

### Ask a question with all enhancements on (like Phase 1)

After making the profiles (Step 5, part 4):

```powershell
pqa -s phase2_off ask "Since 2023, can large language models solve university mathematics and computer science course questions?"
pqa -s phase2_all ask "Since 2023, can large language models solve university mathematics and computer science course questions?"
```

The first time, the 16 papers are loaded (about 3 minutes, a few cents).
With `phase2_all` you should see lines starting with `Year filter` (E1),
`Trust check` (E2) and `Source diversity` (E3). The answer should **not** cite
`zhang2023exploringthemit`, which is a retracted paper. With `phase2_off` it usually does.

### Try one enhancement on one question (about 5-15 cents)

The script `scripts/run_eval.py` asks questions, records time, cost and which
papers were read and cited, and saves logs. `--feature demo` keeps your
practice runs separate from the official results. Type the question in the
command with `--question`, and see the answer on screen with `--show-answer`:

**E1, year filter on** (`[2023-]` is the year range the question asks for; it's only used for scoring):

```powershell
python scripts/run_eval.py --feature demo --label e1_on --papers test_papers/e1_years --set parsing.use_doc_details=true --clients openalex,journal_quality --set agent.apply_year_filter=true --runs 1 --show-answer --question "[2023-] What approaches published in 2023 or later let language models use external tools?"
```

**E2, trust score on** (the planted retracted paper should get flagged):

```powershell
python scripts/run_eval.py --feature demo --label e2_on --papers test_papers/e2_trust --set parsing.use_doc_details=true --clients openalex,journal_quality --set answer.use_trust_score=true --runs 1 --show-answer --question "Can large language models solve university mathematics and computer science course questions?"
```

**E3, source diversity on:**

```powershell
python scripts/run_eval.py --feature demo --label e3_on --papers test_papers/e3_diversity --set parsing.use_doc_details=true --clients openalex,journal_quality --set agent.show_source_diversity=true --runs 1 --show-answer --question "What makes a language agent's answers reliable and well cited?"
```

**You should see:** first `Indexing ...` (only the first time for each label,
1-3 minutes), then the time, cost and papers read. After that come
`What the enhancements told the agent` (the E1/E2/E3 lines) and the full `ANSWER`.

**Where to look afterwards** (open these in VS Code, not Excel):

| File | What's in it |
|---|---|
| `results\phase2\demo\papers_<label>.csv` | Every paper with the year, citation count and institutions PaperQA found |
| `results\phase2\demo\results.csv` | One row per question: time, cost, papers read, searches, cited papers |
| `results\phase2\demo\logs\<label>_q1_run1.log` | The answer, plus what the tools told the agent. Search for `Year filter` (E1) or `Source diversity` (E3) |

To compare, run the same command with the setting off (leave out the
`--set ...=true` part and use a different `--label`).

**Useful options:**

| Option | What it does |
|---|---|
| `--questions <file>` | Ask every question in a file (instead of `--question "..."`) |
| `--only 2 4` | Only questions 2 and 4 of the file |
| `--runs 1` | One run per question (the answers are almost the same every time) |
| `--show-answer` | Print the enhancement notes and the full answer |
| `--fresh-index` | Reload all papers, e.g. after adding one or after a failed paper |
| `--index-from <label>` | Reuse the papers already loaded by an earlier label, so nothing is loaded again |
| `--index-only` | Only load the papers and write `papers_<label>.csv` (check years and trust scores) |

The official before/after results of the team are in `results\phase2\e1`,
`e2` and `e3`, the regression check is in `results\phase2\regression`, and the
code measurements (cloc, lizard) are in `results\phase2\code_metrics`. Please
don't add practice runs there.

### Using a setting with `pqa`

Any setting can also be given to `pqa` directly, for example:

```powershell
pqa -s claude_cheap --parsing.use_doc_details true --parsing.metadata_clients '["openalex","journal_quality"]' --agent.apply_year_filter true ask "What retrieval methods were proposed in 2020 or 2021?"
```

If you change `parsing.use_doc_details` or `parsing.metadata_clients`, first
delete the old index (`Remove-Item -Recurse -Force "$HOME\.pqa\indexes"`), because
the stored paper details don't update by themselves.

---

## Understanding the output

While a question runs, paper-qa prints a status line after each step, like:

`Status: Paper Count=1 | Relevant Papers=1 | Current Evidence=5 | Current Cost=$0.0412`

| Part | Meaning |
|---|---|
| **Paper Count** | Papers the AI picked up for this question (not the number of files) |
| **Relevant Papers** | Papers with at least one useful part |
| **Current Evidence** | Parts of the papers that scored as relevant. Only these are used in the answer |
| **Current Cost** | Money spent on this question so far |

At the very start, all of these are 0. That's normal: the AI hasn't read
anything yet.

With the enhancements on, the agent also sees lines like these:

| Line | Enhancement | Meaning |
|---|---|---|
| `Year filter 2023-: kept 3 paper(s) from these years and 0 with unknown year, skipped 9 outside these years.` | E1 | The search kept only papers from the asked years. Papers with an unknown year are kept, not hidden |
| `Trust check: 1 of your top 2 source(s) are low-trust (trust score below 0.60): zhang2023... (0.00, RETRACTED, do not cite).` | E2 | Some of the best evidence comes from weak or retracted papers |
| `Source diversity: Institutions=3 \| Countries=1 (from 2 relevant paper(s), ...)` | E3 | Where the evidence comes from |

**Messages you can ignore:** `CROSSREF_MAILTO ... not set`, `OPENALEX_MAILTO ... not set` (Phase 1 commands only),
`SEMANTIC_SCHOLAR_API_KEY ... not set`, `DeprecationWarning`, and a message
about "symlinks on Windows".

---

## Asking about your own papers

1. Copy your PDFs into the `my_papers` folder.
2. Ask: `pqa -s claude_cheap ask "your question"`

Only new papers are read. **Avoid big PDFs full of images with `claude_demo`**:
it describes every image with AI, which can cost several dollars per paper.

---

## If something goes wrong

| You see | What to do |
|---|---|
| `running scripts is disabled` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, type `Y` |
| `py` or `git` is "not recognized" | Reinstall it (Python: tick "Add python.exe to PATH"), reopen PowerShell |
| `pqa` is "not recognized" | You forgot `.venv\Scripts\Activate.ps1`, or you're not in the `paper-qa` folder |
| `invalid x-api-key` | Set your key again with the `$env:ANTHROPIC_API_KEY = ...` line (it must start with `sk-ant-api03-`) |
| `credit balance is too low` | Add credit at console.anthropic.com, Billing |
| `Error parsing ... skipping index for this file` | Run `Remove-Item -Recurse -Force "$HOME\.pqa\indexes"`, then ask again |
| `429` or `503` errors | The service is busy. Wait 1-2 minutes and try again |
| Files other than your papers being indexed | Press **Ctrl + C**. Make sure the command has `-s claude_cheap` or `-s claude_demo` |
| `UnicodeEncodeError` | Run `$env:PYTHONUTF8 = 1` |
| Test 2 says `Cannot find path` | Toolformer is already in `my_papers`; skip the `Move-Item` line |
| `Current Cost=` climbing fast | Press **Ctrl + C** to stop |
| `PermissionError: ... Permission denied: ...csv` | The CSV is open in Excel, which locks it. Close it and run again |
| `Missing Anthropic API Key` in a log, a paper shows `FAILED` | The key wasn't set when papers were loaded. Set it, then run again with `--fresh-index` |
| `echo $env:OPENALEX_MAILTO` prints nothing | Close **all** VS Code/PowerShell windows after `setx` and reopen |
| `Unknown metadata client(s)` | A typo in `--clients`; use `crossref`, `semantic_scholar`, `openalex`, `unpaywall`, `journal_quality`, `retractions` |
| `test_settings_default_instantiation` fails | Add `--basetemp C:\pqa_test_tmp` to the command (a Windows temp-folder issue, also in the original) |
| Phase 2 tests fail with a "cassette" error | Your email is set; run `$env:CROSSREF_MAILTO = $null; $env:OPENALEX_MAILTO = $null` first (this window only) |
| `No index from label ...` | `--index-from` needs a label you already ran for the same `--feature` |
| `phase2_all` question runs until the 500 s timeout | A known limitation with all three on at once: the agent sometimes keeps resetting and searching again. Press **Ctrl + C**, or test the enhancements one at a time |
| `claude_cheap.json not found` from `make_phase2_profiles.py` | Run `.\team_setup.ps1` first |

---

## What's different from the original project

**On `main` (Phase 1), the original source code was not changed.** We only added files and
settings:

| Added | Why |
|---|---|
| `MY_SETUP_LOG.md` | This guide |
| `team-requirements.txt` | Version fixes. A newer `fhlmi` breaks paper-qa; `aiohttp` and `vcrpy` are pinned to the versions in the project's `uv.lock` so the tests run |
| `team_setup.ps1` | Downloads the papers and saves the two profiles |
| `smoke_test.py` | A small script that checks PDF reading and asks a question from Python |
| `.gitignore` (4 lines) | Keeps the downloaded PDFs out of git |

**Settings we changed** (through profiles, not code):

| Setting | Original default | Our profiles | Why |
|---|---|---|---|
| AI model | OpenAI GPT-4o | Claude Haiku (cheap) or Sonnet (demo) | We use Anthropic |
| Search | OpenAI embeddings | Keyword search (cheap) or a free local model (demo) | Anthropic has no embedding models |
| Paper details lookup (citation counts) | On | Off | Semantic Scholar blocks requests without its own API key |
| Image reading | On | Off (cheap), on (demo) | Images are the most expensive part |
| Pieces of evidence per question | 20 | 5 (cheap), 20 (demo) | Cost |

To prove the code is original: `git log` shows the original FutureHouse
commits, and our changes are only the files listed above.

**On `phase2`, we changed the code** (everything is behind on/off settings):

| File | Change |
|---|---|
| `src/paperqa/clients/openalex.py` | Saves institutions and countries of the first 3 authors (E3), venue quality and retraction status (E2). **Bug fix:** translates field names (`author` → `authorships`, ...), because OpenAlex rejected every lookup during indexing with HTTP 400 |
| `src/paperqa/clients/client_models.py` | **Bug fix:** an HTTP error such as `429 Too Many Requests` now skips that source instead of crashing indexing of the whole folder |
| `src/paperqa/clients/__init__.py`, `docs.py` | Choose metadata sources by name (`parsing.metadata_clients`) |
| `src/paperqa/trust.py` (new) | E2 trust score formula and the 0.60 low-trust threshold |
| `src/paperqa/university_rankings.py` (new) | E2: the THE 2027 top-100 university list |
| `src/paperqa/types.py` | New paper fields `trust_score`, `top_university_rank`, `top_university_affiliations`, `institutions`, `countries`; E2 trust table in the answer |
| `src/paperqa/settings.py`, `README.md` | New settings `parsing.metadata_clients`, `parsing.extract_author_affiliations_from_front_matter`, `agent.apply_year_filter`, `agent.show_source_diversity`, `answer.use_trust_score`; E2 ranks evidence by relevance × trust |
| `src/paperqa/docs.py`, `prompts.py` | E2: optional author affiliations read from the PDF's first page (off by default), and the trust-score comparison answer |
| `src/paperqa/agents/tools.py`, `agents/env.py` | E1 year filter in `paper_search`; E2 trust check and E3 diversity line in `gather_evidence` |
| `tests/test_phase2_metadata.py`, `test_year_filter.py`, `test_trust.py`, `test_diversity.py` | 82 offline tests (no API) |
| `scripts/run_eval.py`, `scripts/get_phase2_papers.ps1`, `scripts/make_phase2_profiles.py`, `test_questions/`, `test_papers/e2_trust_PLANTED.txt` | Evaluation runner, test papers, Phase 2 profiles, test questions |
| `results/phase2/` | Before/after results, regression check, code metrics |

**Bugs found by the regression check and fixed:** the year filter hid papers
whose year was unknown, the E2 trust note appeared in "cannot answer" replies,
and the trust table listed a paper once per cited page range.

**New tools, for measuring only** (not needed to run the project):

```powershell
pip install lizard     # complexity (cyclomatic complexity per function)
npx cloc --version     # lines of code; needs Node.js, and Perl (comes with Git for Windows)
```

To see every change since Phase 1: `git diff phase2-baseline phase2 --stat`.

---

## Safety rules

- **Never put your API key in a file** or commit it to git. Always set it with
  `$env:ANTHROPIC_API_KEY` in PowerShell.
- **Don't upload PDFs** to GitHub. `my_papers` and `papers_later` are ignored
  by git on purpose.
- Watch `Current Cost=` and press **Ctrl + C** if a question gets expensive.
