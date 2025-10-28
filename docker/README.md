# Docker Setup for ACP Integration Tests

This directory contains Docker configuration for running ACP integration tests in an isolated environment.

## Quick Start

```bash
# Set your GitHub token
export GITHUB_TOKEN="your_github_token"

# Run tests with Docker Compose
docker-compose -f docker/docker-compose.integration.yml up --build
```

## Files

- **Dockerfile.integration**: Docker image with Python, git, and gh CLI
- **docker-compose.integration.yml**: Compose configuration for easy test execution

## Usage

### Building the Image

```bash
docker build -f docker/Dockerfile.integration -t acp-integration-test .
```

### Running Tests

**With Docker:**
```bash
docker run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e ACP_TEST_ORG="your-test-org" \
  -e ACP_TEST_FORK_OWNER="your-username" \
  acp-integration-test
```

**With Docker Compose:**
```bash
# Run all tests
docker-compose -f docker/docker-compose.integration.yml up

# Run specific test
docker-compose -f docker/docker-compose.integration.yml run --rm integration-test \
  pytest test_integration.py::TestIntegrationNonFork -v
```

## Environment Variables

- `GITHUB_TOKEN` (required): Your GitHub personal access token
- `ACP_TEST_ORG` (optional): Test organization name (default: acp-integration-test)
- `ACP_TEST_REPO` (optional): Non-fork test repo (default: test-repo)
- `ACP_TEST_UPSTREAM` (optional): Upstream repo for fork tests (default: upstream-repo)
- `ACP_TEST_FORK_OWNER` (optional): Fork owner username (default: test-user)

## Development

The docker-compose setup mounts source files as read-only volumes, so you can edit code locally and re-run tests without rebuilding:

```bash
# Edit acp.py or test_integration.py locally
vim acp.py

# Re-run tests (no rebuild needed)
docker-compose -f docker/docker-compose.integration.yml run --rm integration-test
```

For more information, see [docs/INTEGRATION_TESTING.md](../docs/INTEGRATION_TESTING.md).
