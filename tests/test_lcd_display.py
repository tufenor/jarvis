import importlib
from pathlib import Path
import sys
import unittest

from lcd_fakes import Bus, Clock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware" / "micropython"))
try:
    lcd = importlib.import_module("lcd_display")
except ModuleNotFoundError as exc:
    if exc.name != "lcd_display":
        raise
    lcd = None


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(lcd, "The LCD integration has not been implemented")
        self.clock = Clock()
        self.bus = Bus()

    def driver(self, bus=None):
        return lcd.LCD1602(self.bus if bus is None else bus, clock=self.clock)

    def service(self, factory=None):
        self.messages = []
        return lcd.SensorDisplay(
            lcd_factory=factory or self.driver,
            clock=self.clock,
            report=self.messages.append,
        )

    def test_sensor_values_and_motion_fit_both_rows(self):
        # Catches swapped fields, missing padding, or reversed PIR status.
        self.assertEqual(lcd.format_lines(31, 8, True),
                         ("T:31C U:08%     ", "Movimento: SIM  "))
        self.assertEqual(lcd.format_lines(0, 100, False),
                         ("T:0C U:100%     ", "Movimento: NAO  "))

    def test_missing_or_suspect_measurement_is_not_shown_as_current(self):
        for temperature, humidity in ((None, None), (31, None), (None, 8), (0, 0)):
            with self.subTest(temperature=temperature, humidity=humidity):
                self.assertEqual(lcd.format_lines(temperature, humidity, False),
                                 ("Sem leitura     ", "Movimento: NAO  "))

    def test_driver_initializes_four_bit_mode_before_character_writes(self):
        self.driver().show(("hello Word", "JARVIS"))
        self.assertEqual(self.bus.writes[:9],
                         [8, 0x3C, 0x38, 0x3C, 0x38, 0x3C, 0x38, 0x2C, 0x28])
        self.assertEqual(self.bus.characters(), b"hello Word      JARVIS          ")
        self.assertTrue(all(value & 8 for value in self.bus.writes))
        self.assertTrue(all(not value & 2 for value in self.bus.writes))
        self.assertEqual(self.bus.writes[-1] & 4, 0)

    def test_shorter_row_erases_old_characters_and_clips_to_sixteen(self):
        driver = self.driver()
        driver.show(("0123456789abcdefEXTRA", "unchanged"))
        self.assertEqual(self.bus.characters()[:16], b"0123456789abcdef")
        start = len(self.bus.writes)
        driver.show(("OK", "unchanged"))
        self.assertEqual(self.bus.characters(start), b"OK              ")

    def test_unchanged_rows_do_not_send_redundant_i2c_writes(self):
        driver = self.driver()
        self.assertTrue(driver.show(("first", "second")))
        count = len(self.bus.writes)
        self.assertFalse(driver.show(("first", "second")))
        self.assertEqual(len(self.bus.writes), count)

    def test_initialization_error_releases_i2c_bus(self):
        self.bus.fail = True
        with self.assertRaises(OSError):
            self.driver()
        self.assertTrue(self.bus.closed)

    def test_render_failure_does_not_commit_a_partial_frame(self):
        driver = self.driver()
        self.bus.fail = True
        with self.assertRaises(OSError):
            driver.show(("new", "frame"))
        self.bus.fail = False
        start = len(self.bus.writes)
        self.assertTrue(driver.show(("new", "frame")))
        self.assertEqual(self.bus.characters(start), b"new             frame           ")

    def test_refresh_is_rate_limited_but_uses_latest_values(self):
        display = self.service()
        self.assertTrue(display.update(31, 8, False, now_ms=0))
        count = len(self.bus.writes)
        self.assertFalse(display.update(32, 9, True, now_ms=999))
        self.assertEqual(len(self.bus.writes), count)
        self.assertTrue(display.update(32, 9, True, now_ms=1000))
        self.assertEqual(self.bus.characters(count),
                         b"T:32C U:09%     Movimento: SIM  ")

    def test_failed_connection_retries_after_backoff_without_raising(self):
        attempts = []

        def connect():
            attempts.append(True)
            if len(attempts) == 1:
                raise OSError(19, "ENODEV")
            return self.driver()

        display = self.service(connect)
        self.assertFalse(display.update(31, 8, False, now_ms=0))
        self.assertFalse(display.update(32, 9, True, now_ms=4999))
        self.assertEqual(len(attempts), 1)
        self.assertTrue(display.update(32, 9, True, now_ms=5000))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.bus.characters(),
                         b"T:32C U:09%     Movimento: SIM  ")

    def test_bus_failure_closes_driver_then_reconnects_with_current_state(self):
        replacement = Bus()
        buses = iter((self.bus, replacement))
        display = self.service(lambda: self.driver(next(buses)))
        self.assertTrue(display.update(31, 8, False, now_ms=0))
        self.bus.fail = True
        self.assertFalse(display.update(32, 9, True, now_ms=1000))
        self.assertTrue(self.bus.closed)
        self.assertFalse(display.update(None, None, False, now_ms=5999))
        self.assertTrue(display.update(None, None, False, now_ms=6000))
        self.assertEqual(replacement.characters(),
                         b"Sem leitura     Movimento: NAO  ")

    def test_backoff_handles_micropython_tick_wrap(self):
        attempts = []

        def unavailable():
            attempts.append(True)
            raise OSError(19, "ENODEV")

        display = self.service(unavailable)
        self.assertFalse(display.update(None, None, False, now_ms=(1 << 30) - 100))
        self.assertFalse(display.update(None, None, True, now_ms=100))
        self.assertEqual(len(attempts), 1)
        self.assertFalse(display.update(None, None, True, now_ms=4900))
        self.assertEqual(len(attempts), 2)


if __name__ == "__main__":
    unittest.main()
