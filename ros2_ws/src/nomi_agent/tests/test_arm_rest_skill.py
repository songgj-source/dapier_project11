"""로봇팔 Skill(ArmRestSkill)과 ToolRegistry 연결 확인.

로봇팔 PC의 REST API를 흉내 내는 작은 HTTP 서버를 띄워 쓴다. 실제 로봇·카메라·ROS는 쓰지 않는다.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nomi_agent.skills.arm_rest_skill import ArmRestSkill, resolve_object
from nomi_agent.tool_registry import ToolRegistry
from tests.mock_adapters import MockNavigation, mock_skills

TOKEN = "t"


class FakeArmApi:
    """POST /api/menu/N → 202 task_id, GET /tasks/<id> → running을 polls_until_done번 돌려준 뒤 결과."""

    def __init__(self):
        self.calls = []
        self.outcome = {"ok": True}
        self.polls_until_done = 2
        self.busy = False
        self.stopped = threading.Event()
        self._polls = 0
        api = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _authorized(self):
                return self.headers.get("Authorization") == f"Bearer {TOKEN}"

            def do_GET(self):
                if not self._authorized():
                    return self._send(401, {"ok": False, "reason_code": "unauthorized"})
                api.calls.append(("GET", self.path, None))
                if self.path == "/status":
                    return self._send(200, {"state": "idle", "arm_home": True})
                if self.path.startswith("/tasks/"):
                    api._polls += 1
                    if api.stopped.is_set():
                        return self._send(200, {"state": "failed", "phases": [],
                                                "result": {"ok": False, "reason": "cancelled", "reason_code": "cancelled"}})
                    if api._polls <= api.polls_until_done:
                        return self._send(200, {"state": "running", "phase_label": "물체에 접근",
                                                "phases": [{"label": "물체에 접근"}]})
                    state = "done" if api.outcome.get("ok") else "failed"
                    return self._send(200, {"state": state, "phases": [{"label": "물체에 접근"}, {"label": "칸에 놓기"}],
                                            "items": [], "result": {**api.outcome, "seconds": 61.2, "warnings": []}})
                self._send(404, {"ok": False})

            def do_POST(self):
                if not self._authorized():
                    return self._send(401, {"ok": False, "reason_code": "unauthorized"})
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                api.calls.append(("POST", self.path, body))
                if self.path == "/stop":
                    api.stopped.set()
                    return self._send(200, {"ok": True, "stopped": True})
                if self.path == "/api/image":
                    return self._send(200, {"ok": True, "objects": [
                        {"label": "red_cube", "name": "빨간 정육면체", "pixel": [1, 2], "position_mm": [250, 0], "pickable": True}],
                        "available_menus": [2, 5, 6], "note": "n", "captured_at": "2026-10-21T12:00:00",
                        "image_url": "/api/image/latest.jpg", "image_jpeg_base64": "AAAA"})
                if self.path.startswith("/api/menu/"):
                    if api.busy:
                        return self._send(409, {"ok": False, "reason_code": "busy", "reason": "다른 작업을 실행 중입니다."})
                    return self._send(202, {"ok": True, "task_id": "task-1"})
                self._send(404, {"ok": False})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def menu_posts(self):
        return [(path, body) for method, path, body in self.calls if method == "POST" and path.startswith("/api/menu/")]


class ArmRestSkillTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeArmApi()
        self.addCleanup(self.api.close)
        self.skill = ArmRestSkill(base_url=self.api.url, token=TOKEN)
        self.skill.POLL_S = 0.01

    def test_resolves_korean_names(self):
        self.assertEqual(resolve_object("흰 상자"), "white_box")
        self.assertEqual(resolve_object("빨간큐브"), "red_cube")
        self.assertIsNone(resolve_object("컵"))

    def test_default_slot_waits_for_verified_completion(self):
        result = self.skill.sort_object("tape_measure")
        self.assertTrue(result["success"])
        self.assertTrue(result["data"]["completion_verified"])
        self.assertEqual(self.api.menu_posts(), [("/api/menu/3", {})])

    def test_named_slot_uses_menu5_and_unknown_uses_menu7(self):
        self.skill.sort_object("red_cube", slot=1)
        self.skill.sort_object("unknown", slot=3)
        self.assertEqual(self.api.menu_posts(), [("/api/menu/5", {"object": "red_cube", "slot": 1}),
                                                 ("/api/menu/7", {"slot": 3})])

    def test_robot_failure_is_not_verified(self):
        self.api.outcome = {"ok": False, "reason": "물체를 찾지 못했습니다.", "reason_code": "target_not_found"}
        result = self.skill.sort_object("white_box")
        self.assertFalse(result["success"])
        self.assertFalse(result["data"]["completion_verified"])
        self.assertEqual(result["data"]["error_code"], "target_not_found")

    def test_missing_slot_or_unknown_name_asks_without_moving(self):
        self.assertTrue(self.skill.sort_object("unknown")["data"]["needs_clarification"])
        self.assertTrue(self.skill.sort_object("컵")["data"]["needs_clarification"])
        self.assertEqual(self.api.menu_posts(), [])

    def test_busy_robot_is_reported(self):
        self.api.busy = True
        result = self.skill.sort_all_objects()
        self.assertFalse(result["success"])
        self.assertEqual(result["data"]["error_code"], "busy")

    def test_stop_cancels_wait_and_sends_robot_stop(self):
        self.api.polls_until_done = 10_000
        out = {}
        worker = threading.Thread(target=lambda: out.setdefault("r", self.skill.sort_object("흰 상자")))
        worker.start()
        while not any(p.startswith("/tasks/") for _m, p, _b in list(self.api.calls)):
            pass
        self.assertTrue(self.skill.stop())
        worker.join(5)
        self.assertEqual(out["r"]["data"]["error_code"], "cancelled")
        self.assertTrue(self.api.stopped.is_set())

    def test_timeout_sends_robot_stop(self):
        self.api.polls_until_done = 10_000
        result = self.skill._run(6, None, "HOME 복귀", timeout=0.2)
        self.assertEqual(result["data"]["error_code"], "timeout")
        self.assertTrue(self.api.stopped.is_set())

    def test_wrong_token_and_unreachable_server_fail(self):
        self.assertFalse(ArmRestSkill(base_url=self.api.url, token="x").get_arm_status()["success"])
        result = ArmRestSkill(base_url="http://127.0.0.1:9", token=TOKEN).get_arm_status()
        self.assertEqual(result["data"]["error_code"], "connection_error")

    def test_look_at_table_drops_image_bytes(self):
        result = self.skill.look_at_table()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["available_menus"], [2, 5, 6])
        self.assertNotIn("image_jpeg_base64", result["data"])
        self.assertIn("빨간 정육면체", result["message"])


class ArmRegistryTests(unittest.TestCase):
    def setUp(self):
        self.api = FakeArmApi()
        self.addCleanup(self.api.close)
        self.arm = ArmRestSkill(base_url=self.api.url, token=TOKEN)
        self.arm.POLL_S = 0.01
        self.navigation_stops = []
        navigation = MockNavigation()
        navigation.stop = lambda: self.navigation_stops.append(True)
        self.registry = ToolRegistry(skills={**mock_skills(navigation=navigation), "arm": self.arm})

    def test_arm_tools_are_registered_with_schemas(self):
        names = {schema["function"]["name"] for schema in self.registry.get_tool_schemas()}
        self.assertLessEqual({"look_at_table", "get_arm_status", "sort_object", "sort_all_objects", "arm_return_home"}, names)

    def test_registry_validates_object_and_slot(self):
        bad_object = self.registry.execute("sort_object", {"object_name": "컵"})
        bad_slot = self.registry.execute("sort_object", {"object_name": "red_cube", "slot": 4})
        self.assertEqual(bad_object.data["error_code"], "invalid_value")
        self.assertEqual(bad_slot.data["error_code"], "out_of_range")
        self.assertEqual(self.api.menu_posts(), [])

    def test_registry_runs_sort_object_with_evidence(self):
        result = self.registry.execute("sort_object", {"object_name": "red_cube"})
        self.assertTrue(result.success)
        self.assertTrue(result.data["completion_verified"])

    def test_emergency_stop_stops_navigation_and_arm(self):
        self.registry.emergency_stop()
        self.assertEqual(self.navigation_stops, [True])
        self.assertTrue(self.api.stopped.is_set())

    def test_emergency_stop_still_stops_arm_when_navigation_raises(self):
        def broken():
            raise RuntimeError("navigation down")
        self.registry.skills["navigation"].stop = broken
        self.registry.emergency_stop()
        self.assertTrue(self.api.stopped.is_set())

    def test_registry_without_arm_skill_is_unchanged(self):
        registry = ToolRegistry(skills=mock_skills())
        self.assertNotIn("sort_object", registry.get_tool_names())


if __name__ == "__main__":
    unittest.main()
