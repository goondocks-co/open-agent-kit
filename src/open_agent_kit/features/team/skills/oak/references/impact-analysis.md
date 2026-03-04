# Impact Analysis

Find all code that might be affected by a change, including conceptually related code that import analysis would miss.

## When to Use

Use this workflow when:
- Planning to refactor a component
- Changing an API or interface
- Modifying shared functionality
- Assessing risk before making changes

**Why this over import analysis**: Import analysis finds direct dependencies. This finds *conceptual* dependencies - code that relies on the same patterns, makes similar assumptions, or would break for the same reasons.

## How It Works

Semantic search finds code related by meaning. When you change how something works, this helps find all code that depends on that *behavior*, not just code that imports it.

## Commands

### Find potentially affected code

```bash
# Find all code related to what you're changing
{oak-cli-command} ci search "AuthService token validation" --type code -n 20

# Get impact context for a specific file
{oak-cli-command} ci context "impact of changes" -f src/services/auth.py

# Search for code using similar patterns
{oak-cli-command} ci search "code that depends on JWT token format" --type code
```

### Check for related memories

```bash
# Find past learnings that might be relevant
{oak-cli-command} ci search "gotchas with auth changes" --type memory

# Find decisions that might be affected
{oak-cli-command} ci search "decisions about token handling"
```

## Example: Before Refactoring

**Task**: Refactoring the `PaymentProcessor` class

```bash
# 1. Find all code conceptually related to payment processing
{oak-cli-command} ci search "payment processing flow" --type code -n 20

# 2. Find code that handles payment errors (often missed)
{oak-cli-command} ci search "payment error handling and recovery" --type code

# 3. Find related integrations
{oak-cli-command} ci search "payment gateway integration" --type code

# 4. Check for past issues/decisions
{oak-cli-command} ci search "payment processing gotchas" --type memory
```

**What you'll find**:
- Order service (processes payments)
- Refund handler (reverses payments)
- Notification service (sends payment confirmations)
- Webhook handlers (receives payment updates)
- Test fixtures (mock payment data)

Many of these won't show up in import analysis!

## Example: Before API Change

**Task**: Changing the response format of `/api/users/{id}`

```bash
# Find all code that might parse this response
{oak-cli-command} ci search "user API response handling" --type code

# Find frontend code consuming this API
{oak-cli-command} ci search "fetch user data from API" --type code

# Find tests that might break
{oak-cli-command} ci search "user API endpoint tests" --type code

# Check for integration patterns
{oak-cli-command} ci context "code that depends on user API format"
```

## Impact Analysis Workflow

1. **Identify the change**: What are you modifying?
2. **Search for direct usage**: `{oak-cli-command} ci search "ComponentName" --type code`
3. **Search for conceptual usage**: `{oak-cli-command} ci search "what ComponentName does" --type code`
4. **Check for patterns**: `{oak-cli-command} ci search "code using similar patterns" --type code`
5. **Review memories**: `{oak-cli-command} ci search "past issues with this area" --type memory`
6. **Read the results**: Assess which code might need updates

## Tips

- Cast a wide net first (`-n 20` or more)
- Search for what the code *does*, not just its name
- Include error handling and edge cases in your search
- Check memories for past issues in this area
- Use `{oak-cli-command} ci context` with the file you're changing for focused results
