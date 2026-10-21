#!/usr/bin/env bash
# 한 번만: NOMI가 쓰는 pip 패키지를 ~/venvs/nomi_jazzy/site에 설치한다(python3-venv, sudo 필요 없음).
set -e
source "$(dirname "$0")/env.sh"
mkdir -p "$NOMI_SITE"
"$NOMI_PY" -m pip install -q --target "$NOMI_SITE" "ollama>=0.3.0" "python-dotenv>=1.0.0" requests openai
"$NOMI_PY" -c "import rclpy, ollama, dotenv; print('NOMI deps OK')"
