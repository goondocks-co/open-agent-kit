# Releasing open-agent-kit

This guide explains how to create and publish new releases of open-agent-kit.

## Table of Contents

- [Overview](#overview)
- [Release Process](#release-process)
- [Version Numbering](#version-numbering)
- [Pre-Release Checklist](#pre-release-checklist)
- [Creating a Release](#creating-a-release)
- [What Gets Released](#what-gets-released)
- [Post-Release](#post-release)
- [Troubleshooting](#troubleshooting)

## Overview

open-agent-kit uses GitHub Actions to automate the release process. When you push a semver tag (e.g., `v0.1.0`), the release workflow automatically:

1. Validates the tag matches the version in code
2. Builds Python packages (wheel and source distribution)
3. Creates template packages for each agent/script combination
4. Runs the full test suite
5. Creates a GitHub release with all artifacts
6. Generates release notes from commits

## Release Process

### 1. Prepare the Release

**Update Version Numbers:**

Edit `pyproject.toml`:
```toml
[project]
name = "open-agent-kit"
version = "0.2.0"  # Update this
```

Edit `src/open_agent_kit/__init__.py`:
```python
__version__ = "0.2.0"  # Update this
```

**Update CHANGELOG** (if you maintain one):
```markdown
## [0.2.0] - 2024-01-15

### Added
- New RFC validation rules
- Support for custom templates

### Fixed
- Bug in RFC numbering
- Template rendering issue

### Changed
- Improved CLI output formatting
```

### 2. Commit Changes

```bash
git add pyproject.toml src/open_agent_kit/__init__.py CHANGELOG.md
git commit -m "Bump version to 0.2.0"
git push origin main
```

### 3. Create and Push Tag

```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release version 0.2.0"

# Push tag to trigger release
git push origin v0.2.0
```

**The release workflow will now run automatically!**

### 4. Monitor Release

1. Go to **Actions** tab in GitHub
2. Watch the **Release** workflow
3. Check for any errors
4. Once complete, go to **Releases** tab
5. Verify all artifacts are present

## Version Numbering

open-agent-kit follows [Semantic Versioning](https://semver.org/):

### Format: `MAJOR.MINOR.PATCH[-PRERELEASE]`

**Examples:**
- `v0.1.0` - Initial release
- `v0.2.0` - New features added
- `v0.2.1` - Bug fixes
- `v1.0.0` - First stable release
- `v1.0.0-beta.1` - Pre-release
- `v1.0.0-rc.1` - Release candidate

### When to Increment:

**MAJOR** (v1.0.0 → v2.0.0)
- Breaking API changes
- Major architectural changes
- Incompatible changes

**MINOR** (v0.1.0 → v0.2.0)
- New features (backward compatible)
- New commands or options
- New templates

**PATCH** (v0.1.0 → v0.1.1)
- Bug fixes
- Documentation updates
- Minor improvements

### Pre-Release Versions

Use pre-release suffixes for testing:

```bash
# Beta releases
git tag -a v0.2.0-beta.1 -m "Beta 1 for v0.2.0"

# Release candidates
git tag -a v1.0.0-rc.1 -m "Release candidate 1 for v1.0.0"

# Alpha releases
git tag -a v0.2.0-alpha.1 -m "Alpha 1 for v0.2.0"
```

Pre-releases are marked as "Pre-release" in GitHub and won't be considered the "Latest" release.

## Pre-Release Checklist

Before creating a release tag, ensure:

- [ ] All tests pass (`pytest`)
- [ ] Code is linted (`ruff check src/`)
- [ ] Code is formatted (`black src/`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Version numbers are updated and consistent
- [ ] CHANGELOG is updated (if maintained)
- [ ] All PRs for this release are merged
- [ ] Documentation is up to date
- [ ] Templates are validated
- [ ] Scripts are tested on both bash and PowerShell
- [ ] Integration tests pass

**Run local validation:**

```bash
# Run all checks
ruff check src/
black src/ --check
mypy src/
pytest --cov=oak

# Test installation
pip install -e .
oak --version

# Test basic workflow
cd /tmp/test-release
oak init --no-interactive --agent claude
# Note: RFC creation is done via AI agent commands, not CLI
# Test that init worked correctly
ls -la .oak/
```

## Creating a Release

### Standard Release

```bash
# 1. Update version numbers
# Edit pyproject.toml and src/open_agent_kit/__init__.py

# 2. Commit changes
git add .
git commit -m "Bump version to 0.2.0"
git push origin main

# 3. Create and push tag
git tag -a v0.2.0 -m "Release version 0.2.0

New features:
- RFC validation improvements
- Additional template options
- Bug fixes

Full changelog: https://github.com/sirkirby/open-agent-kit/blob/main/CHANGELOG.md"

git push origin v0.2.0

# 4. Watch workflow in GitHub Actions
```

### Pre-Release

```bash
# Same process but with pre-release version
git tag -a v0.2.0-beta.1 -m "Beta release for testing new features"
git push origin v0.2.0-beta.1
```

### Hotfix Release

```bash
# Create hotfix branch from main
git checkout -b hotfix/0.1.1 main

# Make fixes
# ... edit files ...

# Update version to 0.1.1
# ... edit pyproject.toml and __init__.py ...

# Commit and tag
git commit -am "Fix critical bug in RFC validation"
git tag -a v0.1.1 -m "Hotfix: Fix RFC validation bug"

# Push branch and tag
git push origin hotfix/0.1.1
git push origin v0.1.1

# Merge back to main
git checkout main
git merge hotfix/0.1.1
git push origin main
```

## What Gets Released

When a release is created, the following artifacts are generated:

### Python Packages

1. **Wheel** (`oak-0.2.0-py3-none-any.whl`)
   - Binary distribution
   - Fast installation
   - Recommended for users

2. **Source Distribution** (`open-agent-kit-0.2.0.tar.gz`)
   - Source code archive
   - For building from source

### Template Packages

8 template packages (4 agents × 2 script types):

1. `open-agent-kit-templates-claude-bash-0.2.0.tar.gz`
2. `open-agent-kit-templates-claude-powershell-0.2.0.tar.gz`
3. `open-agent-kit-templates-copilot-bash-0.2.0.tar.gz`
4. `open-agent-kit-templates-copilot-powershell-0.2.0.tar.gz`
5. `open-agent-kit-templates-codex-bash-0.2.0.tar.gz`
6. `open-agent-kit-templates-codex-powershell-0.2.0.tar.gz`
7. `open-agent-kit-templates-cursor-bash-0.2.0.tar.gz`
8. `open-agent-kit-templates-cursor-powershell-0.2.0.tar.gz`

Each template package contains:
- RFC templates (engineering, architecture, feature, process)
- Agent-specific command templates
- Shell scripts (bash or PowerShell)
- README with installation instructions

### Release Notes

Auto-generated release notes include:
- Version number
- Change summary from commits
- Installation instructions
- Link to documentation
- List of all artifacts

## Post-Release

After a successful release:

### 1. Verify Release

- [ ] Check GitHub Releases page
- [ ] Verify all artifacts are present
- [ ] Download and test a template package
- [ ] Test Python package installation

```bash
# Test wheel installation
pip install oak-0.2.0-py3-none-any.whl
oak --version

# Test template package
tar -xzf open-agent-kit-templates-claude-bash-0.2.0.tar.gz
cd open-agent-kit-templates-claude-bash-0.2.0
cat README.md
```

### 2. Announce Release

Announce the release:

**Email:**
```
Subject: open-agent-kit v0.2.0 Released

The latest version of open-agent-kit is now available!

Key Improvements:
- RFC validation enhancements
- Additional template options
- Various bug fixes

Get it here:
https://github.com/sirkirby/open-agent-kit/releases/tag/v0.2.0

Documentation:
https://github.com/sirkirby/open-agent-kit/blob/main/README.md
```

### 3. Update Documentation

If needed, update:
- README with new features
- QUICKSTART with new commands
- RFC_WORKFLOW with process changes

### 4. Close Milestone

If using GitHub milestones:
1. Go to **Milestones**
2. Close the milestone for this version
3. Create next milestone

## Troubleshooting

### Release Workflow Failed

**Problem:** Release workflow fails after pushing tag

**Solutions:**

1. **Check workflow logs:**
   - Go to Actions tab
   - Click on failed workflow
   - Review error messages

2. **Common issues:**

   **Version mismatch:**
   ```
   Error: Version mismatch between tag and pyproject.toml
   ```
   Solution: Ensure tag matches version in files

   **Tests failed:**
   ```
   Error: Test suite failed
   ```
   Solution: Fix tests, delete tag, recreate after fix

   **Build failed:**
   ```
   Error: Package build failed
   ```
   Solution: Check pyproject.toml configuration

### Delete and Recreate Tag

If you need to recreate a tag:

```bash
# Delete local tag
git tag -d v0.2.0

# Delete remote tag
git push origin :refs/tags/v0.2.0

# Delete release in GitHub UI (if created)
# Go to Releases → Click release → Delete release

# Recreate tag
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

### Artifacts Missing

**Problem:** Some artifacts are missing from release

**Solution:**
1. Check workflow logs for build errors
2. Re-run failed jobs in Actions tab
3. If still failing, delete release and tag, fix issue, recreate

### Pre-Release Not Marked

**Problem:** Pre-release version marked as "Latest"

**Solution:**
Ensure tag follows pre-release format: `v1.0.0-beta.1`, `v1.0.0-rc.1`, etc.
The workflow detects `-` in version and marks as pre-release.

## GitHub Secrets

The release workflow may require these secrets:

| Secret | Purpose | Required |
|--------|---------|----------|
| `GITHUB_TOKEN` | Create releases, upload artifacts | Yes (auto-provided) |
| `CODECOV_TOKEN` | Upload code coverage | No (optional) |

Secrets are managed in: **Settings → Secrets and variables → Actions**

## Manual Release (If Workflow Fails)

If automated release fails, create manually:

```bash
# 1. Build packages locally
python -m build

# 3. Create release in GitHub UI
# Go to Releases → Draft a new release
# - Tag: v0.2.0
# - Title: open-agent-kit 0.2.0
# - Description: (paste release notes)
# - Upload artifacts
# - Publish release
```

## Best Practices

1. **Always test before releasing**
   - Run full test suite
   - Test installation in clean environment
   - Test basic workflows

2. **Use semantic versioning**
   - Follow semver strictly
   - Use pre-releases for testing

3. **Write good release notes**
   - Summarize changes clearly
   - Link to issues/PRs
   - Provide upgrade instructions if needed

4. **Tag messages**
   - Use descriptive tag messages
   - List key changes
   - Include links

5. **Announce releases**
   - Notify team via Teams/email
   - Update internal documentation
   - Provide migration guides if needed

---

For questions about releasing, contact the platform engineering team or open an issue.
