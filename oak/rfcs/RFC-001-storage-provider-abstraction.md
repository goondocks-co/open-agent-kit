# RFC-001: Storage Provider Abstraction

**Author:** OAK Engineering
**Date:** 2026-02-22
**Status:** DRAFT
**Tags:** architecture, storage, infrastructure, multi-user

## Summary

OAK's Codebase Intelligence subsystem currently stores all data in a local SQLite database (activities.db) with a local ChromaDB directory for vector search. These are hard-wired — every module imports `sqlite3` directly and every vector operation calls ChromaDB APIs. This RFC introduces a **Storage Provider** abstraction layer that preserves today's behavior while enabling future backends: shared Postgres (with pgvector), cloud-hosted databases, and remote backup targets. The abstraction follows the same pattern already proven by `EmbeddingProvider`.

## Motivation

**Problem Statement**

Today, every team member runs their own local SQLite + ChromaDB stack. Knowledge sharing requires exporting/importing `.sql` backup files through git. This works for individuals but creates friction for teams:

- No live shared state — observations, sessions, and plans are siloed per machine.
- Backup/restore is manual and error-prone, with complex deduplication logic.
- Scaling to larger teams means shipping ever-larger backup files.
- There is no path to cloud-hosted storage without rewriting every storage call site.

The storage layer is deeply coupled to specific technologies:

- **SQLite coupling**: ~15 modules import `sqlite3` directly, use SQLite-specific PRAGMAs (WAL, mmap, cache_size), FTS5 virtual tables, `INSERT OR IGNORE`, and `AUTOINCREMENT`.
- **ChromaDB coupling**: VectorStore directly instantiates `chromadb.PersistentClient`, manages ChromaDB collections, and handles ChromaDB-specific dimension mismatch behavior.

**Impact**

Without this abstraction, any new storage backend (Postgres, cloud DB, etc.) would require touching 20+ files and risk subtle breakage. The current backup-file workflow will not scale to teams beyond 3–5 people.

**Goals**

- [ ] Define abstract interfaces (`RelationalProvider`, `VectorSearchProvider`) that capture the full current API surface.
- [ ] Implement `SQLiteProvider` and `ChromaDBProvider` as the default providers — behavior-identical to today.
- [ ] Refactor `ActivityStore` and `VectorStore` to delegate all storage operations through their respective providers.
- [ ] Centralize provider configuration so backends can be selected via `oak/ci.yaml` or environment variables.
- [ ] Maintain 100% backward compatibility — existing local-first installations see no change.

**Non-Goals**

- [ ] Implementing a Postgres provider (Phase 2).
- [ ] Implementing cloud backup/object storage providers (Phase 3).
- [ ] Changing the data model or schema — this RFC is purely about plumbing.
- [ ] Adding an ORM (SQLAlchemy, etc.) — providers own their SQL dialect directly.
- [ ] Multi-tenancy or user authentication on shared storage — that is a separate concern.
- [ ] Migrating data between providers (e.g., SQLite → Postgres migration tooling).

