"""JARVIS - primeiro firmware próprio para ESP32-S3.

Mantém o teste mínimo e seguro: mensagem serial e LED RGB onboard, quando
presente. Sensores serão adicionados em módulos separados depois.
"""
import time
from machine import Pin

# Saida de teste para o primeiro LED externo.
# O LED deve estar em serie com resistor de 220 ou 330 ohms.
external_led = Pin(4, Pin.OUT, value=0)

pixel = None
try:
    import neopixel
    pixel = neopixel.NeoPixel(Pin(48), 1)
except Exception:
    pixel = None

def set_pixel(rgb):
    if pixel is not None:
        pixel[0] = rgb
        pixel.write()

print("JARVIS ESP32-S3 ONLINE")
print("Firmware: MicroPython local")
print("Aguardando proximo modulo")

while True:
    external_led.value(1)
    set_pixel((0, 20, 0))
    print("JARVIS HEARTBEAT ON - GPIO4 HIGH")
    time.sleep(1)
    external_led.value(0)
    set_pixel((0, 0, 0))
    print("JARVIS HEARTBEAT OFF - GPIO4 LOW")
    time.sleep(1)
