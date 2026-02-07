---
title: Releasing
description: Version management, release workflow, and post-release verification.
---

## Version Management

OAK uses **hatch-vcs** for version management — versions are derived from git tags, not hardcoded in source files.

- Stable releases: `v0.3.0`, `v1.0.0`
- Pre-releases: `v0.3.1-rc.1`, `v0.4.0-beta.1`
- TestPyPI releases: `v0.3.0-testpypi.1`

The version is determined at build time by `hatch-vcs` reading the latest git tag. The `_version.py` file is auto-generated and gitignored.

## Release Workflow

Releases are fully automated via GitHub Actions. The flow is:

1. **Tag the commit**: `git tag v0.3.1 && git push --tags`
2. **GitHub Actions triggers**: The `release.yml` workflow runs on `v*` tags
3. **Build**: Python package (wheel + sdist) with frontend assets
4. **GitHub Release**: Created automatically with generated release notes
5. **PyPI Publish**: Package published to PyPI (or TestPyPI for test tags)

### Workflow Jobs

| Job | Purpose |
|-----|---------|
| `validate-tag` | Extract version, detect pre-release/TestPyPI flags |
| `build-python-package` | Build frontend assets (npm), build Python package |
| `create-release` | Create GitHub Release with artifacts and notes |
| `publish-pypi` | Publish to PyPI (stable releases only) |
| `publish-testpypi` | Publish to TestPyPI (testpypi tags only) |

### Frontend Asset Safety

The release workflow builds frontend assets (the CI dashboard UI) as part of the Python package build. This ensures the published package always contains up-to-date UI assets:

1. Node.js is set up in CI
2. `npm ci && npm run build` runs in the daemon UI directory
3. Built assets are verified before packaging
4. The Python build includes the static assets in the wheel

## Pre-Release Testing with TestPyPI

To test the full publishing pipeline without affecting the real PyPI package:

```bash
# Create a TestPyPI-specific tag
git tag v0.3.1-testpypi.1
git push --tags

# The workflow publishes to TestPyPI instead of PyPI
# Verify with:
pip install --index-url https://test.pypi.org/simple/ oak-ci
```

TestPyPI tags are detected by the `-testpypi` suffix and routed to the `testpypi` environment in GitHub Actions.

## Creating a Release

```bash
# Ensure all checks pass
make check

# Ensure frontend assets are current
make ui-build

# Tag the release
git tag v0.3.1
git push --tags

# Monitor the workflow
gh run watch
```

## Post-Release Verification

After a release completes:

1. **Check GitHub Release**: Verify artifacts are attached and release notes look correct
2. **Check PyPI**: `pip install oak-ci==0.3.1` should work within a few minutes
3. **Smoke test**:
   ```bash
   pipx install oak-ci
   oak --version     # Should show the new version
   oak init --agent claude --no-interactive
   oak ci start
   oak ci status
   ```
4. **Check the release workflow summary** in GitHub Actions for any warnings
