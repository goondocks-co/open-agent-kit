# GitHub Workflows

This document describes the GitHub Actions workflows used in open-agent-kit.

## Table of Contents

- [Overview](#overview)
- [PR Validation Workflow](#pr-validation-workflow)
- [Release Workflow](#release-workflow)
- [Workflow Configuration](#workflow-configuration)
- [Troubleshooting](#troubleshooting)

## Overview

open-agent-kit uses two main GitHub Actions workflows:

1. **PR Validation** (`.github/workflows/pr-check.yml`)
   - Runs on every pull request
   - Validates code quality, tests, and standards
   - Must pass before PR can be merged

2. **Release** (`.github/workflows/release.yml`)
   - Runs when version tags are pushed
   - Builds and publishes release artifacts
   - Creates GitHub releases automatically

## PR Validation Workflow

**Trigger:** Pull requests to `main` or `develop` branches

**File:** `.github/workflows/pr-check.yml`

### Jobs

#### 1. Lint and Format Check
- **Runs on:** Ubuntu Latest
- **Python:** 3.13
- **Checks:**
  - Ruff linting (`ruff check src/`)
  - Black formatting (`black src/ tests/ --check`)
  - MyPy type checking (`mypy src/`)

#### 2. Test
- **Runs on:** Ubuntu, Windows, macOS
- **Python:** 3.13
- **Matrix strategy:** Tests across OS and Python versions
- **Actions:**
  - Runs pytest with coverage
  - Uploads coverage to Codecov (Ubuntu + Python 3.13 only)

#### 3. Validate Templates
- **Runs on:** Ubuntu Latest
- **Checks:**
  - Markdown linting on RFC templates
  - Markdown linting on command templates
  - Uses markdownlint-cli with `.markdownlint.json` config

#### 4. Integration Test (Smoke)
- **Runs on:** Ubuntu Latest
- **Python:** 3.13
- **Tests:**
  - `oak --version` command works
  - `oak init` command completes
  - Detailed structure validation is in the test suite (`tests/test_cli_init.py`)

#### 5. Check Version
- **Runs on:** Ubuntu Latest
- **Validates:**
  - Version in `pyproject.toml` matches runtime `open_agent_kit.__version__`
  - Prevents version mismatches

#### 6. PR Summary
- **Depends on:** All previous jobs
- **Purpose:** Final status check
- **Fails if:** Any job fails
- **Succeeds if:** All jobs pass

### Status Checks

The following checks must pass:
- ✓ Lint and Format Check
- ✓ Test (all OS/Python combinations)
- ✓ Validate Templates
- ✓ Integration Test
- ✓ Check Version
- ✓ PR Summary

### Running Checks Locally

```bash
# Lint
ruff check src/

# Format check
black src/ tests/ --check

# Type check
mypy src/

# Run tests
pytest --cov=open_agent_kit

# Validate markdown
markdownlint 'features/**/*.md'
```

## Release Workflow

**Trigger:** Tags matching `v[0-9]+.[0-9]+.[0-9]+*`

**File:** `.github/workflows/release.yml`

### Supported Tag Formats

- `v0.1.0` - Stable release
- `v0.1.1` - Patch release
- `v1.0.0` - Major release
- `v0.2.0-beta.1` - Pre-release (beta)
- `v1.0.0-rc.1` - Pre-release (release candidate)
- `v0.1.0-alpha.1` - Pre-release (alpha)

### Jobs

#### 1. Validate Tag
- **Extracts version** from tag (e.g., `v0.1.0` → `0.1.0`)
- **Determines if pre-release** (checks for `-` in version)
- **Verifies version** matches `pyproject.toml`
- **Fails if:** Version mismatch detected

#### 2. Build Python Package
- **Builds:** Wheel and source distribution
- **Verifies:** Package installs correctly
- **Tests:** `oak version` command works
- **Uploads:** Artifacts for release

**Artifacts:**
- `oak-X.Y.Z-py3-none-any.whl`
- `open-agent-kit-X.Y.Z.tar.gz`

#### 3. Create Release
- **Downloads:** All artifacts
- **Generates:** Release notes from git commits
- **Creates:** GitHub release
- **Uploads:** All artifacts to release
- **Marks:** Pre-release flag if applicable

### Release Notes

Auto-generated release notes include:

```markdown
# open-agent-kit X.Y.Z

AI-assisted engineering productivity tools.

## What's Changed

- List of commits since last tag
- Formatted as: "- commit message (author)"

## Installation

### Python Package
...instructions...

### Template Packages
...list of packages...

## Quick Start
...basic usage...

## Documentation
...links...
```

### Triggering a Release

```bash
# 1. Update version in pyproject.toml [project] section
# The open_agent_kit package reads version from pyproject.toml at runtime

# 2. Commit changes
git add pyproject.toml
git commit -m "Bump version to 0.2.0"
git push origin main

# 3. Create and push tag
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0

# 4. Workflow runs automatically
# Go to: https://github.com/sirkirby/open-agent-kit/actions
```

## Workflow Configuration

### Required Permissions

Both workflows require these permissions:

```yaml
permissions:
  contents: write    # Create releases, push tags
  packages: write    # Publish packages
```

### Environment Variables

No special environment variables required. Workflows use:
- `GITHUB_TOKEN` - Auto-provided by GitHub Actions
- `CODECOV_TOKEN` - Optional, for coverage uploads

### Secrets

Set these in: **Settings → Secrets and variables → Actions**

| Secret | Purpose | Required |
|--------|---------|----------|
| `GITHUB_TOKEN` | Auto-provided by GitHub | Yes (automatic) |
| `CODECOV_TOKEN` | Upload test coverage | No (optional) |

## Troubleshooting

### PR Check Failures

#### Lint Errors
```
Error: Ruff found linting errors
```
**Fix:**
```bash
ruff check src/ --fix
git add .
git commit -m "Fix linting errors"
git push
```

#### Format Errors
```
Error: Code not formatted with black
```
**Fix:**
```bash
black src/ tests/
git add .
git commit -m "Format code with black"
git push
```

#### Test Failures
```
Error: pytest failed
```
**Fix:**
```bash
# Run tests locally
pytest -v

# Fix failing tests
# ... make changes ...

git add .
git commit -m "Fix failing tests"
git push
```

#### Version Mismatch
```
Error: Version mismatch between files
```
**Fix:**
```bash
# Version is defined in pyproject.toml [project] section
# open_agent_kit reads version from pyproject.toml at runtime
# Just update pyproject.toml:

git add pyproject.toml
git commit -m "Fix version consistency"
git push
```

### Release Workflow Failures

#### Tag Version Mismatch
```
Error: Version mismatch between tag and files
```
**Fix:**
```bash
# Delete incorrect tag
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0

# Fix version in pyproject.toml
# Edit pyproject.toml [project] section

# Commit and recreate tag
git commit -am "Fix version to 0.2.0"
git push origin main
git tag -a v0.2.0 -m "Release 0.2.0"
git push origin v0.2.0
```

#### Build Failures
```
Error: Package build failed
```
**Fix:**
```bash
# Test build locally
python -m pip install build
python -m build

# Fix any errors
# Commit fixes
# Delete and recreate tag
```

#### Artifact Upload Failed
```
Error: Failed to upload artifacts
```
**Fix:**
- Check workflow logs for specific error
- Verify permissions are correct
- Re-run failed jobs in Actions UI
- If persists, delete release and tag, recreate

### Re-running Workflows

**Re-run PR checks:**
1. Go to PR → Checks tab
2. Click "Re-run jobs"
3. Select "Re-run failed jobs" or "Re-run all jobs"

**Re-run release workflow:**
1. Go to Actions tab
2. Click on failed workflow
3. Click "Re-run jobs"
4. Select specific job or all jobs

## Workflow Files

### Location
- `.github/workflows/pr-check.yml` - PR validation
- `.github/workflows/release.yml` - Release automation

### Syntax
Both use GitHub Actions YAML syntax. Key concepts:

```yaml
on:                     # Trigger conditions
  push:
    tags:
      - 'v*'

jobs:                   # Workflow jobs
  job-name:
    runs-on: ubuntu-latest
    steps:              # Job steps
      - name: Step 1
        run: |
          echo "Command"
```

### Modifying Workflows

1. Edit workflow file
2. Commit changes
3. Push to test branch
4. Create PR to test changes
5. Merge to main when validated

## Best Practices

### For PR Workflows

1. **Keep checks fast**
   - Use caching for dependencies
   - Run expensive checks only when needed
   - Use matrix strategy for parallel execution

2. **Fail fast**
   - Run quick checks first (linting)
   - Run slow checks later (integration tests)

3. **Provide clear feedback**
   - Use descriptive job names
   - Add comments in code
   - Log helpful messages

### For Release Workflows

1. **Validate thoroughly**
   - Check version consistency
   - Run full test suite
   - Verify artifacts build correctly

2. **Generate good release notes**
   - Use descriptive commit messages
   - Include issue/PR references
   - Categorize changes (features, fixes, etc.)

3. **Test releases**
   - Use pre-release tags for testing
   - Verify artifacts work correctly
   - Test installation procedures

## Monitoring

### GitHub Actions Dashboard

View all workflows:
`https://github.com/sirkirby/open-agent-kit/actions`

### Workflow Status Badges

Add to README:
```markdown
![PR Checks](https://github.com/sirkirby/open-agent-kit/workflows/PR%20Validation/badge.svg)
![Release](https://github.com/sirkirby/open-agent-kit/workflows/Release/badge.svg)
```

### Notifications

Configure in: **Settings → Notifications**
- Email notifications on workflow failures
- Slack/Teams integration available

---

For questions about workflows, open an issue.
