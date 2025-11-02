.PHONY: help test clean

# Default target
help:
	@echo "ACP - Automatic Commit Pusher"
	@echo ""
	@echo "Available targets:"
	@echo "  make test   - Run unit tests"
	@echo "  make clean  - Clean up test artifacts"

# Unit tests
test:
	@echo "Running unit tests..."
	pytest test_acp.py -v

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	@find . -type f -name "test_integration_file.txt" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "Cleanup completed!"
