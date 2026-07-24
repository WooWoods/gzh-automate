<#
.SYNOPSIS
    WeWrite installer for Windows PowerShell

.DESCRIPTION
    Installs the wewrite CLI and registers skills for Claude Code,
    Agent Skills, OpenClaw, and Codex on Windows.

    Parameters:
        -NoCli:      Skip CLI installation
        -NoSkills:   Skip skill registration
        -NoMigrate:  Skip state migration

.EXAMPLE
    .\install.ps1
    .\install.ps1 -NoCli
#>

param(
    [switch]$NoCli,
    [switch]$NoSkills,
    [switch]$NoMigrate
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-ClaudeSkillsDir {
    if ($env:CLAUDE_SKILLS_DIR) {
        return $env:CLAUDE_SKILLS_DIR
    }
    return Join-Path $env:USERPROFILE ".claude\skills"
}

function Get-AgentsSkillsDir {
    if ($env:AGENTS_SKILLS_DIR) {
        return $env:AGENTS_SKILLS_DIR
    }
    return Join-Path $env:USERPROFILE ".agents\skills"
}

function Get-ExtraSkillTargets {
    $extra = @()
    foreach ($name in @("openclaw", "codex")) {
        $parent = Join-Path $env:USERPROFILE ".$name"
        if (Test-Path $parent) {
            $extra += Join-Path $parent "skills"
        }
    }
    return $extra
}

function Register-Skills {
    param(
        [string]$SkillsSrc,
        [string[]]$Targets
    )

    if (-not (Test-Path $SkillsSrc)) {
        Write-Host "  (no skills/ directory at $SkillsSrc, skipping)"
        return 0
    }

    $skillDirs = Get-ChildItem $SkillsSrc -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName "SKILL.md")
    }

    if (-not $skillDirs) {
        Write-Host "  (no skill directories found in $SkillsSrc)"
        return 0
    }

    foreach ($target in $Targets) {
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        $linked = 0
        foreach ($skillDir in $skillDirs) {
            $dest = Join-Path $target $skillDir.Name

            # Remove existing
            if (Test-Path $dest) {
                Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
            }

            # Try symbolic link first (needs Developer Mode or admin)
            $symlinked = $false
            try {
                New-Item -ItemType SymbolicLink -Path $dest -Target $skillDir.FullName -ErrorAction Stop | Out-Null
                Write-Host "    ln: $($skillDir.Name) -> $dest"
                $symlinked = $true
            } catch {
                # Fall back to copy
            }

            if (-not $symlinked) {
                Copy-Item -Recurse $skillDir.FullName $dest
                Write-Host "    cp: $($skillDir.Name) -> $dest"
            }
            $linked++
        }
        Write-Host "  [OK] $linked skills registered to $target"
    }
    return $skillDirs.Count
}

