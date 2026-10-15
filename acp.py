#!/usr/bin/env python3
"""ACP - Automatic Commit Pusher.

A CLI tool to create GitHub pull requests from staged changes in one command.
"""

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

import argcomplete

__version__ = "1.8.0"


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


def get_gh_user() -> str:
    return run(["gh", "api", "user", "--jq", ".login"], quiet=True)


def is_acp_branch(branch: str) -> bool:
    """Return True for acp temporary branches and acp stack layer branches."""
    if branch.startswith("acp/"):
        return True
    parts = branch.split("/")
    return len(parts) == 3 and parts[0] == "users" and parts[2].startswith("acp-")


def generate_temp_branch_name(verbose: bool) -> str:
    gh_user = get_gh_user()
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
    base: str | None = None,
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

    if base:
        gh_cmd.extend(["--base", base])

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


def list_branches(show_all: bool = False, verbose: bool = False) -> None:
    """List open ACP PRs authored by the current user."""
    if verbose:
        print("Querying open ACP PRs from 'gh pr list --author @me'...")

    pr_result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--author",
            "@me",
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

    if pr_result.returncode != 0:
        print(f"Error: {pr_result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    prs = []
    if pr_result.stdout.strip():
        prs = [
            pr
            for pr in json.loads(pr_result.stdout)
            if is_acp_branch(pr["headRefName"])
        ]

    if verbose:
        print(f"Open ACP PRs: {[pr['headRefName'] for pr in prs] or '(none)'}")

    if not prs:
        print("No ACP branches with linked PRs found.")
        return

    for pr in prs:
        print(f"  {pr['headRefName']} -> #{pr['number']} {pr['title']}")


def sync_fork(branch: str = "main", verbose: bool = False) -> None:
    """Sync fork's branch with upstream repository."""
    fork_repo, _upstream_repo, is_fork = get_repo_info(verbose)

    if not is_fork:
        print("No upstream detected. Sync is only available for forked repositories.")
        sys.exit(0)

    if verbose:
        print(f"Syncing fork '{fork_repo}' branch '{branch}' with upstream...")

    if verbose:
        sync_result = subprocess.run(
            ["gh", "repo", "sync", fork_repo, "-b", branch], text=True, check=False
        )
    else:
        sync_result = subprocess.run(
            ["gh", "repo", "sync", fork_repo, "-b", branch],
            capture_output=True,
            text=True,
            check=False,
        )

    if sync_result.returncode != 0:
        if verbose:
            print("Error: Failed to sync fork", file=sys.stderr)
        else:
            print(
                f"Error: Failed to sync fork: {sync_result.stderr.strip()}",
                file=sys.stderr,
            )
        sys.exit(1)

    if verbose:
        print("Fork synced on GitHub")

    current_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)

    fetch_cmd = ["git", "fetch", "origin", branch]
    if verbose:
        fetch_cmd.append("--progress")
        fetch_result = subprocess.run(fetch_cmd, check=False)
        if fetch_result.returncode != 0:
            print("Error: git fetch failed", file=sys.stderr)
            sys.exit(1)
    else:
        run(fetch_cmd, quiet=True)

    if current_branch == branch:
        merge_cmd = ["git", "merge", "--ff-only", f"origin/{branch}"]
        if verbose:
            merge_result = subprocess.run(merge_cmd, text=True, check=False)
        else:
            merge_result = subprocess.run(
                merge_cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        if merge_result.returncode != 0:
            if verbose:
                print(
                    f"Warning: Could not fast-forward local '{branch}'",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Warning: Could not fast-forward local '{branch}': "
                    f"{merge_result.stderr.strip()}",
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


def pull(verbose: bool = False) -> None:
    """Pull latest changes, recursing into submodules if any are out of sync."""
    submodule_result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True,
        text=True,
        check=False,
    )

    has_submodules = (
        submodule_result.returncode == 0 and submodule_result.stdout.strip()
    )
    needs_recurse = has_submodules and any(
        line and line[0] in ("+", "-") for line in submodule_result.stdout.splitlines()
    )

    if needs_recurse:
        if verbose:
            print("Submodules out of sync, running: git pull --recurse-submodules")
        cmd = ["git", "pull", "--recurse-submodules"]
    else:
        if verbose:
            print("Running: git pull")
        cmd = ["git", "pull"]

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


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

    stack = load_current_stack()
    if stack is not None:
        create_stack_layer(
            stack,
            commit_message,
            verbose=verbose,
            body=body,
            interactive=interactive,
            merge=merge,
            auto_merge=auto_merge,
            merge_method=merge_method,
            add=add,
            reviewers=reviewers,
            draft=draft,
        )
        return

    if add:
        if verbose:
            print("Adding all changes with 'git add .'...")
        run(["git", "add", "."], quiet=True)

    original_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if verbose:
        print(f"Current branch: '{original_branch}'")

    if is_acp_branch(original_branch):
        print(
            f"Error: Already on an ACP branch '{original_branch}'. "
            "Switch to your base branch before creating a new PR.",
            file=sys.stderr,
        )
        sys.exit(1)

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


def fail(message: str) -> NoReturn:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def get_stack_root() -> Path:
    # The common dir is shared by all worktrees, so a stack is visible from each of them.
    git_dir = run(["git", "rev-parse", "--git-common-dir"], quiet=True)
    return Path(git_dir).resolve() / "acp"


def stack_file(stack_id: str) -> Path:
    return get_stack_root() / "stacks" / f"{stack_id}.json"


def load_stack(stack_id: str) -> dict[str, Any] | None:
    path = stack_file(stack_id)
    if not path.exists():
        return None
    state: dict[str, Any] = json.loads(path.read_text())
    return state


def save_stack(state: dict[str, Any]) -> None:
    path = stack_file(state["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def get_current_stack_id() -> str | None:
    path = get_stack_root() / "current"
    if not path.exists():
        return None
    return path.read_text().strip() or None


def set_current_stack_id(stack_id: str | None) -> None:
    path = get_stack_root() / "current"
    if stack_id is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stack_id + "\n")


def delete_stack(stack_id: str) -> None:
    stack_file(stack_id).unlink(missing_ok=True)
    if get_current_stack_id() == stack_id:
        set_current_stack_id(None)


def load_current_stack() -> dict[str, Any] | None:
    stack_id = get_current_stack_id()
    return load_stack(stack_id) if stack_id else None


def list_stacks() -> list[dict[str, Any]]:
    """Return all known stacks, oldest first."""
    stacks_dir = get_stack_root() / "stacks"
    if not stacks_dir.is_dir():
        return []
    files = sorted(stacks_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return [json.loads(p.read_text()) for p in files]


def resolve_stack(stack_id: str | None, allow_latest: bool = False) -> dict[str, Any]:
    """Return the requested stack, else the open stack, else (optionally) the latest unfinished one."""
    if stack_id:
        state = load_stack(stack_id)
        if state is None:
            fail(f"Stack '{stack_id}' not found")
        return state

    state = load_current_stack()
    if state is not None:
        return state

    if allow_latest:
        unfinished = [s for s in list_stacks() if s["status"] != "done"]
        if unfinished:
            return unfinished[-1]

    fail("No open stack. Run 'acp stack start' first or pass a stack id.")


def generate_stack_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))


def stack_branch_name(gh_user: str, stack_id: str, n: int) -> str:
    # LLVM only allows 'users/<username>/' branches in the main repo, for stacked PRs.
    return f"users/{gh_user}/acp-{stack_id}-{n}"


def can_push_to_repo(repo: str) -> bool:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}", "--jq", ".permissions.push"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_pr_state(repo: str, number: int) -> str:
    """Return OPEN, DRAFT, MERGED, CLOSED, or UNKNOWN."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "state,isDraft",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return "UNKNOWN"
    data = json.loads(result.stdout)
    if data["state"] == "OPEN" and data.get("isDraft"):
        return "DRAFT"
    return str(data["state"])


def fetch_pr_states(state: dict[str, Any]) -> dict[int, str]:
    return {
        layer["n"]: get_pr_state(state["repo"], layer["pr_number"])
        for layer in state["layers"]
        if layer.get("pr_number")
    }


def format_stack_tree(
    state: dict[str, Any], pr_states: dict[int, str], head_branch: str | None = None
) -> list[str]:
    lines = [state["base_branch"]]
    for depth, layer in enumerate(state["layers"]):
        indent = "   " * depth
        pr = f"#{layer['pr_number']}" if layer.get("pr_number") else "(no PR)"
        fallback_state = "MERGED" if layer.get("merged") else "UNKNOWN"
        pr_state = pr_states.get(layer["n"], fallback_state).lower()
        line = f"{indent}└─ {pr} {layer['title']} [{pr_state}] {layer['branch']}"
        if layer["branch"] == head_branch:
            line += "  <- HEAD"
        lines.append(line)
    return lines


def stack_start(
    draft: bool = False, reviewers: str | None = None, verbose: bool = False
) -> None:
    current = load_current_stack()
    if current is not None:
        fail(
            f"Stack '{current['id']}' is already open. "
            "Run 'acp stack end' or 'acp stack abort' first."
        )

    base_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if base_branch == "HEAD":
        fail("HEAD is detached. Check out the base branch before starting a stack.")
    if is_acp_branch(base_branch):
        fail(
            f"Already on an ACP branch '{base_branch}'. "
            "Switch to your base branch before starting a stack."
        )

    fork_repo, upstream_repo, is_fork = get_repo_info(verbose)

    if not is_fork:
        mode, remote, head_repo = "stacked", "origin", fork_repo
    elif can_push_to_repo(upstream_repo):
        mode, remote, head_repo = "stacked", "upstream", upstream_repo
    else:
        mode, remote, head_repo = "fallback", "origin", fork_repo

    if not check_remote_branch_exists(upstream_repo, base_branch):
        fail(f"Base branch '{base_branch}' does not exist in '{upstream_repo}'")

    state: dict[str, Any] = {
        "id": generate_stack_id(),
        "status": "open",
        "mode": mode,
        "repo": upstream_repo,
        "head_repo": head_repo,
        "remote": remote,
        "base_remote": "upstream" if is_fork else "origin",
        "base_branch": base_branch,
        "base_sha": run(["git", "rev-parse", "HEAD"], quiet=True),
        "gh_user": get_gh_user(),
        "defaults": {"draft": draft, "reviewers": reviewers},
        "layers": [],
    }
    save_stack(state)
    set_current_stack_id(state["id"])

    print(f"Stack '{state['id']}' started on '{base_branch}' ({upstream_repo})")
    if mode == "fallback":
        print(
            f"Note: no push access to '{upstream_repo}'. Every PR will target "
            f"'{base_branch}' and include the commits of the PRs below it."
        )
    elif verbose:
        print(f"Layer branches will be pushed to '{remote}' ({head_repo})")


def stack_status(stack_id: str | None = None, verbose: bool = False) -> None:
    if stack_id is None and load_current_stack() is None:
        stacks = list_stacks()
        if not stacks:
            print("No stacks found.")
            return
        for s in stacks:
            print(
                f"  {s['id']} [{s['status']}] base '{s['base_branch']}', "
                f"{len(s['layers'])} layer(s)"
            )
        return

    state = resolve_stack(stack_id)
    if verbose:
        print(f"Querying PR states in '{state['repo']}'...")
    pr_states = fetch_pr_states(state)
    head = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)

    print(
        f"Stack '{state['id']}' [{state['status']}, {state['mode']}] in {state['repo']}"
    )
    for line in format_stack_tree(state, pr_states, head):
        print(line)


def stack_abort(stack_id: str | None = None) -> None:
    state = resolve_stack(stack_id)
    delete_stack(state["id"])
    print(
        f"Stack '{state['id']}' aborted. Local stack state was removed; "
        "PRs and branches were left untouched."
    )


def find_pr_number(state: dict[str, Any], branch: str) -> int | None:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            state["repo"],
            "--head",
            branch,
            "--state",
            "all",
            "--json",
            "number",
            "--jq",
            ".[0].number",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    out = result.stdout.strip()
    return int(out) if result.returncode == 0 and out.isdigit() else None


def stack_comment_marker(stack_id: str) -> str:
    return f"<!-- acp-stack:{stack_id} -->"


def render_stack_comment(
    state: dict[str, Any], pr_states: dict[int, str], current_n: int
) -> str:
    repo = state["repo"]
    base = state["base_branch"]
    layers = state["layers"]

    count = f"{len(layers)} PR" if len(layers) == 1 else f"{len(layers)} PRs"
    lines = [
        stack_comment_marker(state["id"]),
        f"**Stack** ({count}, base `{base}`), merge from the bottom up:",
        "",
        f"- `{base}`",
    ]
    for depth, layer in enumerate(layers, start=1):
        number = layer.get("pr_number")
        if number:
            text = f"#{number} {layer['title']}"
        else:
            text = f"`{layer['branch']}` {layer['title']} (no PR yet)"

        pr_state = pr_states.get(layer["n"], "")
        label = (
            f" ({pr_state.lower()})"
            if pr_state in {"MERGED", "CLOSED", "DRAFT"}
            else ""
        )

        if layer["n"] == current_n:
            text = f"**{text}**{label} ← this PR"
        elif pr_state in {"MERGED", "CLOSED"}:
            text = f"~~{text}~~{label}"
        else:
            text += label

        if state["mode"] == "fallback" and number:
            text += f" ([own commit](https://github.com/{repo}/pull/{number}/commits/{layer['head_sha']}))"

        lines.append(f"{'  ' * depth}- {text}")

    if state["mode"] == "fallback":
        lines += [
            "",
            (
                f"Every PR in this stack targets `{base}`, so each PR also contains the "
                "commits of the PRs below it. Review only the last commit (linked as "
                "*own commit*)."
            ),
        ]
    if state["status"] == "open":
        lines += ["", "_This stack is still in progress, more PRs may be added._"]

    lines += [
        "",
        (
            "<sub>Managed by [acp](https://github.com/vbvictor/acp). "
            "This comment is updated automatically.</sub>"
        ),
    ]
    return "\n".join(lines)


def find_stack_comment(repo: str, number: int, marker: str) -> int | None:
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/issues/{number}/comments",
            "--jq",
            f'.[] | select(.body | contains("{marker}")) | .id',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ids = result.stdout.split()
    return int(ids[0]) if result.returncode == 0 and ids else None


def upsert_stack_comment(
    repo: str, number: int, marker: str, body: str, comment_id: int | None
) -> int | None:
    """Edit the stack comment on a PR in place, or create it. Return the comment id."""
    if comment_id is None:
        comment_id = find_stack_comment(repo, number, marker)

    if comment_id is not None:
        patch = subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/comments/{comment_id}",
                "-f",
                f"body={body}",
                "--jq",
                ".id",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if patch.returncode == 0:
            return comment_id

    create = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{number}/comments",
            "-f",
            f"body={body}",
            "--jq",
            ".id",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if create.returncode != 0:
        print(
            f"Warning: Could not post stack comment on #{number}: {create.stderr.strip()}",
            file=sys.stderr,
        )
        return None
    return int(create.stdout.strip())


def refresh_stack_comments(
    state: dict[str, Any], verbose: bool = False
) -> dict[int, str]:
    for layer in state["layers"]:
        if not layer.get("pr_number"):
            layer["pr_number"] = find_pr_number(state, layer["branch"])

    pr_states = fetch_pr_states(state)
    marker = stack_comment_marker(state["id"])

    for layer in state["layers"]:
        if not layer.get("pr_number"):
            continue
        if verbose:
            print(f"Updating stack comment on #{layer['pr_number']}...")
        body = render_stack_comment(state, pr_states, layer["n"])
        layer["comment_id"] = upsert_stack_comment(
            state["repo"], layer["pr_number"], marker, body, layer.get("comment_id")
        )

    save_stack(state)
    return pr_states


def build_stack_compare_url(state: dict[str, Any], base: str, branch: str) -> str:
    head = branch
    if state["head_repo"] != state["repo"]:
        head = f"{state['head_repo'].split('/', maxsplit=1)[0]}:{branch}"
    return f"https://github.com/{state['repo']}/compare/{base}...{head}?expand=1"


def rollback_stack_layer(
    state: dict[str, Any], branch: str, parent: str, parent_sha: str, pushed: bool
) -> None:
    """Return to the parent layer with the layer's changes staged again."""
    print(
        f"\nError occurred. Returning to '{parent}' with your changes staged...",
        file=sys.stderr,
    )
    run_check(["git", "reset", "--soft", parent_sha])
    run_check(["git", "checkout", parent])
    run_check(["git", "branch", "-D", branch])
    if pushed:
        run_check(["git", "push", "--quiet", state["remote"], "--delete", branch])


