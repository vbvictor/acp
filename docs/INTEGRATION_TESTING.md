# Integration Testing Guide

This document explains how to set up and run integration tests for `acp` using real GitHub repositories.

## Overview

Integration tests use real GitHub repositories and the GitHub CLI to test `acp` in realistic scenarios. These tests complement unit tests by catching issues that only appear with real git/GitHub operations.

## Prerequisites

1. **GitHub Account**: You need a GitHub account to create test repositories
2. **GitHub Token**: Personal access token with appropriate permissions
3. **Git & GitHub CLI**: Installed on your system
4. **Python 3.11+**: With pytest installed

## Setting Up Test Repositories

### Step 1: Create a Test Organization (Recommended)

Creating a dedicated organization keeps test repositories separate from your personal projects.

1. Go to https://github.com/settings/organizations
2. Click "New organization"
3. Choose "Create a free organization"
4. Name it (e.g., `acp-integration-test`)
5. Complete the setup

**Alternative**: You can use your personal account, but it's less organized.

### Step 2: Create Test Repositories

Create two repositories in your test organization:

#### Repository 1: `test-repo` (for non-fork scenarios)

```bash
gh repo create acp-integration-test/test-repo --public
cd /tmp
git clone https://github.com/acp-integration-test/test-repo.git
cd test-repo
echo "# Test Repository" > README.md
echo "test content" > test_file.txt
git add .
git commit -m "Initial commit"
git push
```

#### Repository 2: `upstream-repo` (for fork scenarios)

```bash
gh repo create acp-integration-test/upstream-repo --public
cd /tmp
git clone https://github.com/acp-integration-test/upstream-repo.git
cd upstream-repo
echo "# Upstream Repository" > README.md
echo "test content" > test_file.txt
git add .
git commit -m "Initial commit"
git push
```

### Step 3: Fork the Upstream Repository

Fork `upstream-repo` to your personal account (or another test account):

1. Go to https://github.com/acp-integration-test/upstream-repo
2. Click "Fork" in the top right
3. Select your personal account as the destination
4. This creates `your-username/upstream-repo`

## Configuration

### Environment Variables

Set these environment variables to configure the integration tests:

```bash
# Required
export GITHUB_TOKEN="your_personal_access_token"

# Optional (use these if your repos have different names)
export ACP_TEST_ORG="acp-integration-test"
export ACP_TEST_REPO="test-repo"
export ACP_TEST_UPSTREAM="upstream-repo"
export ACP_TEST_FORK_OWNER="your-username"
```

### Creating a GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token" → "Generate new token (classic)"
3. Give it a descriptive name: "ACP Integration Tests"
4. Select scopes:
   - `repo` (Full control of private repositories)
   - `workflow` (Update GitHub Action workflows)
