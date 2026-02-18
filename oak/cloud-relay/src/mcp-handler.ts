/**
 * MCP Streamable HTTP protocol handler.
 *
 * Handles MCP JSON-RPC requests from cloud agents at POST /mcp.
 * For v1 we support:
 *   - initialize       -- returns server capabilities
 *   - tools/list       -- returns cached tool list from DO
 *   - tools/call       -- proxied to local daemon via Durable Object / WebSocket
 */

import { RelayMessageType, type ToolCallRequest } from "./types";

const SERVER_NAME = "oak-cloud-relay";
const PROTOCOL_VERSION = "2025-03-26";
const DEFAULT_TIMEOUT_MS = 30_000;

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

  if (!req || req.jsonrpc !== "2.0" || !req.method) {
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
      return handleToolsList(req, doStub);
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
        version: "1.0.0",
      },
    },
  };
}

async function handleToolsList(
  req: JsonRpcRequest,
  doStub: DurableObjectStub,
): Promise<JsonRpcResponse> {
  // Fetch the cached tool list directly from the DO (no WebSocket round-trip).
  const response = await doStub.fetch("https://relay/tools");
  const data = (await response.json()) as { tools: unknown[] };

  return { jsonrpc: "2.0", id: req.id, result: { tools: data.tools } };
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

  const toolCallRequest: ToolCallRequest = {
    type: RelayMessageType.TOOL_CALL,
    call_id: crypto.randomUUID(),
    tool_name: toolName,
    arguments: (params.arguments as Record<string, unknown>) ?? {},
    timeout_ms: DEFAULT_TIMEOUT_MS,
  };

  const result = await forwardToDo(doStub, toolCallRequest);

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
  toolCallRequest: ToolCallRequest,
): Promise<DoResponse> {
  const response = await doStub.fetch("https://relay/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(toolCallRequest),
  });

  return (await response.json()) as DoResponse;
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
