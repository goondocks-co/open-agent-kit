# P2 IMPORTANT: Missing MCP Tools for Agent Parity

## Summary
Several UI/CLI actions lack corresponding MCP tools, breaking the agent-native principle that "any action a user can take, an agent can also take."

## Missing Tools

### 1. `oak_list_memories`
- **CLI**: `oak ci memories`
- **API**: `GET /api/memories`
- **Agent Tool**: MISSING
- **Impact**: Agents cannot browse stored memories without searching

### 2. `oak_delete_memory`
- **UI**: DataExplorer delete button
- **API**: `DELETE /api/memories/{id}`
- **Agent Tool**: MISSING
- **Impact**: Agents cannot clean up incorrect or outdated memories

### 3. `oak_status`
- **CLI**: `oak ci status`
- **API**: `GET /api/index/status`
- **Agent Tool**: MISSING
- **Impact**: Agents cannot check if index is ready or indexing is in progress

## Location
- `src/open_agent_kit/features/codebase_intelligence/daemon/mcp_tools.py`

## Recommended Fix
Add the missing MCP tools:

```python
MCP_TOOLS = [
    # ... existing tools ...
    {
        "name": "oak_list_memories",
        "description": "List stored memories with pagination and filtering",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
                "offset": {"type": "integer", "default": 0},
                "memory_type": {"type": "string"},
            },
        },
    },
    {
        "name": "oak_delete_memory",
        "description": "Delete a memory by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {"type": "string"},
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "oak_status",
        "description": "Get daemon and index status",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
```

## Review Agent
agent-native-reviewer

## Status
- [ ] Fix implemented
- [ ] Tests added
- [ ] Reviewed
