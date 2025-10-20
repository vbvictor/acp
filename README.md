# acp - Automatic Commit Pusher

[![Python Tests](https://github.com/vbvictor/acp/actions/workflows/tests.yaml/badge.svg)](https://github.com/vbvictor/acp/actions/workflows/python-tests.yaml)
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
2. Create a temporary branch `pr/{your-github-username}/{random-16-digits}`
3. Commit your staged changes with your message
4. Push the branch to origin repo
5. Create a pull request to upstream if present of origin otherwise.
6. Switch you back to your original branch
7. Print the PR URL

## Getting Started

**Prerequisites:** [Python 3.9+][python], [Git][git], and [GitHub CLI (gh)][gh]

Install from source:

```bash
git clone https://github.com/vbvictor/acp.git
cd acp
pip install .
# or install into venv
pipx install .
```

Authenticate GitHub CLI (if you haven't already):

```bash
gh auth login
```

## Usage

Basic usage:

```bash
git add .
acp pr "fix: correct calculation bug"
```

With a PR body message and verbose output:

```bash
acp pr "fix: resolve issue" -b "Closes #123" -v
```

Review PR before final submission (interactive mode):

```bash
acp pr "feat: new feature" -i
```

The `-i` (`--interactive`) flag skips automatic PR creation and instead gives you a GitHub link. \
This lets you review the changes, edit the PR title/description, and publish it manually.

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

### Running tests

Create a virtual environment, install dev dependencies, and run tests:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
pytest test_acp.py -v
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
