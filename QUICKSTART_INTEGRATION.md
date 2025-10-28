# Quick Start: Integration Tests

Simple guide to run integration tests with your test repository.

## Prerequisites

1. ✅ Test repository created: `vbvictor/acp-integrational-testing`
2. ✅ GitHub personal access token with `repo` scope
3. ✅ `gh` CLI installed and authenticated

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
# Run all integration tests
pytest -m integration -v

# Run specific test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive_non_fork -v -m integration

# Run with detailed output
pytest -m integration -v -s
```

## What the Tests Do

1. **test_create_pr_interactive_non_fork**:
   - Clones your test repo
   - Makes a change to `test_file.txt`
   - Runs `acp pr` in interactive mode (`-i`)
   - Verifies branch created
   - Cleans up the branch

2. **test_create_pr_non_fork**:
   - Clones your test repo
   - Makes a change
   - Runs `acp pr` to auto-create PR with `gh`
   - Verifies PR created
   - Closes the PR and cleans up

3. **test_verbose_output**:
   - Tests verbose mode (`-v` flag)
   - Verifies expected output messages

4. **test_commit_with_hook**:
   - Creates a pre-commit hook
   - Verifies it runs successfully

## Expected Output

```
test_integration.py::TestIntegrationNonFork::test_create_pr_interactive_non_fork PASSED
test_integration.py::TestIntegrationNonFork::test_create_pr_non_fork PASSED
test_integration.py::TestIntegrationVerbose::test_verbose_output PASSED
test_integration.py::TestIntegrationHooks::test_commit_with_hook PASSED

4 passed in 15.23s
```

## Troubleshooting

### "GITHUB_TOKEN not set"
```bash
echo $GITHUB_TOKEN  # Should print your token
export GITHUB_TOKEN="your_token"
```

### "Clone failed"
Make sure the repo exists:
```bash
gh repo view vbvictor/acp-integrational-testing
```

### Authentication errors
Re-authenticate:
```bash
gh auth login
gh auth status
```

### Tests leave branches
Clean up manually:
```bash
# List branches
gh api repos/vbvictor/acp-integrational-testing/git/refs | grep acp

# Delete a branch
gh api -X DELETE repos/vbvictor/acp-integrational-testing/git/refs/heads/acp/vbvictor/123456
```

## Using Different Repository

If you want to use a different test repository:

```bash
export ACP_TEST_REPO_FULL="your-username/your-test-repo"
pytest -m integration -v
```

## Next Steps

Once these tests pass:
1. ✅ Your `acp` tool works with real GitHub!
2. You can add more test scenarios
3. Later: set up fork testing (requires forking a repo)
4. Later: add CI/CD (GitHub Actions)

## Quick Commands

```bash
# Run tests
export GITHUB_TOKEN=$(gh auth token)
pytest -m integration -v

# Clean up all test branches
gh api repos/vbvictor/acp-integrational-testing/git/refs \
  | jq -r '.[] | select(.ref | contains("acp/")) | .ref' \
  | while read ref; do
      gh api -X DELETE "repos/vbvictor/acp-integrational-testing/git/$ref"
    done
```
