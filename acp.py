#!/usr/bin/env python3

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
    print("usage: acp pr <commit message>")
    print()
    print("Automatic Commit Pusher - create PRs in one command")
    print()
    print("Examples:")
    print('  acp pr "fix: some typo"')
    print('  acp pr "feat: add new feature"')


def create_pr(commit_message):
    """Create a PR with staged changes."""
    # Get current state
    original_branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True)
    print(f"Current branch: {original_branch}")

    # Check for staged changes
    if run_check(["git", "diff", "--cached", "--quiet"]):
        print("Error: No staged changes. Run 'git add' first.", file=sys.stderr)
        sys.exit(1)

    # Get GitHub username and create temp branch name
    gh_user = run(["gh", "api", "user", "--jq", ".login"], quiet=True)
    random_num = random.randint(1000000000000000, 9999999999999999)
    temp_branch = f"pr/{gh_user}/{random_num}"
    print(f"Creating temporary branch: {temp_branch}")

    try:
        # Create branch and commit
        run(["git", "checkout", "-b", temp_branch], quiet=True)
        print(f"Committing: {commit_message}")
        run(["git", "commit", "-m", commit_message], quiet=True)

        # Push
        print(f"Pushing {temp_branch}...")
        run(["git", "push", "-u", "origin", temp_branch], quiet=True)

        # Get upstream repo (handle forks)
        repo_json = run(["gh", "repo", "view", "--json", "parent,nameWithOwner"], quiet=True)
        if not repo_json:
            print("Error: Could not get repository info", file=sys.stderr)
            sys.exit(1)

        repo_info = json.loads(repo_json)
        parent = repo_info.get("parent")
        if parent:
            upstream = parent.get("nameWithOwner")
        else:
            upstream = repo_info.get("nameWithOwner")

        if not upstream:
            print("Error: Could not determine upstream repository", file=sys.stderr)
            sys.exit(1)

        print(f"Creating PR to: {upstream}")

        # Create PR
        pr_url = run([
            "gh", "pr", "create",
            "--repo", upstream,
            "--title", commit_message,
            "--body", f"Automated PR from branch {original_branch}",
            "--head", temp_branch
        ], quiet=True)

        # Go back
        run(["git", "checkout", original_branch], quiet=True)
        print(f"Switched back to original branch: {original_branch}")

        print(f"\n✓ PR created: {pr_url}")

    except Exception:
        # Try to go back on error
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True
            ).stdout.strip()
            if current != original_branch:
                subprocess.run(["git", "checkout", original_branch], capture_output=True)
        except Exception:
            pass
        raise


def main():
    """Main entry point."""
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help"]:
        show_help()
        sys.exit(0)

    if len(sys.argv) < 3 or sys.argv[1] != "pr":
        show_help()
        sys.exit(1)

    try:
        create_pr(sys.argv[2])
    except KeyboardInterrupt:
        print("\n\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
