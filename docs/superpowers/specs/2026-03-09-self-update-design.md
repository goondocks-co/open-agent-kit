# Self-Update System Design

## Summary

Replace the current manual update workflow (Homebrew/uv upgrade → oak upgrade → oak team restart) with a daemon-driven self-update system. The daemon auto-downloads new releases in the background, notifies the user via a subtle UI indicator, and applies the update (package install + project upgrade + daemon restart) with a single click.

Includes a channel redesign: replace the current two-binary model (`oak` + `oak-beta`) with a single binary and a config-based channel toggle.

## Problem

- Users must manually run OS-level package manager commands to update
- Teams/swarms have nodes on different versions, causing compatibility issues
- Version fragmentation grows with each release since not everyone updates promptly
- The current beta channel requires a separate binary, separate Homebrew formula, and a complex binary-swap workflow

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Update model | Auto-download, manual restart | Safety of user control, no surprise interruptions |
| Update scope | Python package only | Workers are templates bundled in the package; deploy is separate |
| Version detection | PyPI polling | Simple, no auth, canonical source. `GET pypi.org/pypi/oak-ci/json` |
| Poll frequency | Every 6 hours + on-demand | Sparse enough to be polite, with manual "Check Now" |
| Update owner | Daemon only (team + swarm) | If daemon isn't running, OAK isn't doing anything useful |
| Install mechanism | Stage-then-swap | Daemon downloads wheel, detached script installs after daemon exits |
| Editable installs | Fully exempt (double-guarded) | Detected via PEP 610 in daemon AND in update script. Belt-and-suspenders. |
| Multi-daemon coordination | First wins, file lock | `~/.oak/update.lock` prevents races; others detect mismatch and prompt restart |
| Project upgrade | Automatic on apply | Update script runs `oak upgrade --force` after installing the wheel |
| Channel model | One binary, config toggle | `update_channel: stable \| beta` in `~/.oak/update.yaml` |
| UI treatment | Badge on About icon | Green dot indicator, replaces the current full-width yellow banner |
| Platform scope | POSIX first (macOS/Linux), Windows follow-up | Update script is shell-based; Windows `.ps1` variant is a follow-up |

## Architecture

### Update Lifecycle

```
DETECT (non-blocking async task at startup + every 6h)
├─ Check is_editable via get_install_source() → skip if true
├─ GET pypi.org/pypi/oak-ci/json
├─ Filter versions by channel config (stable│beta)
│   └─ Beta channel: max(latest_stable, latest_beta) — never downgrade
├─ Compare against running version (no-downgrade rule from existing code)
└─ If newer version exists → proceed to DOWNLOAD (or NOTIFY if auto_download=false)

DOWNLOAD
├─ Clean ~/.oak/staging/ (remove any previously staged wheel)
├─ Acquire file lock ~/.oak/update.lock (non-blocking trylock)
├─ Download wheel → ~/.oak/staging/
├─ Verify SHA256 checksum (from PyPI metadata digests)
├─ Write ~/.oak/staged-update.json
│   { schema_version: 1, version, wheel_path, channel, downloaded_at, sha256 }
└─ Release lock

NOTIFY
├─ Set update_available flag in daemon state
├─ UI: green badge on About icon in sidebar
├─ /api/update/status returns full update details
└─ If auto_download=false: show "Download & Install" button instead of "Apply Update"

APPLY (user-initiated)
├─ User clicks "Apply Update" in About panel
├─ POST /api/update/apply
├─ Daemon generates update script with project_root baked in
├─ Daemon spawns detached update script
├─ Daemon exits cleanly
└─ update script:
    1. cd $PROJECT_ROOT
    2. Install staged wheel (method-specific, see Install Method Detection)
    3. oak upgrade --force (project-level assets)
    4. oak team start (new daemon with new code)
    5. Cleanup: remove staged wheel + staged-update.json
    On ANY failure:
    - Write error to ~/.oak/update-error.json
    - Attempt oak team start anyway (restart old version as fallback)
```

### Multi-Daemon Coordination

All daemons on a machine share the same global `oak` package. When one daemon applies an update:

1. **Installing daemon**: acquires lock, downloads wheel, installs, restarts
2. **Other daemons** (team and swarm): on their next version check, detect that on-disk package version differs from their running version. Show "restart to apply update" badge. No download needed.
3. **File lock**: `~/.oak/update.lock` prevents two daemons from installing simultaneously. Non-blocking trylock — if locked, skip download (someone else is handling it).

### Swarm Daemon Behavior

The swarm daemon participates in the self-update system as a peer of the team daemon:

