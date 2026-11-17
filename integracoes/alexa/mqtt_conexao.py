"""Conexão MQTT privada; nunca permite TLS sem validar o servidor."""
import re
import ssl


def validar_config(config):
    broker = config.get("broker", {})
    host = broker.get("host", "")
    if (not isinstance(host, str) or not re.fullmatch(r"[a-zA-Z0-9.-]{4,253}", host)
            or host in {"broker.emqx.io", "broker.hivemq.com", "test.mosquitto.org"}
            or not broker.get("usuario") or not broker.get("senha")
            or broker.get("porta", 8883) != 8883
            or not re.fullmatch(r"jarvis/[a-f0-9]{32}", config.get("topico", ""))):
        raise ValueError("configure um broker privado com usuário, senha e TLS na porta 8883")
    return broker


def criar_cliente(config, cliente_id):
    import paho.mqtt.client as mqtt
    broker = validar_config(config)
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cliente_id,
                          protocol=mqtt.MQTTv311)
    cliente.username_pw_set(broker["usuario"], broker["senha"])
    cliente.tls_set(ca_certs=broker.get("arquivo_ca") or None,
                    cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    cliente.reconnect_delay_set(min_delay=2, max_delay=30)
    cliente.max_queued_messages_set(20)
    cliente.connect_timeout = 3
    return cliente
