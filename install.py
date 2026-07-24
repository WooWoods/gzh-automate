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
        print(f"  [OK] {linked} skills registered to {target}")

    return len(skill_dirs)


def install_cli(repo: Path) -> None:
    """Install the wewrite CLI package.

    Tries in order: uv, pipx, pip. On all platforms, uv and pipx
    install into isolated environments and link the entry point onto PATH.
    The pip fallback installs into the current Python environment.
    """
    if not (repo / "pyproject.toml").exists():
        print("  (no pyproject.toml at repo root — installing from PyPI)")
        _install_from_pypi()
        return

    if shutil.which("uv"):
        subprocess.run(
            ["uv", "tool", "install", "--force", str(repo)],
            check=True,
        )
        print(f"  [OK] installed via uv")
        return

    if shutil.which("pipx"):
        subprocess.run(
            ["pipx", "install", "--force", str(repo)],
            check=True,
        )
        print(f"  [OK] installed via pipx")
        return

    # Fallback: pip install --editable into venv or current environment
    print("  (no uv/pipx found, installing via pip)")
    _install_via_pip(repo)


def _install_via_pip(repo: Path) -> None:
    """Install via pip, creating a venv if not already in one."""
    # If we're already in a venv, just pip install -e
    if sys.prefix != sys.base_prefix:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "-e", str(repo)],
            check=True,
        )
        _check_wewrite_on_path(repo)
        return

    # Not in a venv — create one
    venv_dir = repo / ".venv"
    if not venv_dir.is_dir():
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    # Platform-aware venv paths
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_wewrite = venv_dir / "Scripts" / "wewrite.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
        venv_wewrite = venv_dir / "bin" / "wewrite"

    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(venv_python), "-m", "pip", "install", "--quiet", "-e", str(repo)],
        check=True,
    )

    # Link wewrite into ~/.local/bin (Unix) or print PATH warning (Windows)
    if os.name == "nt":
        # On Windows, add a PowerShell profile PATH entry or just warn
        user_bin = get_home() / "AppData" / "Local" / "Microsoft" / "WindowsApps"
        print(f"  [WARN] wewrite installed to venv. Add to PATH or use full path:")
        print(f"    {venv_wewrite}")
    else:
        local_bin = get_home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        link_path = local_bin / "wewrite"
        _remove_target(link_path)
        try:
            link_path.symlink_to(venv_wewrite.resolve())
        except OSError:
            shutil.copy(venv_wewrite, link_path)
        print(f"  [OK] linked {link_path}")
        _warn_if_not_on_path(local_bin)


def _install_from_pypi() -> None:
    """Install wewrite from PyPI (for dist copies without pyproject.toml)."""
    if shutil.which("uv"):
        subprocess.run(["uv", "tool", "install", "--force", "wewrite"], check=True)
    elif shutil.which("pipx"):
        subprocess.run(["pipx", "install", "--force", "wewrite"], check=True)
    else:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "wewrite"],
            check=True,
        )


def _check_wewrite_on_path(repo: Path) -> None:
    """Check if wewrite is on PATH; warn if not."""
    if shutil.which("wewrite"):
        print(f"  [OK] wewrite CLI ready: {shutil.which('wewrite')}")
    else:
        print(f"  [WARN] wewrite not found on current PATH — restart terminal or check PATH")


def _warn_if_not_on_path(bin_dir: Path) -> None:
    """Warn if a bin directory is not on PATH."""
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if str(bin_dir) not in path_dirs:
        print(f"  [WARN] {bin_dir} is not on PATH. Add it to use 'wewrite' directly.")


def migrate_if_needed(repo: Path) -> None:
    """Detect pre-v2.2 repo-root state files and migrate to ~/.wewrite/."""
    old_state_files = [
        repo / "style.yaml",
        repo / "history.yaml",
        repo / "config.yaml",
    ]
    has_old_state = any(f.exists() for f in old_state_files)

    if not has_old_state:
        return

    # Check if wewrite CLI is available for migration
    if not shutil.which("wewrite"):
        print("  [WARN] Old state files found but wewrite CLI not on PATH.")
        print(f"    Manually move to {get_home() / '.wewrite'} or re-run after CLI is available.")
        return

    print("-> Detected old repo-root state files. Migrating...")
    try:
        result = subprocess.run(
            ["wewrite", "migrate", "--from", str(repo)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("  [OK] State migrated successfully")
        else:
            print(f"  [WARN] Migration reported issues:\n{result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"  [WARN] Migration failed: {e}")
    except FileNotFoundError:
        print("  [WARN] wewrite CLI not available, skipping migration")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-platform WeWrite installer")
    parser.add_argument("--no-cli", action="store_true", help="Skip CLI installation")
    parser.add_argument("--no-skills", action="store_true", help="Skip skill registration")
    parser.add_argument("--no-migrate", action="store_true", help="Skip state migration")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parent
    print(f"-> Installing WeWrite from {repo}")

    # ---- 1) Install wewrite CLI ----
    if not args.no_cli:
        print("-> Installing wewrite CLI...")
        install_cli(repo)
    else:
        print("  (--no-cli: skipping)")

    # ---- 2) Register skills ----
    if not args.no_skills:
        print("-> Registering skills...")
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
    print("[OK] WeWrite installation complete.")
    print(f"  State directory: {get_home() / '.wewrite'}")


if __name__ == "__main__":
    main()
