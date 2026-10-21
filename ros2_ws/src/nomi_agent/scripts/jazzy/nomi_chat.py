"""터미널에서 NOMI Agent에 명령을 보내고 응답을 보는 작은 ROS 노드(웹 UI 없이 시험할 때).

- 입력한 문장을 /nomi/command로 보낸다. "멈춰", "정지", "취소"는 Agent가 취소로 처리한다.
- Ctrl+C를 누르면 /nomi/cancel을 보내고 끝낸다(진행 중인 로봇팔 작업도 멈춘다).
- /nomi/response(답변)와 /nomi/task_status(상태 변화)를 출력한다.
"""
import json
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class NomiChat(Node):
    def __init__(self):
        super().__init__("nomi_chat")
        self.command = self.create_publisher(String, "/nomi/command", 10)
        self.cancel = self.create_publisher(String, "/nomi/cancel", 10)
        self.create_subscription(String, "/nomi/response", self.on_response, 10)
        self.create_subscription(String, "/nomi/task_status", self.on_status, 10)
        self._last_status = None

    def send(self, text, topic=None):
        message = String()
        message.data = text
        (topic or self.command).publish(message)

    def on_response(self, message):
        print(f"\nNOMI> {message.data}\n> ", end="", flush=True)

    def on_status(self, message):
        try:
            status = json.loads(message.data)
        except (TypeError, ValueError):
            return
        line = status.get("status")
        steps = status.get("steps") or []
        if steps:
            last = steps[-1]
            line += f" · {last.get('tool')}: {'성공' if last.get('success') else '실패'}"
        if line != self._last_status:
            self._last_status = line
            print(f"\n  [상태] {line}\n> ", end="", flush=True)


def main():
    rclpy.init()
    node = NomiChat()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    print("NOMI 명령을 입력하세요. 예: 책상에 뭐 있어? / 빨간 큐브 넣어줘 / 멈춰. 끝내기: Ctrl+C")
    try:
        while True:
            text = input("> ").strip()
            if text:
                node.send(text)
    except (KeyboardInterrupt, EOFError):
        node.send("cancel", node.cancel)
        print("\n취소를 보냈습니다.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
