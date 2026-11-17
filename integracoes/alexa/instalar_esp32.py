"""Instala a ponte MQTT na ESP32 somente depois da preparação local."""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PASTA = Path(__file__).resolve().parent
PRIVADO = PASTA / "privado"


def mpremote(porta, *argumentos, capturar=False):
    comando = [sys.executable, "-m", "mpremote", "connect", porta, *argumentos]
    return subprocess.run(comando, check=True, text=True, capture_output=capturar)


def exigir_privados():
    configuracao = PRIVADO / "esp32_alexa.json"
    certificado = PRIVADO / "alexa_ca.pem"
    if not configuracao.is_file() or not certificado.is_file():
        raise SystemExit("Execute preparar.py --preparar antes de instalar na ESP32.")
    return configuracao, certificado


def instalar(porta):
    configuracao, certificado = exigir_privados()
    copia = PRIVADO / "backups" / ("main_antes_alexa_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py")
    copia.parent.mkdir(parents=True, exist_ok=True)
    try:
        resultado = mpremote(porta, "fs", "cp", ":main.py", str(copia), capturar=True)
        if resultado.stderr:
            raise RuntimeError("não consegui salvar a cópia do firmware atual")
    except subprocess.CalledProcessError as erro:
        raise SystemExit("Não consegui conversar com a ESP32 em " + porta) from erro

    fontes = [
        (RAIZ / "firmware" / "micropython" / "alexa_wake.py", ":alexa_wake.py"),
        (RAIZ / "jarvis" / "alexa_protocolo.py", ":alexa_protocolo.py"),
        (RAIZ / "firmware" / "micropython" / "umqtt" / "simple.py", ":umqtt/simple.py"),
        (configuracao, ":alexa.json"),
        (certificado, ":alexa_ca.pem"),
        (RAIZ / "firmware" / "micropython" / "main_network.py", ":main.py"),
    ]
    try:
        mpremote(porta, "fs", "mkdir", ":umqtt")
    except subprocess.CalledProcessError:
        pass  # a segunda instalação encontra a pasta já criada
    mpremote(porta, "fs", "cp", str(RAIZ / "firmware" / "micropython" / "umqtt" / "__init__.py"), ":umqtt/__init__.py")
    for origem, destino in fontes:
        mpremote(porta, "fs", "cp", str(origem), destino)
    mpremote(porta, "reset")
    print("Ponte instalada. Cópia do main.py anterior guardada em " + str(copia))


def verificar(porta):
    try:
        resultado = mpremote(porta, "fs", "ls", capturar=True)
    except subprocess.CalledProcessError as erro:
        raise SystemExit("Não consegui conversar com a ESP32 em " + porta) from erro
    nomes = resultado.stdout.lower()
    print("ESP32 acessível em " + porta + ". Ponte instalada: " + ("sim" if "alexa_wake.py" in nomes else "não"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--porta", default="COM7")
    parser.add_argument("--instalar", action="store_true", help="faz cópia e envia arquivos à ESP32")
    argumentos = parser.parse_args()
    instalar(argumentos.porta) if argumentos.instalar else verificar(argumentos.porta)


if __name__ == "__main__":
    main()
