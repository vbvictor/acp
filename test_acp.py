#!/usr/bin/env python3

import json
import sys
from unittest import mock
import pytest

import acp


class TestRunCommand:
    """Test the run() function."""

    def test_run_success(self):
        """Test successful command execution."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="output", stderr="")
            result = acp.run(["echo", "test"], quiet=True)
            assert result == "output"

    def test_run_failure(self):
        """Test failed command execution."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error message"
            )
            with pytest.raises(SystemExit) as exc:
                acp.run(["false"])
            assert exc.value.code == 1


class TestRunCheck:
    """Test the run_check() function."""

    def test_run_check_success(self):
        """Test successful command check."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)
            assert acp.run_check(["true"]) is True

    def test_run_check_failure(self):
        """Test failed command check."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=1)
            assert acp.run_check(["false"]) is False


class TestCreatePR:
    """Test the create_pr() function."""

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_no_staged_changes(self, mock_run_check, mock_run):
        """Test PR creation fails when no staged changes."""
        mock_run.return_value = "main"
        mock_run_check.return_value = True  # No staged changes

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_fork_ssh(self, mock_run_check, mock_run, mock_subprocess):
        """Test PR creation in non-fork repo with SSH URL."""
        mock_run_check.return_value = False  # Has staged changes

        # Mock subprocess.run for upstream check (should fail - no upstream)
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        # Mock all the run() calls in order
        mock_run.side_effect = [
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify PR was created to same repo (not a fork)
        calls = mock_run.call_args_list
        pr_create_call = calls[6]
        # Should use --head branch (not owner:branch)
        assert "--head" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_fork_https(self, mock_run_check, mock_run, mock_subprocess):
        """Test PR creation in non-fork repo with HTTPS URL."""
        mock_run_check.return_value = False

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/user/repo.git",  # HTTPS origin URL
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",
            None,
        ]

        acp.create_pr("test commit", verbose=False, body="")
        assert mock_run.call_count == 8

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork_ssh(self, mock_run_check, mock_run, mock_subprocess):
        """Test PR creation on a fork with SSH URLs."""
        mock_run_check.return_value = False

        # Mock upstream remote exists
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@github.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork-owner/repo.git",  # origin (fork)
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/upstream/repo/pull/1",
            None,
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Check that PR was created with fork-owner:branch format
        calls = mock_run.call_args_list
        pr_create_call = calls[6]
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork_https(self, mock_run_check, mock_run, mock_subprocess):
        """Test PR creation on a fork with HTTPS URLs."""
        mock_run_check.return_value = False

        # Mock upstream remote exists
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="https://github.com/upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/fork-owner/repo.git",  # origin (fork)
            None,
            None,
            None,
            "https://github.com/upstream/repo/pull/1",
            None,
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify fork logic was used
        calls = mock_run.call_args_list
        pr_create_call = calls[6]
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_github(self, mock_run_check, mock_run):
        """Test PR creation fails for non-GitHub repos."""
        mock_run_check.return_value = False

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@gitlab.com:user/repo.git",  # Not GitHub
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_upstream_not_github(
        self, mock_run_check, mock_run, mock_subprocess
    ):
        """Test PR creation fails when upstream is not GitHub."""
        mock_run_check.return_value = False

        # Mock upstream remote exists but not GitHub
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@gitlab.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork/repo.git",  # origin is GitHub
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1


class TestMain:
    """Test the main() function."""

    def test_help_flag(self, capsys):
        """Test -h flag shows help."""
        with mock.patch.object(sys, "argv", ["acp", "-h"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_no_args(self, capsys):
        """Test no arguments shows help."""
        with mock.patch.object(sys, "argv", ["acp"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_invalid_command(self, capsys):
        """Test invalid command shows help."""
        with mock.patch.object(sys, "argv", ["acp", "invalid", "message"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "usage:" in captured.out

    @mock.patch("acp.create_pr")
    @mock.patch("acp.run_check")
    def test_valid_pr_command(self, mock_run_check, mock_create_pr):
        """Test valid pr command."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test message"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test message", verbose=False, body=""
            )

    @mock.patch("acp.create_pr")
    def test_verbose_flag(self, mock_create_pr):
        """Test verbose flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "-v"]):
            acp.main()
            mock_create_pr.assert_called_once_with("test", verbose=True, body="")

    @mock.patch("acp.create_pr")
    def test_keyboard_interrupt(self, mock_create_pr):
        """Test keyboard interrupt handling."""
        mock_create_pr.side_effect = KeyboardInterrupt()

        with mock.patch.object(sys, "argv", ["acp", "pr", "test"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 130


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
