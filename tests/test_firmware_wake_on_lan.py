import sys
from pathlib import Path
import unittest

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "micropython"
sys.path.insert(0, str(FIRMWARE))

from wake_on_lan import (build_magic_packet, decode_form_value,
                         directed_broadcast, wake_response)


class FakeDatagramSocket:
    def __init__(self, owner):
        self.owner = owner

    def setsockopt(self, *args):
        self.owner.options.append(args)

    def sendto(self, packet, destination):
        self.owner.sent.append((packet, destination))
        return len(packet)

    def close(self):
        self.owner.closed += 1


class FakeSocketModule:
    AF_INET = 2
    SOCK_DGRAM = 2
    SOL_SOCKET = 1
    SO_BROADCAST = 6

    def __init__(self):
        self.sent = []
        self.options = []
        self.closed = 0

    def socket(self, family, kind):
        self.created_with = (family, kind)
        return FakeDatagramSocket(self)


class WakeOnLanTests(unittest.TestCase):
    def test_form_decoder_preserves_special_characters_and_utf8(self):
        self.assertEqual(decode_form_value("Casa+WiFi%2B%25%C3%A9"),
                         "Casa WiFi+%é")

    def test_magic_packet_repeats_the_target_mac_sixteen_times(self):
        packet = build_magic_packet("AA-BB-CC-DD-EE-FF")
        mac = bytes((0x48, 0xA4, 0x72, 0x35, 0x4F, 0xE9))
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], mac * 16)

    def test_directed_broadcast_uses_the_connected_wifi_subnet(self):
        self.assertEqual(directed_broadcast("192.168.50.10", "255.255.255.0"),
                         "192.168.50.255")

    def test_unauthorized_request_does_not_send_a_packet(self):
        sockets = FakeSocketModule()
        request = "POST /wake HTTP/1.1\r\nHost: jarvis\r\n\r\n"
        response = wake_response(request, "a" * 32, True, "192.168.50.10",
                                 "255.255.255.0", "AA-BB-CC-DD-EE-FF", sockets)
        self.assertTrue(response.startswith("HTTP/1.1 401 Unauthorized\r\n"))
        self.assertEqual(sockets.sent, [])

    def test_missing_or_short_token_keeps_wake_endpoint_disabled(self):
        sockets = FakeSocketModule()
        request = "POST /wake HTTP/1.1\r\nAuthorization: Bearer short\r\n\r\n"
        response = wake_response(request, "short", True, "192.168.50.10",
                                 "255.255.255.0", "AA-BB-CC-DD-EE-FF", sockets)
        self.assertTrue(response.startswith("HTTP/1.1 503 Service Unavailable\r\n"))
        self.assertEqual(sockets.sent, [])

    def test_authorized_request_sends_magic_packet_to_subnet_broadcast(self):
        sockets = FakeSocketModule()
        token = "a1b2c3d4" * 4
        request = ("POST /wake HTTP/1.1\r\nHost: jarvis\r\n"
                   "Authorization: Bearer " + token + "\r\n\r\n")
        response = wake_response(request, token, True, "192.168.50.10",
                                 "255.255.255.0", "AA-BB-CC-DD-EE-FF", sockets)
        self.assertTrue(response.startswith("HTTP/1.1 200 OK\r\n"))
        packet, destination = sockets.sent[0]
        self.assertEqual(destination, ("192.168.50.255", 9))
        self.assertEqual(len(packet), 102)
        self.assertEqual(sockets.closed, 1)

    def test_disconnected_station_never_sends_magic_packet(self):
        sockets = FakeSocketModule()
        token = "a1b2c3d4" * 4
        request = "POST /wake HTTP/1.1\r\nAuthorization: Bearer " + token + "\r\n\r\n"
        response = wake_response(request, token, False, "192.168.4.1",
                                 "255.255.255.0", "AA-BB-CC-DD-EE-FF", sockets)
        self.assertTrue(response.startswith("HTTP/1.1 503 Service Unavailable\r\n"))
        self.assertEqual(sockets.sent, [])


if __name__ == "__main__":
    unittest.main()
