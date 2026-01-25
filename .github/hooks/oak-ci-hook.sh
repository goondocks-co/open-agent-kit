#!/bin/bash
# Codebase Intelligence hooks for GitHub Copilot
# Installed by: oak ci enable
# Template placeholders replaced: 38283, /Users/chris/Repos/open-agent-kit

EVENT="${1:-unknown}"
INPUT="$(cat || true)"

PORT="38283"
PROJECT_ROOT="/Users/chris/Repos/open-agent-kit"
HOOK_LOG="${PROJECT_ROOT}/.oak/ci/hooks.log"

SAFE_INPUT="$(printf "%s" "${INPUT}" | jq -c . 2>/dev/null || echo "{}")"
SESSION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.session_id // .conversation_id // empty')"
CONVERSATION_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.conversation_id // empty')"
TOOL_USE_ID="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_use_id // empty')"
HOOK_ORIGIN="copilot_config"

echo "[${EVENT}] $(date '+%Y-%m-%d %H:%M:%S') session_id=${SESSION_ID:-unknown}" >> "${HOOK_LOG}" 2>&1

case "${EVENT}" in
  sessionStart)
    SOURCE="$(printf "%s" "${SAFE_INPUT}" | jq -r '.source // "startup"')"
    (curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1 || oak ci start --quiet >/dev/null 2>&1 || true)
    RESPONSE="$(jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg source "${SOURCE}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, source: $source, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-start" -H "Content-Type: application/json" -d @- || true)"
    echo "${RESPONSE}" | jq -c 'if .context.injected_context then {additional_context: .context.injected_context} else {} end' 2>/dev/null || echo "{}"
    ;;
  sessionEnd)
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/session-end" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  userPromptSubmitted)
    PROMPT="$(printf "%s" "${SAFE_INPUT}" | jq -r '.prompt // ""')"
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg prompt "${PROMPT}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, prompt: $prompt, hook_origin: $hook_origin, hook_event_name: $hook_event_name}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/prompt-submit" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  postToolUse)
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_name // ""')"
    printf "%s" "${SAFE_INPUT}" | jq -c --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg tool_use_id "${TOOL_USE_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, hook_origin: $hook_origin, hook_event_name: $hook_event_name, tool_use_id: $tool_use_id, tool_name: .tool_name, tool_input: .tool_input, tool_output_b64: ((.tool_response // "") | tostring | @base64)}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  errorOccurred)
    # Maps to post-tool-use-failure endpoint
    TOOL_NAME="$(printf "%s" "${SAFE_INPUT}" | jq -r '.tool_name // "unknown"')"
    ERROR_MSG="$(printf "%s" "${SAFE_INPUT}" | jq -r '.error.message // .error // ""')"
    jq -cn --arg agent "copilot" --arg session_id "${SESSION_ID}" --arg conversation_id "${CONVERSATION_ID}" --arg tool_name "${TOOL_NAME}" --arg error_message "${ERROR_MSG}" --arg hook_origin "${HOOK_ORIGIN}" --arg hook_event_name "${EVENT}" --arg tool_use_id "${TOOL_USE_ID}" '{agent: $agent, session_id: $session_id, conversation_id: $conversation_id, tool_name: $tool_name, error_message: $error_message, hook_origin: $hook_origin, hook_event_name: $hook_event_name, tool_use_id: $tool_use_id}' | curl -s -X POST "http://localhost:${PORT}/api/oak/ci/post-tool-use-failure" -H "Content-Type: application/json" -d @- >/dev/null || true
    echo "{}"
    ;;
  *)
    echo "{}"
    ;;
esac
