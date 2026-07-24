# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

WeWrite is a Claude Code plugin for end-to-end WeChat Official Account (公众号) article creation — topic selection, writing, editorial review, optional AI illustration, themed formatting, and draft publishing. It's a **three-layer architecture**: prompt layer (10 self-contained skills in `skills/`), runtime layer (`wewrite` CLI Python package in `src/`), and state layer (`~/.wewrite/`, outside the repo). The skills are the primary interface users interact with; the CLI handles deterministic operations (scoring, HTML conversion, WeChat API, image generation).

Design principle: **prompt handles judgment, Python handles determinism.**

## Build / Test / Lint

```bash
# Install editable + test deps (cross-platform)
pip install -e . pytest

# On Windows, use install.ps1 or python install.py instead of install.sh

# Run all tests
python3 -m pytest tests/ -q

# Run a single test file
python3 -m pytest tests/test_converter.py -q

# Context budget guard (CI gate at 15500 tokens)
python3 scripts/context_budget.py --budget-tokens 15500

# Install the CLI (user-facing; not needed for dev)
bash install.sh
```

There is no linter or type checker configured. CI (`.github/workflows/checks.yml`) runs `pytest` + context budget guard on Python 3.11.

## Architecture

### Three layers

| Layer | Location | Purpose |
|-------|----------|---------|
| Prompt | `skills/` (10 skill dirs) | Topic curation, claims & evidence, writing, editorial judgment — each skill is self-contained with `SKILL.md` + `references/` |
| Runtime | `src/wewrite/` (pip package) | `wewrite` CLI: scoring, Markdown→WeChat HTML, WeChat API, image gen, cost routing |
| State | `~/.wewrite/` (`WEWRITE_HOME`) | Credentials, style, history, run artifacts, learned themes — never in repo |

### Skills (10 total)

- **`wewrite`** — main entry point; orchestrates the full pipeline and routes to optional post-completion actions
- **`wewrite-topic`** — hotspot discovery, topic scoring, dedup
- **`wewrite-write`** — article brief → claims & evidence → content enhancement → first draft (with 7 writing personas)
- **`wewrite-review`** — editorial judgment on 5 dimensions (accuracy, viewpoint, usefulness, voice, readability); revise-and-re-review loop
- **`wewrite-visual`** — cover image / full illustration (post-completion, never overwrites original article)
- **`wewrite-publish`** — Markdown→WeChat HTML formatting (18 themes), local preview, draft publishing with explicit permission gate
- **`wewrite-rewrite`** — multi-platform adaptation (Xiaohongshu, Douyin)
- **`wewrite-learn`** — style flywheel: learn from user edits, import exemplars
- **`wewrite-stats`** — WeChat analytics data feedback
- **`wewrite-style`** — persona onboarding and style configuration

Key contract: the main entry (`wewrite`) always calls `wewrite run start` to create a per-article run directory under `~/.wewrite/runs/<id>/`. Visuals, formatting, and publishing are **independent post-completion actions** — they don't auto-trigger and don't overwrite the original article. Publishing requires explicit permission (`wewrite run permission publish allow`).

### CLI package (`src/wewrite/`)

- **`cli.py`** — subcommand dispatcher; maps command name → module, no argument duplication
- **`commands/`** — one module per subcommand (17 commands: `diagnose`, `score`, `content-eval`, `hotspots`, `search-articles`, `seo`, `stats`, `learn-edits`, `learn-theme`, `exemplar`, `fetch-article`, `llm-write`, `similarity`, `run`, `sources`, `build-playbook`, `validate`)
- **`toolkit/`** — `cli.py` (preview/publish/gallery/themes/image-post subcommands), `converter.py` (Markdown→WeChat HTML with inline CSS, dark mode, WeChat compatibility fixes), `theme.py` (18 built-in YAML themes), `publisher.py`, `wechat_api.py`, `image_gen.py`
- **`paths.py`** — resolves `WEWRITE_HOME` (default `~/.wewrite/`)
- **`runs.py`**, **`sources.py`**, **`history.py`** — run lifecycle, source ledger, history management
- **`migrate.py`** — one-time migration from pre-v2.2 repo-root state

### Tests

- `test_converter.py` — Markdown→HTML conversion (the most complex deterministic logic)
- `test_skill_contracts.py` — skill SKILL.md content contracts (pipeline must use run-scoped state, visuals must be post-completion, writing must require source ledger, etc.)
- `test_workflow_contracts.py` — workflow-level invariants
- `test_readme_sync.py` — README ↔ skill docs consistency
- `test_context_budget.py` — verifies `scripts/context_budget.py` works

### Scripts

- `scripts/context_budget.py` — measures token load of a full pipeline run by summing SKILL.md + reference files loaded on the happy path; doubles as CI regression guard
- `scripts/gen_star_history.py` — generates star-history SVG chart

## Key design constraints

- Skills must not use repo-relative paths for output; all artifacts go to `~/.wewrite/runs/<id>/`
- Visual generation and publishing are never auto-triggered by the writing pipeline
- All 7 writing personas enforce `personal_material_policy: "only_current_user_supplied"` — no invented author experiences
- The editorial review loop is capped at **two rounds** (revise → re-review → pass or needs_input)
- Claims in `claims.yaml` distinguish fact/inference/opinion/user-experience, each with source status; model memory must never be marked `verified`
- The repo is NOT a git repository (no `.git` directory found)

## Cross-platform notes

- **Installation:** `python install.py` works on all platforms. `install.sh` is Unix-only; `install.ps1` is Windows-only.
- **Paths:** All state paths use `pathlib.Path.home()` which resolves correctly on each OS. `~/.wewrite/` maps to `C:\Users\<name>\.wewrite\` on Windows.
- **Symlinks:** Skill registration prefers symlinks but falls back to directory copy on Windows without Developer Mode. Re-run the installer after `git pull` to sync copied skills.
- **CLI tests:** `pytest tests/` and `python scripts/context_budget.py` work identically on all platforms.
