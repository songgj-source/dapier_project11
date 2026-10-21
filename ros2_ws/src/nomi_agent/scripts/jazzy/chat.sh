#!/usr/bin/env bash
# 터미널 2: NOMI에 말로 명령 보내기(/nomi/command), 응답·작업 상태 보기.
set -e
source "$(dirname "$0")/env.sh"
exec "$NOMI_PY" "$(dirname "$0")/nomi_chat.py"
