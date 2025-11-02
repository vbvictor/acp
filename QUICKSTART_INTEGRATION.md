# Quick Start: Integration Tests (Local)

Simple guide to run integration tests on the acp repository itself.

## Prerequisites

1. ✅ GitHub personal access token with `repo` scope
2. ✅ `gh` CLI installed and authenticated
3. ✅ Repository has "origin" remote pointing to GitHub

## Step 1: Authenticate GitHub CLI

```bash
gh auth login
# Follow prompts to authenticate
```

## Step 2: Set Your GitHub Token

```bash
export GITHUB_TOKEN=$(gh auth token)
```

Or use your personal token directly:
```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

## Step 3: Run Integration Tests

```bash
# From the acp repository root
cd /home/victor/repos/acp

# Run all integration tests
pytest -m integration -v

# Run specific test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive -v -m integration

# Run with detailed output
pytest -m integration -v -s
```

## What the Tests Do

1. **test_create_pr_interactive**:
   - Creates `test_integration_file.txt`
   - Runs `acp pr` in interactive mode (`-i`)
   - Verifies branch created on remote
   - Cleans up the test file and branch

2. **test_create_pr_auto**:
   - Creates `test_integration_file.txt`
   - Runs `acp pr` to auto-create PR with `gh`
   - Verifies PR created
   - Closes the PR
   - Cleans up

3. **test_verbose_mode**:
   - Tests verbose mode (`-v` flag)
   - Verifies expected output messages

## Expected Output

```
test_integration.py::TestIntegrationNonFork::test_create_pr_interactive PASSED
test_integration.py::TestIntegrationNonFork::test_create_pr_auto PASSED
test_integration.py::TestIntegrationNonFork::test_verbose_mode PASSED

======================== 3 passed in 45.23s ========================
```

## What Happens

Each test:
1. Creates a `test_integration_file.txt` in the repo
2. Stages the file with git
3. Runs the acp command
4. Verifies the output
5. Cleans up:
   - Deletes the test file locally
   - Deletes the temporary branch from remote
   - Closes any created PRs

## Troubleshooting

### "GITHUB_TOKEN not set"
```bash
echo $GITHUB_TOKEN  # Should print your token
export GITHUB_TOKEN=$(gh auth token)
```

### "gh" not authenticated
```bash
gh auth login
gh auth status
```

### Tests fail with "origin not found"
Ensure your repository has an "origin" remote:
```bash
git remote -v
# Should show: origin  git@github.com:yourname/acp.git
```

### Tests leave branches
Clean up manually:
```bash
# List branches
git branch -r | grep acp/

# Delete a specific branch
git push origin --delete acp/vbvictor/123456789
```

### PR doesn't get created
Check that you can create PRs manually:
```bash
gh pr create --help
```

## Quick Commands

```bash
# Setup
export GITHUB_TOKEN=$(gh auth token)
cd /home/victor/repos/acp

# Run tests
pytest -m integration -v

# Run one test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive -v

# Cleanup all test branches
git fetch --prune
git branch -r | grep 'origin/acp/' | sed 's|origin/||' | xargs -I {} git push origin --delete {}
```

## Next Steps

Once these tests pass:
1. ✅ Your `acp` tool works with real git/GitHub!
2. You can add more test scenarios
3. Later: add fork testing
4. Later: add CI/CD (GitHub Actions)

## Important Notes

- Tests actually modify GitHub (create branches/PRs)
- Tests clean up after themselves
- If interrupted, branches may remain
- Each test takes 10-20 seconds
- Don't run multiple tests in parallel (they share the same repo)
