#!/usr/bin/env python3
"""ACP - Automatic Commit Pusher.

A CLI tool to create GitHub pull requests from staged changes in one command.
"""

import argparse
import random
import subprocess
import sys

__version__ = "0.3.0"


def run(cmd, quiet=False):
    """Run a command and return output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def run_check(cmd):
    """Run a command that might fail, return True if successful."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def parse_github_url(url):
    """Parse GitHub URL and extract owner/repo.

    Handles both SSH and HTTPS formats:
    - SSH: git@github.com:owner/repo.git
    - HTTPS: https://github.com/owner/repo.git

    Returns owner/repo string or None if not a GitHub URL.
    """
    if "github.com" not in url:
        return None

    if url.startswith("git@"):
        # SSH format
        return url.split(":")[1].replace(".git", "")

    # HTTPS format
    return "/".join(url.split("/")[-2:]).replace(".git", "")


def validate_merge_options(interactive, merge, auto_merge, merge_method):
    """Validate merge-related command line options.

    Exits with error if invalid combination is detected.
    """
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

    valid_methods = ["merge", "squash", "rebase"]
    if merge_method not in valid_methods:
        print(
            f"Error: Invalid merge method '{merge_method}'. Must be one of: {', '.join(valid_methods)}",
            file=sys.stderr,
        )
        sys.exit(1)


def get_repo_info(verbose):
    """Get repository information (fork status, upstream, origin).

    Returns tuple: (fork_repo, upstream_repo, is_fork)
    """
    # Get origin remote URL
    origin_url = run(["git", "remote", "get-url", "origin"], quiet=True)
    fork_repo = parse_github_url(origin_url)

    if not fork_repo:
        print("Error: Not a GitHub repository", file=sys.stderr)
        sys.exit(1)

    # Check if there's an upstream remote
    upstream_check = subprocess.run(
        ["git", "remote", "get-url", "upstream"], capture_output=True, text=True
    )

    if upstream_check.returncode == 0:
        # Has upstream remote, this is a fork
        upstream_url = upstream_check.stdout.strip()
        upstream_repo = parse_github_url(upstream_url)

        if not upstream_repo:
            print("Error: upstream repo is not a github.com repo", file=sys.stderr)
            sys.exit(1)

        is_fork = True
    else:
        # No upstream remote, not a fork
        upstream_repo = fork_repo
        is_fork = False

    return fork_repo, upstream_repo, is_fork


def generate_temp_branch_name(verbose):
    """Generate a unique temporary branch name.

    Format: acp/{github-username}/{16-digit-random-number}
    """
    gh_user = run(["gh", "api", "user", "--jq", ".login"], quiet=True)
    random_num = random.randint(1000000000000000, 9999999999999999)
    temp_branch = f"acp/{gh_user}/{random_num}"

    if verbose:
        print(f"Creating temporary branch: '{temp_branch}'")

    return temp_branch


def build_compare_url(upstream_repo, fork_repo, temp_branch, is_fork):
    """Build GitHub PR creation URL for interactive mode.

    Returns the URL for manual PR creation (same format as git push shows).
    """
    # Format: https://github.com/owner/repo/pull/new/branch
    return f"https://github.com/{upstream_repo}/pull/new/{temp_branch}"


def create_github_pr(
    upstream_repo, fork_repo, temp_branch, commit_message, body, is_fork, verbose
):
    """Create a GitHub PR using gh CLI.

    Returns the PR URL.
    """
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

    # For forks, we need to specify head as "username:branch"
    if is_fork:
        fork_owner = fork_repo.split("/")[0]
        gh_cmd.extend(["--head", f"{fork_owner}:{temp_branch}"])
    else:
        gh_cmd.extend(["--head", temp_branch])

    pr_url = run(gh_cmd, quiet=True)

    if verbose:
        print(f"PR created: {pr_url}")

    return pr_url


def check_remote_branch_exists(upstream_repo, temp_branch):
    """Check if remote branch exists.

    Returns True if branch exists, False otherwise.
    """
    check_result = subprocess.run(
        ["gh", "api", f"repos/{upstream_repo}/git/refs/heads/{temp_branch}"],
        capture_output=True,
        text=True,
    )
    return check_result.returncode == 0


