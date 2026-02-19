#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}pass $1${NC}"; }
fail() { echo -e "${RED}fail $1${NC}"; exit 1; }
info() { echo -e "${YELLOW}info $1${NC}"; }

# Syntax validation
python acp.py completions bash | bash -n && pass "Bash syntax valid" || fail "Bash syntax invalid"
python acp.py completions zsh | zsh -n && pass "Zsh syntax valid" || fail "Zsh syntax invalid"
python acp.py completions fish | fish -n && pass "Fish syntax valid" || fail "Fish syntax invalid"

# Bash functional tests
eval "$(python acp.py completions bash)"

# Command completion
COMP_WORDS=(acp ""); COMP_CWORD=1; _acp
[[ " ${COMPREPLY[*]} " =~ " pr " ]] || fail "Bash: 'pr' not in command completions"
[[ " ${COMPREPLY[*]} " =~ " checkout " ]] || fail "Bash: 'checkout' not in command completions"
[[ " ${COMPREPLY[*]} " =~ " completions " ]] || fail "Bash: 'completions' not in command completions"
pass "Bash: command completion (pr, checkout, completions)"

# Option completion with -- prefix
COMP_WORDS=(acp pr --); COMP_CWORD=2; _acp
[[ " ${COMPREPLY[*]} " =~ " --merge " ]] || fail "Bash: '--merge' not in option completions"
[[ " ${COMPREPLY[*]} " =~ " --verbose " ]] || fail "Bash: '--verbose' not in option completions"
[[ " ${COMPREPLY[*]} " =~ " --add " ]] || fail "Bash: '--add' not in option completions"
[[ " ${COMPREPLY[*]} " =~ " --reviewers " ]] || fail "Bash: '--reviewers' not in option completions"
pass "Bash: option completion (--merge, --verbose, --add, --reviewers)"

# 'acp pr <TAB>' shows options without -- prefix
COMP_WORDS=(acp pr ""); COMP_CWORD=2; _acp
[[ " ${COMPREPLY[*]} " =~ " --merge " ]] || fail "Bash: '--merge' not in 'acp pr <TAB>' completions"
[[ " ${COMPREPLY[*]} " =~ " --verbose " ]] || fail "Bash: '--verbose' not in 'acp pr <TAB>' completions"
[[ " ${COMPREPLY[*]} " =~ " -v " ]] || fail "Bash: '-v' not in 'acp pr <TAB>' completions"
pass "Bash: 'acp pr <TAB>' shows options without -- prefix"

# Short option completion
COMP_WORDS=(acp pr -); COMP_CWORD=2; _acp
[[ " ${COMPREPLY[*]} " =~ " -v " ]] || fail "Bash: '-v' not in short option completions"
[[ " ${COMPREPLY[*]} " =~ " -b " ]] || fail "Bash: '-b' not in short option completions"
[[ " ${COMPREPLY[*]} " =~ " -a " ]] || fail "Bash: '-a' not in short option completions"
[[ " ${COMPREPLY[*]} " =~ " -r " ]] || fail "Bash: '-r' not in short option completions"
[[ " ${COMPREPLY[*]} " =~ " -s " ]] || fail "Bash: '-s' not in short option completions"
pass "Bash: short option completion (-v, -b, -a, -r, -s)"

# --merge-method values
COMP_WORDS=(acp pr --merge-method ""); COMP_CWORD=3; _acp
[[ " ${COMPREPLY[*]} " =~ " squash " ]] || fail "Bash: 'squash' not in --merge-method completions"
[[ " ${COMPREPLY[*]} " =~ " merge " ]] || fail "Bash: 'merge' not in --merge-method completions"
[[ " ${COMPREPLY[*]} " =~ " rebase " ]] || fail "Bash: 'rebase' not in --merge-method completions"
pass "Bash: --merge-method values (squash, merge, rebase)"

# completions subcommand values
COMP_WORDS=(acp completions ""); COMP_CWORD=2; _acp
[[ " ${COMPREPLY[*]} " =~ " bash " ]] || fail "Bash: 'bash' not in completions values"
[[ " ${COMPREPLY[*]} " =~ " zsh " ]] || fail "Bash: 'zsh' not in completions values"
[[ " ${COMPREPLY[*]} " =~ " fish " ]] || fail "Bash: 'fish' not in completions values"
pass "Bash: completions values (bash, zsh, fish)"

# Partial completion
COMP_WORDS=(acp pr --mer); COMP_CWORD=2; _acp
[[ " ${COMPREPLY[*]} " =~ " --merge " ]] || fail "Bash: '--merge' not in partial completions"
[[ " ${COMPREPLY[*]} " =~ " --merge-method " ]] || fail "Bash: '--merge-method' not in partial completions"
pass "Bash: partial completion (--mer -> --merge, --merge-method)"

echo ""
echo -e "${GREEN}All completion tests passed!${NC}"
