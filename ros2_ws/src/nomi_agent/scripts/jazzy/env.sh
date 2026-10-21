# NOMI를 Ubuntu 24.04 + ROS 2 Jazzy(시스템 Python 3.12)에서 돌리기 위한 환경. source로 불러 쓴다.
# ~/.bashrc가 Humble을 불러오므로, 여기서 ROS 환경 변수를 비우고 Jazzy만 불러온다.
# 로봇팔 터미널(arm_api, sort_menu)에서는 이 파일을 source하지 않는다.
NOMI_AGENT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
for v in ROS_LOCALHOST_ONLY AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION; do unset $v; done
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v '^/opt/ros/' | paste -sd:)
export PYTHONNOUSERSITE=1                                     # ~/.local 패키지 섞임 방지
source /opt/ros/jazzy/setup.bash
export PYTHONPATH=$NOMI_AGENT_DIR:$PYTHONPATH
export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-222}
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST   # Jazzy에서는 ROS_LOCALHOST_ONLY가 deprecated
export NOMI_MODEL_PROFILE=${NOMI_MODEL_PROFILE:-qwen35_single}
export OLLAMA_HOST=${OLLAMA_HOST:-http://127.0.0.1:11434}
export NOMI_AGENT_ENV=${NOMI_AGENT_ENV:-$NOMI_AGENT_DIR/.env}  # ARM_API_URL, ARM_API_TOKEN
# 시스템 Python 3.12 + Jazzy rclpy. ollama 등 pip 패키지는 NOMI_SITE에 둔다(bash setup_deps.sh로 설치).
NOMI_SITE=${NOMI_SITE:-$HOME/venvs/nomi_jazzy/site}
export PYTHONPATH=$NOMI_SITE:$PYTHONPATH
NOMI_PY=/usr/bin/python3
