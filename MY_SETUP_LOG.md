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

This copy runs the **original code unchanged**. We only added this guide, a few
helper files, and settings to use **Anthropic's Claude** instead of OpenAI.

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
```

**You should see:** `Cloning into 'paper-qa'...` and then `done`.

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

---

## Free checks (no API key needed)

### Check 1: The project's own tests pass

```powershell
python -m pytest tests/test_configs.py tests/test_utils.py --record-mode=none -p no:cacheprovider -q --basetemp C:\pqa_test_tmp
```

**You should see:** `24 passed` (and `93 subtests passed`).

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

**Messages you can ignore:** `CROSSREF_MAILTO ... not set`,
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

---

## What's different from the original project

**The original source code was not changed.** We only added files and
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

---

## Safety rules

- **Never put your API key in a file** or commit it to git. Always set it with
  `$env:ANTHROPIC_API_KEY` in PowerShell.
- **Don't upload PDFs** to GitHub. `my_papers` and `papers_later` are ignored
  by git on purpose.
- Watch `Current Cost=` and press **Ctrl + C** if a question gets expensive.
