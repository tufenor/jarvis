import sys
from pathlib import Path
import unittest

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "micropython"
sys.path.insert(0, str(FIRMWARE))

from mobile_panel import control_page, send_response


class MobilePanelTests(unittest.TestCase):
    def test_serves_a_mobile_html_page_with_correct_length(self):
        response = control_page()
        header, body = response.split("\r\n\r\n", 1)
        self.assertTrue(response.startswith("HTTP/1.1 200 OK\r\n"))
        self.assertIn("Content-Type: text/html; charset=utf-8", header)
        self.assertIn("width=device-width", body)
        self.assertIn("Content-Length: %d" % len(body.encode("utf-8")), header)

    def test_panel_reads_real_telemetry_and_controls_whitelisted_routes(self):
        body = control_page().split("\r\n\r\n", 1)[1]
        for expected in ("fetch('/status'", "temperature", "humidity",
                         "motion", "fetch('/led/'", "data-led=\"auto\""):
            with self.subTest(expected=expected):
                self.assertIn(expected, body)

    def test_wake_button_uses_bearer_auth_without_persisting_token(self):
        body = control_page().split("\r\n\r\n", 1)[1]
        self.assertIn("protectedPost('/wake'", body)
        self.assertIn("Authorization':'Bearer '+token", body)
        self.assertNotIn("localStorage", body)
        self.assertNotIn("sessionStorage", body)

    def test_pc_power_controls_are_protected_and_have_confirmation(self):
        body = control_page().split("\r\n\r\n", 1)[1]
        for expected in ("/pc/shutdown", "/pc/cancel", "Desligar em 30 segundos",
                         "Cancelar desligamento", "window.confirm", "Authorization"):
            with self.subTest(expected=expected):
                self.assertIn(expected, body)
        self.assertIn("não fecha aplicativos à força", body.lower())

    def test_http_writer_completes_partial_tcp_sends(self):
        class PartialClient:
            def __init__(self):
                self.data = bytearray()

            def send(self, data):
                count = min(7, len(data))
                self.data.extend(data[:count])
                return count

        client = PartialClient()
        send_response(client, "HTTP/1.1 200 OK\r\n\r\nOlá")
        self.assertEqual(bytes(client.data), "HTTP/1.1 200 OK\r\n\r\nOlá".encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
