# Merge a feature branch into main, gated by verify.ps1.
# Usage:  .\scripts\merge_branch.ps1 feat/extraction
param([Parameter(Mandatory=$true)][string]$Branch)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if ((git status --porcelain)) { Write-Host "Main worktree is dirty. Commit or stash first." -ForegroundColor Red; exit 1 }

Write-Host "Merging $Branch -> main" -ForegroundColor Cyan
git checkout main
git fetch origin --quiet
git pull --rebase origin main
git merge --no-ff $Branch -m "merge($Branch): into main"
if ($LASTEXITCODE -ne 0) { Write-Host "`nCONFLICT. Resolve, then: git add -A; git commit; .\scripts\verify.ps1" -ForegroundColor Red; exit 1 }

& (Join-Path $PSScriptRoot "verify.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nVerify failed after merge. Rolling back." -ForegroundColor Red
    git reset --hard HEAD~1
    exit 1
}
git push origin main
Write-Host "`nMerged and pushed. Recommended order: extraction -> sequencer -> register -> case-memory -> ui -> voice" -ForegroundColor Green
