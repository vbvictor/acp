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

# Syntax validation via register-python-argcomplete
if register-python-argcomplete --shell bash acp | bash -n; then pass "Bash syntax valid"; else fail "Bash syntax invalid"; fi
if register-python-argcomplete --shell zsh acp | zsh -n; then pass "Zsh syntax valid"; else fail "Zsh syntax invalid"; fi
if register-python-argcomplete --shell fish acp | fish -n; then pass "Fish syntax valid"; else fail "Fish syntax invalid"; fi

# Syntax validation via 'acp completions' subcommand
if python acp.py completions bash | bash -n; then pass "acp completions bash syntax valid"; else fail "acp completions bash syntax invalid"; fi
if python acp.py completions zsh | zsh -n; then pass "acp completions zsh syntax valid"; else fail "acp completions zsh syntax invalid"; fi
if python acp.py completions fish | fish -n; then pass "acp completions fish syntax valid"; else fail "acp completions fish syntax invalid"; fi

echo ""
echo -e "${GREEN}All completion tests passed!${NC}"
