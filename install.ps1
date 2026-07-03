# Auto Skill Finder — Windows Installer (PowerShell 5.1+)
# Remote install (one-liner):
#   irm https://raw.githubusercontent.com/prantikmedhi/auto-skill-finder/main/install.ps1 | iex
#
# Local install (already cloned):
#   .\install.ps1
#
# Options:
#   $env:AUTO_SKILL_DIR   Override install directory
#   $env:AUTO_SKILL_ONLY  Install for one agent only (e.g. "claude")
#   $env:AUTO_SKILL_UPDATE = "1"  Force re-clone

param(
  [string]$Only  = $env:AUTO_SKILL_ONLY,
  [switch]$Update = ($env:AUTO_SKILL_UPDATE -eq "1")
)

$ErrorActionPreference = "Stop"

$REPO        = "https://github.com/prantikmedhi/auto-skill-finder.git"
$InstallDir  = if ($env:AUTO_SKILL_DIR) { $env:AUTO_SKILL_DIR } `
               else { Join-Path $env:USERPROFILE ".auto-skill-finder" }

# ── Helpers ───────────────────────────────────────────────────────────────────

function Write-Header {
  Write-Host ""
  Write-Host "╔══════════════════════════════════════╗" -ForegroundColor Cyan
  Write-Host "║     Auto Skill Finder Installer      ║" -ForegroundColor Cyan
  Write-Host "╚══════════════════════════════════════╝" -ForegroundColor Cyan
  Write-Host ""
}

function Write-Step  { param($msg) Write-Host "[auto-skill-finder] $msg" -ForegroundColor White }
function Write-Ok    { param($msg) Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

# ── Dependency checks ─────────────────────────────────────────────────────────

function Check-Node {
  $node = Get-Command node -ErrorAction SilentlyContinue
  if (-not $node) {
    Write-Fail "Node.js not found. Install from https://nodejs.org (v18+) and re-run."
  }
  $ver = (node -e "process.stdout.write(process.versions.node.split('.')[0])") -as [int]
  if ($ver -lt 18) {
    Write-Fail "Node.js v$ver found but v18+ required. Upgrade and re-run."
  }
  Write-Ok "Node.js $(node --version)"
}

function Check-Git {
  $git = Get-Command git -ErrorAction SilentlyContinue
  if (-not $git) {
    Write-Fail "git not found. Install Git for Windows (https://git-scm.com) and re-run."
  }
  Write-Ok "git $((git --version) -replace 'git version ','')"
}

# ── Clone or reuse ────────────────────────────────────────────────────────────

function Get-SkillDir {
  # Running from local clone?
  $localInstaller = Join-Path $PSScriptRoot "bin\install.js"
  if ($PSScriptRoot -and (Test-Path $localInstaller)) {
    return $PSScriptRoot
  }

  # Already installed?
  $gitDir = Join-Path $InstallDir ".git"
  if (Test-Path $gitDir) {
    if ($Update) {
      Write-Step "Updating existing install at $InstallDir..."
      git -C $InstallDir pull --ff-only --quiet
      Write-Ok "Updated"
    } else {
      Write-Step "Found existing install at $InstallDir (set `$env:AUTO_SKILL_UPDATE=1 to update)"
    }
    return $InstallDir
  }

  # Fresh clone
  Write-Step "Cloning to $InstallDir..."
  git clone --depth 1 --quiet $REPO $InstallDir
  Write-Ok "Cloned to $InstallDir"
  return $InstallDir
}

# ── Main ──────────────────────────────────────────────────────────────────────

Write-Header

Write-Step "Checking dependencies..."
Check-Git
Check-Node
Write-Host ""

$SkillDir = Get-SkillDir
Write-Host ""

Write-Step "Running installer..."
$nodeArgs = @("$SkillDir\bin\install.js")
if ($Only) { $nodeArgs += "--only", $Only }

& node @nodeArgs
if ($LASTEXITCODE -ne 0) { Write-Fail "Installer exited with code $LASTEXITCODE" }

Write-Host ""
Write-Host "Auto Skill Finder installed successfully." -ForegroundColor Green
Write-Host ""
Write-Host "  Skill dir : $SkillDir"
Write-Host "  Docs      : https://github.com/prantikmedhi/auto-skill-finder"
Write-Host ""
Write-Host "  Restart your AI agent session to activate."
Write-Host ""
