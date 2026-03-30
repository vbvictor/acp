#!/usr/bin/env python3

import subprocess
import sys
from unittest import mock

import pytest

import acp


class TestRunCommand:
    def test_run_success(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout="output", stderr="")
            result = acp.run(["echo", "test"], quiet=True)
            assert result == "output"

    def test_run_failure(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=1, stdout="", stderr="error message"
            )
            with pytest.raises(SystemExit) as exc:
                acp.run(["false"])
            assert exc.value.code == 1


class TestRunCheck:
    def test_run_check_success(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0)
            assert acp.run_check(["true"]) is True

    def test_run_check_failure(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=1)
            assert acp.run_check(["false"]) is False


class TestCreatePR:
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_no_staged_changes(self, mock_run_check, mock_run):
        mock_run.return_value = "main"
        mock_run_check.return_value = True

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
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")

        calls = mock_run.call_args_list
        pr_create_call = calls[5]
        assert "--head" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_fork_https(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/user/repo.git",
            None,  # git checkout -b
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
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@github.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork-owner/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/upstream/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")

        calls = mock_run.call_args_list
        pr_create_call = calls[5]
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_fork_https(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="https://github.com/upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/fork-owner/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/upstream/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")

        calls = mock_run.call_args_list
        pr_create_call = calls[5]
        assert "fork-owner:" in str(pr_create_call)

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_not_github(self, mock_run_check, mock_run):
        mock_run_check.side_effect = [False, True]

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@gitlab.com:user/repo.git",
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
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@gitlab.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork/repo.git",
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_fork(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(
            returncode=0, stdout="git@github.com:upstream/repo.git\n"
        )

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:fork-owner/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        captured = capsys.readouterr()
        assert "PR creation URL:" in captured.out
        assert "github.com/fork-owner/repo/pull/new/acp/" in captured.out
        assert mock_run.call_count == 5

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_interactive_non_fork_url(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "https://github.com/user/myrepo.git",
            None,  # git checkout -b
            None,  # git checkout original
        ]

        acp.create_pr("test commit", verbose=False, body="", interactive=True)

        captured = capsys.readouterr()
        assert "PR creation URL:" in captured.out
        assert "github.com/user/myrepo/pull/new/acp/" in captured.out

    def test_create_pr_merge_with_interactive_error(self):
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", interactive=True, merge=True
            )
        assert exc.value.code == 1

    def test_create_pr_auto_merge_with_interactive_error(self):
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", interactive=True, auto_merge=True
            )
        assert exc.value.code == 1

    def test_create_pr_merge_and_auto_merge_together_error(self):
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
        mock_run_check.side_effect = [False, True]

        api_check_count = {"count": 0}

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
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
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            elif "rev-parse" in str(cmd) and "--verify" in str(cmd):
                return mock.Mock(returncode=0, stdout="abc123", stderr="")
            elif "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            elif "branch" in str(cmd) and "-rd" in str(cmd):
                return mock.Mock(
                    returncode=0, stdout="Deleted remote-tracking branch", stderr=""
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr(
            "test commit", verbose=False, body="", merge=True, merge_method="squash"
        )

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

        check_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "api" in str(call[0][0])
            and "DELETE" not in str(call[0])
            and "refs/heads/" in str(call[0])
        ]
        assert len(check_calls) > 0

        delete_calls = [
            call
            for call in mock_subprocess.call_args_list
            if len(call[0]) > 0
            and "api" in str(call[0][0])
            and "DELETE" in str(call[0])
        ]
        assert len(delete_calls) > 0

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
        mock_run_check.side_effect = [False, True]

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
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr(
            "test commit",
            verbose=False,
            body="",
            auto_merge=True,
            merge_method="squash",
        )

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
        mock_run_check.side_effect = [False, True]

        api_check_count = {"count": 0}

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
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
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            elif "rev-parse" in str(cmd) and "--verify" in str(cmd):
                return mock.Mock(returncode=0, stdout="abc123", stderr="")
            elif "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            elif "branch" in str(cmd) and "-rd" in str(cmd):
                return mock.Mock(
                    returncode=0, stdout="Deleted remote-tracking branch", stderr=""
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr(
            "test commit", verbose=True, body="", merge=True, merge_method="squash"
        )

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
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="GraphQL: Merge commits are not allowed on this repository",
                )
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test commit", verbose=False, body="", merge=True, merge_method="squash"
            )

        assert exc.value.code == 1

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
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd) and "--auto" in cmd:
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="auto-merge is not enabled for this repository",
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
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
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr(
            "test commit", verbose=False, body="", reviewers="vbvictor,octodad"
        )

        calls = mock_run.call_args_list
        pr_create_call = calls[5]
        assert "--reviewer" in str(pr_create_call)
        assert "vbvictor,octodad" in str(pr_create_call)


