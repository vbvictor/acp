#!/usr/bin/env python3
"""Release automation script for acp.

This script automates the release process:
1. Updates version in pyproject.toml, acp.py, and README.md
2. Creates a release commit
3. Pushes directly to main using acp --merge
4. Creates and pushes a version tag
5. Triggers GitHub Actions to create the release

Usage:
    python tools/release.py <version>

Example:
    python tools/release.py 0.4.0
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True, capture_output=True):
    """Run a shell command and return the result."""
    result = subprocess.run(
        cmd,
        shell=True,
        check=check,
        capture_output=capture_output,
        text=True,
    )
    return result


def validate_version(version):
    """Validate version format (semver: X.Y.Z)."""
    pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(pattern, version):
        print(f"Error: Invalid version format '{version}'", file=sys.stderr)
        print("Version must be in format X.Y.Z (e.g., 0.4.0, 1.0.0)", file=sys.stderr)
        sys.exit(1)
    return version


def get_current_version():
    """Get current version from pyproject.toml."""
    toml_path = Path("pyproject.toml")
    content = toml_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if match:
        return match.group(1)
    return None


def update_pyproject_toml(version):
    """Update version in pyproject.toml."""
    toml_path = Path("pyproject.toml")
    content = toml_path.read_text()

    new_content = re.sub(r'version = "[^"]+"', f'version = "{version}"', content)

    toml_path.write_text(new_content)
    print(f'Updated pyproject.toml: version = "{version}"')


def update_acp_py(version):
    """Update __version__ in acp.py."""
    acp_path = Path("acp.py")
    content = acp_path.read_text()

    new_content = re.sub(
        r'__version__ = "[^"]+"', f'__version__ = "{version}"', content
    )

    acp_path.write_text(new_content)
    print(f'Updated acp.py: __version__ = "{version}"')


def update_readme(version):
    """Update version in README.md installation URLs."""
    readme_path = Path("README.md")
    content = readme_path.read_text()

    new_content = re.sub(
        r"acp-\d+\.\d+\.\d+-py3-none-any\.whl",
        f"acp-{version}-py3-none-any.whl",
        content,
    )

    readme_path.write_text(new_content)
    print(f"Updated README.md: acp-{version}-py3-none-any.whl")


def check_git_status():
    """Check if git working directory is clean."""
    result = run_command("git status --porcelain", check=False)
    if result.stdout.strip():
        lines = result.stdout.strip().split("\n")
        allowed_files = {"pyproject.toml", "acp.py", "README.md"}
        for line in lines:
            filename = line[3:].strip()
            if filename not in allowed_files:
                print("Error: Working directory is not clean", file=sys.stderr)
                print(f"Uncommitted changes found in: {filename}", file=sys.stderr)
                print("Please commit or stash your changes first", file=sys.stderr)
                sys.exit(1)


def check_on_main_branch():
    """Check if currently on main branch."""
    result = run_command("git branch --show-current", check=False)
    branch = result.stdout.strip()
    if branch != "main":
        print(f"Error: Not on main branch (currently on '{branch}')", file=sys.stderr)
        print("Please switch to main branch first: git checkout main", file=sys.stderr)
        sys.exit(1)


def check_acp_installed():
    """Check if acp is installed and available."""
    result = run_command("which acp", check=False)
    if result.returncode != 0:
        print("Error: acp is not installed or not in PATH", file=sys.stderr)
        print("Please install acp first: pip install -e .", file=sys.stderr)
        sys.exit(1)


def stage_files():
    """Stage the modified files."""
    run_command("git add pyproject.toml acp.py README.md")
    print("Staged modified files")


def create_pr_and_merge(version):
    """Create PR and merge it immediately using acp."""
    commit_message = f"chore: bump version to {version}"

    print(f"\nCreating PR with acp: '{commit_message}'")

    result = run_command(
        f'acp pr "{commit_message}" --merge --merge-method squash -v',
        check=False,
        capture_output=False,
    )

    if result.returncode != 0:
        print("\nError: Failed to create or merge PR", file=sys.stderr)
        sys.exit(1)

    print("\nPR created and merged successfully")


def create_and_push_tag(version):
    """Create and push the version tag."""
    tag_name = f"v{version}"

    print("\nFetching latest changes from remote...")
    result = run_command("git fetch origin main", check=False)
    if result.returncode != 0:
        print("Error: Failed to fetch from remote", file=sys.stderr)
        sys.exit(1)

    print("Syncing with origin/main...")
    result = run_command("git reset --hard origin/main", check=False)
    if result.returncode != 0:
        print("Error: Failed to sync with origin/main", file=sys.stderr)
        sys.exit(1)

    result = run_command(f"git tag -l {tag_name}", check=False)
    if result.stdout.strip():
        print(f"Warning: Tag {tag_name} already exists locally")
        response = input("Delete and recreate? [y/N]: ")
        if response.lower() == "y":
            run_command(f"git tag -d {tag_name}")
            print(f"Deleted local tag {tag_name}")
        else:
            print("Aborted")
            sys.exit(1)

    print(f"\nCreating tag {tag_name}...")
    result = run_command(f'git tag -a {tag_name} -m "Release {tag_name}"', check=False)
    if result.returncode != 0:
        print(f"Error: Failed to create tag {tag_name}", file=sys.stderr)
        sys.exit(1)

    print(f"Created tag {tag_name}")

    print(f"\nPushing tag {tag_name} to remote...")
    result = run_command(
        f"git push origin {tag_name}", check=False, capture_output=False
    )
    if result.returncode != 0:
        print(f"Error: Failed to push tag {tag_name}", file=sys.stderr)
        print("You may need to delete the remote tag first:", file=sys.stderr)
        print(f"  git push origin --delete {tag_name}", file=sys.stderr)
        sys.exit(1)

    print(f"Pushed tag {tag_name}")


def main():
    """Main release automation workflow."""
    parser = argparse.ArgumentParser(
        description="Automate the acp release process",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/release.py 0.4.0
  python tools/release.py 1.0.0

Prerequisites:
  - On main branch with clean working directory
  - acp installed (pip install -e .)

The script updates version files, creates a PR, merges it,
creates a tag, and triggers GitHub Actions for release.
        """,
    )
    parser.add_argument(
        "version",
        help="version number (X.Y.Z format)",
    )

    args = parser.parse_args()

    new_version = validate_version(args.version)
    current_version = get_current_version()

    print("ACP Release Automation")
    print("=" * 50)
    print(f"Current version: {current_version}")
    print(f"New version:     {new_version}")
    print("=" * 50)

    response = input(f"\nProceed with release {new_version}? [y/N]: ")
    if response.lower() != "y":
        print("Release cancelled")
        sys.exit(0)

    print("\nRunning pre-flight checks...")
    check_on_main_branch()
    check_git_status()
    check_acp_installed()
    print("All pre-flight checks passed")

    print("\nUpdating version files...")
    update_pyproject_toml(new_version)
    update_acp_py(new_version)
    update_readme(new_version)

    print("\nStaging files...")
    stage_files()

    print("\nCreating and merging PR...")
    create_pr_and_merge(new_version)

    print("\nCreating and pushing tag...")
    create_and_push_tag(new_version)

    print("\n" + "=" * 50)
    print(f"Release {new_version} completed successfully")
    print("=" * 50)
    print("\nGitHub Actions will now build and publish the release")
    print("Workflow: https://github.com/vbvictor/acp/actions/workflows/release.yaml")
    print(f"Release: https://github.com/vbvictor/acp/releases/tag/v{new_version}")
    print("\nNote: You can edit the release notes on GitHub to add changelog details")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nRelease cancelled by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)
