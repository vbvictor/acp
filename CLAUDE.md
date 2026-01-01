# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

ACP (Automatic Commit Pusher) is a Python CLI tool that creates GitHub pull
requests from staged changes in a single command. It handles branch creation,
committing, pushing, and PR creation automatically.

**Requirements**: Python 3.9+, Git CLI, GitHub CLI (`gh`)

## Common Commands

```bash
# Run tests
pytest test_acp.py -v
make test

# Run single test
pytest test_acp.py::TestClassName::test_method_name -v

# Run with coverage
pytest test_acp.py --cov=acp --cov-report=term-missing

# Clean test artifacts
make clean

# Install for development
pip install -e ".[dev]"

# Linting (checked in CI)
ruff check acp.py test_acp.py
black acp.py test_acp.py
```

## Architecture

The codebase is a single-file CLI tool (`acp.py`) with tests (`test_acp.py`).

### Core Flow (`create_pr()` function)

1. Validate staged changes exist
2. Generate temporary branch: `acp/{username}/{random-16-digits}`
3. Checkout temp branch, commit (interactive for git hooks), push
4. Switch back to original branch, restore any unstaged changes
5. Create PR via `gh pr create`
6. Optionally merge and cleanup branches

### Key Functions in acp.py

- `run()` / `run_check()` / `run_interactive()` - Command execution
- `parse_github_url()` - Extract owner/repo from git remote URLs
- `get_repo_info()` - Detect fork status and determine upstream/origin
- `create_github_pr()` - PR creation via GitHub CLI
- `merge_pr()` / `enable_auto_merge()` - Post-creation merge handling
- `cleanup_branches_after_merge()` - Remove temporary branches after merge

### Fork Handling

The tool automatically detects fork vs non-fork repos and adjusts PR target.

## CI Workflows

All workflows in `.github/workflows/`:

- **tests.yaml** - pytest across Python 3.9-3.13
- **code-lint.yaml** - Ruff linting
- **code-format.yaml** - Black formatting check

## Release Process

Use `python tools/release.py <version>` to:

- Update version in pyproject.toml, acp.py, README.md
- Create release commit and tag
- Trigger GitHub Actions release workflow