function Install-WewriteCli {
    param([string]$Repo)

    $hasPyproject = Test-Path (Join-Path $Repo "pyproject.toml")

    if (-not $hasPyproject) {
        Write-Host "  (no pyproject.toml found -- installing from PyPI)"
        $installed = $false
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            uv tool install --force wewrite
            if ($LASTEXITCODE -eq 0) { $installed = $true; Write-Host "  [OK] installed via uv" }
        }
        if (-not $installed -and (Get-Command pipx -ErrorAction SilentlyContinue)) {
            pipx install --force wewrite
            if ($LASTEXITCODE -eq 0) { $installed = $true; Write-Host "  [OK] installed via pipx" }
        }
        if (-not $installed) {
            python -m pip install --quiet wewrite
            if ($LASTEXITCODE -eq 0) { $installed = $true; Write-Host "  [OK] installed via pip" }
        }
        if (-not $installed) {
            Write-Host "  [FAIL] All install methods failed. Check your network and try again."
            exit 1
        }
        Check-WewriteOnPath
        return
    }

    # Try uv first
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv tool install --force $Repo
        if ($?) { Write-Host "  [OK] installed via uv"; return }
    }

    # Try pipx
    if (Get-Command pipx -ErrorAction SilentlyContinue) {
        pipx install --force $Repo
        if ($?) { Write-Host "  [OK] installed via pipx"; return }
    }

    # Fallback: pip install into venv
    Write-Host "  (no uv/pipx found, installing via pip into venv)"
    $venvDir = Join-Path $Repo ".venv"
    if (-not (Test-Path $venvDir)) {
        python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [FAIL] Failed to create venv. Check that Python 3.11+ is installed."
            exit 1
        }
    }
    $venvPython = if ($env:OS -eq "Windows_NT") { Join-Path $venvDir "Scripts\python.exe" } else { Join-Path $venvDir "bin\python" }
    & $venvPython -m pip install --quiet --upgrade pip | Out-Null
    & $venvPython -m pip install --quiet -e $Repo
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] installed via pip into venv"
        Write-Host "  [WARN] Add wewrite to PATH or use the full path:"
        if ($env:OS -eq "Windows_NT") {
            Write-Host "    $(Join-Path $venvDir 'Scripts\wewrite.exe')"
        } else {
            Write-Host "    $(Join-Path $venvDir 'bin\wewrite')"
        }
    } else {
        Write-Host "  [FAIL] pip install failed. Check your network and try again."
        exit 1
    }
    Check-WewriteOnPath
}

function Check-WewriteOnPath {
    if (Get-Command wewrite -ErrorAction SilentlyContinue) {
        $wewritePath = (Get-Command wewrite).Source
        Write-Host "  [OK] wewrite CLI ready: $wewritePath"
    } else {
        Write-Host "  [WARN] wewrite not found on current PATH."
        Write-Host "    Restart your terminal or add the Python Scripts directory to PATH."
        Write-Host "    Usually: $env:APPDATA\Python\Python3*\Scripts"
    }
}

function Migrate-OldState {
    param([string]$Repo)

    $oldFiles = @(
        (Join-Path $Repo "style.yaml"),
        (Join-Path $Repo "history.yaml"),
        (Join-Path $Repo "config.yaml")
    )

    $hasOldState = $false
    foreach ($f in $oldFiles) {
        if (Test-Path $f) {
            $hasOldState = $true
            break
        }
    }

    if (-not $hasOldState) {
        Write-Host "  (no old state files found, skipping)"
        return
    }

    if (-not (Get-Command wewrite -ErrorAction SilentlyContinue)) {
        Write-Host "  [WARN] Old state files found but wewrite CLI not available."
        Write-Host "    Re-run install.ps1 after CLI is installed."
        return
    }

    Write-Host "-> Old repo-root state files detected. Migrating..."
    try {
        wewrite migrate --from $Repo
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [OK] State migrated successfully"
        } else {
            Write-Host "  [WARN] Migration reported issues (exit code: $LASTEXITCODE)"
        }
    } catch {
        Write-Host "  [WARN] Migration error: $_"
    }
}

Write-Host "-> Installing WeWrite from $Repo"

# ---- 1) Install CLI ----
if (-not $NoCli) {
    Write-Host "-> Installing wewrite CLI..."
    Install-WewriteCli -Repo $Repo
} else {
    Write-Host "  (--no-cli: skipping)"
}

# ---- 2) Register skills ----
if (-not $NoSkills) {
    Write-Host "-> Registering skills..."
    $skillsSrc = Join-Path $Repo "skills"
    $targets = @(Get-ClaudeSkillsDir; Get-AgentsSkillsDir) + (Get-ExtraSkillTargets)
    $null = Register-Skills -SkillsSrc $skillsSrc -Targets $targets
} else {
    Write-Host "  (--no-skills: skipping)"
}

# ---- 3) Migrate ----
if (-not $NoMigrate) {
    Write-Host "-> Checking for old state..."
    Migrate-OldState -Repo $Repo
} else {
    Write-Host "  (--no-migrate: skipping)"
}

Write-Host ""
Write-Host "[OK] WeWrite installation complete."
Write-Host "  State directory: $env:USERPROFILE\.wewrite"
