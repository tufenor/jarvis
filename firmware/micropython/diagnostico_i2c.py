"""Descobre se o LCD/PCA9685 estao ALIMENTADOS, sem chutar pinos.

Todo modulo I2C traz resistores de pull-up ligados ao seu VCC. Entao:

  - se o modulo esta alimentado, SDA e SCL ficam em nivel ALTO
  - se nao esta, os pinos caem para BAIXO

O teste liga o pull-down interno (fraco, ~45k) e le. Um pull-up externo
(~4.7k) vence esse cabo de guerra e o pino le ALTO. Sem modulo
alimentado do outro lado, le BAIXO.

Isso separa "sem energia" de "pino errado" - que e exatamente a duvida.
"""
from machine import Pin, SoftI2C
from time import sleep_ms

SDA, SCL = 15, 16

print("Teste eletrico do barramento I2C (SDA=GPIO%d, SCL=GPIO%d)" % (SDA, SCL))
print("-" * 52)

leituras = {}
for nome, numero in (("SDA", SDA), ("SCL", SCL)):
    pino = Pin(numero, Pin.IN, Pin.PULL_DOWN)
    sleep_ms(50)
    valor = pino.value()
    leituras[nome] = valor
    print("  %s (GPIO%-2d): %s" % (nome, numero, "ALTO" if valor else "BAIXO"))

print("-" * 52)
if leituras["SDA"] and leituras["SCL"]:
    print("VEREDITO: ha modulo I2C alimentado nesses pinos.")
    print("Os pull-ups estao puxando as duas linhas para cima.")
    print("Entao o problema NAO e energia - e comunicacao ou endereco.")
    print()
    print("Tentando falar com ele...")
    try:
        bus = SoftI2C(sda=Pin(SDA), scl=Pin(SCL), freq=50000)
        achados = bus.scan()
        print("  Scan:", [hex(a) for a in achados] if achados else "ninguem respondeu")
    except Exception as exc:
        print("  Falhou:", exc)
elif leituras["SDA"] or leituras["SCL"]:
    alto = "SDA" if leituras["SDA"] else "SCL"
    baixo = "SCL" if leituras["SDA"] else "SDA"
    print("VEREDITO: so %s esta em nivel alto; %s esta solto." % (alto, baixo))
    print("Provavelmente falta o fio de %s, ou ele esta no pino errado." % baixo)
else:
    print("VEREDITO: as duas linhas estao em nivel BAIXO.")
    print()
    print("Significa que NAO ha modulo alimentado ligado nesses pinos.")
    print("O codigo nao tem como consertar isso. Confira, com o USB fora:")
    print("  1. o VCC do LCD esta no trilho de 5V?")
    print("  2. esse trilho tem energia de verdade?")
    print("  3. o GND do LCD vai ao MESMO GND da ESP32?")
    print("  4. SDA no GPIO15 e SCL no GPIO16?")
