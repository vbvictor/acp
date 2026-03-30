#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}pass $1${NC}"; }
fail() { echo -e "${RED}fail $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}info $1${NC}"; }

pip install -e . --quiet

# Get argcomplete completions for a given command line.
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

# Assert that a completion result contains a value.
assert_has() {
    local completions="$1" value="$2" context="$3"
    [[ "$completions" == *"$value"* ]] || fail "$context: '$value' not found"
}

# Assert that a completion result does NOT contain a value.
assert_not_has() {
    local completions="$1" value="$2" context="$3"
    [[ "$completions" != *"$value"* ]] || fail "$context: '$value' should not be present"
}

# =============================================================================
# Syntax validation via register-python-argcomplete
# =============================================================================

if register-python-argcomplete --shell bash acp | bash -n; then pass "Bash syntax valid"; else fail "Bash syntax invalid"; fi
if register-python-argcomplete --shell zsh acp | zsh -n; then pass "Zsh syntax valid"; else fail "Zsh syntax invalid"; fi
if register-python-argcomplete --shell fish acp | fish -n; then pass "Fish syntax valid"; else fail "Fish syntax invalid"; fi

# =============================================================================
# Top-level command completions: "acp <TAB>"
# =============================================================================

completions=$(get_completions "acp ")
assert_has "$completions" "pr" "acp <TAB>"
assert_has "$completions" "checkout" "acp <TAB>"
assert_not_has "$completions" ".py" "acp <TAB> (no files)"
pass "acp <TAB>: shows subcommands, no files"

# =============================================================================
# PR subcommand: "acp pr <TAB>" and "acp pr -<TAB>"
# =============================================================================

# "acp pr <TAB>" should show options, not files
completions=$(get_completions "acp pr ")
assert_not_has "$completions" ".py" "acp pr <TAB> (no files)"
pass "acp pr <TAB>: no file completions"

# "acp pr -<TAB>" should show pr-specific options
completions=$(get_completions "acp pr -")
assert_has "$completions" "--verbose" "acp pr -<TAB>"
assert_has "$completions" "--merge" "acp pr -<TAB>"
assert_has "$completions" "--auto-merge" "acp pr -<TAB>"
assert_has "$completions" "--add" "acp pr -<TAB>"
assert_has "$completions" "--reviewers" "acp pr -<TAB>"
assert_has "$completions" "--draft" "acp pr -<TAB>"
assert_has "$completions" "--body" "acp pr -<TAB>"
assert_has "$completions" "--interactive" "acp pr -<TAB>"
assert_has "$completions" "--sync" "acp pr -<TAB>"
assert_has "$completions" "--merge-method" "acp pr -<TAB>"
assert_has "$completions" "-v" "acp pr -<TAB>"
assert_has "$completions" "-a" "acp pr -<TAB>"
assert_has "$completions" "-d" "acp pr -<TAB>"
assert_has "$completions" "-r" "acp pr -<TAB>"
assert_has "$completions" "-s" "acp pr -<TAB>"
assert_has "$completions" "-b" "acp pr -<TAB>"
assert_has "$completions" "-i" "acp pr -<TAB>"
pass "acp pr -<TAB>: shows all pr options"

# --merge-method choices
completions=$(get_completions "acp pr --merge-method ")
assert_has "$completions" "squash" "acp pr --merge-method <TAB>"
assert_has "$completions" "merge" "acp pr --merge-method <TAB>"
assert_has "$completions" "rebase" "acp pr --merge-method <TAB>"
pass "acp pr --merge-method <TAB>: shows choices (squash, merge, rebase)"

# =============================================================================
# Checkout subcommand: "acp checkout <TAB>" should show nothing (no files)
# =============================================================================

completions=$(get_completions "acp checkout ")
assert_not_has "$completions" ".py" "acp checkout <TAB> (no files)"
assert_not_has "$completions" "--merge" "acp checkout <TAB> (no pr options)"
assert_not_has "$completions" "--verbose" "acp checkout <TAB> (no pr options)"
assert_not_has "$completions" "--add" "acp checkout <TAB> (no pr options)"
pass "acp checkout <TAB>: no file or pr option completions"

# "acp checkout -<TAB>" should show checkout options, not pr options
completions=$(get_completions "acp checkout -")
assert_has "$completions" "--fetch" "acp checkout -<TAB>"
assert_has "$completions" "-f" "acp checkout -<TAB>"
assert_not_has "$completions" "--merge" "acp checkout -<TAB> (no pr options)"
assert_not_has "$completions" "--verbose" "acp checkout -<TAB> (no pr options)"
assert_not_has "$completions" "--add" "acp checkout -<TAB> (no pr options)"
assert_not_has "$completions" "--reviewers" "acp checkout -<TAB> (no pr options)"
pass "acp checkout -<TAB>: shows checkout options, no pr options leak"

echo ""
echo -e "${GREEN}All completion tests passed!${NC}"
