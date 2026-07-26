# The gate. Every agent runs this before opening a PR; main runs it before every merge.
# Usage:  .\scripts\verify.ps1
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$fail = 0

Write-Host "`n[1/3] tests" -ForegroundColor Cyan
py -3.12 -m pytest -q
if ($LASTEXITCODE -ne 0) { $fail = 1; Write-Host "  FAIL: tests red" -ForegroundColor Red }

Write-Host "`n[2/3] fixture golden path (demo fallback - must NEVER break)" -ForegroundColor Cyan
$out = py -3.12 -m scripts.run_case 2>&1 | Out-String
if ($out -match "NEXT SINGLE ACTION: \S" -and $out -match "blocked by" -and $out -match "REFUSALS: \['plot_area'\]") {
    Write-Host "  ok: next action + blocking edge + refusal all present" -ForegroundColor Green
} else {
    $fail = 1; Write-Host "  FAIL: golden path degraded" -ForegroundColor Red; Write-Host $out
}

Write-Host "`n[3/3] frozen contract" -ForegroundColor Cyan
$diff = git diff origin/main --name-only -- src/contracts.py 2>$null
if ($diff) {
    Write-Host "  WARNING: src/contracts.py modified. Needs a CONTRACT-CHANGE PR to main" -ForegroundColor Yellow
    Write-Host "  + a decision-log row in IDEA_SCOPE.md section 16." -ForegroundColor Yellow
} else { Write-Host "  ok: contract untouched" -ForegroundColor Green }

if ($fail) { Write-Host "`nVERIFY FAILED - do not merge`n" -ForegroundColor Red; exit 1 }
Write-Host "`nVERIFY PASSED - safe to merge`n" -ForegroundColor Green
