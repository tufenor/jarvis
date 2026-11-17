"""Teste completo da placa JARVIS (ESP32-S3) via serial.

Reseta a placa e captura ~18 segundos de saida serial, que ja cobre,
com o firmware atual (main_network.py), em sequencia:
  - LED externo (GPIO4) alternando ON/OFF
  - PIR HC-SR501 (GPIO7) - estado inicial e mudancas
  - DHT11 (GPIO6) - temperatura/umidade a cada ~2.5s
  - LCD I2C 16x2 (endereco 0x27, SDA=15 SCL=16) - linhas exibidas
  - Wi-Fi/Bluetooth - status de inicializacao

Uso:
    .venv\Scripts\python.exe scripts\teste_completo_serial.py COM7
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
BAUD = 115200
DURATION_S = 18

print(f"Abrindo {PORT} a {BAUD} baud...")
with serial.Serial(PORT, BAUD, timeout=1) as ser:
    ser.setDTR(False)
    ser.setRTS(True)
    time.sleep(0.2)
    ser.setRTS(False)
    time.sleep(0.2)
    print(f"Placa resetada. Capturando {DURATION_S}s de saida serial...\n")
    print("-" * 60)
    end = time.time() + DURATION_S
    while time.time() < end:
        line = ser.readline()
        if line:
            try:
                text = line.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = repr(line)
            if text:
                print(text)
    print("-" * 60)
    print("Captura encerrada.")
