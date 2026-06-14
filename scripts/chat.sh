#!/usr/bin/env bash
set -euo pipefail

MODEL="${MODEL:-gemma4:12b}"

exec ollama run "$MODEL"
