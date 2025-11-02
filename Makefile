.PHONY: help test test-all clean

# Default target
help:
	@echo "ACP - Automatic Commit Pusher"
	@echo ""
	@echo "Available targets:"
	@echo "  make test      - Run unit tests (fast, local)"
	@echo "  make test-all  - Run unit + integration tests in Docker"
	@echo "  make clean     - Clean up test artifacts"

# Unit tests (fast, local, no GitHub token needed)
test:
	@echo "Running unit tests..."
	pytest test_acp.py -v

# Run both unit and integration tests
test-all: test
	@echo ""
	@echo "Running integration tests in Docker..."
	@if [ -z "$$GITHUB_TOKEN" ]; then \
		echo "ERROR: GITHUB_TOKEN environment variable not set"; \
		echo "Set it with: export GITHUB_TOKEN=\$$(gh auth token)"; \
		exit 1; \
	fi
	@docker build -f docker/Dockerfile.integration -t acp-integration-test . > /dev/null 2>&1
	docker run --rm \
		-e GITHUB_TOKEN="$$GITHUB_TOKEN" \
		-v $$(pwd):/app \
		acp-integration-test pytest test_integration.py -v -m integration --tb=short
	@echo ""
	@echo "✅ All tests completed (unit + integration)!"

# Clean up test artifacts
clean:
	@echo "Cleaning up test artifacts..."
	@find . -type f -name "test_integration_file.txt" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@docker rmi acp-integration-test 2>/dev/null || true
	@echo "Cleanup completed!"
