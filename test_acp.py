import json
import subprocess
import sys
from unittest import mock

import pytest

import acp


@pytest.fixture(autouse=True)
def stack_root(tmp_path, monkeypatch):
    """Keep stack state in a per-test directory instead of the real .git."""
    root = tmp_path / "acp-state"
    monkeypatch.setattr(acp, "get_stack_root", lambda: root)
    return root


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
    def test_create_pr_on_acp_branch(self, mock_run_check, mock_run, capsys):
        mock_run.return_value = "acp/testuser/1234567890123456"

        with pytest.raises(SystemExit) as exc:
            acp.create_pr("test commit", verbose=False, body="")
        assert exc.value.code == 1
        assert "Already on an ACP branch" in capsys.readouterr().err

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
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "api" in str(cmd) and "DELETE" not in str(cmd):
                api_check_count["count"] += 1
                if api_check_count["count"] == 1:
                    return mock.Mock(
                        returncode=0,
                        stdout='{"ref": "refs/heads/acp/testuser/123"}',
                        stderr="",
                    )
                return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            if "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-parse" in str(cmd) and "--verify" in str(cmd):
                return mock.Mock(returncode=0, stdout="abc123", stderr="")
            if "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            if "branch" in str(cmd) and "-rd" in str(cmd):
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
            if "merge" in str(cmd):
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
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "api" in str(cmd) and "DELETE" not in str(cmd):
                api_check_count["count"] += 1
                if api_check_count["count"] == 1:
                    return mock.Mock(
                        returncode=0,
                        stdout='{"ref": "refs/heads/acp/testuser/123"}',
                        stderr="",
                    )
                return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            if "api" in str(cmd) and "DELETE" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "rev-parse" in str(cmd) and "--verify" in str(cmd):
                return mock.Mock(returncode=0, stdout="abc123", stderr="")
            if "branch" in str(cmd) and "-D" in str(cmd):
                return mock.Mock(returncode=0, stdout="Deleted branch", stderr="")
            if "branch" in str(cmd) and "-rd" in str(cmd):
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
            if "merge" in str(cmd):
                return mock.Mock(
                    returncode=1,
                    stdout="",
                    stderr="GraphQL: Merge commits are not allowed on this repository",
                )
            if "api" in str(cmd) and "DELETE" in str(cmd):
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
            if "merge" in str(cmd) and "--auto" in cmd:
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
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout='{"ref": "refs/heads/acp/testuser/123"}',
                    stderr="",
                )
            if "api" in str(cmd) and "DELETE" in str(cmd):
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
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout='{"ref": "refs/heads/acp/testuser/123"}',
                    stderr="",
                )
            if "api" in str(cmd) and "DELETE" in str(cmd):
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
            if "stash" in str(cmd) and "pop" in str(cmd):
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
            if "stash" in str(cmd) and "pop" in str(cmd):
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
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "api" in str(cmd) and "DELETE" not in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="Not Found")
            if "api" in str(cmd) and "DELETE" in str(cmd):
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
            check=False,
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
            return cmd != ["git", "remote", "get-url", "upstream"]

        mock_run_check.side_effect = side_effect
        acp.fetch_upstream_branch("main")
        mock_run_check.assert_any_call(["git", "fetch", "origin", "main"])
        mock_run_check.assert_any_call(["git", "merge", "--ff-only", "origin/main"])

    @mock.patch("acp.run_check")
    def test_no_merge_when_fetch_fails(self, mock_run_check):
        def side_effect(cmd):
            return cmd[0:2] != ["git", "fetch"]

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
    def _gh_pr_result(self, prs=None, returncode=0):
        return subprocess.CompletedProcess(
            args=[],
            returncode=returncode,
            stdout=json.dumps(prs or []) if returncode == 0 else "",
            stderr="gh error" if returncode != 0 else "",
        )

    @mock.patch("subprocess.run")
    def test_no_acp_prs(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result()
        acp.list_branches()
        assert "No ACP branches with linked PRs found." in capsys.readouterr().out

    @mock.patch("subprocess.run")
    def test_shows_own_acp_prs(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result(
            [
                {
                    "headRefName": "acp/testuser/1234",
                    "title": "feat: add feature",
                    "number": 42,
                    "url": "u",
                }
            ]
        )
        acp.list_branches()
        assert "acp/testuser/1234 -> #42 feat: add feature" in capsys.readouterr().out

    @mock.patch("subprocess.run")
    def test_filters_out_non_acp_prs(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result(
            [
                {
                    "headRefName": "acp/testuser/1234",
                    "title": "my fix",
                    "number": 1,
                    "url": "u",
                },
                {
                    "headRefName": "some-feature",
                    "title": "other",
                    "number": 2,
                    "url": "u",
                },
            ]
        )
        acp.list_branches()
        output = capsys.readouterr().out
        assert "acp/testuser/1234" in output
        assert "some-feature" not in output

    @mock.patch("subprocess.run")
    def test_uses_author_me(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result()
        acp.list_branches()
        call_args = mock_run.call_args[0][0]
        assert "--author" in call_args
        assert "@me" in call_args

    @mock.patch("subprocess.run")
    def test_gh_pr_list_failure(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result(returncode=1)
        with pytest.raises(SystemExit) as exc:
            acp.list_branches()
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    def test_verbose_output(self, mock_run, capsys):
        mock_run.return_value = self._gh_pr_result(
            [
                {
                    "headRefName": "acp/testuser/1234",
                    "title": "feat",
                    "number": 1,
                    "url": "u",
                }
            ]
        )
        acp.list_branches(verbose=True)
        out = capsys.readouterr().out
        assert "Querying open ACP PRs" in out
        assert "Open ACP PRs:" in out


class TestSyncFork:
    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_not_a_fork(self, mock_run, mock_subprocess, capsys):
        mock_run.return_value = "git@github.com:user/repo.git"
        mock_subprocess.return_value = mock.Mock(returncode=1, stdout="", stderr="")

        with pytest.raises(SystemExit) as exc:
            acp.sync_fork()
        assert exc.value.code == 0

        captured = capsys.readouterr()
        assert "No upstream detected" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_success_on_target_branch(
        self, mock_run, mock_subprocess, capsys
    ):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
            "main",  # current branch
            None,  # git fetch
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "repo" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        acp.sync_fork(branch="main")

        captured = capsys.readouterr()
        assert "Fork synced with upstream (main)" in captured.out

        sync_calls = [
            c
            for c in mock_subprocess.call_args_list
            if "sync" in str(c[0][0]) and "gh" in str(c[0][0])
        ]
        assert len(sync_calls) == 1
        assert "user/fork" in str(sync_calls[0])

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_success_on_different_branch(
        self, mock_run, mock_subprocess, capsys
    ):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
            "feature-branch",  # current branch (not main)
            None,  # git fetch
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "repo" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        acp.sync_fork(branch="main")

        captured = capsys.readouterr()
        assert "Fork synced with upstream (main)" in captured.out

        merge_calls = [
            c for c in mock_subprocess.call_args_list if "merge" in str(c[0][0])
        ]
        assert len(merge_calls) == 0

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_gh_sync_failure(self, mock_run, mock_subprocess, capsys):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "repo" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="sync failed")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        with pytest.raises(SystemExit) as exc:
            acp.sync_fork(branch="main")
        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Failed to sync fork" in captured.err

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_custom_branch(self, mock_run, mock_subprocess, capsys):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
            "develop",  # current branch
            None,  # git fetch
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "repo" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "merge" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        acp.sync_fork(branch="develop")

        captured = capsys.readouterr()
        assert "Fork synced with upstream (develop)" in captured.out

        sync_calls = [
            c
            for c in mock_subprocess.call_args_list
            if "sync" in str(c[0][0]) and "gh" in str(c[0][0])
        ]
        assert "-b" in str(sync_calls[0])
        assert "develop" in str(sync_calls[0])

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_ff_merge_failure_warns(self, mock_run, mock_subprocess, capsys):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
            "main",  # current branch
            None,  # git fetch
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "repo" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=0, stdout="", stderr="")
            if "merge" in str(cmd):
                return mock.Mock(
                    returncode=1, stdout="", stderr="not possible to fast-forward"
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        acp.sync_fork(branch="main")

        captured = capsys.readouterr()
        assert "Could not fast-forward" in captured.err
        assert "Fork synced with upstream (main)" in captured.out

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_verbose_streams_output(self, mock_run, mock_subprocess, capsys):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
            "main",  # current branch
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        acp.sync_fork(branch="main", verbose=True)

        captured = capsys.readouterr()
        assert "Fork synced with upstream (main)" in captured.out

        for c in mock_subprocess.call_args_list:
            cmd = c[0][0]
            if (
                ("gh" in str(cmd) and "sync" in str(cmd))
                or "fetch" in str(cmd)
                or "merge" in str(cmd)
            ):
                assert "capture_output" not in c.kwargs

        fetch_calls = [
            c for c in mock_subprocess.call_args_list if "fetch" in str(c[0][0])
        ]
        assert len(fetch_calls) == 1
        assert "--progress" in fetch_calls[0][0][0]

    @mock.patch("subprocess.run")
    @mock.patch("acp.run")
    def test_sync_fork_verbose_gh_sync_failure(self, mock_run, mock_subprocess, capsys):
        mock_run.side_effect = [
            "git@github.com:user/fork.git",  # origin url
        ]

        def subprocess_side_effect(*args, **kwargs):
            cmd = args[0]
            if "upstream" in str(cmd) and "get-url" in str(cmd):
                return mock.Mock(
                    returncode=0,
                    stdout="git@github.com:upstream/repo.git",
                    stderr="",
                )
            if "gh" in str(cmd) and "sync" in str(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        mock_subprocess.side_effect = subprocess_side_effect

        with pytest.raises(SystemExit) as exc:
            acp.sync_fork(branch="main", verbose=True)
        assert exc.value.code == 1

        captured = capsys.readouterr()
        assert "Failed to sync fork" in captured.err


class TestSyncCommand:
    @mock.patch("acp.sync_fork")
    def test_sync_command_default(self, mock_sync):
        with mock.patch.object(sys, "argv", ["acp", "sync"]):
            acp.main()
            mock_sync.assert_called_once_with(branch="main", verbose=False)

    @mock.patch("acp.sync_fork")
    def test_sync_command_custom_branch(self, mock_sync):
        with mock.patch.object(sys, "argv", ["acp", "sync", "-b", "develop"]):
            acp.main()
            mock_sync.assert_called_once_with(branch="develop", verbose=False)

    @mock.patch("acp.sync_fork")
    def test_sync_command_custom_branch_long(self, mock_sync):
        with mock.patch.object(sys, "argv", ["acp", "sync", "--branch", "develop"]):
            acp.main()
            mock_sync.assert_called_once_with(branch="develop", verbose=False)

    @mock.patch("acp.sync_fork")
    def test_sync_command_verbose(self, mock_sync):
        with mock.patch.object(sys, "argv", ["acp", "sync", "-v"]):
            acp.main()
            mock_sync.assert_called_once_with(branch="main", verbose=True)


class TestBranchesCommand:
    @mock.patch("acp.list_branches")
    def test_branches_command(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=False, verbose=False)

    @mock.patch("acp.list_branches")
    def test_branches_command_with_all(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "--all"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=True, verbose=False)

    @mock.patch("acp.list_branches")
    def test_branches_command_with_all_short(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "-a"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=True, verbose=False)

    @mock.patch("acp.list_branches")
    def test_branches_command_verbose(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "-v"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=False, verbose=True)

    @mock.patch("acp.list_branches")
    def test_branches_command_verbose_long(self, mock_list):
        with mock.patch.object(sys, "argv", ["acp", "branches", "--verbose"]):
            acp.main()
            mock_list.assert_called_once_with(show_all=False, verbose=True)


class TestPull:
    @mock.patch("subprocess.run")
    def test_pull_no_submodules(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),  # git submodule status
            mock.Mock(returncode=0, stdout="", stderr=""),  # git pull
        ]
        acp.pull()
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "pull"] in calls
        assert ["git", "pull", "--recurse-submodules"] not in calls

    @mock.patch("subprocess.run")
    def test_pull_submodules_in_sync(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(
                returncode=0,
                stdout=" abc123 llvm-project (v17.0.0)\n",
                stderr="",
            ),  # git submodule status (space prefix = in sync)
            mock.Mock(returncode=0, stdout="", stderr=""),  # git pull
        ]
        acp.pull()
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "pull"] in calls
        assert ["git", "pull", "--recurse-submodules"] not in calls

    @mock.patch("subprocess.run")
    def test_pull_submodules_out_of_sync(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(
                returncode=0,
                stdout="+abc123 llvm-project (v17.0.0)\n",
                stderr="",
            ),  # git submodule status (+ prefix = out of sync)
            mock.Mock(
                returncode=0, stdout="", stderr=""
            ),  # git pull --recurse-submodules
        ]
        acp.pull()
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "pull", "--recurse-submodules"] in calls

    @mock.patch("subprocess.run")
    def test_pull_submodule_not_initialized(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(
                returncode=0,
                stdout="-abc123 llvm-project\n",
                stderr="",
            ),  # git submodule status (- prefix = not initialized)
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        acp.pull()
        calls = [c[0][0] for c in mock_run.call_args_list]
        assert ["git", "pull", "--recurse-submodules"] in calls

    @mock.patch("subprocess.run")
    def test_pull_failure_exits(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),  # git submodule status
            mock.Mock(returncode=1, stdout="", stderr=""),  # git pull fails
        ]
        with pytest.raises(SystemExit) as exc:
            acp.pull()
        assert exc.value.code == 1

    @mock.patch("subprocess.run")
    def test_pull_verbose_no_submodules(self, mock_run, capsys):
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        acp.pull(verbose=True)
        assert "git pull" in capsys.readouterr().out

    @mock.patch("subprocess.run")
    def test_pull_verbose_with_submodules(self, mock_run, capsys):
        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="+abc123 sub\n", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        acp.pull(verbose=True)
        assert "--recurse-submodules" in capsys.readouterr().out


class TestPullCommand:
    @mock.patch("acp.pull")
    def test_pull_command(self, mock_pull):
        with mock.patch.object(sys, "argv", ["acp", "pull"]):
            acp.main()
            mock_pull.assert_called_once_with(verbose=False)

    @mock.patch("acp.pull")
    def test_pull_command_verbose(self, mock_pull):
        with mock.patch.object(sys, "argv", ["acp", "pull", "-v"]):
            acp.main()
            mock_pull.assert_called_once_with(verbose=True)

    @mock.patch("acp.pull")
    def test_pull_command_verbose_long(self, mock_pull):
        with mock.patch.object(sys, "argv", ["acp", "pull", "--verbose"]):
            acp.main()
            mock_pull.assert_called_once_with(verbose=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def make_stack(**overrides):
    state = {
        "id": "abc123",
        "status": "open",
        "mode": "stacked",
        "repo": "owner/repo",
        "head_repo": "owner/repo",
        "remote": "origin",
        "base_remote": "origin",
        "base_branch": "main",
        "base_sha": "base000",
        "gh_user": "testuser",
        "defaults": {"draft": False, "reviewers": None},
        "layers": [],
    }
    state.update(overrides)
    return state


def make_layer(n, pr_number=None, **overrides):
    layer = {
        "n": n,
        "branch": f"users/testuser/acp-abc123-{n}",
        "parent_sha": f"sha{n - 1}",
        "head_sha": f"sha{n}",
        "pr_number": pr_number,
        "title": f"feat: part {n}",
        "comment_id": None,
        "merged": False,
    }
    layer.update(overrides)
    return layer


class TestIsAcpBranch:
    def test_temp_branch(self):
        assert acp.is_acp_branch("acp/user/1234567890123456")

    def test_stack_branch(self):
        assert acp.is_acp_branch("users/user/acp-abc123-1")

    def test_other_user_branch(self):
        assert not acp.is_acp_branch("users/user/my-feature")

    def test_regular_branch(self):
        assert not acp.is_acp_branch("main")

    def test_list_branches_includes_stack_branches(self, capsys):
        prs = [
            {"headRefName": "users/u/acp-abc123-1", "title": "t", "number": 3},
            {"headRefName": "users/u/feature", "title": "x", "number": 4},
        ]
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(returncode=0, stdout=json.dumps(prs))
            acp.list_branches()
        out = capsys.readouterr().out
        assert "users/u/acp-abc123-1 -> #3" in out
        assert "users/u/feature" not in out


class TestStackState:
    def test_no_current_stack(self):
        assert acp.load_current_stack() is None

    def test_save_and_load(self):
        state = make_stack()
        acp.save_stack(state)
        acp.set_current_stack_id("abc123")
        assert acp.load_current_stack() == state

    def test_delete_clears_current(self):
        acp.save_stack(make_stack())
        acp.set_current_stack_id("abc123")
        acp.delete_stack("abc123")
        assert acp.load_stack("abc123") is None
        assert acp.get_current_stack_id() is None

    def test_resolve_by_id(self):
        acp.save_stack(make_stack())
        assert acp.resolve_stack("abc123")["id"] == "abc123"

    def test_resolve_unknown_id(self, capsys):
        with pytest.raises(SystemExit):
            acp.resolve_stack("nope")
        assert "Stack 'nope' not found" in capsys.readouterr().err

    def test_resolve_without_open_stack(self, capsys):
        with pytest.raises(SystemExit):
            acp.resolve_stack(None)
        assert "No open stack" in capsys.readouterr().err

    def test_resolve_latest_unfinished(self):
        acp.save_stack(make_stack(id="done01", status="done"))
        acp.save_stack(make_stack(id="clsd01", status="closed"))
        assert acp.resolve_stack(None, allow_latest=True)["id"] == "clsd01"

    def test_stack_branch_name(self):
        assert acp.stack_branch_name("u", "abc123", 2) == "users/u/acp-abc123-2"


class TestPrState:
    @mock.patch("subprocess.run")
    def test_draft(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0, stdout='{"state": "OPEN", "isDraft": true}'
        )
        assert acp.get_pr_state("o/r", 1) == "DRAFT"

    @mock.patch("subprocess.run")
    def test_merged(self, mock_run):
        mock_run.return_value = mock.Mock(
            returncode=0, stdout='{"state": "MERGED", "isDraft": false}'
        )
        assert acp.get_pr_state("o/r", 1) == "MERGED"

    @mock.patch("subprocess.run")
    def test_failure(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout="")
        assert acp.get_pr_state("o/r", 1) == "UNKNOWN"


class TestStackStart:
    def _start(self, is_fork=False, can_push=True, branch="main", **kwargs):
        repo_info = (
            ("me/repo", "up/repo", True) if is_fork else ("me/repo", "me/repo", False)
        )
        with (
            mock.patch("acp.run", side_effect=[branch, "base000"]),
            mock.patch("acp.get_repo_info", return_value=repo_info),
            mock.patch("acp.can_push_to_repo", return_value=can_push),
            mock.patch("acp.check_remote_branch_exists", return_value=True),
            mock.patch("acp.get_gh_user", return_value="me"),
            mock.patch("acp.generate_stack_id", return_value="abc123"),
        ):
            acp.stack_start(**kwargs)
        return acp.load_current_stack()

    def test_non_fork(self, capsys):
        state = self._start()
        assert state["mode"] == "stacked"
        assert state["remote"] == "origin"
        assert state["repo"] == "me/repo"
        assert state["base_branch"] == "main"
        assert state["base_sha"] == "base000"
        assert "Stack 'abc123' started on 'main'" in capsys.readouterr().out

    def test_fork_with_push_access(self):
        state = self._start(is_fork=True, can_push=True)
        assert state["mode"] == "stacked"
        assert state["remote"] == "upstream"
        assert state["head_repo"] == "up/repo"
        assert state["base_remote"] == "upstream"

    def test_fork_without_push_access(self, capsys):
        state = self._start(is_fork=True, can_push=False)
        assert state["mode"] == "fallback"
        assert state["remote"] == "origin"
        assert state["head_repo"] == "me/repo"
        assert state["repo"] == "up/repo"
        assert "no push access" in capsys.readouterr().out

    def test_defaults_saved(self):
        state = self._start(draft=True, reviewers="a,b")
        assert state["defaults"] == {"draft": True, "reviewers": "a,b"}

    def test_already_open(self, capsys):
        acp.save_stack(make_stack())
        acp.set_current_stack_id("abc123")
        with pytest.raises(SystemExit):
            acp.stack_start()
        assert "already open" in capsys.readouterr().err

    def test_on_acp_branch(self, capsys):
        with (
            mock.patch("acp.run", return_value="users/me/acp-xyz-1"),
            pytest.raises(SystemExit),
        ):
            acp.stack_start()
        assert "Already on an ACP branch" in capsys.readouterr().err

    def test_base_missing_on_remote(self, capsys):
        with (
            mock.patch("acp.run", return_value="local-only"),
            mock.patch("acp.get_repo_info", return_value=("me/r", "me/r", False)),
            mock.patch("acp.check_remote_branch_exists", return_value=False),
            pytest.raises(SystemExit),
        ):
            acp.stack_start()
        assert "does not exist in 'me/r'" in capsys.readouterr().err


class TestStackStatus:
    def test_no_stacks(self, capsys):
        acp.stack_status()
        assert "No stacks found." in capsys.readouterr().out

    def test_lists_stacks_when_none_open(self, capsys):
        acp.save_stack(make_stack(status="closed", layers=[make_layer(1, 5)]))
        acp.stack_status()
        assert "abc123 [closed] base 'main', 1 layer(s)" in capsys.readouterr().out

    def test_shows_tree(self, capsys):
        acp.save_stack(make_stack(layers=[make_layer(1, 5), make_layer(2, 6)]))
        acp.set_current_stack_id("abc123")
        with (
            mock.patch("acp.get_pr_state", side_effect=["MERGED", "OPEN"]),
            mock.patch("acp.run", return_value="users/testuser/acp-abc123-2"),
        ):
            acp.stack_status()
        out = capsys.readouterr().out
        assert "└─ #5 feat: part 1 [merged]" in out
        assert "   └─ #6 feat: part 2 [open]" in out
        assert "acp-abc123-2  <- HEAD" in out


class TestStackAbort:
    def test_abort(self, capsys):
        acp.save_stack(make_stack())
        acp.set_current_stack_id("abc123")
        acp.stack_abort()
        assert acp.load_stack("abc123") is None
        assert "aborted" in capsys.readouterr().out

    def test_abort_without_stack(self):
        with pytest.raises(SystemExit):
            acp.stack_abort()


class TestStackCommand:
    @mock.patch("acp.stack_start")
    def test_start(self, mock_start):
        with mock.patch.object(sys, "argv", ["acp", "stack", "start", "-d", "-r", "a"]):
            acp.main()
        mock_start.assert_called_once_with(draft=True, reviewers="a", verbose=False)

    @mock.patch("acp.stack_status")
    def test_status_with_id(self, mock_status):
        with mock.patch.object(sys, "argv", ["acp", "stack", "status", "abc123"]):
            acp.main()
        mock_status.assert_called_once_with("abc123", verbose=False)

    @mock.patch("acp.stack_abort")
    def test_abort(self, mock_abort):
        with mock.patch.object(sys, "argv", ["acp", "stack", "abort"]):
            acp.main()
        mock_abort.assert_called_once_with(None)

    def test_no_subcommand(self, capsys):
        with (
            mock.patch.object(sys, "argv", ["acp", "stack"]),
            pytest.raises(SystemExit) as exc,
        ):
            acp.main()
        assert exc.value.code == 0
