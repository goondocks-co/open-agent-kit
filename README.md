# Open Agent Kit

[![PR Check](https://github.com/goondocks-co/open-agent-kit/actions/workflows/pr-check.yml/badge.svg)](https://github.com/goondocks-co/open-agent-kit/actions/workflows/pr-check.yml)
[![Release](https://github.com/goondocks-co/open-agent-kit/actions/workflows/release.yml/badge.svg)](https://github.com/goondocks-co/open-agent-kit/actions/workflows/release.yml)
![GitHub release (latest SemVer)](https://img.shields.io/github/v/release/goondocks-co/open-agent-kit?sort=semver)
[![PyPI](https://img.shields.io/pypi/v/oak-ci?style=flat-square)](https://pypi.org/project/oak-ci/)

[![Python](https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000?style=flat-square)](https://github.com/astral-sh/ruff)

**The Intelligence Layer for AI Agents**

Open Agent Kit (OAK) gives your AI coding assistants (Claude, Copilot, Cursor, etc.) **sight** and **memory**. It runs locally as a background service, indexing your codebase and remembering past decisions to prevent agents from making the same mistakes twice.

![OAK CI Dashboard](docs/src/assets/images/ci-dashboard.png)

## Why OAK?

- **Persistent Memory**: Remembers gotchas, architectural decisions, and bug fixes across sessions
- **Semantic Search**: Find code by *concept* ("where is auth?") rather than just regex
- **Live Auto-Capture**: Watches agent actions and automatically records new learnings

## Quick Start

```bash
# Install
pipx install oak-ci

# Initialize (interactive mode)
oak init

# Start the intelligence layer
oak ci start
```

## Features

| Feature | Description | Docs |
|---------|-------------|------|
| **Codebase Intelligence** | Semantic code search, AST-aware indexing, persistent memory | [Guide](https://goondocks-co.github.io/open-agent-kit/features/codebase-intelligence/) |
| **Rules Management** | Project constitution and coding standards for AI agents | [Guide](https://goondocks-co.github.io/open-agent-kit/features/rules-management/) |
| **Strategic Planning** | RFC workflow for documenting technical decisions | [Guide](https://goondocks-co.github.io/open-agent-kit/features/strategic-planning/) |
| **Language Parsers** | Tree-sitter parsers for 13 languages | [CLI Reference](https://goondocks-co.github.io/open-agent-kit/cli/) |
| **Agent Skills** | Installable skills for specialized agent workflows | [CLI Reference](https://goondocks-co.github.io/open-agent-kit/cli/) |
| **MCP Tools** | `oak_search`, `oak_remember`, `oak_context` for any MCP agent | [Reference](https://goondocks-co.github.io/open-agent-kit/api/mcp-tools/) |

## Supported Agents

| Agent | Hooks | MCP | Commands |
|-------|-------|-----|----------|
| Claude Code | Full | Yes | Yes |
| Gemini CLI | Full | Yes | Yes |
| Cursor | Full | Yes | Yes |
| Codex CLI | Full (OTel) | Yes | Yes |
| GitHub Copilot | — | — | Yes |
| Windsurf | Full | — | Yes |

## Installation

### Quick Install (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.sh | sh
```

### Quick Install (Windows PowerShell)

```powershell
irm https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.ps1 | iex
```

### Package Managers

```bash
pipx install oak-ci    # Recommended
uv tool install oak-ci # Alternative
pip install oak-ci     # Alternative
```

## How It Works

OAK runs a lightweight local daemon that indexes your codebase using AST-aware chunking (tree-sitter) and stores observations in a local vector database (ChromaDB + SQLite). AI agents connect via MCP tools or agent hooks to search code semantically, recall past decisions, and auto-capture new learnings. See the [Architecture](docs/dev/architecture.md) document for details.

## Documentation

Full documentation is available at **[goondocks-co.github.io/open-agent-kit](https://goondocks-co.github.io/open-agent-kit/)**.

Key pages:
- [Getting Started](https://goondocks-co.github.io/open-agent-kit/)
- [CLI Reference](https://goondocks-co.github.io/open-agent-kit/cli/)
- [MCP Tools Reference](https://goondocks-co.github.io/open-agent-kit/api/mcp-tools/)
- [Architecture](docs/dev/architecture.md) (contributor docs)

## Development

```bash
git clone https://github.com/goondocks-co/open-agent-kit.git
cd open-agent-kit
make setup    # Install dependencies
make check    # Run all CI checks
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor guide.

## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) and follow the [Project Constitution](oak/constitution.md).

## Links

- [GitHub Repository](https://github.com/goondocks-co/open-agent-kit)
- [Documentation](https://goondocks-co.github.io/open-agent-kit/)
- [Issue Tracker](https://github.com/goondocks-co/open-agent-kit/issues)
- [PyPI Package](https://pypi.org/project/oak-ci/)
- [Quick Start Guide](QUICKSTART.md)

## License

[MIT](LICENSE)
