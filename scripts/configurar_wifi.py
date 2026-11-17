"""Grava a rede Wi-Fi direto na ESP32 pelo cabo USB.

Mais facil do que entrar na rede JARVIS-SETUP: voce digita aqui mesmo e
o script escreve o arquivo wifi.json na placa.

A senha e digitada no SEU computador e vai direto para a placa pelo cabo.
Ela nao aparece na tela, nao fica salva em nenhum arquivo do PC e nao passa
por nenhum chat ou internet.

Uso:  .venv\\Scripts\\python.exe scripts\\configurar_wifi.py
"""
import getpass
import json
import subprocess
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MPREMOTE = os.path.join(BASE, ".venv", "Scripts", "mpremote.exe")


def achar_porta():
    """Descobre sozinho em qual COM a placa esta."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    for porta in list_ports.comports():
        # A ESP32-S3 aparece com o fabricante Espressif (VID 303A).
        if porta.vid == 0x303A or "303A" in str(porta.hwid).upper():
            return porta.device
    portas = list(list_ports.comports())
    return portas[0].device if len(portas) == 1 else None


def main():
    print("=" * 52)
    print("  JARVIS - configurar o Wi-Fi da placa")
    print("=" * 52)

    porta = achar_porta()
    if not porta:
        print("\nNao achei a placa. Confira se o cabo USB esta conectado")
        print("e se nenhum outro programa esta usando a porta.")
        sys.exit(1)
    print(f"\nPlaca encontrada em: {porta}\n")

    ssid = input("Nome da sua rede Wi-Fi (exatamente como aparece): ").strip()
    if not ssid:
        print("Nome vazio. Cancelado.")
        sys.exit(1)

    senha = getpass.getpass("Senha da rede (nao aparece enquanto digita): ")

    print("\nATENCAO: a ESP32 so enxerga redes de 2.4 GHz.")
    print("Se a sua rede for 5 GHz, ela nao vai conseguir conectar.")
    print("Muitos roteadores tem as duas com nomes diferentes (ex: 'Casa' e 'Casa_5G').\n")

    conteudo = json.dumps({"ssid": ssid, "password": senha})
    caminho_temp = os.path.join(BASE, "scripts", "_wifi_temp.json")
    with open(caminho_temp, "w", encoding="utf-8") as f:
        f.write(conteudo)

    try:
        print("Enviando para a placa...")
        r = subprocess.run([MPREMOTE, "connect", porta, "fs", "cp",
                            caminho_temp, ":wifi.json"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print("Falhou ao enviar:")
            print(r.stdout, r.stderr)
            sys.exit(1)
        print("Arquivo gravado. Reiniciando a placa...")
        subprocess.run([MPREMOTE, "connect", porta, "reset"],
                       capture_output=True, text=True, timeout=30)
    finally:
        # Nao deixar a senha em disco.
        try:
            os.remove(caminho_temp)
        except Exception:
            pass

    print("\n" + "=" * 52)
    print("Pronto. Agora rode  scripts\\rodar_ver_ip.bat  para ver")
    print("se ela conectou e qual IP recebeu.")
    print("=" * 52)


if __name__ == "__main__":
    main()
