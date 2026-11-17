"""Doubles only for the external MicroPython clock and I2C hardware."""


class Clock:
    PERIOD = 1 << 30

    def __init__(self, now=0):
        self.now = now

    def ticks_ms(self):
        return self.now % self.PERIOD

    def ticks_diff(self, current, previous):
        half = self.PERIOD // 2
        return (current - previous + half) % self.PERIOD - half

    def sleep_ms(self, milliseconds):
        self.now += milliseconds

    def sleep_us(self, microseconds):
        pass


class Bus:
    def __init__(self):
        self.writes = []
        self.fail = False
        self.closed = False

    def writeto(self, address, data):
        if address != 0x27 or len(data) != 1:
            raise AssertionError("Unexpected PCF8574 transaction")
        if self.fail:
            raise OSError(19, "ENODEV")
        self.writes.append(data[0])
        return 1

    def deinit(self):
        self.closed = True

    def characters(self, start=0):
        # Data nibbles sampled while EN is high; RS=1 distinguishes data.
        nibbles = [value & 0xF0 for value in self.writes[start:]
                   if value & 0x05 == 0x05]
        if len(nibbles) % 2:
            raise AssertionError("Incomplete LCD character transfer")
        return bytes(nibbles[index] | (nibbles[index + 1] >> 4)
                     for index in range(0, len(nibbles), 2))
