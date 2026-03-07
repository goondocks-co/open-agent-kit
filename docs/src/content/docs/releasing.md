---
title: Release Process
description: How to cut stable, beta, and TestPyPI releases for open-agent-kit.
---

This document describes the release process for `oak-ci`. All releases are cut directly from `main` (trunk-based development).

## Version numbering

OAK uses **PEP 440** version strings. Tags must use PEP 440-native pre-release suffixes — SemVer-style suffixes (e.g. `v0.6.0-beta.1`) are **not** supported because `hatch-vcs` does not map them to valid PEP 440 versions.

| Release type | Tag format | PyPI version | Example |
|---|---|---|---|
| Stable | `vX.Y.Z` | `X.Y.Z` | `v0.5.0` |
| Beta | `vX.Y.ZbN` | `X.Y.ZbN` | `v0.6.0b1` |
| Release candidate | `vX.Y.ZrcN` | `X.Y.ZrcN` | `v0.6.0rc1` |
| Alpha | `vX.Y.ZaN` | `X.Y.ZaN` | `v0.6.0a1` |
| TestPyPI only | `vX.Y.Z-testpypi.N` | `X.Y.Z.postN.dev0` | `v0.5.0-testpypi.1` |

## Release flows

### Stable release

Tag `vX.Y.Z` on `main`. The workflow:

1. Builds the Python wheel and sdist.
2. Creates a GitHub Release (marked **latest**) with commit log and stable install instructions.
3. Publishes to [PyPI](https://pypi.org/project/oak-ci/).
4. Triggers `update-formula.yml` in `goondocks-co/homebrew-oak` to update `Formula/oak-ci.rb`.

```bash
git tag v0.5.0
git push origin v0.5.0
```

**User install:**

```bash
brew install goondocks-co/oak/oak-ci
pipx install oak-ci --python python3.13
uv tool install oak-ci --python python3.13
```

---

### Beta / pre-release

Tag `vX.Y.ZbN` (or `rcN`, `aN`) on `main`. The workflow:

1. Builds the Python wheel and sdist.
2. Creates a GitHub Release marked **pre-release**, with a `⚠️ This is a pre-release` warning and beta install instructions.
3. Publishes to [PyPI](https://pypi.org/project/oak-ci/) as a PEP 440 pre-release (not installed by default — users must opt in with `--pre`).
4. Triggers `update-formula.yml` in `goondocks-co/homebrew-oak` to update `Formula/oak-ci-beta.rb`.

```bash
git tag v0.6.0b1
git push origin v0.6.0b1
```

**User install:**

```bash
# Homebrew (macOS) — installs the binary as `oak-beta`
brew install goondocks-co/oak/oak-ci-beta

# pipx
pipx install oak-ci --python python3.13 --pip-args='--pre' --suffix=-beta

# uv
uv tool install oak-ci --python python3.13 --prerelease=allow

# pip
pip install oak-ci --pre
```

**After installing, initialise your project with the beta binary:**

```bash
oak-beta init
```

Running `oak-beta init` automatically configures your project to use `oak-beta`
in hooks and skills (via the `cli_command` setting in `.oak/config.yaml`).
You can also switch channels from the daemon UI — open the **About** dialog
(Info icon in the sidebar) and click **Switch to Beta / Stable**.

---

### TestPyPI

Tag `vX.Y.Z-testpypi.N` on any branch. The workflow:

1. Builds the Python wheel and sdist.
2. Creates a GitHub Release marked **pre-release**.
3. Publishes to [TestPyPI](https://test.pypi.org/project/oak-ci/) only — nothing goes to real PyPI or Homebrew.

```bash
git tag v0.5.0-testpypi.1
git push origin v0.5.0-testpypi.1
```

**User install (for testing only):**

```bash
pip install oak-ci --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/
```

---

## Cutting a release (checklist)

1. Ensure `main` is green (`make check` passes, CI is clean).
2. Update `CHANGELOG` or release notes if maintained.
3. Create and push the tag (see formats above).
4. Monitor the [Release workflow](https://github.com/goondocks-co/actions/workflows/release.yml).
5. Verify the GitHub Release was created with the correct `prerelease` flag.
6. For stable: confirm [PyPI](https://pypi.org/project/oak-ci/) shows the new version and `brew upgrade oak-ci` works.
7. For beta: confirm PyPI shows the pre-release and `brew install goondocks-co/oak/oak-ci-beta` works.

## Homebrew tap

The tap lives at [`goondocks-co/homebrew-oak`](https://github.com/goondocks-co/homebrew-oak):

| Formula | Channel | Class |
|---|---|---|
| `Formula/oak-ci.rb` | Stable | `OakCi` |
| `Formula/oak-ci-beta.rb` | Beta / pre-release | `OakCiBeta` |

Both formulas are updated automatically by the `update-formula.yml` workflow, which is triggered by `release.yml` passing `formula=oak-ci` or `formula=oak-ci-beta` respectively. The `HOMEBREW_TAP_TOKEN` secret must have `workflow` scope on the `goondocks-co/homebrew-oak` repo.
