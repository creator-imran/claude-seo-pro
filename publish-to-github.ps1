# publish-to-github.ps1
# One-shot helper to create the private repo on GitHub and push this directory.
# Run this from the claude-seo-pro folder on a machine where you can install tools.
#
#   powershell -ExecutionPolicy Bypass -File publish-to-github.ps1
#   powershell -ExecutionPolicy Bypass -File publish-to-github.ps1 -Public
#   powershell -ExecutionPolicy Bypass -File publish-to-github.ps1 -Repo "creator-imran/claude-seo-pro"

param(
    [string]$Repo = "creator-imran/claude-seo-pro",
    [switch]$Public
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Need($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "[x] '$name' is not installed." -ForegroundColor Red
        Write-Host "    $hint" -ForegroundColor Yellow
        exit 1
    }
}

Need git "Install: winget install --id Git.Git -e   (or https://git-scm.com)"
Need gh  "Install: winget install --id GitHub.cli -e (or https://cli.github.com), then: gh auth login"

# Confirm gh is authenticated
& gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[x] GitHub CLI is not authenticated. Run:  gh auth login" -ForegroundColor Red
    exit 1
}

$vis = if ($Public) { "--public" } else { "--private" }

Write-Host "==> Initializing git repository..." -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
    & git init -b main
} else {
    & git checkout -B main
}

Write-Host "==> Staging files (secrets are excluded by .gitignore)..." -ForegroundColor Cyan
& git add .

# Safety check: make sure no obvious secret file is staged.
$leaks = & git diff --cached --name-only | Where-Object { $_ -match '(-api\.json$|\.env$|client_secret|service_account|oauth-token)' }
if ($leaks) {
    Write-Host "[x] Refusing to commit - these look like secrets and are staged:" -ForegroundColor Red
    $leaks | ForEach-Object { Write-Host "      $_" -ForegroundColor Red }
    Write-Host "    Remove them or fix .gitignore, then re-run." -ForegroundColor Yellow
    exit 1
}

& git commit -m "Claude SEO Pro v1.0.0 - guided onboarding + Evidence Integrity Protocol on claude-seo (MIT)"

Write-Host "==> Creating GitHub repo $Repo ($([string]$vis)) and pushing..." -ForegroundColor Cyan
& gh repo create $Repo $vis --source=. --remote=origin --push

Write-Host ""
Write-Host "[+] Done. Repo: https://github.com/$Repo" -ForegroundColor Green
Write-Host "    Grant a client access:  gh repo edit $Repo  (or via the GitHub web UI > Settings > Collaborators)" -ForegroundColor Gray
