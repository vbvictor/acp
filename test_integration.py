#!/usr/bin/env python3
"""Integration tests for acp using the current repository.

These tests run directly in the acp repository by creating test branches
and testing acp functionality locally.

Requirements:
- GITHUB_TOKEN environment variable set
- Git configured with user name and email
- Remote "origin" points to a GitHub repository

Run with: pytest test_integration.py -v -m integration

Note: Tests create real branches and PRs on the remote repository.
They clean up after themselves, but may leave traces if interrupted.
"""

import os
import subprocess
import pytest
import time
from pathlib import Path


# Check if integration tests should run
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
SKIP_INTEGRATION = not GITHUB_TOKEN


@pytest.fixture
def repo_path():
    """Get the acp repository root."""
    return Path(__file__).parent.absolute()


@pytest.fixture
def acp_path():
    """Get absolute path to acp.py script."""
    return str(Path(__file__).parent.absolute() / "acp.py")


@pytest.fixture(autouse=True)
def setup_git_config():
    """Ensure git is configured."""
    subprocess.run(
        ["git", "config", "--global", "user.name", "ACP Integration Test"],
        capture_output=True
    )
    subprocess.run(
        ["git", "config", "--global", "user.email", "test@acp-integration.test"],
        capture_output=True
    )
    yield


def get_remote_url(repo_path):
    """Get the remote origin URL."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        cwd=repo_path
    )
    return result.stdout.strip() if result.returncode == 0 else None


def cleanup_test_branches(repo_path):
    """Delete all test branches starting with acp/."""
    try:
        os.chdir(repo_path)
        # Fetch latest
        subprocess.run(["git", "fetch", "--prune"], capture_output=True, timeout=10)

        # Get all remote branches
        result = subprocess.run(
            ["git", "branch", "-r"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if "acp/" in line and "origin/" in line:
                    branch_name = line.replace("origin/", "")
                    print(f"Cleaning up branch: {branch_name}")
                    subprocess.run(
                        ["git", "push", "origin", "--delete", branch_name],
                        capture_output=True,
                        timeout=10
                    )
                    time.sleep(0.5)  # Rate limit
    except Exception as e:
        print(f"Cleanup warning: {e}")


@pytest.mark.integration
@pytest.mark.skipif(SKIP_INTEGRATION, reason="GITHUB_TOKEN not set")
class TestIntegrationNonFork:
    """Integration tests for the acp repository itself."""

    def test_create_pr_interactive(self, repo_path, acp_path):
        """Test creating a PR in interactive mode on current repo."""
        os.chdir(repo_path)

        # Verify we're on main/master
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_path
        )
        current_branch = result.stdout.strip()
        print(f"Current branch: {current_branch}")

        # Make sure we're on a clean state
        subprocess.run(["git", "fetch"], capture_output=True, cwd=repo_path, timeout=10)

        # Create a test file with unique content
        test_file = repo_path / "test_integration_file.txt"
        test_content = f"Integration test content - {os.getpid()}\n"
        test_file.write_text(test_content)

        # Stage the change
        subprocess.run(
            ["git", "add", "test_integration_file.txt"],
            check=True,
            cwd=repo_path
        )

        # Run acp in interactive mode
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Interactive {os.getpid()}", "-i"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN},
            cwd=repo_path,
            timeout=60
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0, f"acp failed: {result.stderr}"
        assert "PR creation URL:" in result.stdout

        # Cleanup the test file locally
        test_file.unlink(missing_ok=True)
        subprocess.run(["git", "checkout", "test_integration_file.txt"],
                      capture_output=True, cwd=repo_path)

        # Cleanup remote branches
        cleanup_test_branches(repo_path)

    def test_create_pr_auto(self, repo_path, acp_path):
        """Test creating and auto-closing PR on current repo."""
        os.chdir(repo_path)

        # Fetch latest
        subprocess.run(["git", "fetch"], capture_output=True, cwd=repo_path, timeout=10)

        # Create a test file with unique content
        test_file = repo_path / "test_integration_file.txt"
        test_content = f"Integration test auto - {os.getpid()}\n"
        test_file.write_text(test_content)

        # Stage the change
        subprocess.run(
            ["git", "add", "test_integration_file.txt"],
            check=True,
            cwd=repo_path
        )

        # Run acp to auto-create PR
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Auto {os.getpid()}"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN},
            cwd=repo_path,
            timeout=60
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0, f"acp failed: {result.stderr}"
        assert "PR created:" in result.stdout

        # Extract PR number
        pr_number = None
        for line in result.stdout.splitlines():
            if "pull/" in line:
                pr_number = line.split("/pull/")[-1].strip()
                break

        assert pr_number is not None, "Could not find PR number in output"

        # Close the PR
        print(f"Closing PR #{pr_number}")
        subprocess.run(
            ["gh", "pr", "close", pr_number],
            capture_output=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN},
            cwd=repo_path,
            timeout=10
        )

        # Cleanup the test file locally
        test_file.unlink(missing_ok=True)
        subprocess.run(["git", "checkout", "test_integration_file.txt"],
                      capture_output=True, cwd=repo_path)

        # Cleanup remote branches
        cleanup_test_branches(repo_path)

    def test_verbose_mode(self, repo_path, acp_path):
        """Test verbose mode output."""
        os.chdir(repo_path)

        # Fetch latest
        subprocess.run(["git", "fetch"], capture_output=True, cwd=repo_path, timeout=10)

        # Create a test file
        test_file = repo_path / "test_integration_file.txt"
        test_content = f"Verbose test - {os.getpid()}\n"
        test_file.write_text(test_content)

        # Stage the change
        subprocess.run(
            ["git", "add", "test_integration_file.txt"],
            check=True,
            cwd=repo_path
        )

        # Run acp with verbose flag
        result = subprocess.run(
            ["python", acp_path, "pr", f"[Integration Test] Verbose {os.getpid()}", "-v", "-i"],
            capture_output=True,
            text=True,
            env={**os.environ, "GITHUB_TOKEN": GITHUB_TOKEN},
            cwd=repo_path,
            timeout=60
        )

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)

        assert result.returncode == 0
        # Check for verbose output
        assert "Current branch:" in result.stdout
        assert "Creating temporary branch:" in result.stdout
        assert "Committing:" in result.stdout
        assert "Pushing branch" in result.stdout

        # Cleanup
        test_file.unlink(missing_ok=True)
        subprocess.run(["git", "checkout", "test_integration_file.txt"],
                      capture_output=True, cwd=repo_path)
        cleanup_test_branches(repo_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
