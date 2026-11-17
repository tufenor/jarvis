"""Mensagens autenticadas compartilhadas por Lambda, Windows e MicroPython."""
import hashlib
import json
import time
from binascii import hexlify, unhexlify


def agora_unix():
    # Algumas compilações MicroPython contam segundos desde 2000.
    return int(time.time()) + (946684800 if time.gmtime(0)[0] == 2000 else 0)


def hmac_sha256(chave, mensagem):
    chave = unhexlify(chave)
    if len(chave) != 32:
        raise ValueError("chave de integração inválida")
    chave += b"\x00" * (64 - len(chave))
    interno = bytes(c ^ 0x36 for c in chave)
    externo = bytes(c ^ 0x5c for c in chave)
    return hexlify(hashlib.sha256(externo + hashlib.sha256(
        interno + mensagem).digest()).digest()).decode()


def iguais(a, b):
    if not isinstance(a, str) or not isinstance(b, str) or len(a) != len(b):
        return False
    diferenca = 0
    for x, y in zip(a.encode(), b.encode()):
        diferenca |= x ^ y
    return diferenca == 0


def identificador(valor):
    return hexlify(hashlib.sha256(valor.encode()).digest()).decode()[:32]


def assinar(canal, chave, pedido_id, acao, texto="", estado="", agora=None, validade=90):
    corpo = json.dumps([1, pedido_id, agora_unix() if agora is None else agora,
                        validade, acao, texto, estado])
    assinatura = hmac_sha256(chave, (canal + "\n" + corpo).encode())
    return json.dumps({"corpo": corpo, "assinatura": assinatura}).encode()


def verificar(mensagem, canal, chave, acoes, agora=None):
    if not isinstance(mensagem, (str, bytes)) or len(mensagem) > 8192:
        raise ValueError("mensagem inválida")
    pacote = json.loads(mensagem)
    if not isinstance(pacote, dict):
        raise ValueError("pacote inválido")
    corpo = pacote.get("corpo")
    if not isinstance(corpo, str) or not iguais(pacote.get("assinatura"),
            hmac_sha256(chave, (canal + "\n" + corpo).encode())):
        raise ValueError("assinatura inválida")
    dados = json.loads(corpo)
    if not isinstance(dados, list) or len(dados) != 7:
        raise ValueError("formato inválido")
    versao, pedido_id, quando, validade, acao, texto, estado = dados
    if (type(versao) is not int or versao != 1 or
            not isinstance(pedido_id, str) or len(pedido_id) != 32 or
            any(c not in "0123456789abcdef" for c in pedido_id) or
            type(quando) is not int or type(validade) is not int or
            not 1 <= validade <= 120 or not isinstance(acao, str) or acao not in acoes or
            not isinstance(texto, str) or len(texto) > 1800 or
            not isinstance(estado, str) or len(estado) > 32):
        raise ValueError("conteúdo inválido")
    atual = agora_unix() if agora is None else agora
    if quando > atual + 5 or atual >= quando + validade:
        raise ValueError("mensagem expirada ou relógio incorreto")
    return {"id": pedido_id, "quando": quando, "validade": validade,
            "acao": acao, "texto": texto, "estado": estado}
