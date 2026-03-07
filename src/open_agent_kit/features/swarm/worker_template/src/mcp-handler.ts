/**
 * MCP Streamable HTTP protocol handler for the Swarm Worker.
 *
 * Handles MCP JSON-RPC requests from cloud agents at POST /mcp.
 * For v1 we support:
 *   - initialize       -- returns server capabilities
 *   - tools/list       -- returns the static swarm tool list
 *   - tools/call       -- forwards to the appropriate DO endpoint
 */

const SERVER_NAME = "oak-swarm";
const SERVER_VERSION = "1.0.0";
const PROTOCOL_VERSION = "2025-03-26";

// ---------------------------------------------------------------------------
// JSON-RPC types (minimal subset needed for MCP)
// ---------------------------------------------------------------------------

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const SWARM_TOOLS = [
  {
    name: "swarm_search",
    description: "Search across the swarm for memories, sessions, and plans.",
    inputSchema: {
      type: "object" as const,
      properties: {
        query: { type: "string", description: "Search query string." },
        search_type: {
          type: "string",
          enum: ["all", "memory", "sessions", "plans"],
          description: "Type of search to perform.",
        },
        limit: {
          type: "integer",
          minimum: 1,
          maximum: 50,
          description: "Maximum number of results to return.",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "swarm_fetch",
    description: "Fetch specific items by ID from the swarm.",
    inputSchema: {
      type: "object" as const,
      properties: {
        ids: {
          type: "array",
          items: { type: "string" },
          description: "Array of item IDs to fetch.",
        },
        project_slug: {
          type: "string",
          description: "Optional project slug to scope the fetch.",
        },
      },
      required: ["ids"],
    },
  },
  {
    name: "swarm_nodes",
    description: "List all registered teams/nodes in the swarm.",
    inputSchema: {
      type: "object" as const,
      properties: {},
    },
  },
  {
    name: "swarm_status",
    description: "Get the current status of the swarm.",
    inputSchema: {
      type: "object" as const,
      properties: {},
    },
  },
];

// ---------------------------------------------------------------------------
// Tool endpoint mapping
// ---------------------------------------------------------------------------

const TOOL_ENDPOINTS: Record<string, { path: string; method: string }> = {
  swarm_search: { path: "/api/swarm/search", method: "POST" },
  swarm_fetch: { path: "/api/swarm/fetch", method: "POST" },
  swarm_nodes: { path: "/api/swarm/nodes", method: "GET" },
  swarm_status: { path: "/api/swarm/status", method: "GET" },
};

// ---------------------------------------------------------------------------
// Public handler
// ---------------------------------------------------------------------------

/**
 * Handle an MCP JSON-RPC request by dispatching to the appropriate method.
 */
export async function handleMcpRequest(
  body: unknown,
  doStub: DurableObjectStub,
): Promise<JsonRpcResponse> {
  const req = body as JsonRpcRequest;

  if (!req || req.jsonrpc !== "2.0" || !req.method || req.id === undefined) {
    return jsonRpcError(
      req?.id ?? (null as unknown as number),
      -32600,
      "invalid JSON-RPC request",
    );
  }

  switch (req.method) {
    case "initialize":
      return handleInitialize(req);
    case "tools/list":
      return handleToolsList(req);
    case "tools/call":
      return handleToolsCall(req, doStub);
    default:
      return jsonRpcError(req.id, -32601, `method not found: ${req.method}`);
  }
}

// ---------------------------------------------------------------------------
// Method handlers
// ---------------------------------------------------------------------------

function handleInitialize(req: JsonRpcRequest): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id: req.id,
    result: {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {
        tools: { listChanged: false },
      },
      serverInfo: {
        name: SERVER_NAME,
        version: SERVER_VERSION,
      },
    },
  };
}

function handleToolsList(req: JsonRpcRequest): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id: req.id,
    result: { tools: SWARM_TOOLS },
  };
}

async function handleToolsCall(
  req: JsonRpcRequest,
  doStub: DurableObjectStub,
): Promise<JsonRpcResponse> {
  const params = req.params ?? {};
  const toolName = params.name as string | undefined;

  if (!toolName) {
    return jsonRpcError(req.id, -32602, "missing required parameter: name");
  }

  const endpoint = TOOL_ENDPOINTS[toolName];
  if (!endpoint) {
    return jsonRpcError(req.id, -32602, `unknown tool: ${toolName}`);
  }

  const result = await forwardToDo(
    doStub,
    endpoint,
    (params.arguments as Record<string, unknown>) ?? {},
  );

  if (result.error) {
    return jsonRpcError(req.id, -32000, result.error);
  }

  return {
    jsonrpc: "2.0",
    id: req.id,
    result: {
      content: [{ type: "text", text: JSON.stringify(result.result) }],
    },
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface DoResponse {
  result?: unknown;
  error?: string;
}

async function forwardToDo(
  doStub: DurableObjectStub,
  endpoint: { path: string; method: string },
  args: Record<string, unknown>,
): Promise<DoResponse> {
  const url = `https://swarm${endpoint.path}`;

  const fetchOptions: RequestInit =
    endpoint.method === "GET"
      ? { method: "GET" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(args),
        };

  const response = await doStub.fetch(url, fetchOptions);

  // The DO endpoints return their payload directly; wrap it as result.
  const data = await response.json();
  if (!response.ok) {
    const errMsg =
      (data as Record<string, unknown>).error ?? response.statusText;
    return { error: String(errMsg) };
  }

  return { result: data };
}

function jsonRpcError(
  id: string | number,
  code: number,
  message: string,
): JsonRpcResponse {
  return {
    jsonrpc: "2.0",
    id,
    error: { code, message },
  };
}
