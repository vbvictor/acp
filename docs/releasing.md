# Releasing acp

## GitHub Actions

1. Go to **Actions -> Prepare Release -> Run workflow**.
2. Enter the new version (`X.Y.Z`, must be greater than the current version in `pyproject.toml`) and run.

Requires push access to the repository (`workflow_dispatch` is restricted to collaborators
with write access).

## Locally

```bash
python tools/release.py X.Y.Z
```