def create_stack_layer(
    state: dict[str, Any],
    commit_message: str,
    verbose: bool = False,
    body: str = "",
    interactive: bool = False,
    merge: bool = False,
    auto_merge: bool = False,
    merge_method: str = "squash",
    add: bool = False,
    reviewers: str | None = None,
    draft: bool = False,
) -> None:
    layers = state["layers"]

    if merge:
        fail(
            "--merge is not supported inside a stack. "
            "Merge PRs from the bottom up, then run 'acp stack sync'."
        )
    if auto_merge and layers:
        fail("--auto-merge is only allowed on the bottom PR of a stack")

    if add:
        if verbose:
            print("Adding all changes with 'git add .'...")
        run(["git", "add", "."], quiet=True)

    parent = layers[-1]["branch"] if layers else state["base_branch"]
    current = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if current != parent:
        fail(
            f"Stack '{state['id']}' is open and its tip is '{parent}', but HEAD is "
            f"'{current}'. Check out '{parent}' or run 'acp stack end'."
        )

    if run_check(["git", "diff", "--cached", "--quiet"]):
        fail("No staged changes. Run 'git add' first.")

    n = len(layers) + 1
    branch = stack_branch_name(state["gh_user"], state["id"], n)
    pr_base = parent if state["mode"] == "stacked" else state["base_branch"]
    parent_sha = run(["git", "rev-parse", "HEAD"], quiet=True)
    draft = draft or state["defaults"]["draft"]
    reviewers = reviewers or state["defaults"]["reviewers"]

    if verbose:
        print(f"Creating stack layer {n}: '{branch}' on top of '{parent}'")

    pushed = False
    pr_url = None
    try:
        run(["git", "checkout", "-b", branch], quiet=True)
        if verbose:
            print(f'Committing: "{commit_message}"')
        run_interactive(["git", "commit", "--quiet", "-m", commit_message])

        if verbose:
            print(f"Pushing branch '{branch}' to '{state['remote']}'...")
        run_interactive(["git", "push", "--quiet", "-u", state["remote"], branch])
        pushed = True

        if interactive:
            compare_url = build_stack_compare_url(state, pr_base, branch)
            print(f"PR creation URL: {compare_url}")
        else:
            pr_url = create_github_pr(
                state["repo"],
                state["head_repo"],
                branch,
                commit_message,
                body,
                state["head_repo"] != state["repo"],
                verbose,
                reviewers,
                draft,
                base=pr_base,
            )
    except BaseException:
        rollback_stack_layer(state, branch, parent, parent_sha, pushed)
        raise

    layers.append(
        {
            "n": n,
            "branch": branch,
            "parent_sha": parent_sha,
            "head_sha": run(["git", "rev-parse", "HEAD"], quiet=True),
            "pr_number": int(pr_url.rstrip("/").rsplit("/", 1)[-1]) if pr_url else None,
            "title": commit_message,
            "comment_id": None,
            "merged": False,
        }
    )
    save_stack(state)

    if pr_url and auto_merge:
        enable_auto_merge(pr_url, commit_message, merge_method, verbose)
    elif pr_url and not verbose:
        print(f"PR created: {pr_url} (layer {n} of stack '{state['id']}')")

    refresh_stack_comments(state, verbose)


