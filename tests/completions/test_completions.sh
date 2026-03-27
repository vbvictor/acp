#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}pass $1${NC}"; }
fail() { echo -e "${RED}fail $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}info $1${NC}"; }

# Install acp and argcomplete
pip install -e . --quiet

# Helper: get argcomplete completions for a given command line
# Uses argcomplete's env var protocol: set _ARGCOMPLETE=1, COMP_LINE, COMP_POINT,
# then run the program and capture output from fd 8.
get_completions() {
    local comp_line="$1"
    _ARGCOMPLETE=1 \
    _ARGCOMPLETE_IFS=$'\013' \
    COMP_LINE="$comp_line" \
    COMP_POINT=${#comp_line} \
    acp 8>&1 9>&2 1>/dev/null 2>/dev/null || true
}

# Syntax validation via register-python-argcomplete
if register-python-argcomplete --shell bash acp | bash -n; then pass "Bash syntax valid"; else fail "Bash syntax invalid"; fi
if register-python-argcomplete --shell zsh acp | zsh -n; then pass "Zsh syntax valid"; else fail "Zsh syntax invalid"; fi
if register-python-argcomplete --shell fish acp | fish -n; then pass "Fish syntax valid"; else fail "Fish syntax invalid"; fi

# Syntax validation via 'acp completions' subcommand
if python acp.py completions bash | bash -n; then pass "acp completions bash syntax valid"; else fail "acp completions bash syntax invalid"; fi
if python acp.py completions zsh | zsh -n; then pass "acp completions zsh syntax valid"; else fail "acp completions zsh syntax invalid"; fi
if python acp.py completions fish | fish -n; then pass "acp completions fish syntax valid"; else fail "acp completions fish syntax invalid"; fi

# Functional tests: verify argcomplete returns expected completions
# Command completions
completions=$(get_completions "acp ")
[[ "$completions" == *"pr"* ]] || fail "argcomplete: 'pr' not in command completions"
[[ "$completions" == *"checkout"* ]] || fail "argcomplete: 'checkout' not in command completions"
[[ "$completions" == *"completions"* ]] || fail "argcomplete: 'completions' not in command completions"
pass "argcomplete: command completions (pr, checkout, completions)"

# Option completions for 'acp pr'
completions=$(get_completions "acp pr -")
[[ "$completions" == *"--verbose"* ]] || fail "argcomplete: '--verbose' not in pr option completions"
[[ "$completions" == *"--merge"* ]] || fail "argcomplete: '--merge' not in pr option completions"
[[ "$completions" == *"--add"* ]] || fail "argcomplete: '--add' not in pr option completions"
[[ "$completions" == *"--reviewers"* ]] || fail "argcomplete: '--reviewers' not in pr option completions"
[[ "$completions" == *"--draft"* ]] || fail "argcomplete: '--draft' not in pr option completions"
pass "argcomplete: pr option completions (--verbose, --merge, --add, --reviewers, --draft)"

# --merge-method choices
completions=$(get_completions "acp pr --merge-method ")
[[ "$completions" == *"squash"* ]] || fail "argcomplete: 'squash' not in --merge-method completions"
[[ "$completions" == *"merge"* ]] || fail "argcomplete: 'merge' not in --merge-method completions"
[[ "$completions" == *"rebase"* ]] || fail "argcomplete: 'rebase' not in --merge-method completions"
pass "argcomplete: --merge-method choices (squash, merge, rebase)"

echo ""
echo -e "${GREEN}All completion tests passed!${NC}"
