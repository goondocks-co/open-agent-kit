---
title: OAK Agents
description: Built-in agents that run within OAK's daemon for automated tasks.
sidebar:
  order: 4
---

OAK Agents are AI agents that run within OAK's daemon, powered by the Claude Agent SDK. They are distinct from external coding agents (Claude Code, Cursor, Codex, etc.) — those are documented in [Coding Agents](/open-agent-kit/agents/).

## What are OAK Agents?

OAK Agents use CI's semantic search for code context to perform automated tasks. They run locally on your machine, using whatever LLM provider you've configured. Each agent has:

- **A set of built-in tasks** — Pre-configured work items that ship with OAK
- **Custom task support** — You can create your own tasks that agents will pick up automatically
- **Run history** — Every agent run is logged with status, output, and timing

## Documentation Agent

The first built-in OAK Agent is the **Documentation Agent**. It uses CI's semantic search to understand your codebase and create accurate, context-aware documentation.

### Built-in Tasks

OAK ships built-in task templates for each agent. You can run them directly or use them as starting points for custom tasks.

![Agents page showing templates and task list](../../../../assets/images/agents-page.png)

## Running Tasks

1. Navigate to the **Agents** page in the dashboard
2. Select a task from the task list
3. Click **Run** to start the agent
4. Watch progress in real time — output streams as the agent works
5. View completed runs in the **Run History** section

### Run History

Every agent run is recorded with:
- **Status** — Running, completed, failed, or cancelled
- **Output** — Full agent output including any generated files
- **Timing** — Start time, duration, and token usage
- **Cancellation** — Cancel a running agent at any time

## Custom Tasks

You can create custom tasks that OAK Agents will automatically pick up.

### Task Directory

Custom tasks are stored in `oak/ci/agents/` (git-tracked). Each task is a markdown file:

```
oak/ci/agents/
  documentation/          # Agent name
    my-custom-task.md     # Task file
    another-task.md
```

### Task Format

Task files are markdown with YAML frontmatter:

```markdown
---
name: Generate API docs
description: Create API documentation for all public endpoints
agent: documentation
---

Generate comprehensive API documentation for all public endpoints
in this project. Include request/response examples and error codes.
```

### Creating Tasks from Templates

The dashboard provides a **Create Task** button that lets you create a new task from an existing template. This copies the template to `oak/ci/agents/` where you can customize it.

You can also copy an existing task and modify it for a different purpose.

## Scheduling

Tasks can be scheduled to run automatically at configured intervals. Manage schedules from the Agents page in the dashboard — enable/disable individual task schedules and configure run frequency.

## Provider Configuration

OAK Agents use the LLM provider configured in the **Agents** section of the Configuration page. This is separate from the summarization model — you may want a more capable model for agent tasks.

Test the connection from the Configuration page before running agents.
