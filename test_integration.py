#!/usr/bin/env python3
"""Integration tests for acp that use real git/GitHub operations.

These tests require:
1. GITHUB_TOKEN environment variable set
2. Test GitHub organization with test repositories set up
3. Git configured with user name and email

Run with: pytest test_integration.py -v -m integration

To set up test repositories, see docs/INTEGRATION_TESTING.md

Note: These tests create real branches and PRs on GitHub test repositories.
They clean up after themselves, but may leave traces if interrupted.
"""

import os
import subprocess
import tempfile
import shutil
import pytest
import time
from pathlib import Path


# Check if integration tests should run
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
SKIP_INTEGRATION = not GITHUB_TOKEN

# Test repository configuration
# Set these environment variables or use defaults:
# - ACP_TEST_REPO_FULL: Full repo path (e.g., "vbvictor/acp-integrational-testing")
TEST_REPO_FULL = os.environ.get("ACP_TEST_REPO_FULL", "vbvictor/acp-integrational-testing")

# Split into owner and repo name
TEST_OWNER = TEST_REPO_FULL.split("/")[0]
TEST_REPO = TEST_REPO_FULL.split("/")[1]


@pytest.fixture
def temp_git_repo():
    """Create a temporary directory for git operations."""
    tmpdir = tempfile.mkdtemp(prefix="acp_integration_")
    original_dir = os.getcwd()

    # Ensure git is configured
    subprocess.run(
        ["git", "config", "--global", "user.name", "ACP Integration Test"],
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "--global", "user.email", "test@acp-integration.test"],
        capture_output=True
    )

    os.chdir(tmpdir)
    yield tmpdir

    # Cleanup
    os.chdir(original_dir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def acp_path():
    """Get absolute path to acp.py script."""
    return str(Path(__file__).parent.absolute() / "acp.py")


def cleanup_remote_branches(repo_path, branch_prefix="acp/"):
    """Delete all remote branches matching the prefix."""
    try:
        os.chdir(repo_path)
        # Fetch to get latest branches
        subprocess.run(["git", "fetch", "--prune"], capture_output=True)

        # Get all remote branches
        result = subprocess.run(
            ["git", "branch", "-r"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if branch_prefix in line and "origin/" in line:
                    branch_name = line.replace("origin/", "")
                    print(f"Cleaning up branch: {branch_name}")
                    subprocess.run(
                        ["git", "push", "origin", "--delete", branch_name],
                        capture_output=True
                    )
                    time.sleep(0.5)  # Rate limit
    except Exception as e:
        print(f"Cleanup warning: {e}")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
class TestIntegrationNonFork:
    """Integration tests for non-fork repositories."""

    def test_create_pr_interactive_non_fork(self, temp_git_repo, acp_path):
        """Test creating a PR in non-fork repo (interactive mode)."""
        # Clone test repo
        repo_url = f"https://{GITHUB_TOKEN}@github.com/{TEST_REPO_FULL}.git"
        result = subprocess.run(
            ["git", "clone", repo_url, "."],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Clone failed: {result.stderr}"

        # Make a test change
        test_file = Path("test_file.txt")
        test_content = f"Integration test - interactive - PID {os.getpid()}\n"
        test_file.write_text(test_content)
        subprocess.run(["git", "add", "test_file.txt"], check=True)

        # Run acp in interactive mode
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Interactive {os.getpid()}", "-i"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0, f"acp failed: {result.stderr}"
        assert "PR creation URL:" in result.stdout
        assert f"{TEST_OWNER}/{TEST_REPO}" in result.stdout

        # Verify branch was created on remote
        subprocess.run(["git", "fetch"], check=True)
        branches_result = subprocess.run(
            ["git", "branch", "-r"],
            capture_output=True,
            text=True,
            check=True
        )
        assert "acp/" in branches_result.stdout

        # Cleanup
        cleanup_remote_branches(temp_git_repo)

    def test_create_pr_non_fork(self, temp_git_repo, acp_path):
        """Test creating a PR in non-fork repo (auto-create with gh)."""
        # Clone test repo
        repo_url = f"https://{GITHUB_TOKEN}@github.com/{TEST_REPO_FULL}.git"
        result = subprocess.run(
            ["git", "clone", repo_url, "."],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Clone failed: {result.stderr}"

        # Make a test change
        test_file = Path("test_file.txt")
        test_content = f"Integration test - auto PR - PID {os.getpid()}\n"
        test_file.write_text(test_content)
        subprocess.run(["git", "add", "test_file.txt"], check=True)

        # Run acp (auto-create PR)
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Auto PR {os.getpid()}"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0, f"acp failed: {result.stderr}"
        assert "PR created:" in result.stdout

        # Extract PR URL
        pr_url = None
        for line in result.stdout.splitlines():
            if "PR created:" in line:
                pr_url = line.split("PR created:")[1].strip()
                break

        assert pr_url is not None
        assert f"github.com/{TEST_REPO_FULL}/pull/" in pr_url

        # Cleanup: Close the PR
        pr_number = pr_url.split("/")[-1]
        subprocess.run(
            ["gh", "pr", "close", pr_number, "-R", TEST_REPO_FULL],
            capture_output=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
        )

        # Cleanup branches
        cleanup_remote_branches(temp_git_repo)


# Fork tests - disabled for now, enable when you have fork setup
# @pytest.mark.integration
# @pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
# class TestIntegrationFork:
#     """Integration tests for fork repositories."""
#     pass


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
class TestIntegrationVerbose:
    """Integration tests for verbose output."""

    def test_verbose_output(self, temp_git_repo, acp_path):
        """Test that verbose mode shows expected output."""
        # Clone test repo
        repo_url = f"https://{GITHUB_TOKEN}@github.com/{TEST_REPO_FULL}.git"
        subprocess.run(
            ["git", "clone", repo_url, "."],
            capture_output=True,
            text=True,
            check=True
        )

        # Make a test change
        test_file = Path("test_file.txt")
        test_file.write_text(f"Verbose test - PID {os.getpid()}\n")
        subprocess.run(["git", "add", "test_file.txt"], check=True)

        # Run acp with verbose flag
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Verbose {os.getpid()}", "-v", "-i"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0
        # Check for verbose output indicators
        assert "Current branch:" in result.stdout
        assert "Creating temporary branch:" in result.stdout
        assert "Committing:" in result.stdout
        assert "Pushing branch" in result.stdout

        # Cleanup
        cleanup_remote_branches(temp_git_repo)


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
class TestIntegrationHooks:
    """Integration tests for git hooks."""

    def test_commit_with_hook(self, temp_git_repo, acp_path):
        """Test that commit hooks can run (non-interactive hooks)."""
        # Clone test repo
        repo_url = f"https://{GITHUB_TOKEN}@github.com/{TEST_REPO_FULL}.git"
        subprocess.run(
            ["git", "clone", repo_url, "."],
            capture_output=True,
            text=True,
            check=True
        )

        # Create a simple pre-commit hook
        hooks_dir = Path(".git/hooks")
        hooks_dir.mkdir(exist_ok=True)
        hook_file = hooks_dir / "pre-commit"
        hook_file.write_text(
            "#!/bin/sh\n"
            "# Non-interactive hook - just succeeds\n"
            "exit 0\n"
        )
        hook_file.chmod(0o755)

        # Make a test change
        test_file = Path("test_file.txt")
        test_file.write_text(f"Hook test - PID {os.getpid()}\n")
        subprocess.run(["git", "add", "test_file.txt"], check=True)

        # Run acp - hook should execute without issues
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Hook {os.getpid()}", "-i"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN}
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0, "acp should succeed with non-interactive hook"
        assert "PR creation URL:" in result.stdout

        # Cleanup
        cleanup_remote_branches(temp_git_repo)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
