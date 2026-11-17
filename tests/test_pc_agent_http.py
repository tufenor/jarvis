import hashlib
import json
import sys
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
import unittest
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pc_agent import AgentHandler
import threading


class PCAgentHTTPTests(unittest.TestCase):
    def setUp(self):
        self.token = "9988776655443322" * 2
        self.commands = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AgentHandler)
        self.server.config = {
            "allowed_network": "127.0.0.0/8",
            "token_sha256": hashlib.sha256(self.token.encode("ascii")).hexdigest(),
            "port": self.server.server_address[1],
        }
        self.server.pending = False
        self.server.action_lock = threading.Lock()
        def fake_run(arguments):
            self.commands.append(arguments)
            return 0

        self.server.run_command = fake_run
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=2)

    def tearDown(self):
        self.connection.close()
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_health_and_unauthorized_http_do_not_execute_os_command(self):
        self.connection.request("GET", "/health")
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read())["status"], "ready")
        self.connection.request("POST", "/shutdown", body="confirm=SHUTDOWN",
                                headers={"Authorization": "Bearer " + "f" * 32})
        response = self.connection.getresponse()
        self.assertEqual(response.status, 401)
        self.assertEqual(self.commands, [])

    def test_authorized_http_schedules_only_fixed_delayed_shutdown(self):
        self.connection.request("POST", "/shutdown", body="confirm=SHUTDOWN",
                                headers={"Authorization": "Bearer " + self.token})
        response = self.connection.getresponse()
        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.read())["delay_seconds"], 30)
        self.assertTrue(self.server.pending)
        self.assertEqual(self.commands[0][1:4], ["/s", "/t", "30"])
        self.assertNotIn("/f", self.commands[0])


if __name__ == "__main__":
    unittest.main()
