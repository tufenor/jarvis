"""Execute the real firmware with hardware/network surfaces substituted."""
import builtins
import contextlib
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from lcd_fakes import Bus, Clock

FIRMWARE = Path(__file__).resolve().parents[1] / "firmware" / "micropython"
sys.path.insert(0, str(FIRMWARE))


class EndSimulation(BaseException):
    pass


class FirmwareTests(unittest.TestCase):
    def run_firmware(self, lcd_failure=False, dht_failure=False):
        clock = Clock()
        bus = Bus()
        bus.fail = lcd_failure
        pins = {}
        reads = []
        options = []

        class Pin:
            OUT = 1
            IN = 0

            def __init__(self, number, mode=None, value=0):
                self.number = number
                self.state = value
                self.changes = []
                pins[number] = self

            def value(self, value=None):
                if value is not None:
                    self.state = value
                    self.changes.append(value)
                if self.number == 7:
                    return int(clock.now >= 4000)
                return self.state

        def i2c(number, **kwargs):
            options.append((number, kwargs))
            return bus

        class DHT11:
            def __init__(self, pin):
                self.pin = pin

            def measure(self):
                reads.append(clock.now)
                if dht_failure and len(reads) > 1:
                    raise OSError(116, "ETIMEDOUT")

            def temperature(self):
                return 31

            def humidity(self):
                return 8

        class WLAN:
            def __init__(self, kind):
                self.kind = kind

            def active(self, value=None):
                return True

            def config(self, **kwargs):
                pass

            def ifconfig(self):
                return ("192.0.2.1", "255.255.255.0", "192.0.2.1", "192.0.2.1")

        class Server:
            def setsockopt(self, *args):
                pass

            def bind(self, address):
                self.address = address

            def listen(self, number):
                pass

            def settimeout(self, seconds):
                pass

            def accept(self):
                raise OSError("No incoming client")

        class BLE:
            def active(self, value):
                pass

            def gap_advertise(self, interval, **kwargs):
                pass

        def sleep(seconds):
            clock.now += int(seconds * 1000)
            if clock.now >= 12000:
                raise EndSimulation()

        def no_saved_configuration(*args, **kwargs):
            raise OSError("No wifi.json in isolated test")

        runtime = {
            "time": types.SimpleNamespace(ticks_ms=clock.ticks_ms,
                ticks_diff=clock.ticks_diff, sleep=sleep,
                sleep_ms=clock.sleep_ms, sleep_us=clock.sleep_us),
            "machine": types.SimpleNamespace(Pin=Pin, I2C=i2c),
            "dht": types.SimpleNamespace(DHT11=DHT11),
            "network": types.SimpleNamespace(WLAN=WLAN, STA_IF=0, AP_IF=1, AUTH_WPA2_PSK=3),
            "socket": types.SimpleNamespace(socket=Server, SOL_SOCKET=1, SO_REUSEADDR=2),
            "bluetooth": types.SimpleNamespace(BLE=BLE),
        }
        namespace = {"__name__": "__main__", "__builtins__":
                     dict(vars(builtins), open=no_saved_configuration)}
        output = io.StringIO()
        # Reimport the production driver so its default clock is the simulated one.
        original = sys.modules.pop("lcd_display", None)
        try:
            with patch.dict(sys.modules, runtime), contextlib.redirect_stdout(output):
                try:
                    exec(compile((FIRMWARE / "main_network.py").read_text(encoding="utf-8"),
                                 "main_network.py", "exec"), namespace)
                except EndSimulation:
                    pass
        finally:
            sys.modules.pop("lcd_display", None)
            if original is not None:
                sys.modules["lcd_display"] = original
        return output.getvalue(), pins, reads, bus, options

    def test_main_updates_lcd_without_changing_approved_pins(self):
        output, pins, reads, bus, options = self.run_firmware()
        self.assertIn("LCD: T:31C U:08% | Movimento: SIM", output)
        # A tela AMBIENTE mostra os valores com icones no lugar dos rotulos.
        self.assertIn(b"31C", bus.characters())
        self.assertIn(b"08%", bus.characters())
        # A tela PRESENCA mostra o estado do PIR. A simulacao so chega a
        # exibi-la depois que o movimento dispara, entao o estado calmo nao
        # aparece aqui - ele e coberto pelo teste de format_lines.
        self.assertIn(b"MOVIMENTO", bus.characters())
        self.assertEqual(options[0][0], 0)
        self.assertEqual(options[0][1]["sda"].number, 15)
        self.assertEqual(options[0][1]["scl"].number, 16)
        # 100 kHz, nao 10 kHz: medido na placa em 20/10/2026, o barramento
        # a 10 kHz devolvia ENODEV enquanto a 100 kHz o 0x27 respondia.
        # Foram duas mudancas juntas (SoftI2C e a frequencia), entao nao da
        # para cravar qual das duas era a culpada - a correcao cobre as duas.
        self.assertEqual(options[0][1]["freq"], 100000)
        self.assertGreaterEqual(len(reads), 4)
        self.assertIn(0, pins[4].changes)
        self.assertIn(1, pins[4].changes)
        self.assertIn("HTTP: http://192.0.2.1", output)
        self.assertIn("BLUETOOTH: anunciando JARVIS-ESP32", output)

    def test_missing_lcd_does_not_stop_led_or_sensor_loop(self):
        output, pins, reads, bus, options = self.run_firmware(lcd_failure=True)
        self.assertIn("LCD: indisponivel", output)
        self.assertGreaterEqual(len(reads), 4)
        self.assertGreaterEqual(len(pins[4].changes), 10)
        self.assertIn("PIR GPIO7: MOVIMENTO", output)
        self.assertLessEqual(len(options), 3)

    def test_failed_dht_clears_old_reading_but_keeps_motion_and_led(self):
        output, pins, reads, bus, options = self.run_firmware(dht_failure=True)
        self.assertIn("LCD: T:31C U:08%", output)
        self.assertIn("LCD: Sem leitura | Movimento: SIM", output)
        self.assertIn(b"sem leitura", bus.characters())
        self.assertGreaterEqual(len(pins[4].changes), 10)


if __name__ == "__main__":
    unittest.main()
