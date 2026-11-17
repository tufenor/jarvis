"""Comandos Telegram limitados para o JARVIS.

Somente a conversa privada configurada pode consultar a placa ou alterar a luz.
"""
import ipaddress


COMANDOS = (
    "/status — sensores e luz\n"
    "/luz_ligar — liga a luz\n"
    "/luz_desligar — desliga a luz\n"
    "/luz_auto — volta ao automático\n"
    "/ajuda — mostra esta lista"
)


def _url_placa(config, rota):
    ip = ipaddress.ip_address(str(config.get("ip_da_placa", "")))
    if ip.version != 4 or not ip.is_private:
        raise ValueError("IP local inválido")
    return f"http://{ip}{rota}"


def processar_mensagem(update, config, sessao_http):
    """Retorna a resposta a enviar, ou None para remetentes não autorizados."""
    mensagem = update.get("message") or {}
    chat = mensagem.get("chat") or {}
    remetente = mensagem.get("from") or {}
    autorizado = str(config.get("telegram_chat_id", ""))
    if (chat.get("type") != "private" or not autorizado
            or str(chat.get("id", "")) != autorizado
            or str(remetente.get("id", "")) != autorizado):
        return None

    texto = mensagem.get("text", "").strip()
    if not texto.startswith("/"):
        return f"Comandos disponíveis:\n{COMANDOS}"
    comando = texto.split(maxsplit=1)[0].lower().split("@", 1)[0]
    if comando in ("/start", "/ajuda"):
        return f"JARVIS — comandos disponíveis:\n{COMANDOS}"

    rotas_luz = {
        "/luz_ligar": ("/led/on", "Luz ligada."),
        "/luz_desligar": ("/led/off", "Luz desligada."),
        "/luz_auto": ("/led/auto", "Luz em modo automático."),
    }
    try:
        if comando == "/status":
            resposta = sessao_http.get(_url_placa(config, "/status"), timeout=4)
            resposta.raise_for_status()
            dados = resposta.json()
            movimento = "detectado" if dados.get("motion") else "não detectado"
            luz = "ligada" if dados.get("led") else "desligada"
            return (f"Temperatura: {dados.get('temperature', '—')} °C\n"
                    f"Umidade: {dados.get('humidity', '—')}%\n"
                    f"Movimento: {movimento}\nLuz: {luz}")
        if comando in rotas_luz:
            rota, sucesso = rotas_luz[comando]
            resposta = sessao_http.get(_url_placa(config, rota), timeout=4)
            resposta.raise_for_status()
            return sucesso
    except Exception:
        # Exceções de requests podem conter a URL do Bot API e o token.
        return "Não consegui consultar a ESP32 agora."
    return f"Comandos disponíveis:\n{COMANDOS}"


def ouvir_comandos(config, parar):
    """Faz polling do Telegram; todas as requisições são iniciadas pelo PC."""
    import requests

    token = config["telegram_token"]
    chat_id = str(config["telegram_chat_id"])
    sessao = requests.Session()
    offset = None
    while not parar.is_set():
        try:
            params = {"timeout": 20}
            if offset is not None:
                params["offset"] = offset
            resposta = sessao.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params=params, timeout=25)
            resposta.raise_for_status()
            for update in resposta.json().get("result", []):
                offset = update["update_id"] + 1
                texto = processar_mensagem(update, config, sessao)
                if texto is None:
                    continue
                mensagem = update.get("message") or {}
                destino = str((mensagem.get("chat") or {}).get("id", ""))
                if destino != chat_id:
                    continue
                sessao.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data={"chat_id": chat_id, "text": texto}, timeout=10)
        except Exception:
            # Não registrar a exceção: a URL pode conter o token do bot.
            parar.wait(3)
