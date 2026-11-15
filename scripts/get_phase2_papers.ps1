# Phase 2: download the test papers for each enhancement (see course_docs/Phase2_Plan.md).
# Creates three folders under test_papers and fills them from arXiv:
#   e1_years      - 12 papers from 2017-2024, for the year filter (Enhancement 1)
#   e2_trust      - the same 12 well-cited papers (high trust) + 3 planted low-trust preprints
#                   + 1 retracted paper, for the trust score (Enhancement 2)
#   e3_diversity  - 4 FutureHouse papers + 3 from other institutions (Enhancement 3)
# Papers already present (here or in my_papers) are copied instead of downloaded again.
# Run from the paper-qa folder:
#   .\scripts\get_phase2_papers.ps1

$ErrorActionPreference = "Stop"
$root = Join-Path $PWD "test_papers"

# arXiv ID -> short name (all IDs checked against the arXiv API)
$e1 = [ordered]@{
    "1706.03762" = "2017 Attention Is All You Need"
    "1810.04805" = "2018 BERT"
    "2002.08909" = "2020 REALM"
    "2004.04906" = "2020 Dense Passage Retrieval"
    "2005.11401" = "2020 Retrieval-Augmented Generation"
    "2112.09332" = "2021 WebGPT"
    "2201.11903" = "2022 Chain-of-Thought Prompting"
    "2210.03629" = "2022 ReAct"
    "2302.04761" = "2023 Toolformer"
    "2303.11366" = "2023 Reflexion"
    "2310.11511" = "2023 Self-RAG"
    "2409.13740" = "2024 PaperQA2"
}
$e3 = [ordered]@{
    "2312.07559" = "FutureHouse - PaperQA"
    "2409.13740" = "FutureHouse - PaperQA2"
    "2407.10362" = "FutureHouse - LAB-Bench"
    "2412.21154" = "FutureHouse - Aviary"
    "2210.03629" = "Princeton/Google - ReAct"
    "2302.04761" = "Meta - Toolformer"
    "2310.11511" = "U. Washington/AI2 - Self-RAG"
}
# E2 planted papers (see test_papers\e2_trust_PLANTED.txt). Version 1 of each, because
# later arXiv versions of the retracted paper were withdrawn.
$e2planted = [ordered]@{
    "2511.01059v1" = "LOW-TRUST 2025 Efficient Test-Time RAG (0 citations)"
    "2306.08997v1" = "RETRACTED 2023 MIT Mathematics and EECS Curriculum with LLMs"
    "2511.22832v1" = "LOW-TRUST 2025 Structured Multi-Step Reasoning for Entity Matching (0 citations)"
    "2502.18877v1" = "LOW-TRUST 2025 Hierarchical corpus encoder (0 citations)"
}
$e2 = [ordered]@{}
foreach ($k in $e1.Keys) { $e2[$k] = $e1[$k] }
foreach ($k in $e2planted.Keys) { $e2[$k] = $e2planted[$k] }
$folders = [ordered]@{ "e1_years" = $e1; "e2_trust" = $e2; "e3_diversity" = $e3 }

function Find-Existing([string]$id) {
    # Any earlier copy, e.g. my_papers\2210.03629v3.pdf or test_papers\e1_years\2210.03629.pdf
    $dirs = @((Join-Path $PWD "my_papers"), (Join-Path $PWD "papers_later")) +
        ($folders.Keys | ForEach-Object { Join-Path $root $_ })
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            $hit = Get-ChildItem $dir -Filter "$id*.pdf" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    return $null
}

$downloaded = 0
foreach ($folder in $folders.Keys) {
    $dir = Join-Path $root $folder
    New-Item -ItemType Directory -Force $dir | Out-Null
    Write-Host "`n== $folder =="
    $papers = $folders[$folder]
    foreach ($id in $papers.Keys) {
        $target = Join-Path $dir "$id.pdf"
        if (Get-ChildItem $dir -Filter "$id*.pdf" -ErrorAction SilentlyContinue) {
            Write-Host "  have      $id  $($papers[$id])"
            continue
        }
        $existing = Find-Existing $id
        if ($existing) {
            Copy-Item $existing $target
            Write-Host "  copied    $id  $($papers[$id])"
            continue
        }
        if ($downloaded -gt 0) { Start-Sleep -Seconds 3 }  # arXiv asks for a pause between downloads
        Invoke-WebRequest "https://arxiv.org/pdf/$id" -OutFile $target
        $downloaded++
        Write-Host "  download  $id  $($papers[$id])"
    }
}

# E2 needs hand-picked low-trust and retracted papers; leave a template for the teammate
# Kept OUTSIDE the e2_trust folder, otherwise PaperQA would index it as a paper
$planted = Join-Path $root "e2_trust_PLANTED.txt"
if (-not (Test-Path $planted)) {
    @"
# Planted papers for Enhancement 2 (one per line): file name | why it is low-trust | DOI if any
# Keep this file OUTSIDE the e2_trust folder: PaperQA indexes .txt files as papers.
# Example: 2501.01234.pdf | arXiv preprint, 0 citations, no journal | none
# Example: retracted_paper.pdf | retracted (Retraction Watch) | 10.xxxx/xxxxx
"@ | Set-Content -Encoding utf8 $planted
}

Write-Host "`nDone. Downloaded $downloaded new paper(s)."
Write-Host "E2: test_papers\e2_trust has 12 well-cited + 4 planted papers (listed in test_papers\e2_trust_PLANTED.txt)."
