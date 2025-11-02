# Integration Tests - Summary

## What Changed

**Before**: Tests cloned external repos and ran tests there
**Now**: Tests run directly in the acp repository on test branches

## How It Works

1. **No cloning**: Tests use the current acp repo directly
2. **Test file**: Creates `test_integration_file.txt` and stages it
3. **Run acp**: Executes acp command on staged changes
4. **Verify**: Confirms branches/PRs created on GitHub
5. **Cleanup**: Deletes test file and remote branches

## Quick Start

```bash
# 1. Set token
export GITHUB_TOKEN=$(gh auth token)

# 2. Run tests
cd /home/victor/repos/acp
pytest -m integration -v

# Done! ✅
```

## Files Modified

- `test_integration.py` - Simplified to use local repo
- `QUICKSTART_INTEGRATION.md` - Updated instructions

## Test Scenarios

| Test | What it does | Time |
|------|-------------|------|
| `test_create_pr_interactive` | Tests `acp pr -i` (interactive mode) | ~15s |
| `test_create_pr_auto` | Tests auto PR creation and closes it | ~20s |
| `test_verbose_mode` | Tests `acp pr -v` verbose output | ~15s |

## How Each Test Works

```
1. Create test_integration_file.txt
2. git add test_integration_file.txt
3. Run: python acp.py pr "message" [-flags]
4. Verify: Check output for expected text
5. Cleanup: Delete test file, delete remote branch
```

## Expected Output

```
test_integration.py::TestIntegrationNonFork::test_create_pr_interactive PASSED
test_integration.py::TestIntegrationNonFork::test_create_pr_auto PASSED
test_integration.py::TestIntegrationNonFork::test_verbose_mode PASSED

======================== 3 passed in 45.23s ========================
```

## Run Specific Test

```bash
# Just one test
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive -v -m integration

# With output
pytest test_integration.py::TestIntegrationNonFork::test_create_pr_interactive -v -s
```

## What Happens on GitHub

- ✅ Creates test branches (`acp/vbvictor/...`)
- ✅ Creates real PRs (then closes them)
- ✅ Deletes branches after test
- ❌ No mess left behind (usually)

## Cleanup If Needed

```bash
# List test branches
git branch -r | grep acp/

# Delete one
git push origin --delete acp/vbvictor/123456789

# Delete all test branches
git fetch --prune
git branch -r | grep 'origin/acp/' | sed 's|origin/||' | xargs -I {} git push origin --delete {}
```

## Common Issues

| Issue | Fix |
|-------|-----|
| `GITHUB_TOKEN not set` | `export GITHUB_TOKEN=$(gh auth token)` |
| `origin not found` | Check: `git remote -v` |
| Tests fail to auth | Run: `gh auth login` |
| Branches remain | Use cleanup commands above |

## Why This Approach

✅ Faster - no cloning needed
✅ Simpler - uses current repo
✅ Cleaner - less setup required
✅ Better - tests the actual code
✅ Easier - run from any branch

## Notes

- Tests actually modify GitHub (not local simulation)
- Each test takes 10-20 seconds
- Tests clean up after themselves
- Don't run tests in parallel (shared repo)
- If interrupted, may leave branches

## Next Steps

1. ✅ Run integration tests on acp repo
2. 🔄 Later: Add fork testing
3. 🔄 Later: Add to CI/CD
4. 🔄 Later: Add more test scenarios

See `QUICKSTART_INTEGRATION.md` for detailed instructions.
