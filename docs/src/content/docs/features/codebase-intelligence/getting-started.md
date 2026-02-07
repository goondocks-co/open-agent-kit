---
title: Getting Started
description: Enable Codebase Intelligence in your project and start the daemon.
sidebar:
  order: 1
---

## Prerequisites

- **Open Agent Kit** installed (`pipx install oak-ci`)
- **Ollama** (Recommended for local embeddings) OR **OpenAI API Key**

## Activation

To add Codebase Intelligence to an existing OAK project:

```bash
oak init --feature codebase-intelligence
```

**What this does automatically:**
- Installs the CI daemon and CLI tools
- Configures **Agent Hooks** for supported agents (Claude, Cursor, Gemini, etc.)
- Registers **MCP Servers** for agents that support it
- Updates **IDE Settings** (VSCode/Cursor) for optimal integration

## Starting the Daemon

The CI feature runs as a background daemon. Start it and open the dashboard:

```bash
oak ci start --open
```

### First Run Setup

On the first run, the daemon will:
1. **Scan your codebase** to detect programming languages
2. **Install Parsers**: Prompt you to install AST parsers (tree-sitter) for better code understanding
3. **Build Index**: Begin indexing your codebase (may take a few minutes for large projects)

The dashboard opens automatically in your browser — you can watch indexing progress in real time.

## Configuration

After the daemon starts, **use the dashboard to configure everything**. Open the **Configuration** page from the sidebar to:

- **Choose your embedding provider** — Select from Ollama, LM Studio, or any OpenAI-compatible endpoint. The UI auto-detects available models and dimensions.
- **Enable summarization** — Optionally connect a local LLM for automatic session summaries.
- **Manage exclusions** — Add directory patterns to skip during indexing (e.g., `dist/**`, `vendor/**`).
- **Tune session quality** — Set thresholds for when sessions get titled and summarized.

<!-- TODO: screenshot of configuration page -->
![The Configuration page with embedding and summarization settings](../../../../assets/images/dashboard-config.png)

:::tip
The dashboard also has a built-in **Help** page with contextual guidance for each feature. Click **Help** in the sidebar for quick answers.
:::

## Verify Installation

Open the dashboard home page to verify everything is working:

- **Files Indexed**: Shows the number of source files tracked
- **Memories**: Count of stored observations
- **Sessions**: Agent sessions being tracked
- **System Health**: Embedding and summarization provider status

You can also check from the terminal:

```bash
oak ci status
```