def delete_local_branch(temp_branch, verbose):
    """Delete local temporary branch and its remote tracking reference.

    Only deletes if the local branch exists.
    Also removes the remote tracking branch (remotes/origin/branch) if it exists.
    """
    # Check if local branch exists
    local_check = subprocess.run(
        ["git", "rev-parse", "--verify", temp_branch],
        capture_output=True,
        text=True,
    )

    if local_check.returncode == 0:
        if verbose:
            print(f"Deleting local branch '{temp_branch}'...")

        delete_result = subprocess.run(
            ["git", "branch", "-D", temp_branch],
            capture_output=True,
            text=True,
        )

        if delete_result.returncode == 0:
            if verbose:
                print(f"Local branch '{temp_branch}' deleted")
        else:
            if verbose:
                print(
                    f"Warning: Could not delete local branch '{temp_branch}': {delete_result.stderr.strip()}"
                )
    elif verbose:
        print(f"Local branch '{temp_branch}' does not exist")

    # Delete remote tracking branch (remotes/origin/branch) if it exists
    remote_tracking_check = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{temp_branch}"],
        capture_output=True,
        text=True,
    )

    if remote_tracking_check.returncode == 0:
        if verbose:
            print(f"Deleting remote tracking branch 'origin/{temp_branch}'...")

        delete_tracking_result = subprocess.run(
            ["git", "branch", "-rd", f"origin/{temp_branch}"],
            capture_output=True,
            text=True,
        )

        if delete_tracking_result.returncode == 0:
            if verbose:
                print(f"Remote tracking branch 'origin/{temp_branch}' deleted")
        else:
            if verbose:
                print(
                    f"Warning: Could not delete remote tracking branch: {delete_tracking_result.stderr.strip()}"
                )

    # Delete remote tracking branch (remotes/origin/branch) if it exists
    remote_tracking_check = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{temp_branch}"],
        capture_output=True,
        text=True,
    )

    if remote_tracking_check.returncode == 0:
        if verbose:
            print(f"Deleting remote tracking branch origin/{temp_branch}...")

        delete_tracking_result = subprocess.run(
            ["git", "branch", "-rd", f"origin/{temp_branch}"],
            capture_output=True,
            text=True,
        )

        if delete_tracking_result.returncode == 0:
            if verbose:
                print(f"Remote tracking branch origin/{temp_branch} deleted")
        else:
            if verbose:
                print(
                    f"Warning: Could not delete remote tracking branch: {delete_tracking_result.stderr.strip()}"
                )


def delete_remote_branch(upstream_repo, temp_branch, verbose):
    """Delete remote branch using GitHub API."""
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
    )

    if delete_result.returncode != 0:
        if verbose:
            print(
                f"Warning: Could not delete remote branch '{temp_branch}': {delete_result.stderr.strip()}"
            )
    elif verbose:
        print(f"Remote branch '{temp_branch}' deleted")


def cleanup_branches_after_merge(upstream_repo, temp_branch, verbose):
    """Clean up both remote and local branches after PR merge.

    Makes a single API call to check remote branch status, then:
    - If remote exists: delete remote, then delete local
    - If remote gone: just delete local
    """
    if verbose:
        print(f"Checking if branch '{temp_branch}' still exists...")

    # Single API call to check branch existence
    branch_exists = check_remote_branch_exists(upstream_repo, temp_branch)

    if branch_exists:
        # Delete remote branch
        delete_remote_branch(upstream_repo, temp_branch, verbose)
        # Delete local branch
        delete_local_branch(temp_branch, verbose)
    else:
        if verbose:
            print(f"Branch '{temp_branch}' already deleted by GitHub")
        # Just delete local branch since remote is gone
        delete_local_branch(temp_branch, verbose)


