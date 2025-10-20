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
            acp.create_pr("test commit", verbose=False)
        assert exc.value.code == 1

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_success(self, mock_run_check, mock_run):
        """Test successful PR creation."""
        mock_run_check.return_value = False  # Has staged changes

        # Mock all the run() calls in order
        mock_run.side_effect = [
            "main",  # get current branch
            "testuser",  # get gh username
            '{"nameWithOwner":"user/repo","parent":null}',  # gh repo view
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False)

        # Verify the PR was created
        assert mock_run.call_count == 8

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork(self, mock_run_check, mock_run):
        """Test PR creation on a fork."""
        mock_run_check.return_value = False

        repo_info = {
            "nameWithOwner": "user/repo",
            "parent": {"nameWithOwner": "upstream/repo"},
        }

        mock_run.side_effect = [
            "main",
            "testuser",
            json.dumps(repo_info),
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/upstream/repo/pull/1",
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False)

        # Check that PR was created to upstream repo
        calls = mock_run.call_args_list
        pr_create_call = calls[6]
        assert "upstream/repo" in pr_create_call[0][0]


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
            mock_create_pr.assert_called_once_with("test message", verbose=False, body="")

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
