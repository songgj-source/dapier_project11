#!/usr/bin/env bash
# 터미널 1: NOMI Agent(Qwen3.5 + 로봇팔 Skill). 먼저 로봇팔 PC의 arm_api 서버와 Ollama가 켜져 있어야 한다.
set -e
source "$(dirname "$0")/env.sh"
exec "$NOMI_PY" -m nomi_agent.agent_node
