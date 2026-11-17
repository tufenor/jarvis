"""Sonda temporaria de MISO: somente leituras, com pull interno fraco.

Executar via mpremote run e reiniciar a ESP32 ao terminar.
Nao grava arquivos nem altera os GPIOs usados pela USB.
"""
from machine import Pin, SoftSPI
from time import sleep_ms

cs = Pin(10, Pin.OUT, value=1)
rst = Pin(9, Pin.OUT, value=1)
miso = Pin(13, Pin.IN)
bus = SoftSPI(baudrate=100_000, polarity=0, phase=0,
              sck=Pin(12), mosi=Pin(11), miso=miso)
rst.value(0)
sleep_ms(20)
rst.value(1)
sleep_ms(50)

try:
    for name, pull in [('sem pull', None), ('pull-up', Pin.PULL_UP),
                       ('pull-down', Pin.PULL_DOWN)]:
        miso.init(Pin.IN, pull=pull)
        sleep_ms(10)
        versions = []
        for _ in range(5):
            rx = bytearray(2)
            cs.value(0)
            try:
                bus.write_readinto(b'\xee\x00', rx)
            finally:
                cs.value(1)
            versions.append(rx[1])
            sleep_ms(10)
        print('MISO', name, ':', [hex(v) for v in versions])
finally:
    cs.value(1)
    bus.deinit()
    miso.init(Pin.IN, pull=None)