- **Version check**: swarm daemon runs the same `UpdateChecker` logic. It can detect new versions and trigger downloads independently.
- **UI badge**: swarm daemon UI shows the same green dot on its About icon when an update is available.
- **Apply**: swarm daemon can apply updates via the same `/api/update/apply` endpoint. The update script runs `oak swarm start` instead of `oak team start`.
- **Cross-daemon mismatch**: if a team daemon applies an update, the swarm daemon detects the on-disk version change on its next check and prompts restart. Vice versa.
- **Shared update routes**: the update API routes (`/api/update/*`) are mounted on both team and swarm routers. The `UpdateInstaller` accepts a `daemon_type` parameter to generate the correct restart command.

### Self-Update Exemptions

Two categories of installs are fully exempt from self-update. The daemon functions normally in both cases — only the update system is disabled.

**Editable installs (development)** — double-guarded:

- **Guard 1 — Daemon level:** Detected via PEP 610 `direct_url.json` using the existing `get_install_source()` utility. When `is_editable=True`: skip all PyPI version checks, skip download/staging, no UI badge or notification. API routes return `{ "exempt": true, "reason": "editable_install" }`.
- **Guard 2 — Update script level:** The generated update script checks for editable install before running `pip install`. If editable, it aborts with a clear error message and does NOT attempt installation. This prevents a scenario where a staged update from a previous non-editable install is accidentally applied after switching to editable mode.

**Windows** — detected early via `sys.platform == "win32"`:

- UpdateChecker skips entirely on Windows (same pattern as editable exemption)
- No PyPI checks, no downloads, no UI badge
- API routes return `{ "exempt": true, "reason": "windows_unsupported" }`
- Windows users continue using their current manual update flow (`pip install --upgrade oak-ci`)
- Windows `.ps1` update script support is a future enhancement

### Channel Redesign

**Current model (being replaced):**
- Two binaries: `oak` (stable) + `oak-beta` (beta)
- Two Homebrew formulas: `oak-ci` + `oak-ci-beta`
- `cli_command` alias in `.oak/config.yaml` for binary switching
- Channel switch = install new binary + `oak-beta upgrade --force` + project re-init

**New model:**
- One binary: `oak`
- One Homebrew formula: `oak-ci`
- One PyPI package: `oak-ci` (stable releases + pre-release versions)
- `update_channel: stable | beta` in `~/.oak/update.yaml`
- Channel switch = config change → next update check considers pre-release versions
- `parse_pypi_versions()` already returns both stable and beta versions — the channel config is just a filter

**Version comparison semantics:**
- **Stable channel**: only consider versions where `Version(v).pre is None`. Offer the latest.
- **Beta channel**: consider ALL versions (stable + pre-release). Offer `max(latest_stable, latest_beta)`. This ensures beta users are never offered a downgrade if the latest beta is older than the latest stable.
- **No-downgrade rule**: never offer a version whose base release is less than or equal to the running version's base release (carry forward from existing `is_meaningful_upgrade()`).

**Migration path:**
- Users on `oak-beta` binary: show migration notice in daemon UI pointing them to uninstall `oak-beta` and switch to channel config
- Remove `oak-ci-beta` Homebrew formula from tap
- Remove `cli_command` alias logic from config service
- Remove `target_binary_name()`, `get_current_channel()` binary-detection functions
- Remove binary detection in both `features/team/daemon/routes/release_channel.py` AND `features/swarm/daemon/routes/release_channel.py`
- Update `utils/release_channel.py` to use new config-based channel

## Global State Directory

### `~/.oak/` — Machine-Wide Update State

This is a **new** global config directory, distinct from the per-project `.oak/` directory.

**Creation:** Created on first daemon startup if it doesn't exist. Uses `os.makedirs(mode=0o755, exist_ok=True)`.

**Error handling:** If `~/.oak/` cannot be created (permissions, disk full), the self-update system is disabled for that session. A warning is logged once. The daemon continues to function normally — self-update is non-essential.

**Platform note:** We use `~/.oak/` (home directory) rather than XDG/platform-specific paths for simplicity and cross-platform consistency. This matches the pattern used by similar tools (e.g., `~/.npm/`, `~/.cargo/`).

### Layout

```
~/.oak/                              (global config directory)
├─ update.yaml                       # update_channel, auto_download, check_interval_hours
├─ update.lock                       # file lock for download coordination
├─ staged-update.json                # metadata for staged wheel (schema_version: 1)
├─ last-check.json                   # timestamp + result of last PyPI check
├─ update-error.json                 # error from last failed update attempt
├─ release-notes-cache.json          # cached GitHub release notes (avoid rate limits)
└─ staging/                          # downloaded wheels awaiting install
    └─ oak_ci-1.3.0-py3-none-any.whl
```

Note: the global config file is `update.yaml` (not `config.yaml`) to avoid confusion with the per-project `.oak/config.yaml`.

## New Components

