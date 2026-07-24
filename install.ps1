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
        Write-Host "  ✓ $linked skills registered to $target"
    }
    return $skillDirs.Count
}

Write-Host "→ Installing WeWrite from $Repo"

# ---- 1) Install CLI ----
if (-not $NoCli) {
    Write-Host "→ Installing wewrite CLI..."
    # (Task 5 fills this in)
} else {
    Write-Host "  (--no-cli: skipping)"
}

# ---- 2) Register skills ----
if (-not $NoSkills) {
    Write-Host "→ Registering skills..."
    $skillsSrc = Join-Path $Repo "skills"
    $targets = @(Get-ClaudeSkillsDir, Get-AgentsSkillsDir) + (Get-ExtraSkillTargets)
    $null = Register-Skills -SkillsSrc $skillsSrc -Targets $targets
} else {
    Write-Host "  (--no-skills: skipping)"
}

# ---- 3) Migrate ----
if (-not $NoMigrate) {
    Write-Host "→ Checking for old state..."
    # (Task 6 fills this in)
} else {
    Write-Host "  (--no-migrate: skipping)"
}

Write-Host ""
Write-Host "✓ WeWrite installation complete."
Write-Host "  State directory: $env:USERPROFILE\.wewrite"
