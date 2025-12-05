# Migration Playbook

Use this guide whenever a change requires one-time alterations to existing user projects.
It expands on the migration summary in `.constitution.md`.

## When to Create a Migration

Create a migration if the upgrade must:

- Modify repo files (`.gitignore`, `.editorconfig`, etc.).
- Create or restructure directories.
- Convert config formats or stored data.
- Seed new artifacts that existing installs lack.

Skip migrations for:

- Template or agent-command updates (handled by the upgrade service).
- Pure CLI/service changes that only live inside the package.
- Config field additions that default safely via the config model.

## System Overview

- **Registry:** `src/open_agent_kit/services/migrations.py::get_migrations()`
- **Executor:** `UpgradeService.plan_upgrade()` + `UpgradeService.execute_upgrade()`
- **Tracking:** `.oak/config.yaml` stores completed migration IDs (`migrations: []`)

Flow: plan → show pending migrations → execute → record success → skip next time.

## Migration ID Format

`YYYY.MM.DD_descriptive_name` (e.g., `2024.11.13_gitignore_work_context`)

Benefits: chronological ordering, searchable history, ties to creation date.

## Authoring Steps

### 1. Implement the migration

```python
def _migrate_feature_name(project_root: Path) -> None:
    """Describe what the migration fixes and why."""
    # Use helpers from open_agent_kit.utils whenever possible
```

- Prefix with `_migrate_`.
- Match the function name to the ID suffix.
- Keep it idempotent and well-documented.

### 2. Register it

```python
def get_migrations() -> list[tuple[str, str, Callable[[Path], None]]]:
    return [
        ("2024.11.13_gitignore_issue_context",
         "Add oak/issue/**/context.json to .gitignore",
         _migrate_gitignore_issue_context),
        ("2024.11.15_feature_name",
         "Brief upgrade description",
         _migrate_feature_name),
    ]
```

- Append to the list (preserves chronological order).
- Keep the user-facing description short and actionable.

### 3. Test thoroughly

1. Fresh project (`oak init`, then `oak upgrade`) – migration should not run.
2. Existing project created before the change – migration should run once.
3. Re-run `oak upgrade` – migration should be skipped (already tracked).
4. Inspect `.oak/config.yaml` to confirm the ID is recorded.

### 4. Update docs

- Mention the migration in release notes / changelog.
- Update feature docs describing the one-time change.

## Best Practices

- **Idempotent:** guard against duplicate edits.
- **Error-safe:** surface actionable errors; never swallow exceptions silently.
- **Utilities first:** prefer helpers such as `ensure_dir`, `ensure_gitignore_has_issue_context`,
  `read_file`, `write_file`, etc.
- **Clear messaging:** describe what changed and why in console output.

## Decision Matrix

| Scenario                      | Approach                    |
|-------------------------------|-----------------------------|
| Add new template              | Template upgrade            |
| Add new agent command         | Command upgrade             |
| Update IDE settings           | IDE settings service        |
| Add config field              | Config model defaults       |
| Modify `.gitignore`           | Migration                   |
| Create new directory layout   | Migration                   |
| Convert stored data format    | Migration                   |

## Example

```python
def get_migrations() -> list[tuple[str, str, Callable[[Path], None]]]:
    return [
        ("2024.11.13_gitignore_issue_context",
         "Add oak/issue/**/context.json to .gitignore",
         _migrate_gitignore_issue_context),
    ]

def _migrate_gitignore_issue_context(project_root: Path) -> None:
    """Prevent issue context JSON from being committed."""
    from open_agent_kit.utils import ensure_gitignore_has_issue_context

    ensure_gitignore_has_issue_context(project_root)
```

Why it works:

- Clear ID and docstring.
- Uses an existing utility (already idempotent).
- Minimal logic; easy to reason about and test.

## Testing Checklist

- [ ] ID uses `YYYY.MM.DD_name`.
- [ ] Function is idempotent and error-safe.
- [ ] Registered in `get_migrations()`.
- [ ] User-facing description is understandable.
- [ ] Verified on fresh and existing installs.
- [ ] Documentation updates mention the migration.
