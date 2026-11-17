"""Recebe somente pedidos autenticados de despertar, fora do laço dos sensores."""
import json
import time

from alexa_protocolo import assinar, verificar


class ReceptorWake:
    def __init__(self, config, acordar, publicar):
        self.config, self.acordar, self.publicar = config, acordar, publicar
        self.recebidos = []

    def receber(self, topico, mensagem):
        if isinstance(topico, bytes):
            topico = topico.decode()
        if topico != self.config["topico"] + "/acordar":
            return False
        try:
            pedido = verificar(mensagem, topico, self.config["chave"], {"acordar"})
        except (ValueError, TypeError, KeyError):
            return False
        if pedido["id"] in self.recebidos:
            return False
        self.recebidos = (self.recebidos + [pedido["id"]])[-64:]
        ok, _ = self.acordar()
        texto = ("Enviei o sinal para acordar o computador. O Jarvis vai conectar quando ele voltar. Diga verificar conexão em alguns instantes."
                 if ok else "Não consegui enviar o sinal para acordar o computador.")
        destino = self.config["topico"] + "/respostas"
        self.publicar(destino.encode(), assinar(destino, self.config["chave"],
            pedido["id"], "resposta", texto=texto, estado="acordando" if ok else "erro"))
        return ok


def rodar(config, acordar):
    import network
    import ntptime
    import ssl
    from umqtt.simple import MQTTClient
    espera = 3
    atual = [None]

    def publicar(topico, mensagem):
        if atual[0] is not None:
            atual[0].publish(topico, mensagem, qos=1)

    receptor = ReceptorWake(config, acordar, publicar)
    while True:
        cliente = None
        try:
            if not network.WLAN(network.STA_IF).isconnected():
                time.sleep(5)
                continue
            ntptime.settime()
            contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            contexto.verify_mode = ssl.CERT_REQUIRED
            contexto.load_verify_locations(cafile="alexa_ca.pem")
            broker = config["broker"]
            cliente = MQTTClient(
                ("esp32-" + config["topico"].split("/")[1]).encode(),
                broker["host"], port=8883, user=broker["usuario"].encode(),
                password=broker["senha"].encode(), keepalive=30, ssl=contexto)
            atual[0] = cliente
            cliente.set_callback(receptor.receber)
            cliente.connect()
            cliente.subscribe((config["topico"] + "/acordar").encode(), qos=1)
            print("ALEXA: ponte de despertar conectada")
            espera = 3
            ultimo_ping = time.ticks_ms()
            while network.WLAN(network.STA_IF).isconnected():
                cliente.check_msg()
                if time.ticks_diff(time.ticks_ms(), ultimo_ping) >= 15000:
                    cliente.ping()
                    ultimo_ping = time.ticks_ms()
                time.sleep_ms(100)
        except Exception:
            print("ALEXA: sem ponte; nova tentativa em", espera, "segundos")
        finally:
            atual[0] = None
            if cliente:
                try:
                    cliente.sock.close()
                except Exception:
                    pass
        time.sleep(espera)
        espera = min(60, espera * 2)


def iniciar(acordar):
    try:
        with open("alexa.json") as arquivo:
            config = json.load(arquivo)
        broker = config["broker"]
        topico = config.get("topico", "")
        chave = config.get("chave", "")
        if (not isinstance(broker, dict) or not broker.get("host") or not broker.get("usuario") or not broker.get("senha")
                or broker.get("porta", 8883) != 8883 or len(config.get("chave", "")) != 64
                or broker["host"] in ("broker.emqx.io", "broker.hivemq.com", "test.mosquitto.org")
                or len(topico) != 39 or not topico.startswith("jarvis/")
                or any(c not in "0123456789abcdef" for c in topico[7:])
                or any(c not in "0123456789abcdef" for c in chave)):
            return False
        with open("alexa_ca.pem", "rb") as arquivo:
            if not arquivo.read(1):
                return False
    except (OSError, ValueError, KeyError, TypeError):
        return False
    import _thread
    _thread.start_new_thread(rodar, (config, acordar))
    return True
