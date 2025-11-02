# Integration Testing Guide

This document explains how to run integration tests for `acp`.

## Overview

Integration tests run real git/GitHub operations on the current `acp` repository to test functionality in realistic scenarios. Tests complement unit tests by catching issues that only appear with real git/GitHub operations.

## Prerequisites

1. **GitHub Account & Token**: Personal access token with `repo` scope
2. **GitHub CLI**: `gh` CLI installed and authenticated
3. **Docker**: Docker installed on your system
4. **Git**: Configured with user name and email
5. **Python 3.11+**: With pytest installed

## Quick Start

### Option 1: With Makefile (Recommended)

```bash
# Set your GitHub token
export GITHUB_TOKEN=$(gh auth token)

# Run all tests (unit + integration)
make test-all

# Or just integration tests
# (First run unit tests with: make test)
```

### Option 2: Direct Docker

```bash
# Set your GitHub token
export GITHUB_TOKEN=$(gh auth token)

# Build Docker image
docker build -f docker/Dockerfile.integration -t acp-integration-test .

# Run tests
docker run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -v $(pwd):/app \
  acp-integration-test pytest test_integration.py -v -m integration
```

### Option 3: Local (Without Docker)

```bash
# Set your GitHub token
export GITHUB_TOKEN=$(gh auth token)

# Run integration tests
pytest test_integration.py -v -m integration
```

## Running Specific Tests

```bash
# Run only one test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive -v -m integration

# Run with full output
pytest test_integration.py -v -m integration -s
```

## Cleanup

Tests clean up after themselves automatically. If interrupted, clean up manually:

```bash
# Remove test artifacts
make clean

# Or manually delete test branches
git fetch --prune
git branch -r | grep 'origin/acp/' | sed 's|origin/||' | xargs -I {} git push origin --delete {}
```

## Troubleshooting

### "GITHUB_TOKEN not set"

```bash
export GITHUB_TOKEN=$(gh auth token)
```

### Authentication errors

```bash
gh auth status
gh auth login
```

### Git configuration missing

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## How Tests Work

Tests run on the current `acp` repository:

1. Create `test_integration_file.txt` in repo
2. Stage it with `git add`
3. Run `acp pr` command
4. Verify output and GitHub state
5. Clean up test file and remote branches

This approach is faster and simpler than using external test repositories.
