"""Executar somente apos tirar MOSI/MISO do RC522 e unir GPIO11 a GPIO13.

Usa um jumper entre saida MOSI e entrada MISO para verificar a SPI da ESP32.
Nao grava firmware. Reiniciar a placa ao terminar.
"""
from machine import Pin, SoftSPI, SPI

Pin(10, Pin.OUT, value=1)  # Leitor nao selecionado durante o teste.
pattern = b'\x00\xff\xaa\x55\x12\x34\x87\x78'

for kind in ('SoftSPI', 'SPI(1)'):
    bus = None
    try:
        options = dict(baudrate=100_000, polarity=0, phase=0,
                       sck=Pin(12), mosi=Pin(11), miso=Pin(13))
        bus = SoftSPI(**options) if kind == 'SoftSPI' else SPI(1, **options)
        results = []
        for _ in range(5):
            received = bytearray(len(pattern))
            bus.write_readinto(pattern, received)
            results.append(bytes(received) == pattern)
        print(kind, 'loopback:', 'PASSOU 5/5' if all(results) else 'FALHOU',
              'recebido:', bytes(received).hex())
    finally:
        if bus is not None:
            bus.deinit()
