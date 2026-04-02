#!/usr/bin/env python3
"""ACP - Automatic Commit Pusher.

A CLI tool to create GitHub pull requests from staged changes in one command.
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time
from typing import Any

import argcomplete

__version__ = "1.5.0"


def run(cmd: list[str], quiet: bool = False) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def run_check(cmd: list[str]) -> bool:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode == 0


def run_interactive(cmd: list[str]) -> None:
    """Run a command interactively, filtering out GitHub 'remote:' messages from stderr."""
    read_fd, write_fd = os.pipe()
    process = subprocess.Popen(cmd, stderr=write_fd)
    os.close(write_fd)

    os.set_blocking(read_fd, False)
    stderr_data = b""

    while True:
        ret = process.poll()

        try:
            chunk = os.read(read_fd, 4096)
            if chunk:
                stderr_data += chunk
        except BlockingIOError:
            pass

        if ret is not None:
            try:
                while True:
                    chunk = os.read(read_fd, 4096)
                    if not chunk:
                        break
                    stderr_data += chunk
            except (BlockingIOError, OSError):
                pass
            break

    os.close(read_fd)

    if stderr_data:
        for line in stderr_data.decode("utf-8", errors="replace").splitlines():
            if not line.strip().startswith("remote:"):
                print(line, file=sys.stderr)

    if process.returncode != 0:
        print(
            f"Error: Command failed with exit code {process.returncode}",
            file=sys.stderr,
        )
        sys.exit(1)


def parse_github_url(url: str) -> str | None:
    """Parse GitHub URL (SSH or HTTPS) and extract owner/repo.

    - SSH: git@github.com:owner/repo.git
    - HTTPS: https://github.com/owner/repo.git
    """
    if "github.com" not in url:
        return None

    if url.startswith("git@"):
        return url.split(":")[1].replace(".git", "")

    return "/".join(url.split("/")[-2:]).replace(".git", "")


def validate_merge_options(
    interactive: bool,
    merge: bool,
    auto_merge: bool,
    merge_method: str,
    draft: bool = False,
) -> None:
    if interactive and (merge or auto_merge):
        print(
            "Error: Cannot use --merge or --auto-merge with --interactive mode",
            file=sys.stderr,
        )
        sys.exit(1)

    if merge and auto_merge:
        print(
            "Error: Cannot use --merge and --auto-merge together",
            file=sys.stderr,
        )
        sys.exit(1)

    if draft and (merge or auto_merge):
        print(
            "Error: Cannot use --merge or --auto-merge with --draft",
            file=sys.stderr,
        )
        sys.exit(1)

    valid_methods = ["merge", "squash", "rebase"]
    if merge_method not in valid_methods:
        print(
            f"Error: Invalid merge method '{merge_method}'. Must be one of: {', '.join(valid_methods)}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_repo_info(verbose: bool) -> tuple[str, str, bool]:
    """Returns tuple: (fork_repo, upstream_repo, is_fork)"""
    origin_url = run(["git", "remote", "get-url", "origin"], quiet=True)
    fork_repo = parse_github_url(origin_url)

    if not fork_repo:
        print("Error: Not a GitHub repository", file=sys.stderr)
        sys.exit(1)

    upstream_check = subprocess.run(
        ["git", "remote", "get-url", "upstream"],
        capture_output=True,
        text=True,
        check=False,
    )

    if upstream_check.returncode == 0:
        upstream_url = upstream_check.stdout.strip()
        upstream_repo = parse_github_url(upstream_url)

        if not upstream_repo:
            print("Error: upstream repo is not a github.com repo", file=sys.stderr)
            sys.exit(1)

        is_fork = True
    else:
        upstream_repo = fork_repo
        is_fork = False

    return fork_repo, upstream_repo, is_fork


def generate_temp_branch_name(verbose: bool) -> str:
    gh_user = run(["gh", "api", "user", "--jq", ".login"], quiet=True)
    random_num = random.randint(1000000000000000, 9999999999999999)
    temp_branch = f"acp/{gh_user}/{random_num}"

    if verbose:
        print(f"Creating temporary branch: '{temp_branch}'")

    return temp_branch


def build_compare_url(
    upstream_repo: str, fork_repo: str, temp_branch: str, is_fork: bool
) -> str:
    if is_fork:
        return f"https://github.com/{fork_repo}/pull/new/{temp_branch}"
    return f"https://github.com/{upstream_repo}/pull/new/{temp_branch}"


def create_github_pr(
    upstream_repo: str,
    fork_repo: str,
    temp_branch: str,
    commit_message: str,
    body: str,
    is_fork: bool,
    verbose: bool,
    reviewers: str | None = None,
    draft: bool = False,
) -> str:
    if verbose:
        print(f"Creating PR to: '{upstream_repo}'...")

    gh_cmd = [
        "gh",
        "pr",
        "create",
        "--repo",
        upstream_repo,
        "--title",
        commit_message,
        "--body",
        body,
    ]

    if draft:
        gh_cmd.append("--draft")

    # For forks, specify head as "username:branch"
    if is_fork:
        fork_owner = fork_repo.split("/", maxsplit=1)[0]
        gh_cmd.extend(["--head", f"{fork_owner}:{temp_branch}"])
    else:
        gh_cmd.extend(["--head", temp_branch])

    if reviewers:
        gh_cmd.extend(["--reviewer", reviewers])

    pr_url = run(gh_cmd, quiet=True)

    if verbose:
        print(f"PR created: {pr_url}")

    return pr_url


def check_remote_branch_exists(upstream_repo: str, temp_branch: str) -> bool:
    check_result = subprocess.run(
        ["gh", "api", f"repos/{upstream_repo}/git/refs/heads/{temp_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return check_result.returncode == 0


def delete_local_branch(temp_branch: str, verbose: bool) -> None:
    """Delete local temporary branch and its remote tracking reference."""
    local_check = subprocess.run(
        ["git", "rev-parse", "--verify", temp_branch],
        capture_output=True,
        text=True,
        check=False,
    )

    if local_check.returncode == 0:
        if verbose:
            print(f"Deleting local branch '{temp_branch}'...")

        delete_result = subprocess.run(
            ["git", "branch", "-D", temp_branch],
            capture_output=True,
            text=True,
            check=False,
        )

        if delete_result.returncode == 0:
            if verbose:
                print(f"Local branch '{temp_branch}' deleted")
        elif verbose:
            print(
                f"Warning: Could not delete local branch '{temp_branch}': {delete_result.stderr.strip()}"
            )
    elif verbose:
        print(f"Local branch '{temp_branch}' does not exist")

    remote_tracking_check = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{temp_branch}"],
        capture_output=True,
        text=True,
        check=False,
    )

    if remote_tracking_check.returncode == 0:
        if verbose:
            print(f"Deleting remote tracking branch 'origin/{temp_branch}'...")

        delete_tracking_result = subprocess.run(
            ["git", "branch", "-rd", f"origin/{temp_branch}"],
            capture_output=True,
            text=True,
            check=False,
        )

        if delete_tracking_result.returncode == 0:
            if verbose:
                print(f"Remote tracking branch 'origin/{temp_branch}' deleted")
        elif verbose:
            print(
                f"Warning: Could not delete remote tracking branch: {delete_tracking_result.stderr.strip()}"
            )


def delete_remote_branch(upstream_repo: str, temp_branch: str, verbose: bool) -> None:
    if verbose:
        print(f"Deleting remote branch '{temp_branch}'...")

    delete_result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "DELETE",
            f"repos/{upstream_repo}/git/refs/heads/{temp_branch}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if delete_result.returncode != 0:
        if verbose:
            print(
                f"Warning: Could not delete remote branch '{temp_branch}': {delete_result.stderr.strip()}"
            )
    elif verbose:
        print(f"Remote branch '{temp_branch}' deleted")


def cleanup_branches_after_merge(
    upstream_repo: str, temp_branch: str, verbose: bool
) -> None:
    """Clean up both remote and local branches after PR merge.

    Makes a single API call to check remote branch status, then:
    - If remote exists: delete remote, then delete local
    - If remote gone: just delete local
    """
    if verbose:
        print(f"Checking if branch '{temp_branch}' still exists...")

    branch_exists = check_remote_branch_exists(upstream_repo, temp_branch)

    if branch_exists:
        delete_remote_branch(upstream_repo, temp_branch, verbose)
        delete_local_branch(temp_branch, verbose)
    else:
        if verbose:
            print(f"Branch '{temp_branch}' already deleted by GitHub")
        delete_local_branch(temp_branch, verbose)


def merge_pr(
    pr_url: str,
    commit_message: str,
    merge_method: str,
    upstream_repo: str,
    temp_branch: str,
    verbose: bool,
    sync: bool,
    original_branch: str,
) -> None:
    """Merge a PR immediately after creation.

    Also attempts to delete the remote branch and local branch after merging.
    If sync is True, pulls changes to the original branch after merge.
    """
    if verbose:
        print(f"Merging PR immediately (method: {merge_method})...")

    merge_cmd = ["gh", "pr", "merge", pr_url, f"--{merge_method}"]
    merge_result = subprocess.run(
        merge_cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if merge_result.returncode != 0:
        if not verbose:
            print(f"PR created: {pr_url}")
        print(
            f"Error: Failed to merge PR: {merge_result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f'PR "{commit_message}" ({pr_url}) merged!')

    cleanup_branches_after_merge(upstream_repo, temp_branch, verbose)

    if sync:
        if verbose:
            print(f"Syncing branch '{original_branch}' with remote...")
        pull_result = subprocess.run(
            ["git", "pull", "origin", original_branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if pull_result.returncode != 0:
            print(
                f"Warning: Failed to sync branch '{original_branch}': {pull_result.stderr.strip()}",
                file=sys.stderr,
            )
        elif verbose:
            print(f"Branch '{original_branch}' synced successfully")


def enable_auto_merge(
    pr_url: str, commit_message: str, merge_method: str, verbose: bool
) -> None:
    if verbose:
        print(f"Enabling auto-merge (method: {merge_method})...")

    merge_cmd = ["gh", "pr", "merge", pr_url, "--auto", f"--{merge_method}"]
    merge_result = subprocess.run(
        merge_cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if merge_result.returncode != 0:
        if not verbose:
            print(f"PR created: {pr_url}")
        print(
            f"Error: Failed to enable auto-merge: {merge_result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f'PR "{commit_message}" ({pr_url}) will auto-merge when checks pass')


def strip_branch_prefix(branch: str) -> str:
    """Strip the 'username:' prefix from a branch name.

    GitHub displays fork branches as 'username:branch-name'.
    """
    if ":" in branch:
        return branch.split(":", 1)[1]
    return branch


def is_github_user(username: str) -> bool:
    result = subprocess.run(
        ["gh", "api", f"users/{username}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def list_branches(show_all: bool = False) -> None:
    """List ACP branches with linked PR titles.

    By default, only shows branches with linked PRs.
    With show_all=True, shows all ACP branches on upstream remote.
    """
    gh_user = run(["gh", "api", "user", "--jq", ".login"], quiet=True)

    if show_all:
        remote = (
            "upstream"
            if run_check(["git", "remote", "get-url", "upstream"])
            else "origin"
        )
        run_check(["git", "fetch", "--prune", remote])
        patterns = [f"{remote}/acp/*", f"{remote}/{gh_user}/acp/*"]
    else:
        patterns = ["*/acp/*", f"*/{gh_user}/acp/*"]

    branches: list[str] = []
    for pattern in patterns:
        result = subprocess.run(
            ["git", "branch", "-r", "--list", pattern],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"Error: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        for line in result.stdout.strip().splitlines():
            branch = line.strip()
            if " -> " in branch:
                continue
            if branch not in branches:
                branches.append(branch)

    pr_result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "headRefName,title,number,url",
            "--limit",
            "100",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    pr_map: dict[str, Any] = {}
    if pr_result.returncode == 0 and pr_result.stdout.strip():
        for pr in json.loads(pr_result.stdout):
            pr_map[pr["headRefName"]] = pr

    if not show_all:
        branches = [
            b for b in branches if (b.split("/", 1)[1] if "/" in b else b) in pr_map
        ]

    if not branches:
        if show_all:
            print("No ACP branches found on upstream.")
        else:
            print("No ACP branches with linked PRs found.")
        return

    for branch in branches:
        branch_name = branch.split("/", 1)[1] if "/" in branch else branch
        pr = pr_map.get(branch_name)
        if pr:
            print(f"  {branch_name} -> #{pr['number']} {pr['title']}")
        else:
            print(f"  {branch_name}")


def sync_fork(branch: str = "main", verbose: bool = False) -> None:
    """Sync fork's branch with upstream repository."""
    fork_repo, _upstream_repo, is_fork = get_repo_info(verbose)

    if not is_fork:
        print("No upstream detected. Sync is only available for forked repositories.")
        sys.exit(0)

    if verbose:
        print(f"Syncing fork '{fork_repo}' branch '{branch}' with upstream...")

    sync_result = subprocess.run(
        ["gh", "repo", "sync", fork_repo, "-b", branch],
        capture_output=True,
        text=True,
        check=False,
    )

    if sync_result.returncode != 0:
        print(
            f"Error: Failed to sync fork: {sync_result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    if verbose:
        print("Fork synced on GitHub")

    current_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)

    run(["git", "fetch", "origin", branch], quiet=True)

    if current_branch == branch:
        merge_result = subprocess.run(
            ["git", "merge", "--ff-only", f"origin/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if merge_result.returncode != 0:
            print(
                f"Warning: Could not fast-forward local '{branch}': {merge_result.stderr.strip()}",
                file=sys.stderr,
            )
        elif verbose:
            print(f"Local branch '{branch}' updated")
    elif verbose:
        print(
            f"Not on '{branch}' branch, skipping local update. "
            f"Run 'git pull origin {branch}' when on '{branch}'."
        )

    print(f"Fork synced with upstream ({branch})")


def fetch_upstream_branch(branch: str) -> None:
    remote = (
        "upstream" if run_check(["git", "remote", "get-url", "upstream"]) else "origin"
    )
    if run_check(["git", "fetch", remote, branch]):
        run_check(["git", "merge", "--ff-only", f"{remote}/{branch}"])


def checkout_branch(branch: str, fetch: bool = False) -> None:
    if ":" in branch:
        prefix, rest = branch.split(":", 1)
        if is_github_user(prefix):
            run(["git", "checkout", rest])
            if fetch:
                fetch_upstream_branch(rest)
            return

    run(["git", "checkout", branch])
    if fetch:
        fetch_upstream_branch(branch)


def create_pr(
    commit_message: str,
    verbose: bool = False,
    body: str = "",
    interactive: bool = False,
    merge: bool = False,
    auto_merge: bool = False,
    merge_method: str = "squash",
    sync: bool = False,
    add: bool = False,
    reviewers: str | None = None,
    draft: bool = False,
) -> None:
    validate_merge_options(interactive, merge, auto_merge, merge_method, draft)

    if add:
        if verbose:
            print("Adding all changes with 'git add .'...")
        run(["git", "add", "."], quiet=True)

    original_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if verbose:
        print(f"Current branch: '{original_branch}'")

    if run_check(["git", "diff", "--cached", "--quiet"]):
        print("Error: No staged changes. Run 'git add' first.", file=sys.stderr)
        sys.exit(1)

    temp_branch = generate_temp_branch_name(verbose)

    try:
        fork_repo, upstream_repo, is_fork = get_repo_info(verbose)

        run(["git", "checkout", "-b", temp_branch], quiet=True)
        if verbose:
            print(f'Committing: "{commit_message}"')
        run_interactive(["git", "commit", "--quiet", "-m", commit_message])

        if verbose:
            print(f"Pushing branch '{temp_branch}' to '{fork_repo}'...")
        run_interactive(["git", "push", "--quiet", "-u", "origin", temp_branch])

        has_unstaged = not run_check(["git", "diff", "--quiet"])
        stash_id = None

        if has_unstaged:
            timestamp = int(time.time())
            stash_id = f"acp-stash-{timestamp}"

            if verbose:
                print(f"Stashing unstaged changes as '{stash_id}'...")
            run(["git", "stash", "push", "-m", stash_id], quiet=True)

        run(["git", "checkout", original_branch], quiet=True)
        if verbose:
            print(f"Switched back to original branch: '{original_branch}'")

        if stash_id:
            if verbose:
                print("Restoring stashed changes...")

            stash_pop_result = subprocess.run(
                ["git", "stash", "pop"], capture_output=True, text=True, check=False
            )

            if stash_pop_result.returncode != 0:
                print(
                    "\nWarning: Failed to automatically restore stashed changes due to conflicts.",
                    file=sys.stderr,
                )
                print(
                    f"Your changes are safely stored in stash: '{stash_id}'",
                    file=sys.stderr,
                )
                print(
                    f"To manually apply them, run: git stash apply 'stash^{{/{stash_id}}}'",
                    file=sys.stderr,
                )
                print(
                    f"After resolving conflicts, drop the stash with: git stash drop 'stash^{{/{stash_id}}}'",
                    file=sys.stderr,
                )
                # Continue rather than exiting - the PR was created successfully

        if interactive:
            compare_url = build_compare_url(
                upstream_repo, fork_repo, temp_branch, is_fork
            )
            print(f"PR creation URL: {compare_url}")
        else:
            pr_url = create_github_pr(
                upstream_repo,
                fork_repo,
                temp_branch,
                commit_message,
                body,
                is_fork,
                verbose,
                reviewers,
                draft,
            )

            if merge:
                merge_pr(
                    pr_url,
                    commit_message,
                    merge_method,
                    upstream_repo,
                    temp_branch,
                    verbose,
                    sync,
                    original_branch,
                )
            elif auto_merge:
                enable_auto_merge(pr_url, commit_message, merge_method, verbose)
            elif not verbose:
                print(f"PR created: {pr_url}")

    except Exception:
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()

            print("\nError occurred. Current state:", file=sys.stderr)
            print(f"  Current branch: '{current}'", file=sys.stderr)

            if current != original_branch:
                print(
                    f"  Attempting to switch back to: '{original_branch}'",
                    file=sys.stderr,
                )
                subprocess.run(
                    ["git", "checkout", original_branch],
                    capture_output=True,
                    check=False,
                )
                print(
                    f"  Successfully switched back to: '{original_branch}'",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  Already on original branch: '{original_branch}'",
                    file=sys.stderr,
                )
        except Exception:
            print(
                "  Failed to determine current state or switch branches",
                file=sys.stderr,
            )
        raise


class _NoFilesCompleter:
    suppress = True

    def __call__(self, **kwargs: Any) -> list[str]:
        return []


_no_files = _NoFilesCompleter()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="acp",
        description="acp - create PRs in one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
shell completions:
  Bash:  echo 'eval "$(register-python-argcomplete --no-defaults acp)"' >> ~/.bashrc
  Zsh:   echo 'eval "$(register-python-argcomplete --no-defaults acp)"' >> ~/.zshrc
  Fish:  register-python-argcomplete --shell fish acp > ~/.config/fish/completions/acp.fish

examples:
  acp pr "fix: some typo" -i
  acp pr "fix: urgent" -b "Closes issue #123" --merge --merge-method rebase
  acp pr "feat: new feature" -r vbvictor,octodad""",
    )
    parser.add_argument(
        "--version", action="version", version=f"acp version {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command")

    pr_parser = subparsers.add_parser("pr", help="Create a PR with staged changes")
    pr_parser.add_argument("message", nargs="?", help=argparse.SUPPRESS).completer = (  # type: ignore[attr-defined]
        _no_files
    )
    pr_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    pr_parser.add_argument(
        "-b", "--body", type=str, default="", help="Custom PR body message"
    )
    pr_parser.add_argument(
        "-i", "--interactive", action="store_true", help="Show PR creation URL"
    )
    pr_parser.add_argument(
        "--merge", action="store_true", help="Merge PR immediately after creation"
    )
    pr_parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Enable auto-merge (merge when checks pass)",
    )
    pr_parser.add_argument(
        "--merge-method",
        type=str,
        default="squash",
        choices=["merge", "squash", "rebase"],
        help="Merge method: squash (default), merge, or rebase",
    )
    pr_parser.add_argument(
        "-s",
        "--sync",
        action="store_true",
        help="Sync current branch with remote after merge",
    )
    pr_parser.add_argument(
        "-a",
        "--add",
        action="store_true",
        help="Run 'git add .' before committing changes",
    )
    pr_parser.add_argument(
        "-d",
        "--draft",
        action="store_true",
        help="Create PR as a draft",
    )
    pr_parser.add_argument(
        "-r",
        "--reviewers",
        type=str,
        default=None,
        help="Comma-separated list of GitHub usernames to request reviews from",
    )

    checkout_parser = subparsers.add_parser(
        "checkout", help="Checkout a branch, stripping 'user:' prefix if present"
    )
    checkout_parser.add_argument(
        "branch", nargs="?", help=argparse.SUPPRESS
    ).completer = _no_files  # type: ignore[attr-defined]
    checkout_parser.add_argument(
        "-f",
        "--fetch",
        action="store_true",
        help="Fetch and fast-forward branch from upstream after checkout",
    )

    sync_parser = subparsers.add_parser(
        "sync", help="Sync fork with upstream repository"
    )
    sync_parser.add_argument(
        "-b",
        "--branch",
        type=str,
        default="main",
        help="Branch to sync (default: main)",
    )
    sync_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    branches_parser = subparsers.add_parser(
        "branches", help="List ACP branches with linked PRs"
    )
    branches_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show all ACP branches on upstream remote",
    )

    argcomplete.autocomplete(parser, default_completer=_no_files)  # type: ignore[arg-type]
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "sync":
            sync_fork(branch=args.branch, verbose=args.verbose)
        elif args.command == "branches":
            list_branches(show_all=args.all)
        elif args.command == "checkout":
            if not args.branch:
                print("Error: Branch name required for checkout", file=sys.stderr)
                sys.exit(1)
            checkout_branch(args.branch, fetch=args.fetch)
        elif args.command == "pr":
            if not args.message:
                print("Error: Commit message required for pr", file=sys.stderr)
                sys.exit(1)
            create_pr(
                args.message,
                verbose=args.verbose,
                body=args.body,
                interactive=args.interactive,
                merge=args.merge,
                auto_merge=args.auto_merge,
                merge_method=args.merge_method,
                sync=args.sync,
                add=args.add,
                reviewers=args.reviewers,
                draft=args.draft,
            )
    except KeyboardInterrupt:
        print("\n\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
