#!/bin/bash

EVENT="${1:-unknown}"
INPUT="$(cat || true)"

PORT="38283"
PROJECT_ROOT="/Users/chris/Repos/open-agent-kit"
HOOK_LOG="${PROJECT_ROOT}/.oak/ci/hooks.log"

SAFE_INPUT="$(printf "%s" "${INPUT}" | jq -c . 2>/dev/null || echo "{}")"
SESSION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.session_id // .conversation_id // empty')"
CONVERSATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.conversation_id // empty')"
GENERATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.generation_id // empty')"
TOOL_USE_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_use_id // empty')"
HOOK_ORIGIN="cursor_config"

echo "[${EVENT}] $(date '+%Y-%m-%d %H:%M:%S') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1

case "${EVENT}" in
  sessionStart)
    SOURCE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.source // "startup"')"
    (curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1 || oak ci start --quiet >/dev/null 2>&1 || true)
    RESPONSE="$(jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg source "${SOURCE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, source: $source, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-start" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c 'if .context.injected_context then {additional_context: .context.injected_context} else {} end' 2>/dev/null || echo "{}"
    ;;
  beforeSubmitPrompt)
    PROMPT="$(printf "%s" "${SAFE_INPUT}" | jq -r '.prompt // ""')"
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg prompt "${PROMPT}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, prompt: $prompt, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/prompt-submit" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{\"continue\": true}"
    ;;
  afterFileEdit)
    printf "%s" "${SAFE_INPUT}" | jq -c --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" --arg tool_use_id "${TOOL_USE_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id, tool_use_id: $tool_use_id, tool_name: "Edit", tool_input: {file_path: .file_path, edits: (.edits // [])}}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  afterAgentResponse)
    printf "%s" "${SAFE_INPUT}" | jq -c --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" --arg tool_use_id "${TOOL_USE_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id, tool_use_id: $tool_use_id, tool_name: "agent_response", tool_output_b64: ((.text // "") | @base64)}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  stop)
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/stop" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  sessionEnd)
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg generation_id "${GENERATION_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, generation_id: $generation_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-end" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  postToolUseFailure)
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_name // "unknown"')"
    ERROR_MSG="$(printf "%s" "${SAFE_INPUT}" | jq -r '.error.message // .error // ""')"
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg tool_name "${TOOL_NAME}" --arg error_message "${ERROR_MSG}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg tool_use_id "${TOOL_USE_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, tool_name: $tool_name, error_message: $error_message, hook_origin: $hook_origin, hook_event_name: $hook_event_name, tool_use_id: $tool_use_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use-failure" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  subagentStart)
    AGENT_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_type // .subagent_type // "unknown"')"
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg agent_id "${AGENT_ID}" --arg agent_type "${AGENT_TYPE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, agent_id: $agent_id, agent_type: $agent_type, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/subagent-start" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  subagentStop)
    AGENT_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_id // ""')"
    AGENT_TYPE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_type // .subagent_type // "unknown"')"
    TRANSCRIPT_PATH="$(printf "%s" "${SAFE_INPUT}" | jq -r '.agent_transcript_path // ""')"
    STOP_HOOK_ACTIVE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.stop_hook_active // false')"
    jq -cn --arg agent "cursor" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg agent_id "${AGENT_ID}" --arg agent_type "${AGENT_TYPE}" --arg agent_transcript_path "${TRANSCRIPT_PATH}" --argjson stop_hook_active "${STOP_HOOK_ACTIVE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, agent_id: $agent_id, agent_type: $agent_type, agent_transcript_path: $agent_transcript_path, stop_hook_active: $stop_hook_active, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/subagent-stop" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  *)
    echo "{}"
    ;;
esac
