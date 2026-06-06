# Claude SEO Pro - Self-contained installer (Windows / PowerShell)
# Installs the vendored skills, agents, scripts, and the onboarding wizard from THIS
# repo directory into ~/.claude, then offers guided API onboarding.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -NoOnboard   # skip the wizard

param([switch]$NoOnboard)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "|  Claude SEO Pro - Installer          |" -ForegroundColor Cyan
Write-Host "|  Evidence-verified SEO for Claude    |" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Resolve Python ---
function Resolve-Python {
    if (Get-Command python -ErrorAction SilentlyContinue) { return @{ Exe = 'python'; Args = @() } }
    if (Get-Command py -ErrorAction SilentlyContinue)     { return @{ Exe = 'py'; Args = @('-3') } }
    return $null
}
$python = Resolve-Python
if ($null -eq $python) {
    Write-Host "[x] Python 3.10+ is required but was not found (tried 'python' and 'py')." -ForegroundColor Red
    exit 1
}
$pyv = & $python.Exe @($python.Args + @('--version'))
Write-Host "[+] $pyv detected" -ForegroundColor Green

if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "[+] Node.js detected (MCP servers available)" -ForegroundColor Green
} else {
    Write-Host "[!] Node.js not found - DataForSEO/Firecrawl/Exa MCP servers need it. Install from https://nodejs.org" -ForegroundColor Yellow
}

# --- Paths ---
$SkillsRoot = "$env:USERPROFILE\.claude\skills"
$SkillDir   = "$SkillsRoot\seo"
$AgentDir   = "$env:USERPROFILE\.claude\agents"
New-Item -ItemType Directory -Force -Path $SkillDir, $AgentDir | Out-Null

# --- Skills (all skills/seo*; includes seo-setup) ---
Write-Host "=> Installing skills..." -ForegroundColor Yellow
Get-ChildItem -Directory "$RepoRoot\skills" | ForEach-Object {
    $target = "$SkillsRoot\$($_.Name)"
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -Recurse -Force "$($_.FullName)\*" $target
}

# --- Agents ---
Write-Host "=> Installing agents..." -ForegroundColor Yellow
if (Test-Path "$RepoRoot\agents") {
    Copy-Item -Force "$RepoRoot\agents\*.md" $AgentDir -ErrorAction SilentlyContinue
}

# --- Shared resources bundled under the seo skill (scripts/hooks/schema/pdf) ---
Write-Host "=> Installing shared scripts and resources..." -ForegroundColor Yellow
foreach ($d in @("scripts","hooks","schema","pdf")) {
    if (Test-Path "$RepoRoot\$d") {
        New-Item -ItemType Directory -Force -Path "$SkillDir\$d" | Out-Null
        Copy-Item -Recurse -Force "$RepoRoot\$d\*" "$SkillDir\$d"
    }
}
# operator tools that must work on installed seats without a repo checkout
if (Test-Path "$RepoRoot\tools\switch_provider.py") {
    Copy-Item -Force "$RepoRoot\tools\switch_provider.py" "$SkillDir\scripts\switch_provider.py"
}

# --- Onboarding wizard (the new feature) ---
Write-Host "=> Installing onboarding wizard..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$SkillDir\onboarding" | Out-Null
Copy-Item -Recurse -Force "$RepoRoot\onboarding\*" "$SkillDir\onboarding"

# --- Knowledge layer (persistent client memory + data cache) ---
Write-Host "=> Installing knowledge layer..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$SkillDir\knowledge" | Out-Null
Copy-Item -Recurse -Force "$RepoRoot\knowledge\*" "$SkillDir\knowledge"

# --- Routing layer (model-routing policy) ---
Write-Host "=> Installing routing layer..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$SkillDir\routing" | Out-Null
Copy-Item -Recurse -Force "$RepoRoot\routing\*" "$SkillDir\routing"

# --- Connector (chat -> headless SEO bridge) ---
Write-Host "=> Installing connector..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$SkillDir\connector" | Out-Null
Copy-Item -Recurse -Force "$RepoRoot\connector\*" "$SkillDir\connector"

# --- Extensions ---
if (Test-Path "$RepoRoot\extensions") {
    Write-Host "=> Installing extensions..." -ForegroundColor Yellow
    Get-ChildItem -Directory "$RepoRoot\extensions" | ForEach-Object {
        $extName = $_.Name
        if (Test-Path "$($_.FullName)\skills") {
            Get-ChildItem -Directory "$($_.FullName)\skills" | ForEach-Object {
                $t = "$SkillsRoot\$($_.Name)"; New-Item -ItemType Directory -Force -Path $t | Out-Null
                Copy-Item -Recurse -Force "$($_.FullName)\*" $t
            }
        }
        if (Test-Path "$($_.FullName)\agents") {
            Copy-Item -Force "$($_.FullName)\agents\*.md" $AgentDir -ErrorAction SilentlyContinue
        }
        foreach ($sub in @("references","scripts")) {
            if (Test-Path "$($_.FullName)\$sub") {
                $t = "$SkillDir\extensions\$extName\$sub"; New-Item -ItemType Directory -Force -Path $t | Out-Null
                Copy-Item -Recurse -Force "$($_.FullName)\$sub\*" $t
            }
        }
    }
}

# --- Install manifest (version stamp for drift detection) ---
$ver = "unknown"
try { $ver = (Get-Content "$RepoRoot\system-version.json" -Raw | ConvertFrom-Json).version } catch {}
$cfgDir = "$env:USERPROFILE\.config\claude-seo"
New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
$manifest = @{ pro_version = $ver; installed_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"); source = $RepoRoot } | ConvertTo-Json
Set-Content -Path "$cfgDir\install-manifest.json" -Value $manifest -Encoding utf8
Write-Host "=> Stamped install manifest (v$ver)" -ForegroundColor Yellow

# --- Python dependencies (onboarding itself is stdlib-only; reports need these) ---
$reqFile = "$RepoRoot\requirements.txt"
if (Test-Path $reqFile) {
    Write-Host "=> Installing Python dependencies..." -ForegroundColor Yellow
    Copy-Item -Force $reqFile "$SkillDir\requirements.txt"
    try {
        & $python.Exe @($python.Args + @('-m','pip','install','-q','-r',$reqFile))
    } catch {
        Write-Host "  [!] Could not auto-install packages. Run: $($python.Exe) -m pip install -r `"$SkillDir\requirements.txt`"" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "[+] Claude SEO Pro installed." -ForegroundColor Green
Write-Host ""

# --- Guided onboarding ---
if ($NoOnboard) {
    Write-Host "Onboarding skipped (-NoOnboard). Run it any time:" -ForegroundColor Gray
    Write-Host "  $($python.Exe) `"$SkillDir\onboarding\setup_wizard.py`"" -ForegroundColor Gray
} else {
    Write-Host "Next: configure your API keys (DataForSEO, Google, Firecrawl, Exa)." -ForegroundColor Cyan
    $ans = Read-Host "Run the guided onboarding wizard now? [Y/n]"
    if ($ans -notmatch '^(n|no)$') {
        & $python.Exe @($python.Args + @("$SkillDir\onboarding\setup_wizard.py"))
    } else {
        Write-Host "  Run later with:  $($python.Exe) `"$SkillDir\onboarding\setup_wizard.py`"" -ForegroundColor Gray
        Write-Host "  Or inside Claude Code:  /seo-setup" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Then start Claude Code and run:" -ForegroundColor Cyan
Write-Host "  /seo-setup verify              # confirm everything is wired"
Write-Host "  /seo audit https://example.com # first audit"
Write-Host ""
