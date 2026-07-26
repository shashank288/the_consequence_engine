# Creates one git worktree per feature branch so agents can run in parallel
# without colliding. Run once from the repo root:  .\scripts\setup_worktrees.ps1
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$base = Join-Path (Split-Path -Parent $repo) "ce-worktrees"
Set-Location $repo

New-Item -ItemType Directory -Force -Path $base | Out-Null

$branches = @("feat/extraction","feat/sequencer","feat/register",
              "feat/case-memory","feat/ui","feat/voice")

foreach ($b in $branches) {
    $short = $b.Replace("feat/","")
    $path  = Join-Path $base $short
    if (Test-Path $path) { Write-Host "= $short already exists" -ForegroundColor DarkGray; continue }
    git worktree add $path $b | Out-Null
    Copy-Item (Join-Path $repo ".env") (Join-Path $path ".env") -ErrorAction SilentlyContinue
    Write-Host "+ $short  ->  $path" -ForegroundColor Green
}

Write-Host "`nWorktrees ready under $base" -ForegroundColor Cyan
Write-Host "Launch an agent per folder, e.g.:" -ForegroundColor Cyan
Write-Host "   cd $base\extraction ; claude" -ForegroundColor Yellow
Write-Host "then paste:  Read docs/agents/feat-extraction.md and CLAUDE.md, then execute the brief." -ForegroundColor Yellow
git worktree list
