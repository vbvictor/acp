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
    print("usage: acp pr <commit message> [-b <body>] [-i]")
    print()
    print("acp - create PRs in one command")
    print()
    print("Options:")
    print("  -b, --body <text>     Custom PR body message")
    print("  -i, --interactive     Show PR creation URL instead of creating PR")
    print("  -v, --verbose         Show detailed output")
    print("  -h, --help            Show this help message")
    print("  --version             Show version number")
    print()
    print("Examples:")
    print('  acp pr "fix: some typo" -i')
    print('  acp pr "fix: bug" -b "Closes issue #123"')

def create_pr(commit_message, verbose=False, body="", interactive=False):
    """Create a PR with staged changes."""
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

            # Go back
            run(["git", "checkout", original_branch], quiet=True)
            if verbose:
                print(f"Switched back to original branch: {original_branch}")

            print(f"PR created: {pr_url}")

    except Exception:
        # Try to go back on error
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            if current != original_branch:
                subprocess.run(
                    ["git", "checkout", original_branch], capture_output=True
                )
        except Exception:
            pass
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
        )
    except KeyboardInterrupt:
        print("\n\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
