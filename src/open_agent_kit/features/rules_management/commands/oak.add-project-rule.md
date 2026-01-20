# Add Project Rule

Add a rule to the project's constitution and sync it across all configured AI agents.

## Usage

When the user wants to add a new rule, standard, or practice to the project:

1. **Read the current constitution**
   ```bash
   oak rules get-content
   ```

2. **Edit the constitution** to add the rule in the appropriate section using RFC 2119 language:
   - **MUST** - Absolute requirement
   - **SHOULD** - Strong recommendation
   - **MAY** - Optional

3. **Sync to all agents**
   ```bash
   oak rules sync-agents
   ```

## Example

User: "We should always use TypeScript strict mode"

1. Read: `oak rules get-content`
2. Add to appropriate section: `- All TypeScript projects MUST enable strict mode`
3. Sync: `oak rules sync-agents`

## Notes

- Constitution file: `oak/constitution.md`
- Rules should be achievable, not aspirational
- Include rationale when the "why" isn't obvious