def stack_end(verbose: bool = False) -> None:
    state = resolve_stack(None)
    stack_id = state["id"]

    if not state["layers"]:
        delete_stack(stack_id)
        print(f"Stack '{stack_id}' had no PRs and was removed.")
        return

    state["status"] = "closed"
    pr_states = refresh_stack_comments(state, verbose)
    set_current_stack_id(None)

    base = state["base_branch"]
    if run_check(["git", "checkout", base]):
        if verbose:
            print(f"Switched back to '{base}'")
    else:
        print(f"Warning: Could not check out '{base}'", file=sys.stderr)

    print(f"Stack '{stack_id}' closed with {len(state['layers'])} PR(s):")
    for line in format_stack_tree(state, pr_states):
        print(line)
    print(f"After the bottom PR merges, run 'acp stack sync {stack_id}'.")


def git_rebase_in_progress() -> bool:
    for name in ("rebase-merge", "rebase-apply"):
        path = run(["git", "rev-parse", "--git-path", name], quiet=True)
        if Path(path).exists():
            return True
    return False


def stack_sync(
    stack_id: str | None = None, continue_sync: bool = False, verbose: bool = False
) -> None:
    """Drop merged layers, rebase the rest onto their new parents, push and retarget."""
    state = resolve_stack(stack_id, allow_latest=True)
    layers_by_n = {layer["n"]: layer for layer in state["layers"]}
    progress = state.get("sync")

    if continue_sync:
        if progress is None:
            fail(f"No interrupted sync to continue for stack '{state['id']}'")
        if git_rebase_in_progress():
            fail(
                "A rebase is still in progress. Resolve conflicts, run "
                "'git rebase --continue', then 'acp stack sync --continue'."
            )
        layer = layers_by_n[progress["n"]]
        layer["parent_sha"] = progress["onto"]
        layer["head_sha"] = run(["git", "rev-parse", layer["branch"]], quiet=True)
        progress["rebased"].append(layer["n"])
        resume_after = layer["n"]
    else:
        if progress is not None and git_rebase_in_progress():
            fail(
                "A previous sync stopped on a conflict. Finish it with "
                "'acp stack sync --continue', or run 'git rebase --abort' first."
            )
        if not (
            run_check(["git", "diff", "--quiet"])
            and run_check(["git", "diff", "--cached", "--quiet"])
        ):
            fail("Commit or stash your changes before running 'acp stack sync'.")

        if verbose:
            print(f"Fetching '{state['base_branch']}' from '{state['base_remote']}'...")
        if not run_check(
            ["git", "fetch", "--quiet", state["base_remote"], state["base_branch"]]
        ):
            fail(
                f"Could not fetch '{state['base_branch']}' from '{state['base_remote']}'"
            )

        pr_states = fetch_pr_states(state)
        merged_now = []
        for layer in state["layers"]:
            if layer["merged"]:
                continue
            if pr_states.get(layer["n"]) != "MERGED":
                break
            layer["merged"] = True
            merged_now.append(layer["n"])

        for layer in state["layers"]:
            if not layer["merged"] and pr_states.get(layer["n"]) == "MERGED":
                print(
                    f"Warning: #{layer['pr_number']} is merged but a PR below it is not",
                    file=sys.stderr,
                )

        progress = {
            "return_branch": run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True
            ),
            "merged_now": merged_now,
            "rebased": [],
        }
        resume_after = 0

    active = [layer for layer in state["layers"] if not layer["merged"]]
    base_ref = f"{state['base_remote']}/{state['base_branch']}"

    for i, layer in enumerate(active):
        if layer["n"] <= resume_after:
            continue
        onto = run(
            ["git", "rev-parse", base_ref if i == 0 else active[i - 1]["branch"]],
            quiet=True,
        )
        if onto == layer["parent_sha"]:
            continue

        if verbose:
            print(f"Rebasing '{layer['branch']}' onto {onto[:12]}...")
        state["sync"] = {**progress, "n": layer["n"], "onto": onto}
        save_stack(state)

        rebase = subprocess.run(
            [
                "git",
                "rebase",
                "--quiet",
                "--onto",
                onto,
                layer["parent_sha"],
                layer["branch"],
            ],
            check=False,
        )
        if rebase.returncode != 0:
            fail(
                f"Rebase of '{layer['branch']}' stopped on a conflict. Resolve it, run "
                "'git rebase --continue', then 'acp stack sync --continue'."
            )

        layer["parent_sha"] = onto
        layer["head_sha"] = run(["git", "rev-parse", layer["branch"]], quiet=True)
        progress["rebased"].append(layer["n"])

    finish_stack_sync(state, progress, active, verbose)


