"""MCP tool handlers for Codebase Intelligence.

Exposes tools that AI agents can call via MCP protocol:
- oak_search: Search code and memories semantically
- oak_remember: Store observations for future retrieval
- oak_context: Get relevant context for current task

These tools are the primary interface for all agents, more universal
than skills which are only supported in Claude Code.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Tool Input Schemas (following MCP tool specification)


class OakSearchInput(BaseModel):
    """Input for oak_search tool."""

    query: str = Field(..., description="Natural language search query")
    search_type: str = Field(
        default="all",
        description="Type of search: 'code', 'memory', or 'all'",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=50,
    )


class OakRememberInput(BaseModel):
    """Input for oak_remember tool."""

    observation: str = Field(
        ...,
        description="The observation or learning to remember",
    )
    memory_type: str = Field(
        default="discovery",
        description="Type: 'gotcha', 'bug_fix', 'decision', 'discovery', 'trade_off'",
    )
    context: str | None = Field(
        default=None,
        description="Related file path or context information",
    )


class OakContextInput(BaseModel):
    """Input for oak_context tool."""

    task: str = Field(
        ...,
        description="Description of the current task or what you're working on",
    )
    current_files: list[str] = Field(
        default_factory=list,
        description="Files currently being viewed or edited",
    )
    max_tokens: int = Field(
        default=2000,
        description="Maximum tokens of context to return",
    )


# Tool Definitions (for MCP registration)

MCP_TOOLS = [
    {
        "name": "oak_search",
        "description": (
            "Search the codebase and project memories using semantic similarity. "
            "Use this to find relevant code implementations, past decisions, gotchas, "
            "and learnings. Returns ranked results with relevance scores."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query (e.g., 'authentication middleware', 'database connection handling')",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["all", "code", "memory"],
                    "default": "all",
                    "description": "Search code, memories, or both",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "oak_remember",
        "description": (
            "Store an observation, decision, or learning for future sessions. "
            "Use this when you discover something important about the codebase "
            "that would help in future work. Types: gotcha (pitfalls), bug_fix "
            "(how issues were resolved), decision (architecture choices), "
            "discovery (learned facts), trade_off (compromises made)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "observation": {
                    "type": "string",
                    "description": "The observation or learning to store",
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["gotcha", "bug_fix", "decision", "discovery", "trade_off"],
                    "default": "discovery",
                    "description": "Type of observation",
                },
                "context": {
                    "type": "string",
                    "description": "Related file path or additional context",
                },
            },
            "required": ["observation"],
        },
    },
    {
        "name": "oak_context",
        "description": (
            "Get relevant context for your current task. Call this when starting "
            "work on something to retrieve related code, past decisions, and "
            "applicable project guidelines. Returns a curated set of context "
            "optimized for the task at hand."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Description of what you're working on",
                },
                "current_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files currently being viewed/edited",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Maximum tokens of context to return",
                },
            },
            "required": ["task"],
        },
    },
]


class MCPToolHandler:
    """Handler for MCP tool calls.

    Processes tool calls and returns results in MCP-compatible format.
    """

    def __init__(self, vector_store: Any, embedding_chain: Any) -> None:
        """Initialize handler.

        Args:
            vector_store: VectorStore instance for searching.
            embedding_chain: EmbeddingProviderChain for embeddings.
        """
        self.vector_store = vector_store
        self.embedding_chain = embedding_chain

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP tool call.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool arguments.

        Returns:
            Tool result in MCP format.
        """
        handlers = {
            "oak_search": self._handle_search,
            "oak_remember": self._handle_remember,
            "oak_context": self._handle_context,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            }

        try:
            result = handler(arguments)
            return {
                "content": [{"type": "text", "text": result}],
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.exception(f"Tool {tool_name} failed: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {str(e)}"}],
            }

    def _handle_search(self, args: dict[str, Any]) -> str:
        """Handle oak_search tool call."""
        input_data = OakSearchInput(**args)

        results: dict[str, list[dict[str, Any]]] = {"code": [], "memory": []}

        if input_data.search_type in ("all", "code"):
            code_results = self.vector_store.search_code(
                query=input_data.query,
                limit=input_data.limit,
            )
            results["code"] = [
                {
                    "file": r["filepath"],
                    "name": r.get("name", ""),
                    "type": r.get("chunk_type", ""),
                    "lines": f"{r.get('start_line', 0)}-{r.get('end_line', 0)}",
                    "relevance": round(r["relevance"], 2),
                    "preview": (
                        r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
                    ),
                }
                for r in code_results
            ]

        if input_data.search_type in ("all", "memory"):
            memory_results = self.vector_store.search_memory(
                query=input_data.query,
                limit=input_data.limit,
            )
            results["memory"] = [
                {
                    "type": r.get("memory_type", ""),
                    "observation": r["observation"],
                    "context": r.get("context", ""),
                    "relevance": round(r["relevance"], 2),
                }
                for r in memory_results
            ]

        # Format as readable text
        output = [f"Search results for: {input_data.query}\n"]

        if results["code"]:
            output.append("## Code Results\n")
            for r in results["code"]:
                output.append(
                    f"- **{r['file']}** ({r['type']}: {r['name']}) "
                    f"[lines {r['lines']}] (relevance: {r['relevance']})\n"
                    f"  ```\n  {r['preview']}\n  ```\n"
                )

        if results["memory"]:
            output.append("## Memories\n")
            for r in results["memory"]:
                output.append(
                    f"- [{r['type']}] {r['observation']}"
                    f"{' (context: ' + r['context'] + ')' if r['context'] else ''}\n"
                )

        if not results["code"] and not results["memory"]:
            output.append("No results found.")

        return "\n".join(output)

    def _handle_remember(self, args: dict[str, Any]) -> str:
        """Handle oak_remember tool call."""
        input_data = OakRememberInput(**args)

        from open_agent_kit.features.codebase_intelligence.memory.store import MemoryObservation

        observation = MemoryObservation(
            id=str(uuid4()),
            observation=input_data.observation,
            memory_type=input_data.memory_type,
            context=input_data.context,
            created_at=datetime.now(),
        )

        observation_id = self.vector_store.add_memory(observation)

        return (
            f"Observation stored successfully.\n"
            f"- Type: {input_data.memory_type}\n"
            f"- ID: {observation_id}\n"
            f"This will be surfaced in future searches when relevant."
        )

    def _handle_context(self, args: dict[str, Any]) -> str:
        """Handle oak_context tool call."""
        input_data = OakContextInput(**args)

        # Build context from multiple sources
        context_parts = []

        # Search for relevant code
        code_results = self.vector_store.search_code(
            query=input_data.task,
            limit=5,
        )

        if code_results:
            context_parts.append("## Relevant Code\n")
            for r in code_results:
                context_parts.append(
                    f"### {r['filepath']} ({r.get('chunk_type', 'code')}: {r.get('name', '')})\n"
                    f"Lines {r.get('start_line', 0)}-{r.get('end_line', 0)} "
                    f"(relevance: {round(r['relevance'], 2)})\n\n"
                    f"```{r.get('language', '')}\n{r['content']}\n```\n"
                )

        # Search for relevant memories
        memory_results = self.vector_store.search_memory(
            query=input_data.task,
            limit=5,
        )

        if memory_results:
            context_parts.append("## Related Memories\n")
            for r in memory_results:
                emoji = {
                    "gotcha": "⚠️",
                    "bug_fix": "🐛",
                    "decision": "📋",
                    "discovery": "💡",
                    "trade_off": "⚖️",
                }.get(r.get("memory_type", ""), "📝")

                context_parts.append(
                    f"{emoji} **{r.get('memory_type', 'note')}**: {r['observation']}\n"
                )

        if not context_parts:
            context_parts.append(
                "No specific context found for this task. "
                "This may be a new area of the codebase."
            )

        return "\n".join(context_parts)

    @staticmethod
    def get_tool_definitions() -> list[dict]:
        """Get MCP tool definitions for registration.

        Returns:
            List of tool definitions in MCP format.
        """
        return MCP_TOOLS
