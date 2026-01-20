---
description: Discover semantic relationships between code components using vector search. Use when you need to understand how different parts of the codebase connect beyond simple imports or file references.
---

## Request

```text
$ARGUMENTS
```

## Action

Find semantic relationships between code components that grep and import analysis would miss.

### When to Use This

Use this command when:
- Understanding how two components relate conceptually
- Finding code that serves similar purposes
- Discovering hidden dependencies or patterns
- Mapping how data flows through the system

**Why this over grep**: Grep finds text matches. This finds *conceptual* relationships - code that's related by meaning, not just naming.

### Commands

```bash
# Find code related to a concept
oak ci search "authentication flow"

# Find code related to two concepts (relationship)
oak ci search "how does AuthService interact with TokenManager"

# Search only code (no memories)
oak ci search "database connection handling" --type code

# Get context about a specific relationship
oak ci context "relationship between UserService and PaymentProcessor"

# Get context with specific files in focus
oak ci context "how auth middleware relates to session handling" -f src/middleware/auth.py
```

### Example: Understanding Component Relationships

**Question**: "How does the OrderService relate to the InventoryService?"

```bash
# 1. Search for code mentioning both concepts
oak ci search "OrderService inventory management"

# 2. Get broader context
oak ci context "relationship between orders and inventory"

# 3. Search for data flow patterns
oak ci search "order creation inventory update"
```

**What you'll find**: Semantic search reveals event handlers, shared models, and integration points that aren't obvious from imports alone.

### What Grep Can't Do

| Grep | Semantic Search |
|------|-----------------|
| Finds "UserService" literally | Finds code about user management regardless of naming |
| Misses synonyms (auth vs authentication) | Understands concepts are related |
| Can't find "conceptually similar" code | Groups code by purpose, not text |
| No relevance ranking | Returns most relevant first |

### Tips

- Use natural language queries, not code keywords
- Ask about relationships: "how does X interact with Y"
- Search for concepts: "error handling patterns" not "catch Exception"
- Combine with `oak ci context` for richer understanding