def finish_stack_sync(
    state: dict[str, Any],
    progress: dict[str, Any],
    active: list[dict[str, Any]],
    verbose: bool,
) -> None:
    rebased = set(progress["rebased"])
    merged = [
        layer for layer in state["layers"] if layer["n"] in progress["merged_now"]
    ]

    for layer in active:
        if layer["n"] in rebased:
            if verbose:
                print(f"Force-pushing '{layer['branch']}'...")
            run(
                [
                    "git",
                    "push",
                    "--quiet",
                    "--force-with-lease",
                    state["remote"],
                    layer["branch"],
                ],
                quiet=True,
            )

    # Retarget before deleting merged branches, so GitHub never sees an open PR
    # whose base branch is gone.
    if state["mode"] == "stacked" and merged and active and active[0]["pr_number"]:
        if verbose:
            print(
                f"Retargeting #{active[0]['pr_number']} to '{state['base_branch']}'..."
            )
        run_check(
            [
                "gh",
                "pr",
                "edit",
                str(active[0]["pr_number"]),
                "--repo",
                state["repo"],
                "--base",
                state["base_branch"],
            ]
        )

    for layer in merged:
        if check_remote_branch_exists(state["head_repo"], layer["branch"]):
            delete_remote_branch(state["head_repo"], layer["branch"], verbose)

    merged_branches = {layer["branch"] for layer in merged}
    return_branch = progress["return_branch"]
    if return_branch in merged_branches:
        return_branch = state["base_branch"]
    run_check(["git", "checkout", return_branch])

    for layer in merged:
        delete_local_branch(layer["branch"], verbose)

    state.pop("sync", None)
    if not active:
        state["status"] = "done"
        if get_current_stack_id() == state["id"]:
            set_current_stack_id(None)
    save_stack(state)

    pr_states = refresh_stack_comments(state, verbose)

    print(
        f"Stack '{state['id']}' synced: {len(merged)} merged layer(s) removed, "
        f"{len(rebased)} layer(s) rebased."
    )
    for line in format_stack_tree(state, pr_states):
        print(line)
    if not active:
        print("Every PR in the stack is merged.")


