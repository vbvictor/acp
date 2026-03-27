.PHONY: help activate test test-completions lint format install clean

help:
	@echo "Available targets:"
	@echo ""
	@echo "  make activate          - Create venv and install dev dependencies"
	@echo "  make test              - Run unit tests"
	@echo "  make test-completions  - Run shell completion tests in Docker"
	@echo "  make lint              - Run linters"
	@echo "  make format            - Format code"
	@echo "  make install           - Install acp with pipx from current branch"
	@echo "  make clean             - Clean up test artifacts"

activate:
	@echo "Setting up development environment..."
	python3 -m venv venv
	venv/bin/pip install -e ".[dev]"
	@echo "Done!"

test:
	@echo "Running tests..."
	venv/bin/pytest test_acp.py -v

test-completions:
	docker build -t acp-completions-test -f tests/completions/Dockerfile .
	docker run --rm acp-completions-test

format:
	@echo "Formatting Python files..."
	venv/bin/black .

lint:
	@failed=""; \
	output=$$(venv/bin/black --check --color . 2>&1) || { echo "$$output"; failed="$$failed black"; }; \
	output=$$(FORCE_COLOR=1 venv/bin/ruff check . 2>&1) || { echo "$$output"; failed="$$failed ruff"; }; \
	output=$$(venv/bin/yamllint -f colored -c .yamllint.yaml .github/ 2>&1) || { echo "$$output"; failed="$$failed yamllint"; }; \
	output=$$(venv/bin/zizmor --color=always --config .zizmor.yml .github/workflows/ 2>&1) || { echo "$$output"; failed="$$failed zizmor"; }; \
	output=$$(venv/bin/shellcheck --color=always tests/completions/test_completions.sh 2>&1) || { echo "$$output"; failed="$$failed shellcheck"; }; \
	output=$$(venv/bin/mypy --color-output acp.py 2>&1) || { echo "$$output"; failed="$$failed mypy"; }; \
	if [ -n "$$failed" ]; then \
		msg="FAILED LINTERS:$$failed"; \
		line=$$(printf '%*s' $${#msg} '' | tr ' ' '-'); \
		echo "\n$$line"; \
		echo "$$msg"; \
		echo "$$line"; \
		exit 1; \
	else \
		echo "All linters passed."; \
	fi

install:
	pipx install . --force

clean:
	rm -rf __pycache__/ .pytest_cache/
	rm -rf *.egg-info/
	rm -f test_integration_file.txt
