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
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_fork_ssh(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation in non-fork repo with SSH URL."""
        # First call: has staged changes (False = has changes)
        # Second call: no unstaged changes (True = no unstaged changes)
        mock_run_check.side_effect = [False, True]

        # Mock subprocess.run for upstream check (should fail - no upstream)
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        # Mock all the run() calls in order
        mock_run.side_effect = [
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify PR was created to same repo (not a fork)
        calls = mock_run.call_args_list
        pr_create_call = calls[
            5
        ]  # Updated index after removing git commit and git push from run() calls
        # Should use --head branch (not owner:branch)
        assert "--head" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_fork_https(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation in non-fork repo with HTTPS URL."""
        # First call: has staged changes (False = has changes)
        # Second call: no unstaged changes (True = no unstaged changes)
        mock_run_check.side_effect = [False, True]

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/user/repo.git",  # HTTPS origin URL
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")
        assert mock_run.call_count == 6

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork_ssh(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation on a fork with SSH URLs."""
        mock_run_check.side_effect = [False, True]

        # Mock upstream remote exists
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@github.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork-owner/repo.git",  # origin (fork)
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/upstream/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Check that PR was created with fork-owner:branch format
        calls = mock_run.call_args_list
        pr_create_call = calls[
            5
        ]  # Updated index after removing git commit and git push from run() calls
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork_https(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation on a fork with HTTPS URLs."""
        mock_run_check.side_effect = [False, True]

        # Mock upstream remote exists
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="https://github.com/upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/fork-owner/repo.git",  # origin (fork)
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/upstream/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify fork logic was used
        calls = mock_run.call_args_list
        pr_create_call = calls[
            5
        ]  # Updated index after removing git commit and git push from run() calls
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_github(self, mock_run_check, mock_run):
        """Test PR creation fails for non-GitHub repos."""
        mock_run_check.side_effect = [False, True]

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@gitlab.com:user/repo.git",  # Not GitHub
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_upstream_not_github(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation fails when upstream is not GitHub."""
        mock_run_check.side_effect = [False, True]

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
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_non_fork(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test interactive mode on non-fork repo."""
        mock_run_check.side_effect = [False, True]

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        # Should not call gh pr create (only 5 calls, not 6)
        assert mock_run.call_count == 5

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_fork(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test interactive mode on fork with correct URL format."""
        mock_run_check.side_effect = [False, True]

        # Mock upstream remote exists
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@github.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork-owner/repo.git",  # origin (fork)
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        # Capture output and verify URL format
        captured = capsys.readouterr()
        assert "PR creation URL:" in captured.out
        # For forks, URL should use fork repo (fork-owner/repo), not upstream
        assert "github.com/fork-owner/repo/pull/new/acp/" in captured.out

        # Should not call gh pr create
        assert mock_run.call_count == 5

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_non_fork_url(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test interactive mode URL format for non-fork."""
        mock_run_check.side_effect = [False, True]

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
        assert "github.com/user/myrepo/pull/new/acp/" in captured.out

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
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation with immediate merge."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

        api_check_count = {"count": 0}

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return success
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Branch existence check via API - return success first, then 404
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                api_check_count["count"] += 1
                if api_check_count["count"] == 1:
                    # First check: branch exists (for deletion)
                    return mock.Mock(
                        returncode=0,
                        stdout='{"ref": "refs/heads/acp/testuser/123"}',
                        stderr="",
                    )
                else:
                    # Second check: branch is gone (for local cleanup check)
                    return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            # Branch deletion via API - return success
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Local branch check (git rev-parse --verify)
            elif "rev-parse" in str(cmd) and "--verify" in str(cmd):
                # First check: local branch exists
                # Second check: remote tracking branch exists
                if "origin/" in str(cmd):
                    return mock.Mock(returncode=0, stdout="abc123", stderr="")
                else:
                    return mock.Mock(returncode=0, stdout="abc123", stderr="")
            # Local branch deletion (git branch -D)
            elif "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            # Remote tracking branch deletion (git branch -rd)
            elif "branch" in str(cmd) and "-rd" in str(cmd):
                return mock.Mock(
                    returncode=0, stdout="Deleted remote-tracking branch", stderr=""
                )
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr(
            "test commit", verbose=False, body="", merge=True, merge_method="squash"
        )

        # Verify subprocess.run was called for merge with squash (no --delete-branch)
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
        assert "--delete-branch" not in str(merge_call)

        # Verify branch existence check API call was made
        check_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "api" in str(call[0][0])
            and "DELETE" not in str(call[0])
            and "refs/heads/" in str(call[0])
        ]
        assert len(check_calls) > 0

        # Verify branch deletion API call was made
        delete_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "api" in str(call[0][0])
            and "DELETE" in str(call[0])
        ]
        assert len(delete_calls) > 0

        # Verify output message includes PR link
        captured = capsys.readouterr()
        assert 'PR "test commit"' in captured.out
        assert "https://github.com/user/repo/pull/1" in captured.out
        assert "merged!" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_auto_merge(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation with auto-merge enabled."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

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
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr(
            "test commit",
            verbose=False,
            body="",
            auto_merge=True,
            merge_method="squash",
        )

        # Verify auto-merge was called with squash (no --delete-branch)
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
        assert "--delete-branch" not in str(merge_call)

        # Verify output message includes PR link
        captured = capsys.readouterr()
        assert 'PR "test commit"' in captured.out
        assert "https://github.com/user/repo/pull/1" in captured.out
        assert "will auto-merge when checks pass" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge_verbose(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation with merge in verbose mode."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

        api_check_count = {"count": 0}

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command - return success
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Branch existence check via API - return success first, then 404
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                api_check_count["count"] += 1
                if api_check_count["count"] == 1:
                    return mock.Mock(
                        returncode=0,
                        stdout='{"ref": "refs/heads/acp/testuser/123"}',
                        stderr="",
                    )
                else:
                    return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            # Branch deletion via API - return success
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Local branch check (git rev-parse --verify)
            elif "rev-parse" in str(cmd) and "--verify" in str(cmd):
                # First check: local branch exists
                # Second check: remote tracking branch exists
                if "origin/" in str(cmd):
                    return mock.Mock(returncode=0, stdout="abc123", stderr="")
                else:
                    return mock.Mock(returncode=0, stdout="abc123", stderr="")
            # Local branch deletion (git branch -D)
            elif "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            # Remote tracking branch deletion (git branch -rd)
            elif "branch" in str(cmd) and "-rd" in str(cmd):
                return mock.Mock(
                    returncode=0, stdout="Deleted remote-tracking branch", stderr=""
                )
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr(
            "test commit", verbose=True, body="", merge=True, merge_method="squash"
        )

        # Verify verbose output includes merge step with method and PR link
        captured = capsys.readouterr()
        assert 'Committing: "test commit"' in captured.out
        assert "Pushing branch" in captured.out
        assert "Creating PR to: 'user/repo'..." in captured.out
        assert "PR created: https://github.com/user/repo/pull/1" in captured.out
        assert "Merging PR immediately (method: squash)" in captured.out
        assert 'PR "test commit"' in captured.out
        assert "merged!" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_merge_failure(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation when merge fails - should show PR created and error."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

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
            # Branch deletion shouldn't be called if merge fails
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
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
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_auto_merge_failure(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation when auto-merge fails - should show PR created and error."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

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
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original (moved before PR creation)
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit",
                verbose=False,
                body="",
                auto_merge=True,
                merge_method="squash",
                sync=False,
            )

        assert exc.value.code == 1

        # Verify output shows PR was created and then error
        captured = capsys.readouterr()
        assert "PR created: https://github.com/user/repo/pull/1" in captured.out
        assert "Failed to enable auto-merge" in captured.err
        assert "auto-merge is not enabled" in captured.err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_reviewers(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation with reviewers."""
        mock_run_check.side_effect = [False, True]

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr(
            "test commit", verbose=False, body="", reviewers="vbvictor,octodad"
        )

        # Verify PR was created with reviewers
        calls = mock_run.call_args_list
        pr_create_call = calls[5]  # gh pr create call
        assert "--reviewer" in str(pr_create_call)
        assert "vbvictor,octodad" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_without_reviewers(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation without reviewers (default behavior)."""
        mock_run_check.side_effect = [False, True]

        # No upstream remote
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",  # current branch
            "testuser",  # gh username
            "git@github.com:user/repo.git",  # origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify PR was created without reviewers
        calls = mock_run.call_args_list
        pr_create_call = calls[5]  # gh pr create call
        assert "--reviewer" not in str(pr_create_call)


class TestAddFlag:
    """Test the --add flag functionality."""

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_calls_git_add(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test that --add flag calls 'git add .' before checking staged changes."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            None,  # git add .
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="", add=True)

        # Verify git add . was called first
        calls = mock_run.call_args_list
        assert calls[0] == mock.call(["git", "add", "."], quiet=True)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_verbose_output(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test that --add flag shows verbose output when verbose=True."""
        mock_run_check.side_effect = [False, True]  # Has staged changes

        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            None,  # git add .
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=True, body="", add=True)

        captured = capsys.readouterr()
        assert "Adding all changes with 'git add .'" in captured.out

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_not_called_when_false(self, mock_run_check, mock_run):
        """Test that git add . is not called when add=False."""
        mock_run.return_value = "main"
        mock_run_check.return_value = True  # No staged changes

        with pytest.raises(SystemExit):
            acp.create_pr("test commit", verbose=False, body="", add=False)

        # Verify git add . was NOT called
        calls = mock_run.call_args_list
        git_add_calls = [
            c for c in calls if c == mock.call(["git", "add", "."], quiet=True)
        ]
        assert len(git_add_calls) == 0


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
                sync=False,
                add=False,
                reviewers=None,
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
                sync=False,
                add=False,
                reviewers=None,
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
                sync=False,
                add=False,
                reviewers=None,
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
                sync=False,
                add=False,
                reviewers=None,
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
                sync=False,
                add=False,
                reviewers=None,
            )

    @mock.patch("acp.create_pr")
    def test_add_flag(self, mock_create_pr):
        """Test --add flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "--add"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
                sync=False,
                add=True,
                reviewers=None,
            )

    @mock.patch("acp.create_pr")
    def test_add_flag_short(self, mock_create_pr):
        """Test -a flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "-a"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
                sync=False,
                add=True,
                reviewers=None,
            )

    @mock.patch("acp.create_pr")
    def test_reviewers_flag(self, mock_create_pr):
        """Test --reviewers flag is passed."""
        with mock.patch.object(
            sys, "argv", ["acp", "pr", "test", "--reviewers", "vbvictor,octodad"]
        ):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
                sync=False,
                add=False,
                reviewers="vbvictor,octodad",
            )

    @mock.patch("acp.create_pr")
    def test_reviewers_flag_short(self, mock_create_pr):
        """Test -r flag is passed."""
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "-r", "user1"]):
            acp.main()
            mock_create_pr.assert_called_once_with(
                "test",
                verbose=False,
                body="",
                interactive=False,
                merge=False,
                auto_merge=False,
                merge_method="squash",
                sync=False,
                add=False,
                reviewers="user1",
            )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_method_merge(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test --merge with merge method."""
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout='{"ref": "refs/heads/acp/testuser/123"}',
                    stderr="",
                )
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="merge")

        # Verify --merge flag is used
        merge_calls = [
            c for c in mock_subprocess.call_args_list if "merge" in str(c[0][0])
        ]
        assert len(merge_calls) > 0
        assert "--merge" in str(merge_calls[0])

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_method_rebase(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test --merge with rebase method."""
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout='{"ref": "refs/heads/acp/testuser/123"}',
                    stderr="",
                )
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,
            "https://github.com/user/repo/pull/1",
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

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_unstaged_changes(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        """Test PR creation with unstaged changes stashes and restores them."""
        # First call: has staged changes (False = has changes)
        # Second call: has unstaged changes (False = has unstaged changes)
        mock_run_check.side_effect = [False, False]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Stash pop - return success
            elif "stash" in str(cmd) and "pop" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git stash push
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify stash push was called with unique ID
        stash_push_calls = [
            call
            for call in mock_run.call_args_list
            if len(call[0]) > 0
            and "stash" in str(call[0][0])
            and "push" in str(call[0][0])
        ]
        assert len(stash_push_calls) == 1
        # Verify the stash message contains acp-stash prefix
        assert "acp-stash-" in str(stash_push_calls[0])

        # Verify stash pop was called via subprocess.run
        stash_pop_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "stash" in str(call[0][0])
            and "pop" in str(call[0][0])
        ]
        assert len(stash_pop_calls) == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_unstaged_changes_conflict(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test PR creation with unstaged changes that conflict on stash pop."""
        # First call: has staged changes (False = has changes)
        # Second call: has unstaged changes (False = has unstaged changes)
        mock_run_check.side_effect = [False, False]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            # Upstream check - return error (no upstream)
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Stash pop - return failure (conflict)
            elif "stash" in str(cmd) and "pop" in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="CONFLICT (content): Merge conflict in file.txt",
                )
            # Default
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",  # get current branch
            "testuser",  # get gh username
            "git@github.com:user/repo.git",  # git remote get-url origin
            None,  # git checkout -b
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,  # git stash push
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",  # gh pr create
        ]

        acp.create_pr("test commit", verbose=False, body="")

        # Verify warning message was printed
        captured = capsys.readouterr()
        assert "Failed to automatically restore stashed changes" in captured.err
        assert "acp-stash-" in captured.err
        assert "git stash apply" in captured.err
        assert "git stash drop" in captured.err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_with_branch_already_deleted(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test merge succeeds when branch check shows it's already deleted by GitHub."""
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command succeeds
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Branch existence check returns 404 (already deleted)
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr='{\n  "message": "Reference does not exist",\n  "documentation_url": "https://docs.github.com/rest/git/refs#get-a-reference"\n}',
                )
            # Branch deletion should not be called
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                # This shouldn't be reached, but return success if it is
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="squash")

        # Should succeed and show merged message
        captured = capsys.readouterr()
        assert 'PR "test"' in captured.out
        assert "merged!" in captured.out
        assert "Error" not in captured.err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_with_http_404_only(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        """Test merge succeeds when branch check returns HTTP 404."""
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            # Merge command succeeds
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            # Branch existence check returns 404
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="gh: Not Found (HTTP 404)",
                )
            # Branch deletion should not be called
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                # This shouldn't be reached, but return success if it is
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,
            # git commit now uses run_interactive, not run
            # git push now uses run_interactive, not run
            None,
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="squash")

        # Should succeed and show merged message
        captured = capsys.readouterr()
        assert 'PR "test"' in captured.out
        assert "merged!" in captured.out
        assert "Error" not in captured.err

    @mock.patch("acp.create_pr")
    def test_keyboard_interrupt(self, mock_create_pr):
        """Test keyboard interrupt handling."""
        mock_create_pr.side_effect = KeyboardInterrupt()

        with mock.patch.object(sys, "argv", ["acp", "pr", "test"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 130


class TestStripBranchPrefix:
    """Test the strip_branch_prefix() function."""

    def test_strip_prefix_with_colon(self):
        """Test stripping username prefix from branch name."""
        assert (
            acp.strip_branch_prefix("vbvictor:acp/vbvictor/1234") == "acp/vbvictor/1234"
        )

    def test_strip_prefix_without_colon(self):
        """Test branch name without prefix is unchanged."""
        assert acp.strip_branch_prefix("acp/vbvictor/1234") == "acp/vbvictor/1234"

    def test_strip_prefix_simple_branch(self):
        """Test simple branch name without prefix."""
        assert acp.strip_branch_prefix("feature-branch") == "feature-branch"

    def test_strip_prefix_multiple_colons(self):
        """Test branch with multiple colons only strips first."""
        assert (
            acp.strip_branch_prefix("user:branch:with:colons") == "branch:with:colons"
        )

    def test_strip_prefix_empty_after_colon(self):
        """Test branch with empty name after colon."""
        assert acp.strip_branch_prefix("user:") == ""


class TestIsGithubUser:
    """Test the is_github_user() function."""

    @mock.patch("subprocess.run")
    def test_valid_github_user(self, mock_run):
        """Test returns True for valid GitHub user."""
        mock_run.return_value = mock.Mock(returncode=0)
        assert acp.is_github_user("vbvictor") is True
        mock_run.assert_called_once_with(
            ["gh", "api", "users/vbvictor"],
            capture_output=True,
            text=True,
        )

    @mock.patch("subprocess.run")
    def test_invalid_github_user(self, mock_run):
        """Test returns False for invalid GitHub user."""
        mock_run.return_value = mock.Mock(returncode=1)
        assert acp.is_github_user("not-a-real-user-12345") is False


class TestCheckoutBranch:
    """Test the checkout_branch() function."""

    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_valid_user_prefix(self, mock_is_user, mock_run):
        """Test checkout strips prefix when it's a valid GitHub user."""
        mock_is_user.return_value = True
        acp.checkout_branch("vbvictor:acp/vbvictor/1234")
        mock_is_user.assert_called_once_with("vbvictor")
        mock_run.assert_called_once_with(["git", "checkout", "acp/vbvictor/1234"])

    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_invalid_user_prefix(self, mock_is_user, mock_run):
        """Test checkout keeps branch as-is when prefix is not a GitHub user."""
        mock_is_user.return_value = False
        acp.checkout_branch("feature:fix")
        mock_is_user.assert_called_once_with("feature")
        mock_run.assert_called_once_with(["git", "checkout", "feature:fix"])

    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_without_colon(self, mock_is_user, mock_run):
        """Test checkout without colon doesn't check GitHub user."""
        acp.checkout_branch("feature-branch")
        mock_is_user.assert_not_called()
        mock_run.assert_called_once_with(["git", "checkout", "feature-branch"])


class TestCheckoutCommand:
    """Test the checkout command in main()."""

    @mock.patch("acp.checkout_branch")
    def test_checkout_command(self, mock_checkout):
        """Test checkout command calls checkout_branch."""
        with mock.patch.object(sys, "argv", ["acp", "checkout", "user:branch"]):
            acp.main()
            mock_checkout.assert_called_once_with("user:branch")

    def test_checkout_no_branch(self, capsys):
        """Test checkout without branch shows error."""
        with mock.patch.object(sys, "argv", ["acp", "checkout"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Branch name required" in captured.err


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
