#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-gemma4:12b}"
SYSTEM_PROMPT="${SYSTEM_PROMPT:-You are a concise, helpful assistant.}"
PROMPT="${*:-}"

if [[ -z "$PROMPT" ]]; then
  printf 'Usage: %s "prompt text"\n' "$0" >&2
  exit 2
fi

json_escape() {
  python3 -c 'import json, sys; print(json.dumps(sys.stdin.read()))'
}

system_json="$(printf '%s' "$SYSTEM_PROMPT" | json_escape)"
prompt_json="$(printf '%s' "$PROMPT" | json_escape)"

curl -s http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d "{
    \"model\": \"$MODEL\",
    \"stream\": false,
    \"messages\": [
      {\"role\": \"system\", \"content\": $system_json},
      {\"role\": \"user\", \"content\": $prompt_json}
    ],
    \"options\": {
      \"temperature\": 1.0,
      \"top_p\": 0.95,
      \"top_k\": 64
    }
  }" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["message"]["content"])'
