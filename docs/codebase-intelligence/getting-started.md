# Getting Started with Codebase Intelligence

This guide will help you enable Codebase Intelligence (CI) in your project and start the daemon.

## Prerequisites

-   **Open Agent Kit** installed (`uv tool install open-agent-kit`)
-   **Docker** (Optional: only if using containerized vector stores, otherwise runs locally)
-   **Ollama** (Recommended for local embeddings) OR **OpenAI API Key**

## Activation

To add Codebase Intelligence to an existing OAK project:

```bash
oak init --feature codebase-intelligence
```

**What this does automatically:**
- [x] Installs the CI daemon and CLI tools.
- [x] Configures **Agent Hooks** for supported agents (Claude, Cursor, etc.).
- [x] Registers **MCP Servers** for agents that support it.
- [x] Updates **IDE Settings** (VSCode/Cursor) for optimal integration.

## Starting the Daemon

The CI feature runs as a background daemon. You need to start it to enable indexing and search.

```bash
oak ci start
```

### First Run Setup
On the first run, `oak ci start` will:
1.  **Scan your codebase** to detect programming languages.
2.  **Install Parsers**: Prompt you to install AST parsers (tree-sitter) for better code understanding.
3.  **Build Index**: Begin indexing your codebase. This may take a few minutes for large projects.

> [!TIP]
> Use `oak ci start --open` to automatically open the Web Dashboard in your browser.

## Configuration

The daemon is configured via `.oak/config.yaml` or the Web Dashboard.

### Embedding Provider
By default, OAK attempts to use **Ollama** (`nomic-embed-text`) for cost-free, local privacy.

To change the provider:

```bash
# Use OpenAI (requires OPENAI_API_KEY environment variable)
oak ci config --provider openai --model text-embedding-3-small

# Use a custom local endpoint (e.g. LMStudio)
oak ci config --provider openai --base-url http://localhost:1234/v1
```

### Exclusions
To prevent indexing of generated files or vendor directories, use the exclude command:

```bash
oak ci exclude -a "dist/**"
oak ci exclude -a "third_party/**"
```

## Verify Installation

Check the status of the daemon and index:

```bash
oak ci status
```

You should see:
-   **Daemon**: Running
-   **Index**: Ready (with chunk count)