def merge_pr(pr_url, commit_message, merge_method, upstream_repo, temp_branch, verbose):
    """Merge a PR immediately after creation.

    Also attempts to delete the remote branch and local branch after merging.
    """
    if verbose:
        print(f"Merging PR immediately (method: {merge_method})...")

    merge_cmd = ["gh", "pr", "merge", pr_url, f"--{merge_method}"]
    merge_result = subprocess.run(
        merge_cmd,
        capture_output=True,
        text=True,
    )

    if merge_result.returncode != 0:
        if not verbose:
            print(f"PR created: {pr_url}")
        print(
            f"Error: Failed to merge PR: {merge_result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clean up both remote and local branches
    cleanup_branches_after_merge(upstream_repo, temp_branch, verbose)

    print(f'PR "{commit_message}" ({pr_url}) merged!')


def enable_auto_merge(pr_url, commit_message, merge_method, verbose):
    """Enable auto-merge for a PR.

    Note: Branch cannot be auto-deleted with auto-merge.
    """
    if verbose:
        print(f"Enabling auto-merge (method: {merge_method})...")

    merge_cmd = ["gh", "pr", "merge", pr_url, "--auto", f"--{merge_method}"]
    merge_result = subprocess.run(
        merge_cmd,
        capture_output=True,
        text=True,
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


def show_help():
    """Show help message."""
    print(
        "usage: acp pr <commit message> [-b <body>] [-i] [--merge|--auto-merge] [--merge-method <method>]"
    )
    print()
    print("acp - create PRs in one command")
    print()
    print("Options:")
    print("  -b, --body <text>           Custom PR body message")
    print("  -i, --interactive           Show PR creation URL instead of creating PR")
    print("  -v, --verbose               Show detailed output")
    print("  --merge                     Merge PR immediately after creation")
    print("  --auto-merge                Enable GitHub auto-merge after PR creation")
    print(
        "  --merge-method <method>     Merge method: squash (default), merge, or rebase"
    )
    print("  --version                   Show version number")
    print("  -h, --help                  Show this help message")
    print()
    print("Examples:")
    print('  acp pr "fix: some typo" -i')
    print('  acp pr "fix: urgent" -b "Closes issue #123" --merge --merge-method rebase')


def create_pr(
    commit_message,
    verbose=False,
    body="",
    interactive=False,
    merge=False,
    auto_merge=False,
    merge_method="squash",
):
    """Create a PR with staged changes."""
    # Validate inputs
    validate_merge_options(interactive, merge, auto_merge, merge_method)

    # Get current branch
    original_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if verbose:
        print(f"Current branch: '{original_branch}'")

    # Check for staged changes
    if run_check(["git", "diff", "--cached", "--quiet"]):
        print("Error: No staged changes. Run 'git add' first.", file=sys.stderr)
        sys.exit(1)

    # Generate temporary branch name
    temp_branch = generate_temp_branch_name(verbose)

    try:
        # Get repository information
        fork_repo, upstream_repo, is_fork = get_repo_info(verbose)

        # Create branch and commit
        run(["git", "checkout", "-b", temp_branch], quiet=True)
        if verbose:
            print(f'Committing: "{commit_message}"')
        run(["git", "commit", "-m", commit_message], quiet=True)

        # Push to remote
        if verbose:
            print(f"Pushing branch '{temp_branch}' to '{fork_repo}'...")
        run(["git", "push", "-u", "origin", temp_branch], quiet=True)

        # Switch back to original branch
        run(["git", "checkout", original_branch], quiet=True)
        if verbose:
            print(f"Switched back to original branch: '{original_branch}'")

        if interactive:
            # Build and display compare URL for manual PR creation
            compare_url = build_compare_url(
                upstream_repo, fork_repo, temp_branch, is_fork
            )
            print(f"PR creation URL: {compare_url}")
        else:
            # Create PR automatically
            pr_url = create_github_pr(
                upstream_repo,
                fork_repo,
                temp_branch,
                commit_message,
                body,
                is_fork,
                verbose,
            )

            # Handle merge options
            if merge:
                merge_pr(
                    pr_url,
                    commit_message,
                    merge_method,
                    upstream_repo,
                    temp_branch,
                    verbose,
                )
            elif auto_merge:
                enable_auto_merge(pr_url, commit_message, merge_method, verbose)
            else:
                if not verbose:
                    print(f"PR created: {pr_url}")

    except Exception:
        # Try to go back on error and show helpful state information
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            ).stdout.strip()

            print("\nError occurred. Current state:", file=sys.stderr)
            print(f"  Current branch: '{current}'", file=sys.stderr)

            if current != original_branch:
                print(
                    f"  Attempting to switch back to: '{original_branch}'",
                    file=sys.stderr,
                )
                subprocess.run(
                    ["git", "checkout", original_branch], capture_output=True
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="acp",
        usage="acp pr <commit message>",
        description="acp - create PRs in one command",
        add_help=False,
    )

    parser.add_argument("command", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("message", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show detailed output"
    )
    parser.add_argument(
        "-b", "--body", type=str, default="", help="Custom PR body message"
    )
    parser.add_argument(
        "-i", "--interactive", action="store_true", help="Show PR creation URL"
    )
    parser.add_argument(
        "--merge", action="store_true", help="Merge PR immediately after creation"
    )
    parser.add_argument(
        "--auto-merge",
        action="store_true",
        help="Enable auto-merge (merge when checks pass)",
    )
    parser.add_argument(
        "--merge-method",
        type=str,
        default="squash",
        choices=["merge", "squash", "rebase"],
        help="Merge method: squash (default), merge, or rebase",
    )
    parser.add_argument("-h", "--help", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.version:
        print(f"acp version {__version__}")
        sys.exit(0)

    if args.help or not args.command:
        show_help()
        sys.exit(0)

    if args.command != "pr" or not args.message:
        show_help()
        sys.exit(1)

    try:
        create_pr(
            args.message,
            verbose=args.verbose,
            body=args.body,
            interactive=args.interactive,
            merge=args.merge,
            auto_merge=args.auto_merge,
            merge_method=args.merge_method,
        )
    except KeyboardInterrupt:
        print("\n\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
