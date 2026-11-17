import hashlib
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pc_agent import process_action


class PCAgentTests(unittest.TestCase):
    def setUp(self):
        self.token = "0123456789abcdef" * 2
        self.digest = hashlib.sha256(self.token.encode("ascii")).hexdigest()
        self.calls = []
        self.command_result = 0
        self.suspensoes = 0
        self.suspend_falha = False

    def run_command(self, args):
        self.calls.append(args)
        return self.command_result

    def suspend(self):
        if self.suspend_falha:
            raise OSError("recusado")
        self.suspensoes += 1

    def action(self, action="shutdown", token=None, ip="192.168.50.55",
               confirmation="SHUTDOWN", pending=False,
               jarvis_rodando=None, iniciar_jarvis=None):
        token = self.token if token is None else token
        return process_action(
            action=action,
            authorization="Bearer " + token if token else "",
            expected_digest=self.digest,
            allowed_network="192.168.50.0/24",
            client_ip=ip,
            confirmation=confirmation,
            pending=pending,
            run_command=self.run_command,
            suspend=self.suspend,
            jarvis_rodando=jarvis_rodando or (lambda: False),
            iniciar_jarvis=iniciar_jarvis or (lambda: (True, None)),
        )

    # ---- start_jarvis ---------------------------------------------------

    def test_start_jarvis_when_down_launches_and_returns_202(self):
        chamadas = []
        status, result, pending = self.action(
            action="start_jarvis", confirmation="START",
            jarvis_rodando=lambda: False,
            iniciar_jarvis=lambda: (chamadas.append(1), (True, None))[1],
        )
        self.assertEqual(status, 202)
        self.assertEqual(result["status"], "starting")
        self.assertEqual(chamadas, [1])
        self.assertFalse(pending)

    def test_start_jarvis_when_up_returns_already_running_without_relaunch(self):
        chamadas = []
        status, result, _ = self.action(
            action="start_jarvis", confirmation="START",
            jarvis_rodando=lambda: True,
            iniciar_jarvis=lambda: (chamadas.append(1), (True, None))[1],
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "already_running")
        self.assertEqual(chamadas, [])

    def test_start_jarvis_requires_its_own_confirmation(self):
        status, _, _ = self.action(action="start_jarvis", confirmation="SHUTDOWN")
        self.assertEqual(status, 400)

    def test_start_jarvis_bad_token_refuses(self):
        status, _, _ = self.action(action="start_jarvis", confirmation="START",
                                   token="f" * 32)
        self.assertEqual(status, 401)

    def test_start_jarvis_reports_launch_failure(self):
        status, result, _ = self.action(
            action="start_jarvis", confirmation="START",
            jarvis_rodando=lambda: False,
            iniciar_jarvis=lambda: (False, "python nao encontrado"),
        )
        self.assertEqual(status, 503)
        self.assertIn("python nao encontrado", result["error"])

    def test_sleep_suspends_without_running_any_shutdown_command(self):
        # Suspender nao pode virar desligamento: de desligado a placa Wi-Fi
        # fica sem energia e o Wake-on-LAN nunca mais acorda o PC.
        status, result, pending = self.action(action="sleep", confirmation="SLEEP")
        self.assertEqual(status, 202)
        self.assertEqual(result["status"], "suspending")
        self.assertEqual(self.suspensoes, 1)
        self.assertEqual(self.calls, [])
        self.assertFalse(pending)

    def test_sleep_requires_its_own_confirmation(self):
        status, _result, _pending = self.action(action="sleep", confirmation="SHUTDOWN")
        self.assertEqual(status, 400)
        self.assertEqual(self.suspensoes, 0)

    def test_sleep_does_not_disturb_a_scheduled_shutdown(self):
        # Um desligamento agendado precisa continuar cancelavel depois disso.
        _status, _result, pending = self.action(action="sleep", confirmation="SLEEP",
                                                pending=True)
        self.assertTrue(pending)

    def test_sleep_reports_failure_instead_of_pretending_it_worked(self):
        self.suspend_falha = True
        status, result, _pending = self.action(action="sleep", confirmation="SLEEP")
        self.assertEqual(status, 503)
        self.assertIn("error", result)

    def test_shutdown_is_authenticated_delayed_and_never_forces_apps_closed(self):
        status, result, pending = self.action()
        self.assertEqual(status, 202)
        self.assertTrue(pending)
        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(self.calls[0][1:], [
            "/s", "/t", "30", "/c",
            "JARVIS: desligamento solicitado pelo usuario",
        ])
        self.assertTrue(self.calls[0][0].lower().endswith("\\shutdown.exe"))
        self.assertNotIn("/f", self.calls[0])

    def test_bad_token_never_runs_shutdown(self):
        status, _, pending = self.action(token="f" * 32)
        self.assertEqual(status, 401)
        self.assertFalse(pending)
        self.assertEqual(self.calls, [])

    def test_request_from_outside_configured_lan_is_rejected(self):
        status, _, pending = self.action(ip="8.8.8.8")
        self.assertEqual(status, 403)
        self.assertFalse(pending)
        self.assertEqual(self.calls, [])

    def test_shutdown_requires_explicit_confirmation_and_is_not_repeatable(self):
        status, _, pending = self.action(confirmation="")
        self.assertEqual(status, 400)
        self.assertFalse(pending)
        status, _, pending = self.action(pending=True)
        self.assertEqual(status, 409)
        self.assertTrue(pending)
        self.assertEqual(self.calls, [])

    def test_cancel_requires_pending_shutdown_and_runs_fixed_abort_command(self):
        status, result, pending = self.action(
            action="cancel", confirmation="CANCEL", pending=True)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(pending)
        self.assertEqual(self.calls[0][1:], ["/a"])
        self.assertTrue(self.calls[0][0].lower().endswith("\\shutdown.exe"))

    def test_cancel_can_abort_windows_shutdown_even_after_agent_restart(self):
        status, _, pending = self.action(
            action="cancel", confirmation="CANCEL", pending=False)
        self.assertEqual(status, 200)
        self.assertFalse(pending)
        self.assertEqual(self.calls[0][1:], ["/a"])

    def test_cancel_when_windows_has_nothing_pending_reports_conflict(self):
        self.command_result = 1
        status, _, pending = self.action(
            action="cancel", confirmation="CANCEL", pending=False)
        self.assertEqual(status, 409)
        self.assertFalse(pending)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
