#!/bin/bash
# Codebase Intelligence hooks for Claude Code
# Installed by: oak ci enable
# Template placeholder replaced: {{PROJECT_ROOT}}
#
# This script handles all Claude hook events, reading the daemon port from
# the daemon.port file at runtime. This allows the port to change due to
# conflict resolution without requiring hook reinstallation.

EVENT="${1:-unknown}"
INPUT="$(cat || true)"

PROJECT_ROOT="{{PROJECT_ROOT}}"
# Read port from file at runtime (allows port changes without hook reinstall)
# Priority: 1) local override, 2) team-shared, 3) default
PORT="$(cat "${PROJECT_ROOT}/.oak/ci/daemon.port" 2>/dev/null || \
        cat "${PROJECT_ROOT}/oak/ci/daemon.port" 2>/dev/null || \
        echo "37800")"
HOOK_LOG="${PROJECT_ROOT}/.oak/ci/hooks.log"

SAFE_INPUT="$(printf "%s" "${INPUT}" | jq -c . 2>/dev/null || echo "{}")"
SESSION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.session_id // .conversation_id // empty')"
CONVERSATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.conversation_id // empty')"
GENERATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.generation_id // empty')"
TOOL_USE_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_use_id // empty')"
HOOK_ORIGIN="claude_config"

echo "[${EVENT}] $(date '+%Y-%m-%d %H:%M:%S') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1

case "${EVENT}" in
  SessionStart)
    SOURCE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.source // "startup"')"
    # Ensure daemon is running
    (curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1 || oak ci start --quiet >/dev/null 2>&1 || true)
    RESPONSE="$(jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg source "${SOURCE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, source: $source, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-start" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | tee -a "${HOOK_LOG}" | jq -c 'if .context.injected_context then {hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: .context.injected_context}} else {} end' 2>/dev/null || echo "{}"
    ;;
  UserPromptSubmit)
    PROMPT="$(printf "%s" "${SAFE_INPUT}" | jq -r '.prompt // ""')"
    RESPONSE="$(jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg prompt "${PROMPT}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, prompt: $prompt, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/prompt-submit" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c 'if .context.injected_context then {hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: .context.injected_context}} else {} end' 2>/dev/null || echo "{}"
    ;;
  PostToolUse)
    RESPONSE="$(printf "%s" "${SAFE_INPUT}" | jq -c '{agent: "claude", session_id: (.session_id // .conversation_id), conversation_id: .conversation_id, tool_name: .tool_name, tool_input: .tool_input, tool_output_b64: ((.tool_response // {}) | tostring | @base64), tool_use_id: .tool_use_id, hook_origin: "claude_config", hook_event_name: "PostToolUse", generation_id: .generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c 'if .injected_context then {hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: .injected_context}} else {} end' 2>/dev/null || echo "{}"
    ;;
  Stop)
    jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/stop" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  SessionEnd)
    echo "[SessionEnd] $(date '+%Y-%m-%d %H:%M:%S') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1
    jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-end" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "" >> "${HOOK_LOG}"
    echo "{}"
    ;;
  PostToolUseFailure)
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_name // "unknown"')"
    ERROR_MSG="$(printf "%s" "${SAFE_INPUT}" | jq -r '.error.message // .error // ""')"
    jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg tool_name "${TOOL_NAME}" --arg tool_input "$(printf "%s" "${SAFE_INPUT}" | jq -c '.tool_input // {}')" --arg tool_use_id "${TOOL_USE_ID}" --arg error_message "${ERROR_MSG}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, tool_name: $tool_name, tool_input: $tool_input, tool_use_id: $tool_use_id, error_message: $error_message, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use-failure" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  SubagentStart)
    AGENT_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_type // "unknown"')"
    jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg agent_id "${AGENT_ID}" --arg agent_type "${AGENT_TYPE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, agent_id: $agent_id, agent_type: $agent_type, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/subagent-start" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  SubagentStop)
    AGENT_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_type // "unknown"')"
    TRANSCRIPT_PATH="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_transcript_path // ""')"
    STOP_HOOK_ACTIVE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.stop_hook_active // false')"
    jq -cn --arg agent "claude" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg agent_id "${AGENT_ID}" --arg agent_type "${AGENT_TYPE}" --arg agent_transcript_path "${TRANSCRIPT_PATH}" --argjson stop_hook_active "${STOP_HOOK_ACTIVE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, agent_id: $agent_id, agent_type: $agent_type, agent_transcript_path: $agent_transcript_path, stop_hook_active: $stop_hook_active, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/subagent-stop" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  *)
    echo "{}"
    ;;
esac
