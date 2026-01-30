/**
 * OAK Codebase Intelligence Plugin for OpenCode
 *
 * This plugin integrates OpenCode with OAK's Codebase Intelligence system,
 * enabling session tracking, memory injection, and activity capture.
 *
 * Events handled:
 * - session.created: Initialize CI session, inject context
 * - tool.execute.after: Capture tool usage, inject relevant memories
 * - session.idle: End prompt batch, trigger background processing
 * - session.deleted: Finalize session, generate summary
 * - file.edited: Capture file modifications
 * - todo.updated: Capture agent planning/task list updates
 *
 * @see https://opencode.ai/docs/plugins/
 */

import type { Plugin } from "@opencode-ai/plugin";

/**
 * Helper to call oak ci hook command with JSON payload
 */
async function callOakHook(
  $: any,
  hookName: string,
  payload: Record<string, unknown>
): Promise<{ success: boolean; result?: unknown; error?: string }> {
  try {
    const jsonPayload = JSON.stringify(payload);
    const result =
      await $`echo ${jsonPayload} | oak ci hook ${hookName} --agent opencode`;
    return { success: true, result };
  } catch (error) {
    // Don't let hook failures break OpenCode - log and continue
    console.error(`[oak-ci] Hook ${hookName} failed:`, error);
    return { success: false, error: String(error) };
  }
}

/**
 * Format todo items for storage
 */
function formatTodos(
  todos: Array<{ id?: string; content?: string; status?: string }>
): string {
  if (!todos || todos.length === 0) return "";
  return todos.map((t) => `[${t.status || "pending"}] ${t.content || ""}`).join("\n");
}

/**
 * OAK Codebase Intelligence Plugin
 */
export const OakCIPlugin: Plugin = async ({ project, client, $, directory, worktree }) => {
  // Log plugin initialization
  await client.app.log({
    service: "oak-ci",
    level: "info",
    message: "OAK Codebase Intelligence plugin initialized",
    extra: { directory, worktree },
  });

  return {
    /**
     * Session created - initialize CI tracking
     */
    event: async ({ event }) => {
      if (event.type === "session.created") {
        const sessionData = event.properties || {};
        await callOakHook($, "sessionStart", {
          session_id: sessionData.id || sessionData.sessionId,
          agent: "opencode",
          source: "startup",
        });
      }

      // Session deleted - finalize and cleanup
      if (event.type === "session.deleted") {
        const sessionData = event.properties || {};
        await callOakHook($, "sessionEnd", {
          session_id: sessionData.id || sessionData.sessionId,
          agent: "opencode",
        });
      }

      // Session idle - agent finished responding
      if (event.type === "session.idle") {
        const sessionData = event.properties || {};
        await callOakHook($, "stop", {
          session_id: sessionData.id || sessionData.sessionId,
          agent: "opencode",
        });
      }

      // Todo updated - capture planning information
      if (event.type === "todo.updated") {
        const todoData = event.properties || {};
        const todos = todoData.todos || [];
        const todoSummary = formatTodos(todos);

        await callOakHook($, "postToolUse", {
          session_id: todoData.sessionId,
          tool_name: "TodoUpdate",
          tool_input: { todos, count: todos.length },
          tool_output: todoSummary,
          agent: "opencode",
        });
      }

      // File edited - capture file modifications
      if (event.type === "file.edited") {
        const fileData = event.properties || {};
        await callOakHook($, "postToolUse", {
          session_id: fileData.sessionId,
          tool_name: "Write",
          tool_input: { file_path: fileData.path },
          tool_output: `Modified ${fileData.path}`,
          agent: "opencode",
        });
      }
    },

    /**
     * Post-tool execution - capture tool usage and inject context
     */
    "tool.execute.after": async (input, output) => {
      const toolName = input.tool || "unknown";
      const sessionId = input.session?.id;

      // Skip if no session context
      if (!sessionId) return;

      // Build tool input summary (sanitize large content)
      const toolInput: Record<string, unknown> = {};
      if (input.args) {
        for (const [key, value] of Object.entries(input.args)) {
          if (typeof value === "string" && value.length > 500) {
            toolInput[key] = `<${value.length} chars>`;
          } else {
            toolInput[key] = value;
          }
        }
      }

      // Build output summary
      let outputSummary = "";
      if (output.result) {
        const resultStr = String(output.result);
        outputSummary = resultStr.length > 500 ? resultStr.slice(0, 500) + "..." : resultStr;
      }

      await callOakHook($, "postToolUse", {
        session_id: sessionId,
        tool_name: toolName,
        tool_input: toolInput,
        tool_output: outputSummary,
        file_path: input.args?.filePath || input.args?.file_path,
        agent: "opencode",
      });
    },
  };
};

// Default export for OpenCode plugin discovery
export default OakCIPlugin;