### 1. UpdateChecker (`features/team/daemon/lifecycle/update_checker.py`)

Periodic PyPI polling service integrated into the daemon lifecycle.

- Runs as a **non-blocking async task** on daemon startup (does not delay daemon readiness)
- Repeats every `check_interval_hours` (default 6)
- Reads channel config from `~/.oak/update.yaml`
- Uses existing `parse_pypi_versions()` to extract stable/beta versions
- Applies channel filter and no-downgrade rule
- Writes `~/.oak/last-check.json` with timestamp and result
- Fires internal event when new version detected → triggers download (if `auto_download=true`) or notification (if `auto_download=false`)
- On-demand check via API endpoint
- Skips entirely if `get_install_source()` returns `is_editable=True`
- Shared between team and swarm daemons (imported from a common location)

### 2. UpdateDownloader (`features/team/daemon/lifecycle/update_downloader.py`)

Downloads and stages wheels from PyPI.

- Cleans `~/.oak/staging/` before downloading (only one staged version at a time)
- Acquires `~/.oak/update.lock` (non-blocking trylock)
- Downloads wheel URL from PyPI JSON metadata
- Verifies SHA256 checksum against PyPI digests
- Writes wheel to `~/.oak/staging/`
- Writes `~/.oak/staged-update.json` with metadata (includes `schema_version: 1`)
- If lock unavailable, checks for existing `staged-update.json` (another daemon handled it)
- Shared between team and swarm daemons

### 3. UpdateInstaller (`features/team/daemon/lifecycle/update_installer.py`)

Generates and spawns the detached update script.

- Accepts `daemon_type` parameter: `"team"` or `"swarm"`
- Generates a shell script (`/bin/sh`) with:
  1. `cd $PROJECT_ROOT` (baked into script at generation time)
  2. Editable install guard (check `direct_url.json`, abort if editable)
  3. Install staged wheel (see Install Method Detection)
  4. `oak upgrade --force` (project-level asset upgrade)
  5. `oak team start` or `oak swarm start` (based on `daemon_type`)
  6. Cleanup: remove staged wheel + `staged-update.json`
  7. On ANY failure: write `~/.oak/update-error.json` and attempt restart of old version as fallback
- Spawns script as detached subprocess with `cwd=project_root` (same pattern as existing `restart.py`)
- Daemon exits cleanly after spawning
- **Windows (future):** generate `.ps1` script instead, use existing `platform.py` subprocess detachment

### 4. Update API Routes (`features/team/daemon/routes/update.py`)

