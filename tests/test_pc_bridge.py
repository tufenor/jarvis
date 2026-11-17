import sys
from pathlib import Path
import unittest

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "micropython"
sys.path.insert(0, str(FIRMWARE))

from pc_bridge import pc_action_response, valid_private_ipv4


class FakeStream:
    def __init__(self, response=b"HTTP/1.1 202 Accepted\r\nContent-Length: 0\r\n\r\n"):
        self.response = response
        self.sent = bytearray()
        self.destination = None
        self.closed = False

    def settimeout(self, _seconds):
        pass

    def connect(self, destination):
        self.destination = destination

    def send(self, data):
        count = min(11, len(data))
        self.sent.extend(data[:count])
        return count

    def recv(self, _size):
        response, self.response = self.response, b""
        return response

    def close(self):
        self.closed = True


class FakeSocketModule:
    AF_INET = 2
    SOCK_STREAM = 1

    def __init__(self, response=None, error=False):
        self.stream = FakeStream(response) if response is not None else FakeStream()
        self.error = error

    def socket(self, *_args):
        if self.error:
            raise OSError("offline")
        return self.stream


class PCBridgeTests(unittest.TestCase):
    def setUp(self):
        self.token = "ab12cd34" * 4

    def request(self, path="/pc/shutdown", token=None):
        token = self.token if token is None else token
        return "POST %s HTTP/1.1\r\nAuthorization: Bearer %s\r\n\r\n" % (path, token)

    def test_authorized_shutdown_forwards_fixed_path_confirmation_and_token(self):
        socket_module = FakeSocketModule()
        result = pc_action_response(self.request(), self.token, True,
                                    "192.168.50.10", socket_module)
        self.assertTrue(result.startswith("HTTP/1.1 202 Accepted"))
        self.assertEqual(socket_module.stream.destination, ("192.168.50.10", 8765))
        sent = bytes(socket_module.stream.sent).decode("ascii")
        self.assertTrue(sent.startswith("POST /shutdown HTTP/1.1"))
        self.assertIn("Authorization: Bearer " + self.token, sent)
        self.assertTrue(sent.endswith("confirm=SHUTDOWN"))
        self.assertTrue(socket_module.stream.closed)

    def test_invalid_token_or_offline_station_never_contacts_pc(self):
        socket_module = FakeSocketModule(error=True)
        result = pc_action_response(self.request(token="f" * 32), self.token,
                                    True, "192.168.50.10", socket_module)
        self.assertTrue(result.startswith("HTTP/1.1 401 Unauthorized"))
        result = pc_action_response(self.request(), self.token, False,
                                    "192.168.50.10", socket_module)
        self.assertTrue(result.startswith("HTTP/1.1 503 Service Unavailable"))

    def test_fixed_cancel_route_and_pc_agent_unavailable_feedback(self):
        socket_module = FakeSocketModule()
        result = pc_action_response(self.request("/pc/cancel"), self.token,
                                    True, "192.168.50.10", socket_module)
        sent = bytes(socket_module.stream.sent).decode("ascii")
        self.assertTrue(result.startswith("HTTP/1.1 202 Accepted"))
        self.assertTrue(sent.startswith("POST /cancel HTTP/1.1"))
        self.assertTrue(sent.endswith("confirm=CANCEL"))
        unavailable = pc_action_response(self.request(), self.token, True,
                                          "192.168.50.10", FakeSocketModule(error=True))
        self.assertTrue(unavailable.startswith("HTTP/1.1 502 Bad Gateway"))

    def test_pc_agent_target_must_be_private_ipv4(self):
        self.assertTrue(valid_private_ipv4("192.168.50.10"))
        self.assertTrue(valid_private_ipv4("10.0.0.12"))
        self.assertFalse(valid_private_ipv4("8.8.8.8"))
        self.assertFalse(valid_private_ipv4("192.168.50.999"))
        self.assertFalse(valid_private_ipv4("192.168.00.1"))


if __name__ == "__main__":
    unittest.main()
