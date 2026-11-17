"""Relé de Wake-on-LAN: a ESP32 consulta um relé HTTPS configurável e dispara pacote mágico.

Fluxo:
  Celular (4G / fora de casa) -> https://seu-dominio.example/jarvis/wake
  ESP32 (sempre on, dentro de casa) -> poll a cada 5 s em /jarvis/pendente.php
  Se pendente=true, monta e envia o pacote mÃ¡gico na LAN local.

Separado do main pra ficar fÃ¡cil desligar em bloco e testar via REPL.
"""
import time
import socket

try:
    import urequests as requests
except ImportError:
    import requests

from wake_on_lan import build_magic_packet

# Troque se trocar de dominio ou de token.
URL_PENDENTE = "https://seu-dominio.example/jarvis/pendente"
URL_STATUS = "https://seu-dominio.example/jarvis/status"
# Defina o token do relay aqui. Nunca comite o valor real.
TOKEN = "DEFINA_SEU_TOKEN"

CHECAR_A_CADA_MS = 5000

_proxima_checagem = 0


def _enviar_pacote(mac, broadcast):
    packet = build_magic_packet(mac)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        # Portas 9 (canonica) e 7 (eco) - alguns PCs so acordam numa das duas.
        udp.sendto(packet, (broadcast, 9))
        udp.sendto(packet, (broadcast, 7))
    finally:
        udp.close()


def _pedir_pendente():
    url = URL_PENDENTE + "?token=" + TOKEN
    r = requests.get(url, timeout=10)
    try:
        return r.json()
    finally:
        r.close()


def tick(sta, mac, broadcast):
    """Chame a cada iteracao do loop principal. Age so quando a hora bate."""
    global _proxima_checagem
    if sta is None or not sta.isconnected():
        return
    agora = time.ticks_ms()
    if time.ticks_diff(agora, _proxima_checagem) < 0:
        return
    _proxima_checagem = time.ticks_add(agora, CHECAR_A_CADA_MS)
    try:
        dado = _pedir_pendente()
    except Exception as exc:
        print("RELE: falhou pedir pendente:", exc)
        return
    if not dado.get("pendente"):
        return
    print("RELE: pedido de wake recebido, enviando pacote magico")
    try:
        _enviar_pacote(mac, broadcast)
        print("RELE: pacote enviado para", mac, "em", broadcast)
    except Exception as exc:
        print("RELE: falha ao enviar WoL:", exc)


