#!/usr/bin/env python3

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

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_non_fork(
        self, mock_run_check, mock_run, mock_subprocess
    ):
        """Test interactive mode on non-fork repo."""
        mock_run_check.return_value = False

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        # Should not call gh pr create (only 7 calls, not 8)
        assert mock_run.call_count == 7

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_fork(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test interactive mode on fork with correct URL format."""
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
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        # Capture output and verify URL format
        captured = capsys.readouterr()
        assert "PR creation URL:" in captured.out
        assert (
            "github.com/upstream/repo/compare/main...fork-owner:repo:" in captured.out
        )
        assert "?expand=1" in captured.out

        # Should not call gh pr create
        assert mock_run.call_count == 7

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_non_fork_url(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test interactive mode URL format for non-fork."""
        mock_run_check.return_value = False

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/user/myrepo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        # Verify URL format for non-fork
        captured = capsys.readouterr()
        assert "PR creation URL:" in captured.out
        assert "github.com/user/myrepo/compare/main...pr/" in captured.out
        assert "?expand=1" in captured.out

    def test_create_pr_merge_with_interactive_error(self):
        """Test that --merge with --interactive raises error."""
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", interactive=True, merge=True
            )
        assert exc.value.code == 1

    def test_create_pr_auto_merge_with_interactive_error(self):
        """Test that --auto-merge with --interactive raises error."""
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", interactive=True, auto_merge=True
            )
        assert exc.value.code == 1

    def test_create_pr_merge_and_auto_merge_together_error(self):
        """Test that --merge and --auto-merge together raises error."""
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", merge=True, auto_merge=True
            )
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test PR creation with immediate merge."""
        mock_run_check.return_value = False  # Has staged changes

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return success
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        acp.create_pr(
            "test commit", verbose=False, body="", merge=True, merge_method="squash"
        )

        # Verify subprocess.run was called for merge with squash
        merge_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0 and "merge" in str(call[0][0])
        ]
        assert len(merge_calls) > 0
        merge_call = merge_calls[0]
        assert "gh" in str(merge_call)
        assert "merge" in str(merge_call)
        assert "--squash" in str(merge_call)
        assert "--delete-branch" in str(merge_call)

        # Verify output message
        captured = capsys.readouterr()
        assert "merged!" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_auto_merge(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test PR creation with auto-merge enabled."""
        mock_run_check.return_value = False  # Has staged changes

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return success
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        acp.create_pr(
            "test commit",
            verbose=False,
            body="",
            auto_merge=True,
            merge_method="squash",
        )

        # Verify auto-merge was called with squash
        merge_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0 and "merge" in str(call[0][0])
        ]
        assert len(merge_calls) > 0
        merge_call = merge_calls[0]
        assert "gh" in str(merge_call)
        assert "merge" in str(merge_call)
        assert "--auto" in str(merge_call)
        assert "--squash" in str(merge_call)
        assert "--delete-branch" in str(merge_call)

        # Verify output message
        captured = capsys.readouterr()
        assert "will auto-merge when checks pass" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge_verbose(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test PR creation with merge in verbose mode."""
        mock_run_check.return_value = False  # Has staged changes

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return success
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        acp.create_pr(
            "test commit", verbose=True, body="", merge=True, merge_method="squash"
        )

        # Verify verbose output includes merge step with method
        captured = capsys.readouterr()
        assert "Merging PR immediately (method: squash)" in captured.out
        assert "merged!" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge_failure(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test PR creation when merge fails - should show PR created and error."""
        mock_run_check.return_value = False  # Has staged changes

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return failure
            elif "merge" in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="GraphQL: Merge commits are not allowed on this repository",
                )
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", merge=True, merge_method="squash"
            )

        assert exc.value.code == 1

        # Verify output shows PR was created and then error
        captured = capsys.readouterr()
        assert "PR created: https://github.com/user/repo/pull/1" in captured.out
        assert "Failed to merge PR" in captured.err
        assert "Merge commits are not allowed" in captured.err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_auto_merge_failure(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test PR creation when auto-merge fails - should show PR created and error."""
        mock_run_check.return_value = False  # Has staged changes

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return failure
            elif "merge" in str(cmd) and "--auto" in cmd:
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="auto-merge is not enabled for this repository",
                )
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            None,  # git commit
            None,  # git push
            "https://github.com/user/repo/pull/1",  # gh pr create
            None,  # git checkout original
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit",
                verbose=False,
                body="",
                auto_merge=True,
                merge_method="squash",
            )

        assert exc.value.code == 1

        # Verify output shows PR was created and then error
        captured = capsys.readouterr()
        assert "PR created: https://github.com/user/repo/pull/1" in captured.out
        assert "Failed to enable auto-merge" in captured.err
        assert "auto-merge is not enabled" in captured.err


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
                "test message",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
            )

    @mock.patch("acp.create_pr")
    def test_verbose_flag(self, mock_create_pr):
        """Test verbose flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "-v"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=True,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
            )

    @mock.patch("acp.create_pr")
    def test_merge_flag(self, mock_create_pr):
        """Test --merge flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "--merge"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=True,
                auto_merge=False,
                merge_method="squash",
            )

    @mock.patch("acp.create_pr")
    def test_auto_merge_flag(self, mock_create_pr):
        """Test --auto-merge flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "--auto-merge"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=True,
                merge_method="squash",
            )

    @mock.patch("acp.create_pr")
    def test_merge_method_flag(self, mock_create_pr):
        """Test --merge-method flag is passed."""
        with mock.patch.object(
            sys, "argv", ["acp", "pr", "test", "--merge", "--merge-method", "rebase"]
        ):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=True,
                auto_merge=False,
                merge_method="rebase",
            )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_method_merge(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test --merge with merge method."""
        mock_run_check.return_value = False

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            None,
            None,
            "https://github.com/user/repo/pull/1",
            None,
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="merge")

        # Verify --merge flag is used
        merge_calls = [
            c for c in mock_subprocess.call_args_list if "merge" in str(c[0][0])
        ]
        assert len(merge_calls) > 0
        assert "--merge" in str(merge_calls[0])

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_method_rebase(
        self, mock_run_check, mock_run, mock_subprocess, capsys
    ):
        """Test --merge with rebase method."""
        mock_run_check.return_value = False

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            None,
            None,
            "https://github.com/user/repo/pull/1",
            None,
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="rebase")

        # Verify --rebase flag is used
        merge_calls = [
            c for c in mock_subprocess.call_args_list if "merge" in str(c[0][0])
        ]
        assert len(merge_calls) > 0
        assert "--rebase" in str(merge_calls[0])

    def test_invalid_merge_method(self):
        """Test invalid merge method raises error."""
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test", verbose=False, body="", merge=True, merge_method="invalid"
            )
        assert exc.value.code == 1

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
