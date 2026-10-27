# One-time setup after installing (see MY_SETUP_LOG.md, Step 5).
# Downloads the demo papers from arXiv and saves the two paper-qa settings
# profiles, claude_cheap and claude_demo, pointing at this PC's my_papers folder.
# Run from the paper-qa folder with the virtual environment turned on:
#   .\team_setup.ps1

$ErrorActionPreference = "Stop"
$papers = Join-Path $PWD "my_papers"
$later = Join-Path $PWD "papers_later"
New-Item -ItemType Directory -Force $papers, $later | Out-Null

# PaperQA2 and ReAct start in my_papers; Toolformer waits in papers_later for Test 2
$downloads = [ordered]@{
    "2409.13740v2.pdf" = $papers  # PaperQA2
    "2210.03629v3.pdf" = $papers  # ReAct
    "2302.04761v1.pdf" = $later   # Toolformer
}
foreach ($file in $downloads.Keys) {
    if ((Test-Path (Join-Path $papers $file)) -or (Test-Path (Join-Path $later $file))) {
        Write-Host "Already have $file"
        continue
    }
    Write-Host "Downloading $file ..."
    $id = $file -replace '\.pdf$', ''
    Invoke-WebRequest "https://arxiv.org/pdf/$id" -OutFile (Join-Path $downloads[$file] $file)
}

Write-Host "Saving profile claude_cheap (low cost: Claude Haiku, text only, keyword search) ..."
$cheap = "anthropic/claude-haiku-4-5"
pqa --llm $cheap --summary_llm $cheap --agent.agent_llm $cheap --parsing.enrichment_llm $cheap `
    --embedding sparse --parsing.multimodal false --parsing.use_doc_details false `
    --answer.evidence_k 5 --answer.answer_max_sources 3 --answer.max_concurrent_requests 2 `
    --agent.index.concurrency 1 --agent.index.paper_directory $papers `
    save claude_cheap

Write-Host "Saving profile claude_demo (high quality: Claude Sonnet, images on, local semantic search) ..."
$demo = "anthropic/claude-sonnet-4-5"
pqa -s high_quality --llm $demo --summary_llm $demo --agent.agent_llm $demo --parsing.enrichment_llm $demo `
    --embedding st-multi-qa-MiniLM-L6-cos-v1 --parsing.use_doc_details false `
    --agent.index.concurrency 1 --agent.index.paper_directory $papers `
    save claude_demo

Write-Host ""
Write-Host "Setup done. my_papers has PaperQA2 and ReAct; papers_later has Toolformer."
