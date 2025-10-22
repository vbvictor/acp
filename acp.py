#!/usr/bin/env python3

import argparse
import random
import subprocess
import sys

__version__ = "0.1.1"


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
    print('  acp pr "fix: urgent" -b "Closes issue #123" --merge')
    print('  acp pr "feat: feature" --auto-merge --merge-method rebase')


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
    # Validate merge flags
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

    # Validate merge method
    valid_methods = ["merge", "squash", "rebase"]
    if merge_method not in valid_methods:
        print(
            f"Error: Invalid merge method '{merge_method}'. Must be one of: {', '.join(valid_methods)}",
            file=sys.stderr,
        )
        sys.exit(1)
    # Get current state
    original_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    if verbose:
        print(f"Current branch: {original_branch}")

    # Check for staged changes
    if run_check(["git", "diff", "--cached", "--quiet"]):
        print("Error: No staged changes. Run 'git add' first.", file=sys.stderr)
        sys.exit(1)

    # Get GitHub username and create temp branch name
    gh_user = run(["gh", "api", "user", "--jq", ".login"], quiet=True)
    random_num = random.randint(1000000000000000, 9999999999999999)
    temp_branch = f"pr/{gh_user}/{random_num}"
    if verbose:
        print(f"Creating temporary branch: {temp_branch}")

    try:
        # Get origin remote URL to determine the fork repo
        origin_url = run(["git", "remote", "get-url", "origin"], quiet=True)

        # Extract owner/repo from git URL (handles both SSH and HTTPS)
        # SSH: git@github.com:owner/repo.git
        # HTTPS: https://github.com/owner/repo.git
        if "github.com" in origin_url:
            if origin_url.startswith("git@"):
                # SSH format
                fork_repo = origin_url.split(":")[1].replace(".git", "")
            else:
                # HTTPS format
                fork_repo = "/".join(origin_url.split("/")[-2:]).replace(".git", "")
        else:
            print("Error: Not a GitHub repository", file=sys.stderr)
            sys.exit(1)

        # Check if there's an upstream remote
        upstream_check = subprocess.run(
            ["git", "remote", "get-url", "upstream"], capture_output=True, text=True
        )

        if upstream_check.returncode == 0:
            # Has upstream remote, this is a fork
            upstream_url = upstream_check.stdout.strip()
            if "github.com" in upstream_url:
                if upstream_url.startswith("git@"):
                    upstream_repo = upstream_url.split(":")[1].replace(".git", "")
                else:
                    upstream_repo = "/".join(upstream_url.split("/")[-2:]).replace(
                        ".git", ""
                    )
            else:
                print("upstream repo is not a github.com repo")
                sys.exit(1)
            is_fork = True
        else:
            # No upstream remote, not a fork
            upstream_repo = fork_repo
            is_fork = False

        # Create branch and commit
        run(["git", "checkout", "-b", temp_branch], quiet=True)
        if verbose:
            print(f"Committing: {commit_message}")
        run(["git", "commit", "-m", commit_message], quiet=True)

        # Push
        if verbose:
            print(f"Pushing {temp_branch} to {fork_repo}...")
        run(["git", "push", "-u", "origin", temp_branch], quiet=True)

        if interactive:
            # Build GitHub compare URL for manual PR creation
            upstream_base = upstream_repo.split("/")[-1]  # repo name
            if is_fork:
                fork_owner = fork_repo.split("/")[0]
                # Format: https://github.com/upstream/repo/compare/main...fork-owner:repo:branch?expand=1
                compare_url = f"https://github.com/{upstream_repo}/compare/main...{fork_owner}:{upstream_base}:{temp_branch}?expand=1"
            else:
                # Format: https://github.com/owner/repo/compare/main...branch?expand=1
                compare_url = f"https://github.com/{upstream_repo}/compare/main...{temp_branch}?expand=1"

            # Go back
            run(["git", "checkout", original_branch], quiet=True)
            if verbose:
                print(f"Switched back to original branch: {original_branch}")

            print(f"PR creation URL: {compare_url}")
        else:
            if verbose:
                print(f"Creating PR to: {upstream_repo}")

            # Create PR with correct head format for forks
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

            # Always switch back to original branch first
            run(["git", "checkout", original_branch], quiet=True)
            if verbose:
                print(f"Switched back to original branch: {original_branch}")

            # Handle merge options after switching back
            if merge:
                if verbose:
                    print(f"Merging PR immediately (method: {merge_method})...")

                # Build merge command with the specified method
                merge_cmd = [
                    "gh",
                    "pr",
                    "merge",
                    pr_url,
                    f"--{merge_method}",
                    "--delete-branch",
                ]
                merge_result = subprocess.run(
                    merge_cmd,
                    capture_output=True,
                    text=True,
                )

                if merge_result.returncode != 0:
                    print(f"PR created: {pr_url}")
                    print(
                        f"Error: Failed to merge PR: {merge_result.stderr.strip()}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                print(f'PR "{commit_message}" ({pr_url}) merged!')
            elif auto_merge:
                if verbose:
                    print(
                        f"Enabling auto-merge (method: {merge_method}, will merge when checks pass)..."
                    )

                # Build auto-merge command with the specified method
                merge_cmd = [
                    "gh",
                    "pr",
                    "merge",
                    pr_url,
                    "--auto",
                    f"--{merge_method}",
                    "--delete-branch",
                ]
                merge_result = subprocess.run(
                    merge_cmd,
                    capture_output=True,
                    text=True,
                )

                if merge_result.returncode != 0:
                    print(f"PR created: {pr_url}")
                    print(
                        f"Error: Failed to enable auto-merge: {merge_result.stderr.strip()}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                print(
                    f'PR "{commit_message}" ({pr_url}) will auto-merge when checks pass'
                )
            else:
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
            print(f"  Current branch: {current}", file=sys.stderr)

            if current != original_branch:
                print(
                    f"  Attempting to switch back to: {original_branch}",
                    file=sys.stderr,
                )
                subprocess.run(
                    ["git", "checkout", original_branch], capture_output=True
                )
                print(
                    f"  Successfully switched back to: {original_branch}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"  Already on original branch: {original_branch}", file=sys.stderr
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