class TestAddFlag:
    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_calls_git_add(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            None,  # git add .
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="", add=True)

        calls = mock_run.call_args_list
        assert calls[0] == mock.call(["git", "add", "."], quiet=True)

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_verbose_output(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            None,  # git add .
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=True, body="", add=True)

        captured = capsys.readouterr()
        assert "Adding all changes with 'git add .'" in captured.out

    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_add_flag_not_called_when_false(self, mock_run_check, mock_run):
        mock_run.return_value = "main"
        mock_run_check.return_value = True

        with pytest.raises(SystemExit):
            acp.create_pr("test commit", verbose=False, body="", add=False)

        calls = mock_run.call_args_list
        git_add_calls = [
            c for c in calls if c == mock.call(["git", "add", "."], quiet=True)
        ]
        assert len(git_add_calls) == 0


class TestMain:
    def test_help_flag(self, capsys):
        with mock.patch.object(sys, "argv", ["acp", "-h"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_no_args(self, capsys):
        with mock.patch.object(sys, "argv", ["acp"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_invalid_command(self, capsys):
        with mock.patch.object(sys, "argv", ["acp", "invalid", "message"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code != 0

    @mock.patch("acp.create_pr")
    @mock.patch("acp.run_check")
    def test_valid_pr_command(self, mock_run_check, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_verbose_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_merge_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_auto_merge_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_merge_method_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_add_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_add_flag_short(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_reviewers_flag(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_reviewers_flag_short(self, mock_create_pr):
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
                draft=False,
            )

    @mock.patch("acp.create_pr")
    def test_draft_flag(self, mock_create_pr):
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "--draft"]):
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
                reviewers=None,
                draft=True,
            )

    @mock.patch("acp.create_pr")
    def test_draft_flag_short(self, mock_create_pr):
        with mock.patch.object(sys, "argv", ["acp", "pr", "test", "-d"]):
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
                reviewers=None,
                draft=True,
            )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_merge_method_merge(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess, capsys
    ):
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
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="merge")

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
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="rebase")

        merge_calls = [
            c for c in mock_subprocess.call_args_list if "merge" in str(c[0][0])
        ]
        assert len(merge_calls) > 0
        assert "--rebase" in str(merge_calls[0])

    def test_invalid_merge_method(self):
        with pytest.raises(SystemExit) as exc:
            acp.create_pr(
                "test", verbose=False, body="", merge=True, merge_method="invalid"
            )
        assert exc.value.code == 1

    def test_draft_with_merge(self):
        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test", verbose=False, body="", merge=True, draft=True)
        assert exc.value.code == 1

    def test_draft_with_auto_merge(self):
        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test", verbose=False, body="", auto_merge=True, draft=True)
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_draft(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        mock_run_check.side_effect = [False, True]
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="")

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="", draft=True)

        calls = mock_run.call_args_list
        pr_create_call = calls[5]
        assert "--draft" in pr_create_call[0][0]

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_interactive")
    @mock.patch("acp.run")
    @mock.patch("acp.run_check")
    def test_create_pr_with_unstaged_changes(
        self, mock_run_check, mock_run, mock_run_interactive, mock_subprocess
    ):
        mock_run_check.side_effect = [False, False]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "stash" in str(cmd) and "pop" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git stash push
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")

        stash_push_calls = [
            call
            for call in mock_run.call_args_list
            if len(call[0]) > 0
            and "stash" in str(call[0][0])
            and "push" in str(call[0][0])
        ]
        assert len(stash_push_calls) == 1
        assert "acp-stash-" in str(stash_push_calls[0])

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
        mock_run_check.side_effect = [False, False]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "stash" in str(cmd) and "pop" in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="CONFLICT (content): Merge conflict in file.txt",
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git stash push
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test commit", verbose=False, body="")

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
        mock_run_check.side_effect = [False, True]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            elif "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            elif "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            elif "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        mock_run.side_effect = [
            "main",
            "testuser",
            "git@github.com:user/repo.git",
            None,  # git checkout -b
            None,  # git checkout original
            "https://github.com/user/repo/pull/1",
        ]

        acp.create_pr("test", verbose=False, body="", merge=True, merge_method="squash")

        captured = capsys.readouterr()
        assert 'PR "test"' in captured.out
        assert "merged!" in captured.out
        assert "Error" not in captured.err

    @mock.patch("acp.create_pr")
    def test_keyboard_interrupt(self, mock_create_pr):
        mock_create_pr.side_effect = KeyboardInterrupt()

        with mock.patch.object(sys, "argv", ["acp", "pr", "test"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 130


class TestStripBranchPrefix:
    def test_strip_prefix_with_colon(self):
        assert (
            acp.strip_branch_prefix("vbvictor:acp/vbvictor/1234") == "acp/vbvictor/1234"
        )

    def test_strip_prefix_without_colon(self):
        assert acp.strip_branch_prefix("acp/vbvictor/1234") == "acp/vbvictor/1234"

    def test_strip_prefix_simple_branch(self):
        assert acp.strip_branch_prefix("feature-branch") == "feature-branch"

    def test_strip_prefix_multiple_colons(self):
        assert (
            acp.strip_branch_prefix("user:branch:with:colons") == "branch:with:colons"
        )

    def test_strip_prefix_empty_after_colon(self):
        assert acp.strip_branch_prefix("user:") == ""


class TestIsGithubUser:
    @mock.patch("subprocess.run")
    def test_valid_github_user(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0)
        assert acp.is_github_user("vbvictor") is True
        mock_run.assert_called_once_with(
            ["gh", "api", "users/vbvictor"],
            capture_output=True,
            text=True,
        )

    @mock.patch("subprocess.run")
    def test_invalid_github_user(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1)
        assert acp.is_github_user("not-a-real-user-12345") is False


class TestFetchUpstreamBranch:
    @mock.patch("acp.run_check")
    def test_fetch_from_upstream_when_available(self, mock_run_check):
        mock_run_check.return_value = True
        acp.fetch_upstream_branch("main")
        mock_run_check.assert_any_call(["git", "remote", "get-url", "upstream"])
        mock_run_check.assert_any_call(["git", "fetch", "upstream", "main"])
        mock_run_check.assert_any_call(["git", "merge", "--ff-only", "upstream/main"])

    @mock.patch("acp.run_check")
    def test_fetch_from_origin_when_no_upstream(self, mock_run_check):
        def side_effect(cmd):
            if cmd == ["git", "remote", "get-url", "upstream"]:
                return False
            return True

        mock_run_check.side_effect = side_effect
        acp.fetch_upstream_branch("main")
        mock_run_check.assert_any_call(["git", "fetch", "origin", "main"])
        mock_run_check.assert_any_call(["git", "merge", "--ff-only", "origin/main"])

    @mock.patch("acp.run_check")
    def test_no_merge_when_fetch_fails(self, mock_run_check):
        def side_effect(cmd):
            if cmd[0:2] == ["git", "fetch"]:
                return False
            return True

        mock_run_check.side_effect = side_effect
        acp.fetch_upstream_branch("main")
        for call in mock_run_check.call_args_list:
            assert call[0][0][:2] != ["git", "merge"]


class TestCheckoutBranch:
    @mock.patch("acp.fetch_upstream_branch")
    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_valid_user_prefix(self, mock_is_user, mock_run, mock_fetch):
        mock_is_user.return_value = True
        acp.checkout_branch("vbvictor:acp/vbvictor/1234")
        mock_is_user.assert_called_once_with("vbvictor")
        mock_run.assert_called_once_with(["git", "checkout", "acp/vbvictor/1234"])
        mock_fetch.assert_not_called()

    @mock.patch("acp.fetch_upstream_branch")
    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_invalid_user_prefix(
        self, mock_is_user, mock_run, mock_fetch
    ):
        mock_is_user.return_value = False
        acp.checkout_branch("feature:fix")
        mock_is_user.assert_called_once_with("feature")
        mock_run.assert_called_once_with(["git", "checkout", "feature:fix"])
        mock_fetch.assert_not_called()

    @mock.patch("acp.fetch_upstream_branch")
    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_without_colon(self, mock_is_user, mock_run, mock_fetch):
        acp.checkout_branch("feature-branch")
        mock_is_user.assert_not_called()
        mock_run.assert_called_once_with(["git", "checkout", "feature-branch"])
        mock_fetch.assert_not_called()

    @mock.patch("acp.fetch_upstream_branch")
    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_fetch_flag(self, mock_is_user, mock_run, mock_fetch):
        acp.checkout_branch("feature-branch", fetch=True)
        mock_run.assert_called_once_with(["git", "checkout", "feature-branch"])
        mock_fetch.assert_called_once_with("feature-branch")

    @mock.patch("acp.fetch_upstream_branch")
    @mock.patch("acp.run")
    @mock.patch("acp.is_github_user")
    def test_checkout_with_fetch_and_user_prefix(
        self, mock_is_user, mock_run, mock_fetch
    ):
        mock_is_user.return_value = True
        acp.checkout_branch("vbvictor:main", fetch=True)
        mock_run.assert_called_once_with(["git", "checkout", "main"])
        mock_fetch.assert_called_once_with("main")


class TestCheckoutCommand:
    @mock.patch("acp.checkout_branch")
    def test_checkout_command(self, mock_checkout):
        with mock.patch.object(sys, "argv", ["acp", "checkout", "user:branch"]):
            acp.main()
            mock_checkout.assert_called_once_with("user:branch", fetch=False)

    @mock.patch("acp.checkout_branch")
    def test_checkout_command_with_fetch(self, mock_checkout):
        with mock.patch.object(sys, "argv", ["acp", "checkout", "--fetch", "main"]):
            acp.main()
            mock_checkout.assert_called_once_with("main", fetch=True)

    @mock.patch("acp.checkout_branch")
    def test_checkout_command_with_fetch_short(self, mock_checkout):
        with mock.patch.object(sys, "argv", ["acp", "checkout", "-f", "main"]):
            acp.main()
            mock_checkout.assert_called_once_with("main", fetch=True)

    def test_checkout_no_branch(self, capsys):
        with mock.patch.object(sys, "argv", ["acp", "checkout"]):
            with pytest.raises(SystemExit) as exc:
                acp.main()
            assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Branch name required" in captured.err


class TestListBranches:
    def _empty_git_result(self):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def _git_result(self, stdout):
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout, stderr=""
        )

    def _gh_pr_result(self, prs=None):
        import json

        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(prs or []),
            stderr="",
        )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run", return_value="testuser")
    def test_no_branches_with_prs(self, mock_acp_run, mock_run, capsys):
        mock_run.side_effect = [
            self._git_result("  origin/acp/testuser/1234\n"),
            self._empty_git_result(),
            self._gh_pr_result(),
        ]
        acp.list_branches()
        assert "No ACP branches with linked PRs found." in capsys.readouterr().out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run", return_value="testuser")
    def test_default_only_shows_branches_with_prs(self, mock_acp_run, mock_run, capsys):
        mock_run.side_effect = [
            self._git_result(
                "  origin/acp/testuser/1234\n  origin/acp/testuser/5678\n"
            ),
            self._empty_git_result(),
            self._gh_pr_result(
                [
                    {
                        "headRefName": "acp/testuser/1234",
                        "title": "feat: add feature",
                        "number": 42,
                        "url": "https://github.com/owner/repo/pull/42",
                    }
                ]
            ),
        ]
        acp.list_branches()
        output = capsys.readouterr().out
        assert "acp/testuser/1234 -> #42 feat: add feature" in output
        assert "acp/testuser/5678" not in output

    @mock.patch("subprocess.run")
    @mock.patch("acp.run", return_value="testuser")
    def test_default_searches_all_remotes(self, mock_acp_run, mock_run, capsys):
        mock_run.side_effect = [
            self._empty_git_result(),
            self._empty_git_result(),
            self._gh_pr_result(),
        ]
        acp.list_branches()
        mock_run.assert_any_call(
            ["git", "branch", "-r", "--list", "*/acp/*"],
            capture_output=True,
            text=True,
        )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_check", return_value=False)
    @mock.patch("acp.run", return_value="testuser")
    def test_show_all_on_origin(self, mock_acp_run, mock_run_check, mock_run, capsys):
        mock_run.side_effect = [
            self._git_result(
                "  origin/acp/testuser/1234\n  origin/acp/testuser/5678\n"
            ),
            self._empty_git_result(),
            self._gh_pr_result(
                [
                    {
                        "headRefName": "acp/testuser/1234",
                        "title": "feat: add feature",
                        "number": 42,
                        "url": "https://github.com/owner/repo/pull/42",
                    }
                ]
            ),
        ]
        acp.list_branches(show_all=True)
        output = capsys.readouterr().out
        assert "acp/testuser/1234 -> #42 feat: add feature" in output
        assert "acp/testuser/5678" in output

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_check", return_value=True)
    @mock.patch("acp.run", return_value="testuser")
    def test_show_all_uses_upstream_remote(
        self, mock_acp_run, mock_run_check, mock_run, capsys
    ):
        mock_run.side_effect = [
            self._git_result("  upstream/acp/testuser/1234\n"),
            self._empty_git_result(),
            self._gh_pr_result(),
        ]
        acp.list_branches(show_all=True)
        mock_run.assert_any_call(
            ["git", "branch", "-r", "--list", "upstream/acp/*"],
            capture_output=True,
            text=True,
        )

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_check", return_value=False)
    @mock.patch("acp.run", return_value="testuser")
    def test_show_all_no_branches_message(
        self, mock_acp_run, mock_run_check, mock_run, capsys
    ):
        mock_run.side_effect = [
            self._empty_git_result(),
            self._empty_git_result(),
            self._gh_pr_result(),
        ]
        acp.list_branches(show_all=True)
        assert "No ACP branches found on upstream." in capsys.readouterr().out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run", return_value="testuser")
    def test_matches_user_acp_branches(self, mock_acp_run, mock_run, capsys):
        mock_run.side_effect = [
            self._empty_git_result(),
            self._git_result("  origin/testuser/acp/1234\n"),
            self._gh_pr_result(
                [
                    {
                        "headRefName": "testuser/acp/1234",
                        "title": "fix: bug",
                        "number": 10,
                        "url": "https://github.com/owner/repo/pull/10",
                    }
                ]
            ),
        ]
        acp.list_branches()
        output = capsys.readouterr().out
        assert "testuser/acp/1234 -> #10 fix: bug" in output

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_check", return_value=False)
    @mock.patch("acp.run", return_value="testuser")
    def test_deduplicates_branches(
        self, mock_acp_run, mock_run_check, mock_run, capsys
    ):
        mock_run.side_effect = [
            self._git_result("  origin/acp/testuser/1234\n"),
            self._git_result("  origin/acp/testuser/1234\n"),
            self._gh_pr_result(),
        ]
        acp.list_branches(show_all=True)
        output = capsys.readouterr().out
        assert output.count("acp/testuser/1234") == 1

    @mock.patch("subprocess.run")
    @mock.patch("acp.run", return_value="testuser")
    def test_git_branch_failure(self, mock_acp_run, mock_run, capsys):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="git error"
        )
        with pytest.raises(SystemExit) as exc:
            acp.list_branches()
        assert exc.value.code == 1
        assert "git error" in capsys.readouterr().err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run_check", return_value=False)
    @mock.patch("acp.run", return_value="testuser")
    def test_skips_tracking_refs(self, mock_acp_run, mock_run_check, mock_run, capsys):
        mock_run.side_effect = [
            self._git_result(
                "  origin/acp/testuser/1234\n  origin/HEAD -> origin/main\n"
            ),
            self._empty_git_result(),
            self._gh_pr_result(),
        ]
        acp.list_branches(show_all=True)
        output = capsys.readouterr().out
        assert "acp/testuser/1234" in output
        assert "HEAD" not in output


class TestBranchesCommand:
    @mock.patch("acp.list_branches")
    def test_branches_command(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=False)

    @mock.patch("acp.list_branches")
    def test_branches_command_with_all(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "--all"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=True)

    @mock.patch("acp.list_branches")
    def test_branches_command_with_all_short(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "-a"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