def run_stack_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    if args.stack_command == "start":
        stack_start(draft=args.draft, reviewers=args.reviewers, verbose=args.verbose)
    elif args.stack_command == "status":
        stack_status(args.stack_id, verbose=args.verbose)
    elif args.stack_command == "end":
        stack_end(verbose=args.verbose)
    elif args.stack_command == "sync":
        stack_sync(
            args.stack_id, continue_sync=args.continue_sync, verbose=args.verbose
        )
    elif args.stack_command == "abort":
        stack_abort(args.stack_id)
    else:
        parser.print_help()
        sys.exit(0)


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

    pull_parser = subparsers.add_parser(
        "pull", help="Pull latest changes, syncing submodules when needed"
    )
    pull_parser.add_argument(
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
    branches_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    stack_parser = subparsers.add_parser("stack", help="Manage stacked PRs")
    stack_subparsers = stack_parser.add_subparsers(dest="stack_command")

    stack_start_parser = stack_subparsers.add_parser(
        "start", help="Start a stack on the current branch"
    )
    stack_start_parser.add_argument(
        "-d",
        "--draft",
        action="store_true",
        help="Create every PR in the stack as a draft",
    )
    stack_start_parser.add_argument(
        "-r",
        "--reviewers",
        type=str,
        default=None,
        help="Comma-separated list of reviewers for every PR in the stack",
    )
    stack_start_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    stack_status_parser = stack_subparsers.add_parser(
        "status", help="Show stack topology and PR states"
    )
    stack_status_parser.add_argument(
        "stack_id", nargs="?", help=argparse.SUPPRESS
    ).completer = _no_files  # type: ignore[attr-defined]
    stack_status_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    stack_end_parser = stack_subparsers.add_parser(
        "end", help="Finalize stack comments and return to the base branch"
    )
    stack_end_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    stack_sync_parser = stack_subparsers.add_parser(
        "sync", help="Drop merged PRs, rebase the rest and retarget them"
    )
    stack_sync_parser.add_argument(
        "stack_id", nargs="?", help=argparse.SUPPRESS
    ).completer = _no_files  # type: ignore[attr-defined]
    stack_sync_parser.add_argument(
        "--continue",
        dest="continue_sync",
        action="store_true",
        help="Continue a sync that stopped on a rebase conflict",
    )
    stack_sync_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )

    stack_abort_parser = stack_subparsers.add_parser(
        "abort", help="Forget local stack state, leave PRs and branches untouched"
    )
    stack_abort_parser.add_argument(
        "stack_id", nargs="?", help=argparse.SUPPRESS
    ).completer = _no_files  # type: ignore[attr-defined]

    argcomplete.autocomplete(parser, default_completer=_no_files)  # type: ignore[arg-type]
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "pull":
            pull(verbose=args.verbose)
        elif args.command == "sync":
            sync_fork(branch=args.branch, verbose=args.verbose)
        elif args.command == "branches":
            list_branches(show_all=args.all, verbose=args.verbose)
        elif args.command == "stack":
            run_stack_command(args, stack_parser)
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
