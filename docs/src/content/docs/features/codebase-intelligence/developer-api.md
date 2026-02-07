---
title: Developer API
description: REST API reference for the CI daemon.
sidebar:
  order: 6
---

The CI daemon exposes a FastAPI REST interface at `http://localhost:{port}/api`.

## Base URL

The port is dynamic per project. Find it with:
```bash
oak ci port
```

## Endpoints

### Health & Status

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Basic liveness check |
| `GET` | `/api/status` | Detailed daemon status and process info |
| `GET` | `/api/index/status` | Indexing progress and stats |

### Search & Retrieval

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/search` | Search code and memories. Query params: `q`, `limit`, `type` |
| `POST` | `/api/search` | JSON body search |
| `POST` | `/api/fetch` | Retrieve full content for specific chunk IDs |
| `POST` | `/api/remember` | Manually store a memory observation |

### Agent Hooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/hook/session-start` | Initialize session context. Returns injected prompt |
| `POST` | `/api/hook/post-tool-use` | Report tool execution for auto-capture |
| `POST` | `/api/hook/stop` | Finalize session and trigger summarization |

### Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/config` | Get current runtime config |
| `POST` | `/api/config/test` | Test connection to embedding provider |
| `POST` | `/api/restart` | Restart the daemon to apply config changes |

### DevTools

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/devtools/rebuild-index` | Force re-indexing of code |
| `POST` | `/api/devtools/reset-processing` | Reset session state for re-processing |
| `POST` | `/api/devtools/rebuild-memories` | Re-embed memories from SQL to Vector Store |

See also the [MCP Tools Reference](/open-agent-kit/api/mcp-tools/) for the MCP protocol tools exposed to agents.
