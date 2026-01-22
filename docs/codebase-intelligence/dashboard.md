# Web Dashboard

The Codebase Intelligence Dashboard provides a visual interface to your agent's brain. It allows you to explore what the agent knows, search the codebase, and manage project memory.

**Access**: Open `http://localhost:{port}/ui` (The port is unique to your project, use `oak ci port` to find it, or just `oak ci start --open`).

![CI Dashboard](../images/ci-dashboard.png)

## Features

### 1. Dashboard Home
Overview of the system health and indexing status.
-   **Files Indexed**: Total number of source files tracked.
-   **Code Chunks**: Number of semantic vector embeddings.
-   **Memories**: Count of stored observations/learnings.
-   **Recent Sessions**: Activity log of recent agent interactions.

### 2. Search
A playground to test the semantic search capabilities.
-   **Query**: Enter natural language queries e.g., "authentication logic".
-   **Results**: See exactly which code chunks or memories OAK retrieves for that query.
-   **Relevance**: View the similarity score (0-100%) to understand why content was selected.

### 3. Data Explorer
Dive deep into the stored data.
-   **Sessions**: Replay past agent sessions, view inputs, tool outputs, and summaries.
-   **Memories**: View, edit, or delete stored memories.
-   **Prompt Batches**: (Advanced) View background processing of prompts.

### 4. Configuration
Manage your CI settings without editing YAML files.
-   **Resync**: Trigger a full re-index.
-   **Model**: Switch embedding models.
-   **Debug**: Toggle debug logging.

### 5. DevTools
A power-user suite for debugging the CI system itself.
-   **Rebuild Index**: Force a complete wipe and rebuild of the code index.
-   **Processing Reset**: Clear the "processed" state of sessions to force re-summarization.
-   **Rebuild Memories**: Re-embed all memories from the primary store (SQLite) to the vector store (ChromaDB).
