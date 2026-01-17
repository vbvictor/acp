# acp - Automatic Commit Pusher

[![Release](https://img.shields.io/github/v/release/vbvictor/acp)](https://github.com/vbvictor/acp/releases/latest)
[![Python Tests](https://github.com/vbvictor/acp/actions/workflows/tests.yaml/badge.svg)](https://github.com/vbvictor/acp/actions/workflows/tests.yaml)
[![Code Lint](https://github.com/vbvictor/acp/actions/workflows/code-lint.yaml/badge.svg)](https://github.com/vbvictor/acp/actions/workflows/code-lint.yaml)
[![Code Format](https://github.com/vbvictor/acp/actions/workflows/code-format.yaml/badge.svg)](https://github.com/vbvictor/acp/actions/workflows/code-format.yaml)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-GPLv2-blue.svg)](https://github.com/vbvictor/acp/blob/main/LICENSE)

Turn your staged changes into a GitHub pull request with a single command. \
No more branch naming, no browser tabs, no clicking through forms.

```bash
git add .
acp pr "fix: typo in readme"
PR created: https://github.com/vbvictor/acp/pull/12
```

That's it. PR created, you're back on your original branch.

## What it does

When you run `acp pr <commit message>`, `acp` will:

1. Validate you have staged changes
2. Create a temporary branch `acp/{your-github-username}/{random-16-digits}`
3. Commit your staged changes with your message
4. Push the branch to origin repo
5. Create a pull request to upstream if present of origin otherwise.
6. Switch you back to your original branch
7. Print the PR URL

The tool can also merge freshly created PR via `--merge` or `--auto-merge` options, see `--help` for more information.

## Getting Started

**Prerequisites:** [Python 3.9+][python], [Git][git], and [GitHub CLI (gh)][gh]

Authenticate GitHub CLI (if you haven't already):

```bash
gh auth login
```

Install from PyPI via `pip` or `pipx`:

```bash
pip install acp-gh
```

Or install the latest release directly from GitHub via `pip` or `pipx`:

```bash
pip install https://github.com/vbvictor/acp/releases/latest/download/acp_gh-0.7.3-py3-none-any.whl
```

## Usage

Create basic PR:

```bash
git add .
acp pr "fix: correct calculation bug"
```

Create PR body message and run `acp` with verbose output:

```bash
acp pr "fix: resolve issue" -b "Closes #123" -v
```

Skip automatic PR creation and have a GitHub link to crate PR manually:

```bash
acp pr "feat: new feature" --interactive
```

Merge PR immediately after creation or use GitHub [auto-merge][auto-merge] feature:

```bash
# Squash and merge immediately (default merge method)
acp pr "fix: urgent hotfix" --merge

# Use different merge methods: merge, squash, or rebase
acp pr "fix: hotfix" --merge --merge-method merge
acp pr "feat: feature" --auto-merge --merge-method rebase
```

When merging branch immediately, temporary local branch and \
remote tracking branch will also be deleted to keep workspace clean.

## Contributing

Contributions welcome! Please open an issue if you have an idea or submit a pull request.

### Developer environment

To create a virtual environment, install dev dependencies, and run tests:

```bash
make activate # Create venv and install dev dependencies
make test     # Run tests
make lint     # Run ruff/black
```

### Submit your PR

Use `acp` itself to create your PR:

```bash
git add .
acp pr "feat: your awesome feature"
```

## License

[GPLv2](LICENSE)

[python]: https://www.python.org/
[git]: https://git-scm.com/
[gh]: https://cli.github.com/
[auto-merge]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request
