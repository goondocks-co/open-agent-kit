# Remove Project Rule

Remove a rule from the project's constitution and sync the change across all configured AI agents.

## Usage

When the user wants to remove an outdated, incorrect, or deprecated rule:

1. **Read the current constitution**
   ```bash
   oak rules get-content
   ```

2. **Edit the constitution** to remove the rule

3. **Optionally add an amendment** for significant changes:
   ```bash
   oak rules add-amendment --summary "Remove X requirement" --type major --author "Name" --rationale "Reason"
   ```

4. **Sync to all agents**
   ```bash
   oak rules sync-agents
   ```

## Amendment Types

- **major** - Removing MUST requirements, significant policy changes
- **minor** - Removing SHOULD/MAY rules
- **patch** - Clarifications

## Example

User: "We no longer require 100% code coverage"

1. Read: `oak rules get-content`
2. Remove or relax the coverage rule
3. Document: `oak rules add-amendment --summary "Relax coverage requirement" --type major --rationale "Moving to risk-based testing"`
4. Sync: `oak rules sync-agents`

## Notes

- Constitution file: `oak/constitution.md`
- For significant changes, document with an amendment
