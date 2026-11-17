"""So escuta a serial (sem resetar) por N segundos - usar logo apos um reset.

A ESP32-S3 usa USB nativo: ao resetar ela some da lista de portas por um
instante e volta. Abrir na hora falha. Por isso o script espera a porta
reaparecer antes de desistir.
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
DURACAO = int(sys.argv[2]) if len(sys.argv) > 2 else 15
ESPERA_MAX = 20  # segundos aguardando a porta voltar


def abrir(porta):
    limite = time.time() + ESPERA_MAX
    ultima = None
    tentativa = 0
    while time.time() < limite:
        tentativa += 1
        try:
            return serial.Serial(porta, 115200, timeout=1)
        except Exception as exc:
            ultima = exc
            if tentativa == 1:
                print(f"Porta {porta} ainda nao voltou; aguardando...")
            time.sleep(1)
    raise SystemExit(f"Nao consegui abrir {porta} em {ESPERA_MAX}s. Ultimo erro: {ultima}")


ser = abrir(PORT)
with ser:
    print(f"Escutando {PORT} por {DURACAO}s...\n")
    fim = time.time() + DURACAO
    while time.time() < fim:
        linha = ser.readline()
        if linha:
            try:
                print(linha.decode("utf-8", errors="replace").rstrip())
            except Exception:
                print(repr(linha))
