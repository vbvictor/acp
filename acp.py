#!/usr/bin/env python3

import argparse
import json
import random
import subprocess
import sys


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
    print("usage: acp pr <commit message> [-b <pr body>]")
    print()
    print("Automatic Commit Pusher - create PRs in one command")
    print()
    print("Options:")
    print("  -h, --help            Show this help message")
    print("  -v, --verbose         Show detailed output")
    print("  -b, --body <text>     Custom PR body message")
    print()
    print("Examples:")
    print('  acp pr "fix: some typo"')
    print('  acp pr "fix: bug" -b "Closes issue #123"')


def create_pr(commit_message, verbose=False, body=""):
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
        # Get repo info first
        repo_json = run(
            ["gh", "repo", "view", "--json", "parent,nameWithOwner"], quiet=True
        )
        if not repo_json:
            print("Error: Could not get repository info", file=sys.stderr)
            sys.exit(1)

        repo_info = json.loads(repo_json)
        current_repo = repo_info.get("nameWithOwner")
        parent = repo_info.get("parent")
        if parent:
            upstream = parent.get("nameWithOwner")
        else:
            upstream = current_repo

        if not upstream:
            print("Error: Could not determine upstream repository", file=sys.stderr)
            sys.exit(1)

        # Create branch and commit
        run(["git", "checkout", "-b", temp_branch], quiet=True)
        if verbose:
            print(f"Committing: {commit_message}")
        run(["git", "commit", "-m", commit_message], quiet=True)

        # Push
        if verbose:
            print(f"Pushing {temp_branch} to {current_repo}...")
        run(["git", "push", "-u", "origin", temp_branch], quiet=True)

        if verbose:
            print(f"Creating PR to: {upstream}")

        # Create PR
        pr_url = run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                upstream,
                "--title",
                commit_message,
                "--body",
                body,
                "--head",
                temp_branch,
            ],
            quiet=True,
        )

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
        description="Automatic Commit Pusher - create PRs in one command",
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
    parser.add_argument("-h", "--help", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.help or not args.command:
        show_help()
        sys.exit(0)

    if args.command != "pr" or not args.message:
        show_help()
        sys.exit(1)

    try:
        create_pr(args.message, verbose=args.verbose, body=args.body)
    except KeyboardInterrupt:
        print("\n\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
