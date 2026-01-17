.PHONY: help activate test lint clean

# Default target
help:
	@echo "ACP - Automatic Commit Pusher"
	@echo ""
	@echo "Available targets:"
	@echo "  make activate - Create venv and install dev dependencies"
	@echo "  make test     - Run unit tests"
	@echo "  make lint     - Run linters/formatters"
	@echo "  make clean    - Clean up test artifacts"

# Setup dev environment
activate:
	@echo "Setting up development environment..."
	python3 -m venv venv
	venv/bin/pip install -e ".[dev]"
	@echo "Done!"

# Unit tests
test:
	venv/bin/pytest test_acp.py -v

# Format and lint code
lint:
	venv/bin/black .
	venv/bin/ruff check .
	venv/bin/yamllint -c .yamllint.yaml .github/

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	@find . -type f -name "test_integration_file.txt" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "Cleanup completed!"
