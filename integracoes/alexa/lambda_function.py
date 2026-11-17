"""Backend da skill pessoal, para hospedagem Alexa-hosted (Python)."""
import datetime
import json
import queue
import threading
import time
import uuid
from pathlib import Path

try:
    from alexa_protocolo import assinar, identificador, verificar
    from mqtt_conexao import criar_cliente
except ImportError:
    from jarvis.alexa_protocolo import assinar, identificador, verificar
    from .mqtt_conexao import criar_cliente


def resposta(texto, atributos=None, encerrar=False):
    return {"version": "1.0", "sessionAttributes": atributos or {}, "response": {
        "outputSpeech": {"type": "PlainText", "text": texto[:1800]},
        "shouldEndSession": encerrar,
        **({} if encerrar else {"reprompt": {"outputSpeech": {
            "type": "PlainText", "text": "Diga conectar, verificar conexão ou peça um comando ao Jarvis."}}})}}


def autorizado(evento, config, agora=None):
    sistema = evento.get("context", {}).get("System", {})
    skill = sistema.get("application", {}).get("applicationId")
    usuario = sistema.get("user", {}).get("userId")
    if (not config.get("skill_id") or skill != config["skill_id"] or
            not config.get("usuarios_permitidos") or usuario not in config["usuarios_permitidos"]):
        return False
    try:
        data = datetime.datetime.fromisoformat(evento["request"]["timestamp"].replace("Z", "+00:00"))
        pedido_id = evento["request"]["requestId"]
        return (data.tzinfo is not None and isinstance(pedido_id, str) and 1 <= len(pedido_id) <= 256
                and abs((time.time() if agora is None else agora) - data.timestamp()) <= 150)
    except (ValueError, KeyError, TypeError):
        return False


def trocar(config, pedido_id, acao, texto):
    """Espera confirmação real. Publicar um pacote não prova que o PC acordou."""
    topico = config["topico"]
    pronto = threading.Event()
    recebidos = queue.Queue(maxsize=8)
    cliente = criar_cliente(config, "alexa-" + uuid.uuid4().hex[:20])
    def conectado(c, _u, _f, codigo, _p):
        if codigo == 0:
            c.subscribe(topico + "/respostas", qos=1)
    def inscrito(_c, _u, _mid, codigos, _p):
        if all(not codigo.is_failure for codigo in codigos):
            pronto.set()
    def recebido(_c, _u, msg):
        for chave in (config["chave_pc"], config["chave_esp32"]):
            try:
                dado = verificar(msg.payload, msg.topic, chave, {"resposta"})
                if dado["id"] == pedido_id:
                    recebidos.put_nowait(dado)
                return
            except (ValueError, TypeError, KeyError, queue.Full):
                continue
    cliente.on_connect = conectado
    cliente.on_subscribe = inscrito
    cliente.on_message = recebido
    broker = config["broker"]
    cliente.connect_async(broker["host"], 8883, keepalive=20)
    cliente.loop_start()
    limite = time.monotonic() + 5.5
    acordando = None
    processando = None
    try:
        if not pronto.wait(2.5):
            return {"estado": "sem_ponte", "texto": "Não consegui conectar à ponte da sua casa."}
        if acao == "abrir":
            destino = topico + "/acordar"
            info = cliente.publish(destino, assinar(destino, config["chave_esp32"],
                pedido_id, "acordar"), qos=1, retain=False)
            info.wait_for_publish(timeout=0.5)
        destino = topico + "/comandos"
        # O último pedido sobrevive à suspensão; a assinatura expira em 90 s.
        info = cliente.publish(destino, assinar(destino, config["chave_pc"],
            pedido_id, acao, texto=texto), qos=1, retain=True)
        info.wait_for_publish(timeout=0.5)
        while time.monotonic() < limite:
            try:
                dado = recebidos.get(timeout=max(0.01, limite - time.monotonic()))
            except queue.Empty:
                break
            if dado["estado"] == "acordando":
                acordando = dado
            elif dado["estado"] == "processando":
                processando = dado
            else:
                return dado
        return processando or acordando or {"estado": "sem_confirmacao", "texto":
            "Enviei o pedido, mas ainda não recebi confirmação do Jarvis. Diga verificar conexão."}
    finally:
        cliente.disconnect()
        cliente.loop_stop()


def tratar(evento, config, transporte=trocar):
    if not autorizado(evento, config):
        return resposta("Esta skill pessoal ainda não foi vinculada à sua conta.", encerrar=True)
    pedido = evento.get("request", {})
    tipo = pedido.get("type")
    atributos = dict(evento.get("session", {}).get("attributes", {}))
    if tipo == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}
    nome = pedido.get("intent", {}).get("name", "")
    if nome in {"AMAZON.StopIntent", "AMAZON.CancelIntent"}:
        return resposta("Até mais.", encerrar=True)
    if nome in {"AMAZON.HelpIntent", "AMAZON.FallbackIntent"}:
        return resposta("Diga conectar para acordar o computador e abrir o Jarvis. Depois diga: executar, seguido do seu pedido.", atributos)
    texto = ""
    if tipo == "LaunchRequest" or nome == "ConectarIntent":
        acao = "abrir"
    elif nome == "EstadoIntent":
        acao = "status"
    elif nome == "RespostaIntent":
        acao, texto = "consultar", atributos.get("ultimo_pedido", "")
    elif nome in {"AMAZON.YesIntent", "AMAZON.NoIntent"}:
        if not atributos.get("confirmacao_pendente"):
            return resposta("Não há uma ação aguardando confirmação.", atributos)
        acao = "comando"
        texto = "sim" if nome == "AMAZON.YesIntent" else "não"
    elif nome == "ComandoIntent":
        acao = "comando"
        texto = pedido.get("intent", {}).get("slots", {}).get("pedido", {}).get("value", "").strip()
        if not texto or len(texto) > 1000:
            return resposta("Diga executar, seguido de um pedido curto.", atributos)
    else:
        return resposta("Diga conectar ou verificar conexão.", atributos)
    pedido_id = identificador(pedido.get("requestId", ""))
    try:
        resultado = transporte(config, pedido_id, acao, texto)
    except Exception:
        # Senhas, host privado e exceções do broker não vão para CloudWatch.
        return resposta("A ponte está indisponível. Verifique a configuração da integração.", atributos)
    if acao == "comando":
        atributos["ultimo_pedido"] = pedido_id
    if resultado.get("estado") == "confirmacao":
        atributos["confirmacao_pendente"] = True
    else:
        atributos.pop("confirmacao_pendente", None)
    return resposta(resultado["texto"], atributos)


def lambda_handler(event, context):
    try:
        config = json.loads(Path(__file__).with_name("config_local.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return resposta("A integração do Jarvis ainda precisa ser configurada.", encerrar=True)
    return tratar(event, config)