## Detailed Design

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Consumers (unchanged API)                                       │
│  ActivityProcessor · RetrievalEngine · CodebaseIndexer · CLI     │
├──────────────────────────────────────────────────────────────────┤
│  Store Facades                                                   │
│  ActivityStore                    VectorStore                    │
│  (business logic + delegation)    (business logic + delegation)  │
├─────────────────┬────────────────┬───────────────┬──────────────┤
│  Provider Interfaces (NEW)                                       │
│  ┌─────────────────────────┐     ┌────────────────────────────┐ │
│  │  RelationalProvider     │     │  VectorSearchProvider      │ │
│  │  (Protocol)             │     │  (Protocol)                │ │
│  └────────┬────────────────┘     └─────────┬──────────────────┘ │
│           │                                │                     │
│  ┌────────┴────────┐  ┌─────────┐  ┌──────┴─────────────────┐  │
│  │ SQLiteProvider  │  │ Future: │  │ ChromaDBProvider        │  │
│  │ (default)       │  │ Postgres│  │ (default)               │  │
│  └─────────────────┘  │ Provider│  └────────────────────────┘  │
│                        │ (both) │                               │
│                        └─────────┘                               │
└──────────────────────────────────────────────────────────────────┘
```

Key principles:

1. **Store facades keep their public API** — `ActivityStore.create_session()`, `VectorStore.search_code()`, etc. remain unchanged. Consumers never know about providers.
2. **Providers own the dialect** — SQLiteProvider knows about PRAGMAs, FTS5, `INSERT OR IGNORE`. A future PostgresProvider would use `ON CONFLICT DO NOTHING`, `tsvector`, and `pgvector` operators.
3. **One configuration point** — Provider selection happens at the composition root (daemon `lifespan()`) and flows down through dependency injection.
4. **Postgres can implement both interfaces** — A single `PostgresProvider` class can satisfy both `RelationalProvider` and `VectorSearchProvider` since Postgres + pgvector handles both relational and vector workloads.

### Provider Interfaces

#### RelationalProvider Protocol

This protocol captures the storage operations that `ActivityStore` and its operation modules need. It does **not** expose raw SQL to consumers — instead it provides typed operations that each provider implements in its native dialect.

```python
# src/open_agent_kit/features/codebase_intelligence/storage/relational.py

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CursorResult(Protocol):
    """Minimal cursor interface returned by execute()."""

    @property
    def lastrowid(self) -> int | None: ...
    @property
    def rowcount(self) -> int: ...
    @property
    def description(self) -> list[tuple[str, ...]] | None: ...
    def fetchone(self) -> dict[str, Any] | None: ...
    def fetchall(self) -> list[dict[str, Any]]: ...
    def fetchmany(self, size: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class RelationalProvider(Protocol):
    """Abstract interface for relational (SQL) storage backends.

    Implementations must be thread-safe. Connection pooling and
    lifecycle management are the provider's responsibility.
    """

    # -- Lifecycle --------------------------------------------------------

    def initialize(self, schema_sql: str, schema_version: int) -> None:
        """Ensure the database schema exists, applying migrations as needed.

        Args:
            schema_sql: Full CREATE TABLE/INDEX DDL for fresh databases.
            schema_version: Target schema version number.
        """
        ...

    def close(self) -> None:
        """Release all connections and resources."""
        ...

    @property
    def machine_id(self) -> str:
        """Machine identifier for this provider instance."""
        ...

    # -- Query execution --------------------------------------------------

    def execute(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> CursorResult:
        """Execute a read-write SQL statement.

        Args:
            sql: SQL statement (may use provider-specific dialect).
            params: Positional or named parameters.

        Returns:
            CursorResult with results.
        """
        ...

    def execute_readonly(
        self,
        sql: str,
        params: tuple[Any, ...] | dict[str, Any] = (),
    ) -> CursorResult:
        """Execute a read-only SQL statement.

        Providers may use a separate connection or connection pool
        optimized for reads.
        """
        ...

    def executemany(
        self,
        sql: str,
        params_list: list[tuple[Any, ...]] | list[dict[str, Any]],
    ) -> CursorResult:
        """Execute a statement with multiple parameter sets."""
        ...

    def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements as a script (DDL, migrations)."""
        ...

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Context manager for an explicit transaction.

        Commits on clean exit, rolls back on exception.
        """
        ...

    # -- Schema introspection ---------------------------------------------

    def get_schema_version(self) -> int:
        """Get the current schema version, or 0 if uninitialized."""
        ...

    def get_table_columns(self, table: str) -> set[str]:
        """Get column names for a table."""
        ...

    def column_exists(self, table: str, column: str) -> bool:
        """Check if a column exists in a table."""
        ...

    # -- Dialect helpers ---------------------------------------------------
    # These methods encapsulate SQL dialect differences so that operation
    # modules can call them instead of writing provider-specific SQL.

    def upsert_sql(
        self,
        table: str,
        columns: list[str],
        conflict_columns: list[str],
        update_columns: list[str] | None = None,
    ) -> str:
        """Generate an UPSERT statement in the provider's dialect.

        SQLite: INSERT OR REPLACE / INSERT ... ON CONFLICT
        Postgres: INSERT ... ON CONFLICT ... DO UPDATE

        Args:
            table: Target table name.
            columns: All columns in the INSERT.
            conflict_columns: Columns that define the conflict target.
            update_columns: Columns to update on conflict (None = ignore).

        Returns:
            Parameterized SQL string.
        """
        ...

    def insert_or_ignore_sql(self, table: str, columns: list[str]) -> str:
        """Generate INSERT-or-skip statement.

        SQLite: INSERT OR IGNORE INTO ...
        Postgres: INSERT ... ON CONFLICT DO NOTHING
        """
        ...

    def fts_search(
        self,
        fts_table: str,
        content_table: str,
        query: str,
        columns: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Perform full-text search.

        SQLite: Uses FTS5 MATCH syntax.
        Postgres: Uses tsvector/tsquery.

        Args:
            fts_table: FTS virtual table name (SQLite) or ignored (Postgres).
            content_table: Source table with the data.
            query: Search query string.
            columns: Columns to return.
            limit: Maximum results.

        Returns:
            List of matching rows as dicts.
        """
        ...

    # -- Maintenance ------------------------------------------------------

    def optimize(
        self,
        *,
        vacuum: bool = True,
        analyze: bool = True,
        reindex: bool = False,
    ) -> list[str]:
        """Run provider-specific maintenance operations.

        Returns:
            List of operation names executed.
        """
        ...
```

#### VectorSearchProvider Protocol

This protocol captures the embedding storage and search operations that `VectorStore` needs.

```python
# src/open_agent_kit/features/codebase_intelligence/storage/vector.py

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorSearchProvider(Protocol):
    """Abstract interface for vector/embedding search backends.

    Implementations manage their own connection lifecycle and
    collection/namespace management.
    """

    # -- Lifecycle --------------------------------------------------------

    def initialize(self, embedding_dimensions: int) -> None:
        """Initialize the provider and ensure collections exist.

        Args:
            embedding_dimensions: Dimensionality of embedding vectors.
        """
        ...

    def close(self) -> None:
        """Release all connections and resources."""
        ...

    def update_dimensions(self, new_dimensions: int) -> None:
        """Handle embedding dimension changes (e.g., provider switch).

        May recreate collections/indexes if dimensions changed.
        """
        ...

    # -- Collection management --------------------------------------------

    def ensure_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ensure a collection/namespace exists.

        ChromaDB: get_or_create_collection()
        Postgres: ensure table + ivfflat/hnsw index exists
        """
        ...

    def delete_collection(self, name: str) -> None:
        """Delete an entire collection and its data."""
        ...

    def collection_count(self, name: str) -> int:
        """Count documents in a collection."""
        ...

    # -- Document operations ----------------------------------------------

    def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add or update documents with their embeddings.

        Args:
            collection: Target collection name.
            ids: Document IDs.
            embeddings: Pre-computed embedding vectors.
            documents: Raw document text (stored alongside embeddings).
            metadatas: Per-document metadata dicts.
        """
        ...

    def delete(
        self,
        collection: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> int:
        """Delete documents by IDs or metadata filter.

        Args:
            collection: Target collection.
            ids: Specific document IDs to delete.
            where: Metadata filter (provider-specific operators).

        Returns:
            Number of documents deleted.
        """
        ...

    def get(
        self,
        collection: str,
        ids: list[str],
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch documents by IDs.

        Args:
            collection: Target collection.
            ids: Document IDs to fetch.
            include: What to include: "documents", "metadatas", "embeddings".

        Returns:
            Dict with keys: ids, documents, metadatas, embeddings.
        """
        ...

    # -- Search -----------------------------------------------------------

    def query(
        self,
        collection: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Semantic similarity search.

        Args:
            collection: Collection to search.
            query_embedding: Query vector.
            n_results: Maximum results.
            where: Metadata filter.
            include: What to include in results.

        Returns:
            Dict with keys: ids, documents, metadatas, distances, embeddings.
        """
        ...

    # -- Bulk operations --------------------------------------------------

    def peek(
        self,
        collection: str,
        limit: int = 1,
    ) -> dict[str, Any]:
        """Peek at a sample of documents (for diagnostics).

        Returns:
            Dict with keys: ids, documents, metadatas, embeddings.
        """
        ...

    def list_ids(
        self,
        collection: str,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[str]:
        """List document IDs in a collection.

        Args:
            collection: Target collection.
            where: Optional metadata filter.
            limit: Maximum IDs to return.
            offset: Pagination offset.

        Returns:
            List of document ID strings.
        """
        ...

    # -- Maintenance ------------------------------------------------------

    def hard_reset(self) -> int:
        """Delete all data and reclaim storage.

        Returns:
            Approximate bytes freed (0 if unknown).
        """
        ...
```

### Implementation Details

#### File Layout

New files introduced (under the existing `codebase_intelligence` feature):

```
src/open_agent_kit/features/codebase_intelligence/storage/
├── __init__.py                    # Re-exports protocols + factory
├── relational.py                  # RelationalProvider protocol
├── vector.py                      # VectorSearchProvider protocol
├── factory.py                     # Provider factory (reads config, returns instances)
├── providers/
│   ├── __init__.py
│   ├── sqlite.py                  # SQLiteProvider (implements RelationalProvider)
│   └── chromadb.py                # ChromaDBProvider (implements VectorSearchProvider)
└── dialect/
    ├── __init__.py
    └── sql_compat.py              # Shared SQL compatibility utilities
```

#### SQLiteProvider Implementation Strategy

The `SQLiteProvider` wraps the existing connection management from `ActivityStore`:

- Thread-local connections with WAL mode, mmap, cache_size PRAGMAs
- Read-only connection pool for analysis queries
- `executescript()` for schema DDL
- FTS5 search via `MATCH` operator
- `INSERT OR IGNORE` and `INSERT OR REPLACE` for upsert patterns
- `PRAGMA table_info()` for column introspection

The key refactoring: all the connection management code currently in `ActivityStore.__init__`, `_get_connection`, `_get_readonly_connection`, and `_transaction` moves into `SQLiteProvider`. `ActivityStore` receives a `RelationalProvider` in its constructor instead of a `db_path`.

```python
# Before (current):
class ActivityStore:
    def __init__(self, db_path: Path, machine_id: str):
        self.db_path = db_path
        self._local = threading.local()
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        # ... 20 lines of SQLite-specific setup ...

# After (refactored):
class ActivityStore:
    def __init__(self, provider: RelationalProvider):
        self._provider = provider
        self._ensure_schema()

    # Operation modules use self._provider.execute() instead of
    # self._get_connection().execute()
```

#### ChromaDBProvider Implementation Strategy

The `ChromaDBProvider` wraps the existing ChromaDB initialization from `VectorStore`:

- Lazy `chromadb.PersistentClient` creation with `Settings(anonymized_telemetry=False)`
- Collection management with HNSW configuration
- Dimension mismatch detection and automatic collection recreation
- Maps `upsert()`, `query()`, `delete()`, `get()` to ChromaDB collection methods

```python
# Before (current):
class VectorStore:
    def __init__(self, persist_directory: Path, embedding_provider: EmbeddingProvider):
        self._client: Any = None
        # ... ChromaDB-specific init ...

# After (refactored):
class VectorStore:
    def __init__(
        self,
        vector_provider: VectorSearchProvider,
        embedding_provider: EmbeddingProvider,
    ):
        self._provider = vector_provider
        self.embedding_provider = embedding_provider
```

#### Operation Module Migration

The ~15 operation modules (`sessions.py`, `batches.py`, `activities.py`, `observations.py`, etc.) currently call `store._get_connection().execute(sql, params)`. The migration strategy:

**Phase 1a — Provider passthrough**: Operation modules call `store._provider.execute(sql, params)` instead of `store._get_connection().execute(sql, params)`. This is a mechanical find-and-replace that maintains the exact same SQL. The `SQLiteProvider.execute()` method returns results with the same dict-like row access.

**Phase 1b — Dialect-sensitive operations**: Operations using SQLite-specific syntax are migrated to use provider dialect helpers:

| Current SQLite-specific pattern | Provider method |
|---|---|
| `INSERT OR IGNORE INTO ...` | `provider.insert_or_ignore_sql(table, cols)` |
| `INSERT OR REPLACE INTO ...` | `provider.upsert_sql(table, cols, conflict_cols)` |
| `PRAGMA table_info(t)` | `provider.get_table_columns(table)` |
| `MATCH ?` (FTS5) | `provider.fts_search(fts_table, content_table, query)` |
| `AUTOINCREMENT` in DDL | Provider-specific schema SQL |

Operations that use standard SQL (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`, `CREATE INDEX`) remain unchanged — standard SQL works across SQLite and Postgres.

#### Composition Root Changes

The daemon's `lifespan()` function becomes the provider factory call site:

```python
# src/open_agent_kit/features/codebase_intelligence/daemon/server.py

async def lifespan(app):
    from open_agent_kit.features.codebase_intelligence.storage.factory import (
        create_relational_provider,
        create_vector_provider,
    )

    # Provider selection reads from ci.yaml or env vars
    relational = create_relational_provider(config, machine_id)
    vector = create_vector_provider(config, embedding_chain)

    state.activity_store = ActivityStore(relational)
    state.vector_store = VectorStore(vector, embedding_chain)
    # ... rest of initialization unchanged ...
```

#### Provider Factory

```python
# src/open_agent_kit/features/codebase_intelligence/storage/factory.py

def create_relational_provider(
    config: CIConfig,
    machine_id: str,
) -> RelationalProvider:
    """Create a relational storage provider based on configuration.

    Default: SQLiteProvider (local file).
    Future: PostgresProvider (shared database).
    """
    backend = config.storage.relational_backend  # "sqlite" (default)

    if backend == "sqlite":
        from .providers.sqlite import SQLiteProvider
        return SQLiteProvider(
            db_path=config.storage.sqlite_path,
            machine_id=machine_id,
        )
    # Future:
    # elif backend == "postgres":
    #     from .providers.postgres import PostgresProvider
    #     return PostgresProvider(dsn=config.storage.postgres_dsn, ...)

    raise ValueError(f"Unknown relational backend: {backend}")


def create_vector_provider(
    config: CIConfig,
    embedding_provider: EmbeddingProvider,
) -> VectorSearchProvider:
    """Create a vector search provider based on configuration.

    Default: ChromaDBProvider (local directory).
    Future: PostgresVectorProvider (pgvector).
    """
    backend = config.storage.vector_backend  # "chromadb" (default)

    if backend == "chromadb":
        from .providers.chromadb import ChromaDBProvider
        return ChromaDBProvider(
            persist_directory=config.storage.chroma_path,
        )
    # Future:
    # elif backend == "pgvector":
    #     from .providers.postgres import PostgresVectorProvider
    #     return PostgresVectorProvider(dsn=config.storage.postgres_dsn, ...)

    raise ValueError(f"Unknown vector backend: {backend}")
```

### Configuration

Add a `storage` section to `oak/ci.yaml`:

```yaml
# oak/ci.yaml (new storage section)
storage:
  # Relational backend: "sqlite" (default) | "postgres" (future)
  relational_backend: sqlite

  # SQLite-specific (used when relational_backend=sqlite)
  # sqlite_path is auto-resolved to .oak/ci/activities.db if omitted

  # Vector search backend: "chromadb" (default) | "pgvector" (future)
  vector_backend: chromadb

  # ChromaDB-specific (used when vector_backend=chromadb)
  # chroma_path is auto-resolved to .oak/ci/chroma/ if omitted

  # Future: shared Postgres configuration
  # postgres:
  #   dsn: "postgresql://user:pass@host:5432/oak_ci"
  #   pool_size: 5
  #   ssl: true
```

Environment variable overrides (following existing OAK patterns):

```
OAK_CI_RELATIONAL_BACKEND=sqlite
OAK_CI_VECTOR_BACKEND=chromadb
# Future:
# OAK_CI_POSTGRES_DSN=postgresql://...
```

### Data Model

No schema changes. The SQLite schema (`schema.py`) and ChromaDB collections remain identical. The provider abstraction sits beneath the data model — it's about *how* data is stored, not *what* is stored.

### Migration Strategy

This refactoring is done in a sequence of backward-compatible steps:

**Step 1: Introduce protocols and default providers** (no behavior change)
- Create `storage/` package with protocols
- Implement `SQLiteProvider` and `ChromaDBProvider` that wrap current behavior
- Add factory functions

**Step 2: Wire providers at composition root** (no behavior change)
- Update daemon `lifespan()` to use factory
- `ActivityStore` and `VectorStore` accept providers
- Keep backward-compatible constructors that auto-create default providers

**Step 3: Migrate operation modules** (no behavior change)
- Systematic migration of `store._get_connection().execute()` → `store._provider.execute()`
- One module at a time, each as a separate commit
- Tests validate identical behavior after each commit

**Step 4: Extract dialect-specific patterns** (no behavior change)
- Move FTS5 calls to `provider.fts_search()`
- Move `INSERT OR IGNORE` to `provider.insert_or_ignore_sql()`
- Move `PRAGMA table_info` to `provider.get_table_columns()`

**Step 5: Remove deprecated internal APIs** (cleanup)
- Remove `ActivityStore._get_connection()` (now internal to provider)
- Remove `ActivityStore._get_readonly_connection()`
- Remove `ActivityStore._transaction()` (now `provider.transaction()`)

Each step is independently deployable and testable. Rollback at any point is simply reverting the commit.

### Backup/Restore Implications

The current backup system (SQL dump files in `oak/history/`) continues to work unchanged for SQLite. When a shared Postgres backend is active, backup/restore semantics change fundamentally:

- **Shared backend**: No backup files needed — all team members connect to the same database. The backup directory becomes a local cache/fallback.
- **Hybrid**: A team might use shared Postgres for primary storage but still generate local backups for disaster recovery.

This RFC does **not** change the backup system. A future RFC should address backup strategy when shared backends are introduced.

## Drawbacks

- [x] **Migration effort**: ~15 operation modules need mechanical updates to use provider methods instead of direct SQLite calls. Mitigation: this is a systematic find-and-replace with high test coverage.
- [x] **Indirection cost**: One extra function call layer between store and database. Mitigation: negligible for I/O-bound operations; the database round-trip dominates.
- [x] **Testing surface**: Each new provider implementation needs its own test suite. Mitigation: protocol-based contract tests that any provider must pass.
- [x] **Dialect divergence risk**: As providers accumulate, SQL differences may cause subtle bugs. Mitigation: comprehensive contract tests; dialect helpers centralize differences.

## Alternatives

### Alternative 1: SQLAlchemy ORM

**Description**
Use SQLAlchemy as the abstraction layer, replacing raw SQL with ORM models.

**Pros**
- [ ] Mature, battle-tested library with dialect support for SQLite and Postgres.
- [ ] Automatic schema migration via Alembic.

**Cons**
- [x] Heavy dependency (~15MB) for a CLI tool that values minimal footprint.
- [x] ORM overhead for the simple append-heavy workload OAK uses.
- [x] FTS5 and pgvector support require SQLAlchemy extensions with their own complexity.
- [x] Forces an ORM paradigm on a codebase designed around raw SQL — large rewrite.

### Alternative 2: Abstract at the Store Level

**Description**
Make `ActivityStore` and `VectorStore` themselves abstract (ABC), with `SQLiteActivityStore` and `ChromaDBVectorStore` as concrete implementations.

**Pros**
- [ ] Cleaner separation — no shared SQL between implementations.

**Cons**
- [x] Duplicates 100+ methods across implementations (ActivityStore's full API surface).
- [x] Every operation module gets duplicated per provider — massive code bloat.
- [x] Harder to share business logic between providers.

### Alternative 3: Do Nothing (Status Quo)

**Description**
Keep direct SQLite/ChromaDB coupling and address shared storage when specifically needed.

**Pros**
- [ ] No immediate work needed.
- [ ] Simpler codebase without abstraction layers.

**Cons**
- [x] Every future backend requires touching 20+ files.
- [x] Team scaling remains blocked on backup-file workflow.
- [x] Accumulates more technical debt as more modules are added.

## Security Considerations

- **Shared database credentials**: When Postgres is introduced, connection strings will contain credentials. These must never be committed to git. OAK already supports `.env` files and environment variables for sensitive configuration.
- **Network exposure**: Shared Postgres connections traverse the network. SSL/TLS should be required by default for non-localhost connections.
- **SQL injection**: The provider protocol uses parameterized queries exclusively. Raw SQL string concatenation is prohibited in the protocol design.
- **Read-only isolation**: The `execute_readonly()` method must enforce read-only access regardless of backend. SQLite uses `?mode=ro` URI; Postgres would use a read-only transaction or role.

## Performance Implications

- **Local (SQLite/ChromaDB)**: No measurable performance change. The abstraction adds one Python function call per database operation — negligible compared to I/O.
- **Remote (future Postgres)**: Network latency replaces local file I/O. Batch operations (`add_activities`, `add_code_chunks_batched`) become critical for performance. The provider protocol's `executemany()` and bulk `upsert()` methods are designed for this.
- **Connection pooling**: Remote providers will need connection pools. The protocol's lifecycle methods (`initialize()`, `close()`) accommodate this.

## Testing Strategy

- **Contract tests**: A shared test suite that any `RelationalProvider` implementation must pass. Tests CRUD operations, transactions, schema management, FTS, and edge cases. Run against both SQLiteProvider and future PostgresProvider.
- **Contract tests (vector)**: Same pattern for `VectorSearchProvider` — tests upsert, query, delete, dimension handling. Run against ChromaDBProvider and future PgvectorProvider.
- **Integration tests**: Existing store-level tests continue to work unchanged (they test through the store facade).
- **Regression tests**: Before/after comparison ensuring `ActivityStore` produces identical results with the provider layer vs. direct SQLite calls.

## Rollout Plan

1. **Phase 1 — Abstraction layer** (this RFC): Introduce protocols, implement SQLite/ChromaDB providers, refactor stores to use providers. All behavior unchanged. Timeline: 2–3 weeks of incremental commits.

2. **Phase 2 — Postgres provider**: Implement `PostgresProvider` (relational) and `PostgresVectorProvider` (pgvector). Add connection pooling, SSL, shared-storage configuration. Requires a separate RFC.

3. **Phase 3 — Cloud storage**: Object storage providers for backups (S3, GCS). Remote backup targets. Cloud-managed vector databases (Pinecone, Weaviate) as additional vector provider options. Requires a separate RFC.

## Monitoring and Observability

- **Logging**: Provider initialization logs backend type, connection details (redacted), and version info. Query failures log the provider type for debugging.
- **Metrics (future)**: When shared backends are introduced, add query latency histograms, connection pool utilization, and error rate counters.
- **Health checks (future)**: Shared backends need connectivity health checks in the daemon status endpoint.

## Documentation

- [ ] Update `oak/constitution.md` Anchor Index with new storage provider paths.
- [ ] Add `storage/` to the feature architecture docs.
- [ ] Document provider configuration in `oak/ci.yaml` reference.
- [ ] Add "How to implement a storage provider" guide for contributors.

## Unresolved Questions

- [ ] Should the `RelationalProvider` protocol expose cursor-based iteration for large result sets, or is `fetchall()` sufficient for OAK's data volumes?
- [ ] Should backup/restore be part of the `RelationalProvider` protocol, or remain a separate concern that reads provider configuration?
- [ ] For shared Postgres, should locking/concurrency be handled at the provider level or the store level? (Multiple daemon instances writing simultaneously.)
- [ ] Should the FTS abstraction be part of `RelationalProvider` or a separate `FullTextSearchProvider` protocol for cases where FTS is backed by a different system (Elasticsearch, Meilisearch)?

## Future Work

- [ ] **PostgresProvider**: Full implementation with pgvector, connection pooling, and SSL. Enables team-shared storage.
- [ ] **Cloud backup providers**: S3/GCS object storage for backup files instead of local git-tracked directories.
- [ ] **Provider health monitoring**: Dashboard showing storage backend health, latency, and capacity.
- [ ] **Data migration tooling**: `oak ci migrate --from sqlite --to postgres` for seamless transitions.
- [ ] **Multi-tenant Postgres**: Schema-per-project isolation for teams sharing a single Postgres instance.
- [ ] **Hybrid mode**: Local SQLite as write-ahead cache with async replication to shared Postgres (eventual consistency for offline work).

## References

- `src/open_agent_kit/features/codebase_intelligence/activity/store/core.py` — Current ActivityStore (SQLite)
- `src/open_agent_kit/features/codebase_intelligence/memory/store/core.py` — Current VectorStore (ChromaDB)
- `src/open_agent_kit/features/codebase_intelligence/embeddings/base.py` — EmbeddingProvider pattern (prior art)
- `src/open_agent_kit/features/codebase_intelligence/daemon/server.py` — Composition root
- `src/open_agent_kit/features/codebase_intelligence/activity/store/schema.py` — Current SQLite schema
- `src/open_agent_kit/features/codebase_intelligence/activity/store/backup.py` — Current backup/restore system

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-02-22 | 0.1 | Initial draft | OAK Engineering |
