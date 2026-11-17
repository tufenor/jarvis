"""Prepara os arquivos privados da ponte Alexa sem mostrar segredos no terminal."""
import argparse
import getpass
import json
import os
import re
import secrets
import shutil
import zipfile
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PASTA = Path(__file__).resolve().parent
PRIVADO = PASTA / "privado"
PUBLICOS = {"broker.emqx.io", "broker.hivemq.com", "test.mosquitto.org"}


def escrever_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)


def pedir(rotulo, segredo=False):
    while True:
        valor = (getpass.getpass(rotulo + ": ") if segredo else input(rotulo + ": ")).strip()
        if valor:
            return valor
        print("Esse campo é obrigatório.")


def preparar():
    print("Preparação local da ponte Alexa. Nenhuma senha será exibida.")
    # IDs podem ser passados apenas para esta execução pelo configurador local;
    # assim não precisam ser digitados novamente nem aparecer no chat.
    skill_id = os.environ.get("JARVIS_ALEXA_SKILL_ID", "").strip() or pedir(
        "ID da skill Alexa (amzn1.ask.skill...)")
    usuario = os.environ.get("JARVIS_ALEXA_USER_ID", "").strip() or pedir(
        "ID de usuário Alexa autorizado (amzn1.ask.account...)")
    host = pedir("Host TLS do broker MQTT").lower()
    if (not re.fullmatch(r"[a-z0-9.-]{4,253}", host) or host in PUBLICOS):
        raise SystemExit("Use um broker privado com TLS; brokers públicos não são aceitos.")
    broker_usuario = pedir("Usuário MQTT")
    broker_senha = pedir("Senha MQTT", segredo=True)
    arquivo_ca = Path(pedir("Caminho do certificado CA PEM para a ESP32")).expanduser()
    if not arquivo_ca.is_file():
        raise SystemExit("Não encontrei o certificado CA PEM indicado.")

    topico = "jarvis/" + secrets.token_hex(16)
    chave_pc = secrets.token_hex(32)
    chave_esp32 = secrets.token_hex(32)
    broker = {"host": host, "porta": 8883, "usuario": broker_usuario, "senha": broker_senha}
    cloud = {"skill_id": skill_id, "usuarios_permitidos": [usuario], "topico": topico,
             "chave_pc": chave_pc, "chave_esp32": chave_esp32, "broker": broker}
    computador = {"topico": topico, "chave": chave_pc, "broker": broker}
    esp32 = {"topico": topico, "chave": chave_esp32, "broker": broker}

    PRIVADO.mkdir(parents=True, exist_ok=True)
    escrever_json(PRIVADO / "config_local.json", cloud)
    escrever_json(PRIVADO / "esp32_alexa.json", esp32)
    escrever_json(RAIZ / "dados" / "alexa.json", computador)
    shutil.copyfile(arquivo_ca, PRIVADO / "alexa_ca.pem")
    print("Arquivos privados preparados. Use --empacotar e depois instalar_esp32.py --instalar.")


def empacotar():
    destino = PASTA / "jarvis-alexa.zip"
    arquivos = {
        PASTA / "lambda_function.py": "lambda/lambda_function.py",
        PASTA / "mqtt_conexao.py": "lambda/mqtt_conexao.py",
        PASTA / "requirements.txt": "lambda/requirements.txt",
        RAIZ / "jarvis" / "alexa_protocolo.py": "lambda/alexa_protocolo.py",
        PASTA / "interactionModels" / "custom" / "pt-BR.json":
            "skill-package/interactionModels/custom/pt-BR.json",
        RAIZ / "docs" / "ALEXA_JARVIS.md": "ALEXA_JARVIS.md",
    }
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        for origem, dentro in arquivos.items():
            if not origem.is_file():
                raise SystemExit("Arquivo ausente para o pacote: " + str(origem))
            pacote.write(origem, dentro)
    print("Pacote sem segredos criado em: " + str(destino))


def empacotar_hosted():
    """Gera o ZIP que pode ser enviado ao editor de código da Alexa.

    O arquivo privado é incluído somente neste artefato local e nunca entra no
    pacote público da skill nem no Git.
    """
    config = PRIVADO / "config_local.json"
    if not config.is_file():
        raise SystemExit(
            "Configuração privada ausente. Execute primeiro --preparar "
            "nesta máquina; nenhuma credencial deve ser enviada pelo chat."
        )
    destino = PASTA / "alexa-hosted-code-configurado.zip"
    arquivos = {
        PASTA / "lambda_function.py": "lambda/lambda_function.py",
        PASTA / "mqtt_conexao.py": "lambda/mqtt_conexao.py",
        PASTA / "requirements.txt": "lambda/requirements.txt",
        RAIZ / "jarvis" / "alexa_protocolo.py": "lambda/alexa_protocolo.py",
        config: "lambda/config_local.json",
    }
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as pacote:
        for origem, dentro in arquivos.items():
            if not origem.is_file():
                raise SystemExit("Arquivo ausente para o pacote: " + str(origem))
            pacote.write(origem, dentro)
    print("Pacote hospedado configurado criado em: " + str(destino))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preparar", action="store_true", help="gera arquivos privados localmente")
    parser.add_argument("--empacotar", action="store_true", help="gera o ZIP sem credenciais")
    parser.add_argument("--empacotar-hosted", action="store_true",
                        help="gera o ZIP do código hospedado incluindo a configuração privada local")
    argumentos = parser.parse_args()
    if not argumentos.preparar and not argumentos.empacotar and not argumentos.empacotar_hosted:
        parser.print_help()
        return
    if argumentos.preparar:
        preparar()
    if argumentos.empacotar:
        empacotar()
    if argumentos.empacotar_hosted:
        empacotar_hosted()


if __name__ == "__main__":
    main()
