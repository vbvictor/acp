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
import os
import re
import subprocess
import sys
import tempfile
import time
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
        r"acp_gh-\d+\.\d+\.\d+-py3-none-any\.whl",
        f"acp_gh-{version}-py3-none-any.whl",
        content,
    )

    readme_path.write_text(new_content)
    print(f"Updated README.md: acp_gh-{version}-py3-none-any.whl")


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


def check_acp_exists():
    """Check if acp.py exists in the current directory."""
    acp_path = Path("acp.py")
    if not acp_path.exists():
        print("Error: acp.py not found in current directory", file=sys.stderr)
        print("Please run this script from the repository root", file=sys.stderr)
        sys.exit(1)


def stage_files():
    """Stage the modified files."""
    run_command("git add pyproject.toml acp.py README.md")
    print("Staged modified files")


def create_pr_and_merge(version):
    """Create PR and merge it immediately using local acp.py.

    Always uses --sync to ensure the current branch is updated with the merge.
    """
    commit_message = f"chore: bump version to {version}"

    print(f"\nCreating PR with acp: '{commit_message}'")

    result = run_command(
        f'python acp.py pr "{commit_message}" --merge --merge-method squash -v -s',
        check=False,
        capture_output=False,
    )

    if result.returncode != 0:
        print("\nError: Failed to create or merge PR", file=sys.stderr)
        sys.exit(1)

    print("\nPR created and merged successfully")


def create_and_push_tag(version):
    """Create and push the version tag.

    Assumes the current branch is already synced (via acp --merge -s).
    """
    tag_name = f"v{version}"

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


def get_previous_tag(current_tag):
    """Get the tag immediately before current_tag."""
    result = run_command(
        f"git describe --abbrev=0 --tags {current_tag}^",
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def generate_filtered_changelog(version):
    """Generate changelog with only feat: and fix: commits since the previous tag."""
    current_tag = f"v{version}"
    previous_tag = get_previous_tag(current_tag)

    if previous_tag:
        range_spec = f"{previous_tag}..{current_tag}"
        print(f"Changelog range: {previous_tag} → {current_tag}")
    else:
        range_spec = current_tag
        print(f"Changelog range: all commits up to {current_tag}")

    result = run_command(
        f"git log {range_spec} --pretty=format:%s",
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    commits = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    features = [c for c in commits if re.match(r"^feat(?:\([^)]*\))?:", c)]
    fixes = [c for c in commits if re.match(r"^fix(?:\([^)]*\))?:", c)]

    parts = []
    if features:
        parts.append("## What's New")
        for feat in features:
            desc = re.sub(r"^feat(?:\([^)]*\))?:\s*", "", feat)
            parts.append(f"- {desc}")
        parts.append("")

    if fixes:
        parts.append("## Bug Fixes")
        for fix in fixes:
            desc = re.sub(r"^fix(?:\([^)]*\))?:\s*", "", fix)
            parts.append(f"- {desc}")
        parts.append("")

    return "\n".join(parts) if parts else None


def update_release_with_filtered_notes(version):
    """Wait for the GitHub release to be created and update it with filtered changelog."""
    tag_name = f"v{version}"

    result = run_command(
        "gh repo view --json nameWithOwner -q .nameWithOwner",
        check=False,
    )
    repository = result.stdout.strip() if result.returncode == 0 else ""

    print("\nGenerating filtered changelog (feat: and fix: commits only)...")
    changelog = generate_filtered_changelog(version)

    install_block = f"### Install from PyPI:\n```bash\npip install acp-gh\n```"
    if repository:
        install_block += (
            f"\n\n### Or install directly from GitHub:\n"
            f"```bash\n"
            f"pip install https://github.com/{repository}/releases/download/"
            f"{tag_name}/acp_gh-{version}-py3-none-any.whl\n"
            f"```"
        )

    full_notes = install_block + "\n\n" + (
        changelog if changelog else "No new features or bug fixes in this release.\n"
    )

    print(f"\nWaiting for GitHub release {tag_name} to be created by Actions...")
    max_wait = 300  # 5 minutes
    elapsed = 0
    release_found = False
    while elapsed < max_wait:
        result = run_command(f"gh release view {tag_name}", check=False)
        if result.returncode == 0:
            release_found = True
            print(f"Release {tag_name} found.")
            break
        time.sleep(15)
        elapsed += 15
        print(f"  Still waiting... ({elapsed}s / {max_wait}s)")

    if not release_found:
        print(
            f"\nWarning: Release {tag_name} not found after {max_wait}s.",
            file=sys.stderr,
        )
        print("You can manually update it with the following notes:", file=sys.stderr)
        print("-" * 40)
        print(full_notes)
        return False

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(full_notes)
        notes_file = f.name

    try:
        result = run_command(
            f"gh release edit {tag_name} --notes-file {notes_file}",
            check=False,
            capture_output=False,
        )
        if result.returncode == 0:
            print(f"Release notes for {tag_name} updated successfully.")
            return True
        else:
            print("Failed to update release notes.", file=sys.stderr)
            print("\nFiltered release notes to paste manually:")
            print(full_notes)
            return False
    finally:
        os.unlink(notes_file)


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

The script updates version files, creates a PR, merges it,
creates a tag, and triggers GitHub Actions for release.
Uses the local acp.py script automatically.
        """,
    )
    parser.add_argument(
        "version",
        help="version number (X.Y.Z format)",
    )
    parser.add_argument(
        "--skip-notes-update",
        action="store_true",
        help="skip waiting for GitHub release and updating its notes",
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
    check_acp_exists()
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

    if not args.skip_notes_update:
        update_release_with_filtered_notes(new_version)

    print("\n" + "=" * 50)
    print(f"Release {new_version} completed successfully")
    print("=" * 50)
    print("\nGitHub Actions will now build and publish the release")
    print("Workflow: https://github.com/vbvictor/acp/actions/workflows/release.yaml")
    print(f"Release: https://github.com/vbvictor/acp/releases/tag/v{new_version}")


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