New API endpoints mounted on **both** team and swarm daemon routers.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/update/status` | GET | Current update state: version, channel, staged update info, last check, errors |
| `/api/update/check` | POST | Trigger on-demand PyPI check |
| `/api/update/apply` | POST | Apply staged update (install + upgrade + restart) |
| `/api/update/release-notes` | GET | Fetch release notes from GitHub Releases API (cached in `~/.oak/`) |
| `/api/update/channel` | PUT | Switch update channel (stable/beta), writes to `~/.oak/update.yaml` |

### 5. UI Changes

**Sidebar indicator:**
- Green dot badge on About icon when update is staged and ready
- Badge disappears when up-to-date
- Applied to both team and swarm daemon UIs

**About panel (replaces current About dialog):**
- Shows current version + channel
- "Up to date" / "Update ready" / "Applying" states
- "Apply Update" button when staged update exists and `auto_download=true`
- "Download & Install" button when new version detected and `auto_download=false`
- "Notes" button to view release notes (cached from GitHub, avoids rate limits)
- Channel toggle: Stable / Beta (writes to `~/.oak/update.yaml`)
- "Check Now" button for on-demand check
- "Last checked X ago" timestamp
- Error state: shows last update error from `~/.oak/update-error.json` with retry option

**Remove:**
- Current full-width yellow version mismatch banner
- Current binary-swap channel switching UI

## Error Handling

| Failure | Behavior |
|---------|----------|
| `~/.oak/` not writable | Log warning once. Self-update disabled. Daemon functions normally. |
| PyPI unreachable | Silent retry on next interval. No user notification. Respects `HTTPS_PROXY` env var. |
| Download fails | Log warning, clear lock, retry on next interval. |
| Checksum mismatch | Discard wheel, log error, notify user in About panel. |
| Install fails (update script) | Write error to `~/.oak/update-error.json`. Attempt `oak team start` anyway to restart old version as fallback. |
| Daemon doesn't restart | Update script has a timeout; if restart fails, writes error file. User can manually run `oak team start`. |
| Lock contention | Non-blocking trylock. If another daemon has the lock, skip and check for `staged-update.json` on next cycle. |
| Version skip (1.3.0 staged, 1.4.0 released) | Next check detects newer version, cleans staging dir, downloads 1.4.0. |

## Install Method Detection

Every install method creates a Python environment with pip. The update installer detects which environment manages the current `oak` binary and installs the staged wheel into that same environment. The core operation is always the same: `pip install <wheel>` into the right venv.

### Detection Strategy

Resolve `sys.executable` to find the Python interpreter running `oak`. From there, determine the install method:

1. **Editable install** — `direct_url.json` has `editable: true` → skip entirely (should never reach here due to guards)
2. **Homebrew** — `sys.executable` resolves inside `/opt/homebrew/Cellar/` or `/usr/local/Cellar/` → Homebrew venv
3. **uv tool** — `is_uv_tool_install()` returns true → uv-managed tool venv
4. **pipx** — `sys.executable` resolves inside `~/.local/share/pipx/venvs/` → pipx venv
5. **pip --user** — fallback for everything else

### Install Commands

| Method | Venv location | Install Command |
|--------|---------------|-----------------|
| Homebrew | `/opt/homebrew/Cellar/oak-ci/X.Y.Z/libexec/` | `libexec/bin/pip install <wheel>` |
| uv tool | `~/.local/share/uv/tools/oak-ci/` | `uv tool install <wheel> --force` |
| pipx | `~/.local/share/pipx/venvs/oak-ci/` | `pipx install <wheel> --force` |
| pip --user | User site-packages | `pip install --user <wheel>` |
| Editable | N/A | Skip entirely |

### Notes

**Homebrew:** The formula's `post_install` hook literally runs `libexec/bin/pip install <wheel>` — we do the same thing. The Cellar path version (e.g., `1.5.6`) becomes cosmetically out of sync with the actual package version, but this is harmless. When the release workflow updates the Homebrew tap formula, `brew upgrade` would cleanly reinstall — effectively a no-op if the package is already at the target version. `brew doctor` does not flag pip-installed package updates within the Cellar venv.

**uv tool:** `uv tool install <local-wheel-path> --force` accepts local paths and replaces the existing tool installation. The `--force` flag is required to override the existing installation.

**pipx:** `pipx install <local-wheel-path> --force` works the same way. The `--force` flag overwrites the existing installation.

**Unified principle:** Regardless of install method, the initial install gets the user in the door. From that point forward, self-update takes over. The user never needs to think about which package manager they used.

## Configuration

`~/.oak/update.yaml`:

```yaml
update:
  channel: stable          # stable | beta
  auto_download: true      # download updates automatically (false = notify only)
  check_interval_hours: 6  # how often to poll PyPI
```

All settings have sensible defaults. The config file is created on first daemon startup if it doesn't exist. Missing keys fall back to defaults.

**`auto_download: false` flow:**
1. DETECT: daemon checks PyPI, finds new version
2. NOTIFY: badge on About icon, About panel shows "v1.3.0 available" with "Download & Install" button
3. User clicks "Download & Install" → triggers download + apply in one step
4. Same update script flow from there

## Migration Plan

### From current version mismatch detection
- Keep `check_upgrade_needed()` for project-level upgrade detection (config version vs package version)
- Replace CLI-level `_check_daemon_version_hint()` banner with daemon-side update status
- The self-update system handles the package-level update; `check_upgrade_needed()` handles project-level

### From current beta channel
- Deprecate `oak-beta` binary with a notice period (1-2 releases)
- Add migration notice in daemon UI for users on `oak-beta`
- Remove beta Homebrew formula from tap after migration period
- Files to modify/remove:
  - `features/team/daemon/routes/release_channel.py` — replace binary-swap with config-based channel
  - `features/swarm/daemon/routes/release_channel.py` — same
  - `utils/release_channel.py` — update to use `~/.oak/update.yaml` for channel config
  - Remove `target_binary_name()`, `get_current_channel()`, `cli_command` aliasing in config service

## Platform Support

**Initial release:** macOS and Linux (POSIX). The update script is a `/bin/sh` shell script.

**Windows (follow-up):** Generate a `.ps1` PowerShell script instead. The existing `platform.py` module already handles Windows vs POSIX for process detachment and file locking. The `UpdateInstaller` will check `sys.platform` and generate the appropriate script type.

## Future Enhancements (Out of Scope)

- **Swarm-coordinated updates**: swarm broadcasts "update available" to all connected teams. Nodes auto-download, admin approves fleet-wide restart.
- **Forced minimum version**: swarm rejects nodes below a minimum version, forcing upgrade.
- **Rollback**: keep previous wheel in staging, add "Rollback" button to About panel.
- **Worker auto-deploy**: after package update, detect new worker template hash and prompt for `oak team cloud deploy` / `oak swarm deploy`.
- **Automatic restart on idle**: daemon restarts itself during periods of inactivity (no active sessions).
- **Windows support**: `.ps1` update script generation.
