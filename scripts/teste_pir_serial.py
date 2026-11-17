"""Teste isolado do PIR HC-SR501 (GPIO7) via serial.

Reseta a placa e captura ~20 segundos de saida serial. O firmware
(main_network.py) imprime o estado inicial do PIR e depois so imprime
de novo quando o estado MUDA (movimento detectado / parou de detectar).

Uso:
    .venv\\Scripts\\python.exe scripts\\teste_pir_serial.py COM7
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
BAUD = 115200
DURATION_S = 20

print(f"Abrindo {PORT} a {BAUD} baud...")
with serial.Serial(PORT, BAUD, timeout=1) as ser:
    ser.setDTR(False)
    ser.setRTS(True)
    time.sleep(0.2)
    ser.setRTS(False)
    time.sleep(0.2)
    print(f"Placa resetada. Capturando {DURATION_S}s de saida serial...")
    print("MEXA A MAO NA FRENTE DO SENSOR PIR (GPIO7) DURANTE ESSE TEMPO.\n")
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
