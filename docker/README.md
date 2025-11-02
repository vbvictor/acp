# Docker Setup for ACP Integration Tests

This directory contains Docker configuration for running ACP integration tests in an isolated environment.

## Quick Start

```bash
# Set your GitHub token
export GITHUB_TOKEN=$(gh auth token)

# Run integration tests
make test-all
```

Or manually:

```bash
docker build -f docker/Dockerfile.integration -t acp-integration-test .
docker run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -v $(pwd):/app \
  acp-integration-test pytest test_integration.py -v -m integration
```

## Files

- **Dockerfile.integration**: Docker image with Python, git, and gh CLI

## Usage

### Building the Image

```bash
docker build -f docker/Dockerfile.integration -t acp-integration-test .
```

### Running Tests

```bash
docker run --rm \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -v $(pwd):/app \
  acp-integration-test pytest test_integration.py -v -m integration
```

## Environment Variables

- `GITHUB_TOKEN` (required): Your GitHub personal access token

For more information, see [docs/INTEGRATION_TESTING.md](../docs/INTEGRATION_TESTING.md).