5. Click "Generate token"
6. Copy the token immediately (you won't see it again!)
7. Store it securely in your environment:
   ```bash
   echo 'export GITHUB_TOKEN="ghp_your_token_here"' >> ~/.bashrc
   source ~/.bashrc
   ```

## Running Integration Tests

### Method 1: Local (Direct)

```bash
# From the acp repository root
export GITHUB_TOKEN="your_token"
pytest test_integration.py -v -m integration
```

### Method 2: Docker

```bash
# Build the Docker image
docker build -f docker/Dockerfile.integration -t acp-integration-test .

# Run tests
docker run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e ACP_TEST_ORG="your-org" \
  -e ACP_TEST_FORK_OWNER="your-username" \
  acp-integration-test
```

### Method 3: Docker Compose

```bash
# Make sure GITHUB_TOKEN is in your environment
export GITHUB_TOKEN="your_token"

# Run tests
docker-compose -f docker/docker-compose.integration.yml up --build

# Run specific test
docker-compose -f docker/docker-compose.integration.yml run --rm integration-test \
  pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive_non_fork -v
```

## CI/CD Setup (GitHub Actions)

### Step 1: Add Token as Secret

1. Go to your `acp` repository settings
2. Click "Secrets and variables" → "Actions"
3. Click "New repository secret"
4. Name: `INTEGRATION_TEST_TOKEN`
5. Value: Your GitHub token
6. Click "Add secret"

### Step 2: Enable Workflow

The workflow at `.github/workflows/integration-tests.yml` will automatically:
- Run on pushes to `main`
- Run on pull requests
- Can be manually triggered
- (Optional) Run on a schedule

To manually trigger:
1. Go to "Actions" tab in GitHub
2. Select "Integration Tests" workflow
3. Click "Run workflow"

## Test Structure

### Available Test Classes

1. **TestIntegrationNonFork**: Tests for non-fork repositories
   - `test_create_pr_interactive_non_fork`: Create PR in interactive mode
   - `test_create_pr_non_fork`: Create PR with automatic gh CLI

2. **TestIntegrationFork**: Tests for fork scenarios
   - `test_create_pr_fork_interactive`: Create PR from fork

3. **TestIntegrationVerbose**: Tests for verbose output
   - `test_verbose_output`: Verify verbose mode output

4. **TestIntegrationHooks**: Tests for git hooks
   - `test_commit_with_hook`: Test with pre-commit hook

### Running Specific Tests

```bash
# Run only non-fork tests
pytest test_integration.py::TestIntegrationNonFork -v -m integration

# Run single test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive_non_fork -v -m integration

# Run with output
pytest test_integration.py -v -m integration -s
```

## Cleanup

Integration tests attempt to clean up after themselves by:
- Deleting temporary branches
- Closing created PRs

However, if tests are interrupted, you may need to manually clean up:

```bash
# Delete all acp/* branches
gh api repos/acp-integration-test/test-repo/git/refs \
  | jq -r '.[] | select(.ref | contains("acp/")) | .ref' \
  | while read ref; do
      gh api -X DELETE "repos/acp-integration-test/test-repo/git/$ref"
    done

# Close all open PRs
gh pr list -R acp-integration-test/test-repo --state open \
  | grep "Integration Test" \
  | awk '{print $1}' \
  | xargs -I {} gh pr close {} -R acp-integration-test/test-repo
```

## Troubleshooting

### Tests Skip with "GITHUB_TOKEN not set"

**Solution**: Ensure `GITHUB_TOKEN` environment variable is set:
```bash
echo $GITHUB_TOKEN  # Should print your token
export GITHUB_TOKEN="your_token"
```

### Authentication Errors

**Solutions**:
1. Verify token has correct scopes (repo access)
2. Check token hasn't expired
3. Ensure gh CLI is authenticated: `gh auth status`
4. Login if needed: `gh auth login`

### Clone Fails

**Solutions**:
1. Verify repositories exist:
   ```bash
   gh repo view acp-integration-test/test-repo
   ```
2. Check repository names match environment variables
3. Ensure repositories are public or token has access

### Rate Limiting

GitHub API has rate limits. If you hit them:
1. Wait for the limit to reset (usually 1 hour)
2. Reduce test frequency
3. Use a token with higher rate limits

### Tests Leave Branches/PRs

If tests are interrupted:
1. Use cleanup commands above
2. Manually delete from GitHub UI
3. Reset test repositories:
   ```bash
   # Delete and recreate (destructive!)
   gh repo delete acp-integration-test/test-repo --yes
   gh repo create acp-integration-test/test-repo --public
   # Re-initialize...
   ```

## Best Practices

1. **Run locally first**: Test changes locally before CI
2. **Use test organization**: Keep test repos separate
3. **Monitor rate limits**: Don't run too frequently
4. **Keep repos clean**: Regularly cleanup old branches
5. **Secure your token**: Never commit tokens to git
6. **Use different tokens**: Separate token for CI vs local

## Adding New Tests

To add a new integration test:

1. Add test method to appropriate class in `test_integration.py`
2. Use the `@pytest.mark.integration` decorator
3. Use fixtures: `temp_git_repo` and `acp_path`
4. Clean up created resources
5. Test locally before committing

Example:
```python
@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
class TestMyNewFeature:
    def test_my_scenario(self, temp_git_repo, acp_path):
        # Clone repo
        # Make changes
        # Run acp
        # Assert results
        # Cleanup
        pass
```

## FAQ

**Q: Do I need to keep test repositories forever?**
A: Yes, tests use the same repositories repeatedly. Don't delete them.

**Q: Can I use private repositories?**
A: Yes, but ensure your token has access to private repos.

**Q: How often should I run integration tests?**
A: Locally before major changes. In CI on main branch pushes and releases.

**Q: What if I don't have a test organization?**
A: You can use your personal account by setting `ACP_TEST_ORG` to your username.

**Q: Can I run tests in parallel?**
A: Not recommended - they share the same test repositories and may conflict.

## Support

If you encounter issues:
1. Check this documentation
2. Review test output carefully
3. Check GitHub Actions logs
4. Open an issue with reproduction steps
