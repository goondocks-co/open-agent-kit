# open-agent-kit Documentation

Welcome to the open-agent-kit documentation. This directory contains comprehensive guides, references, and development documentation.

---

## 📚 Documentation Index

### Getting Started

- **[Main README](../README.md)** - Project overview, features, installation
- **[Quick Start Guide](../QUICKSTART.md)** - Get up and running in 5 minutes
- **[Features System](../README.md#features)** - Modular feature selection and management
- **[RFC Workflow](rfc-workflow.md)** - Complete RFC process and lifecycle
- **[Constitution Workflow](../QUICKSTART.md#creating-a-project-constitution)** - Create engineering standards and conventions
- **[Constitution Upgrade Guide](constitution-upgrade-guide.md)** - Modernize existing constitutions with decision framework
- **[Codebase Intelligence](features/codebase-intelligence.md)** - Semantic code search and AI agent memory

### Contributing

- **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute
- **[Constitution](../oak/constitution.md)** - Project standards and principles
- **[Releasing](development/releasing.md)** - How to create releases

### For AI Agents

- **[Claude Instructions](../CLAUDE.md)** - Claude Code specific guidance
- **[Agent Instructions](../AGENTS.md)** - Codex, Cursor, and compatible agents
- **[Copilot Instructions](../.github/copilot-instructions.md)** - GitHub Copilot guidance

**Note:** When you create a project constitution (via `/oak.constitution-create`), open-agent-kit automatically updates these agent instruction files to reference the constitution. Existing content is preserved - only a constitution reference is appended. See [Agent Instruction Files](../README.md#agent-instruction-files) for details.

### Development

- **[Architecture](development/architecture.md)** - System architecture and design patterns
- **[GitHub Workflows](../.github/WORKFLOWS.md)** - CI/CD workflows documentation

### Reference

- **[Project Constitution](../oak/constitution.md)** - Central reference for all standards
- **[License](../LICENSE)** - MIT License (Internal Use)

---

## 📖 Quick Links by Topic

### I Want To...

#### Use open-agent-kit

| Task | Documentation |
|------|---------------|
| Install and set up | [Quick Start](../QUICKSTART.md) |
| Select features during init | [README - Features](../README.md#features) |
| Add/remove features | [README - Managing Features](../README.md#managing-features) |
| Create my first RFC | [Quick Start](../QUICKSTART.md#step-2-create-your-first-rfc) |
| Create a project constitution | [Quick Start - Constitution](../QUICKSTART.md#creating-a-project-constitution) |
| Upgrade existing constitution | [Constitution Upgrade Guide](constitution-upgrade-guide.md) |
| Understand RFC workflow | [RFC Workflow](rfc-workflow.md) |
| List/manage RFCs | [README - Commands](../README.md#commands) |
| Set up Codebase Intelligence | [Codebase Intelligence](features/codebase-intelligence.md) |
| Configure embedding providers | [CI - Configuration](features/codebase-intelligence.md#configuration) |

#### Contribute to open-agent-kit

| Task | Documentation |
|------|---------------|
| Get started contributing | [Contributing Guide](../CONTRIBUTING.md) |
| Understand code standards | [Constitution - Code Standards](../.constitution.md#iv-code-standards) |
| Add a new feature | [Feature Development](development/features.md) |
| Add a new command | [Claude Instructions - Adding Commands](../CLAUDE.md#vi-adding-new-commands) |
| Add a new agent | [Constitution - Agent Integration](../.constitution.md#ix-ai-agent-integration) |
| Write tests | [Constitution - Testing](../.constitution.md#vii-testing-strategy) |
| Fix a bug | [Contributing - Bug Fixes](../CONTRIBUTING.md#fixing-bugs) |

#### Release open-agent-kit

| Task | Documentation |
|------|---------------|
| Create a release | [Releasing Guide](development/releasing.md#creating-a-release) |
| Understand versioning | [Releasing - Version Numbering](development/releasing.md#version-numbering) |
| Troubleshoot releases | [Releasing - Troubleshooting](development/releasing.md#troubleshooting) |
| Understand workflows | [GitHub Workflows](../.github/WORKFLOWS.md) |

#### Work with AI Agents

| Task | Documentation |
|------|---------------|
| Use Claude Code | [Claude Instructions](../CLAUDE.md) |
| Use Codex/Cursor | [Agent Instructions](../AGENTS.md) |
| Use GitHub Copilot | [Copilot Instructions](../.github/copilot-instructions.md) |
| Generate RFCs with AI | [Claude - RFC Generation](../CLAUDE.md#vii-rfc-generation-your-specialty) |
| Review RFCs with AI | [Claude - RFC Review](../CLAUDE.md#viii-rfc-review-another-specialty) |
| Create constitutions with AI | [Quick Start - Constitution](../QUICKSTART.md#creating-a-project-constitution) |
| Understand agent instruction files | [README - Agent Instruction Files](../README.md#agent-instruction-files) |
| Give AI agents codebase knowledge | [CI - MCP Integration](features/codebase-intelligence.md#mcp-integration) |
| Use semantic code search | [CI - Search](features/codebase-intelligence.md#search-tab) |

---

## 🏗️ Architecture Overview

open-agent-kit follows a layered architecture:

```
┌─────────────────────────────────┐
│     CLI Layer (Typer/Rich)      │  ← User commands
├─────────────────────────────────┤
│      Command Implementations     │  ← init, rfc, etc.
├─────────────────────────────────┤
│      Service Layer (Business)    │  ← RFCService, etc.
├─────────────────────────────────┤
│      Model Layer (Pydantic)      │  ← Data structures
├─────────────────────────────────┤
│   Storage Layer (Filesystem)     │  ← YAML, templates
└─────────────────────────────────┘
```

**Learn more:** [Architecture Documentation](architecture.md)

---

## 🔧 Technology Stack

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.13+ |
| **CLI Framework** | Typer |
| **Terminal UI** | Rich |
| **Templates** | Jinja2 |
| **Data Models** | Pydantic |
| **Configuration** | YAML |
| **Testing** | pytest |
| **Linting** | ruff |
| **Formatting** | black |
| **Type Checking** | mypy |

---

## 📝 Documentation Standards

### File Organization

```
docs/
├── README.md                       # This file - documentation index
├── rfc-workflow.md                 # RFC process and lifecycle
├── constitution-upgrade-guide.md   # Constitution modernization paths
├── features/                       # Feature documentation
│   ├── constitution.md            # Constitution feature
│   ├── codebase-intelligence.md   # Codebase Intelligence (CI)
│   └── ...                        # Other feature docs
├── development/                    # Development guides
│   ├── releasing.md               # Release procedures
│   └── ...                        # Other development docs
├── workflows/                      # Workflow documentation
└── archive/                        # Historical/build docs
```

### Naming Conventions

- Use **lowercase** with **hyphens** for file names
- Use `.md` extension for markdown files
- Keep names **descriptive** and **concise**
- Examples: `rfc-workflow.md`, `architecture.md`

### Markdown Standards

- Follow markdown best practices
- Use proper heading hierarchy (# → ## → ###)
- Include table of contents for long documents
- Add code examples where helpful
- Link to related documentation

---

## 🤝 Contributing to Documentation

Documentation improvements are always welcome!

### How to Contribute Docs

1. **Find what to improve:**
   - Unclear explanations
   - Missing examples
   - Outdated information
   - Typos or errors

2. **Make your changes:**
   - Follow markdown standards
   - Keep language clear and concise
   - Add examples where helpful
   - Update links if moving files

3. **Test your changes:**
   - Check all links work
   - Verify code examples are correct
   - Ensure formatting is consistent

4. **Submit a PR:**
   - Clear description of changes
   - Why the improvement helps
   - Any related issues

---

## 📮 Getting Help

### Documentation Issues

If you find issues with documentation:

1. **Check existing docs** first
2. **Search GitHub issues** for similar questions
3. **Open a new issue** with details:
   - What documentation is unclear?
   - What would make it better?
   - Any suggestions for improvement?

### Code Questions

For code-related questions:

1. **Read the constitution**: [.constitution.md](../oak/constitution.md)
2. **Check existing code**: Look for similar patterns
3. **Review tests**: Often show usage examples
4. **Ask the team**: Open an issue or discussion

---

## 📊 Documentation Coverage

### Core Documentation

- [x] README - Main overview
- [x] Quick Start - Getting started guide
- [x] Contributing - Contribution guidelines
- [x] Constitution - Project standards
- [x] RFC Workflow - RFC process
- [x] Constitution Upgrade Guide - Modernization paths
- [x] Releasing - Release procedures
- [x] Architecture - System design
- [x] GitHub Workflows - CI/CD docs
- [x] Codebase Intelligence - Semantic search and AI memory

### Agent Documentation

- [x] Claude Code instructions
- [x] General agent instructions
- [x] GitHub Copilot instructions

### Additional Guides

- [ ] Advanced configuration guide
- [ ] Troubleshooting guide
- [ ] API reference (if/when needed)

---

## 🎯 Documentation Principles

### 1. Clear and Concise

- Use simple language
- Get to the point quickly
- Avoid unnecessary jargon
- Explain technical terms

### 2. Example-Driven

- Show, don't just tell
- Include code examples
- Provide real-world scenarios
- Add command-line examples

### 3. Well-Organized

- Logical structure
- Clear headings
- Table of contents for long docs
- Cross-references where appropriate

### 4. Up-to-Date

- Keep in sync with code
- Update when features change
- Mark deprecated features
- Remove outdated information

### 5. Accessible

- Easy to find
- Good navigation
- Search-friendly
- Link to related docs

---

## 📚 External Resources

### Python & Tools

- [Python Documentation](https://docs.python.org/3/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)

### Standards & Best Practices

- [PEP 8 Style Guide](https://pep8.org/)
- [Semantic Versioning](https://semver.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Keep a Changelog](https://keepachangelog.com/)

### GitHub & Git

- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Markdown Guide](https://www.markdownguide.org/)

---

## 📞 Contact

For questions about documentation:

- **Issues:** [GitHub Issues](https://github.com/sirkirby/open-agent-kit/issues)
- **General:** See [Contributing Guide](../CONTRIBUTING.md)

---

## 📜 License

This documentation is part of open-agent-kit and is covered by the project's MIT License. See [LICENSE](../LICENSE) for details.

---

**Last Updated:** 2025-11-13
**Version:** 1.0.0

For the latest documentation, always refer to the main branch in the GitHub repository.
