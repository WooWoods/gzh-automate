#!/usr/bin/env python3
"""Cross-platform WeWrite installer.

Usage:
    python install.py              # Full install (CLI + skills + migrate)
    python install.py --no-cli     # Skip CLI installation
    python install.py --no-skills  # Skip skill registration

What it does:
    1. Installs the `wewrite` CLI via uv, pipx, or pip (venv fallback)
    2. Registers skills so Claude Code / Agent Skills / OpenClaw / Codex discover them
    3. Migrates old repo-root state to ~/.wewrite/ (if needed)

Works on Windows, macOS, and Linux. No shell dependency beyond Python 3.11+.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_home() -> Path:
    return Path.home()


def get_claude_skills_dir() -> Path:
    env = os.environ.get("CLAUDE_SKILLS_DIR", "")
    if env:
        return Path(env)
    return get_home() / ".claude" / "skills"


def get_agents_skills_dir() -> Path:
    env = os.environ.get("AGENTS_SKILLS_DIR", "")
    if env:
        return Path(env)
    return get_home() / ".agents" / "skills"


def find_extra_skill_targets() -> list[Path]:
    """Discover additional skill directories for OpenClaw, Codex, etc."""
    extra = []
    for name in ["openclaw", "codex"]:
        parent = get_home() / f".{name}"
        if parent.is_dir():
            skills_dir = parent / "skills"
            extra.append(skills_dir)
    return extra


def _remove_target(dest: Path) -> None:
    """Remove an existing symlink, junction, or directory at dest."""
    if not dest.exists() and not dest.is_symlink():
        return
    if dest.is_symlink():
        dest.unlink()
    elif dest.is_dir():
        # Windows: might be a junction. rmtree handles both regular dirs and junctions.
        shutil.rmtree(dest, ignore_errors=True)
    else:
        dest.unlink(missing_ok=True)


def _try_symlink(src: Path, dest: Path) -> bool:
    """Try to create a symlink. Returns True on success, False if platform denies it."""
    try:
        _remove_target(dest)
        dest.symlink_to(src.resolve())
        return True
    except OSError:
        return False


def register_skills(skills_src: Path, targets: list[Path]) -> int:
    """Register skill directories into target directories.

    Prefers symlinks (fast, updates propagate). Falls back to full directory
    copy on platforms that restrict symlink creation (Windows without
    Developer Mode, some CI environments).

    Args:
        skills_src: Path to the skills/ directory containing wewrite-* subdirs.
        targets: List of target directories to register skills into.

    Returns:
        Number of skills registered per target.
    """
    if not skills_src.is_dir():
        print(f"  (no skills/ directory at {skills_src}, skipping skill registration)")
        return 0

    skill_dirs = sorted(
        d for d in skills_src.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    )
    if not skill_dirs:
        print(f"  (no skill directories found in {skills_src})")
        return 0

    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        linked = 0
        for skill_dir in skill_dirs:
            dest = target / skill_dir.name
            if _try_symlink(skill_dir, dest):
                print(f"    ln: {skill_dir.name} -> {dest}")
            else:
                print(f"    cp: {skill_dir.name} -> {dest}  (symlink unavailable, copying)")
                _remove_target(dest)
                shutil.copytree(skill_dir, dest)
            linked += 1
        print(f"  ✓ {linked} skills registered to {target}")

    return len(skill_dirs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-platform WeWrite installer")
    parser.add_argument("--no-cli", action="store_true", help="Skip CLI installation")
    parser.add_argument("--no-skills", action="store_true", help="Skip skill registration")
    parser.add_argument("--no-migrate", action="store_true", help="Skip state migration")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent
    print(f"→ Installing WeWrite from {repo}")

    # ---- 1) Install wewrite CLI ----
    if not args.no_cli:
        print("→ Installing wewrite CLI...")
        install_cli(repo)
    else:
        print("  (--no-cli: skipping)")

    # ---- 2) Register skills ----
    if not args.no_skills:
        print("→ Registering skills...")
        skills_src = repo / "skills"
        targets = [
            get_claude_skills_dir(),
            get_agents_skills_dir(),
        ] + find_extra_skill_targets()
        register_skills(skills_src, targets)
    else:
        print("  (--no-skills: skipping)")

    # ---- 3) Migrate old state ----
    if not args.no_migrate:
        migrate_if_needed(repo)
    else:
        print("  (--no-migrate: skipping)")

    print("")
    print("✓ WeWrite installation complete.")
    print(f"  State directory: {get_home() / '.wewrite'}")


if __name__ == "__main__":
    main()
