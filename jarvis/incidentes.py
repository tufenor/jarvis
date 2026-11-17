"""Registro local de falhas para revisão do JARVIS.

O arquivo fica em ``C:\\JARVIS\\dados`` (fora do git). Ele serve como ponte de
diagnóstico: o JARVIS registra o que aconteceu e o Codex pode ler o último
incidente quando o usuário abrir o projeto novamente.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path


_SEGREDO = re.compile(
    r"(?i)\b(?:senha|password|token|api[_ -]?key|authorization|bearer)\b"
    r"\s*[:=]?\s*[^\s,;]+"
)

_FALHAS_ENTENDIMENTO = (
    "não entendi", "nao entendi", "não reconheci", "nao reconheci",
    "me perdi", "frase ficou misturada", "não ficou claro", "nao ficou claro",
)
_FALHAS_EXECUCAO = (
    "não consegui", "nao consegui", "não foi possível", "nao foi possivel",
    "falhou", "erro", "indisponível", "indisponivel", "não respondeu",
    "nao respondeu",
)


def _limpar(valor):
    texto = "" if valor is None else str(valor)
    return _SEGREDO.sub("[REDACTED]", texto)[:1000]


class Incidentes:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self._lock = threading.Lock()

    @staticmethod
    def deve_registrar(tipo, texto):
        if tipo == "erro":
            return True
        if tipo not in {"resposta", "sistema"}:
            return False
        return Incidentes.categoria_de(tipo, texto) != "observacao"

    @staticmethod
    def categoria_de(tipo, texto):
        """Classifica o incidente para a revisão automática do JARVIS."""
        if tipo == "erro":
            return "execucao"
        normalizado = str(texto).casefold()
        if any(chave in normalizado for chave in _FALHAS_ENTENDIMENTO):
            return "entendimento"
        if any(chave in normalizado for chave in _FALHAS_EXECUCAO):
            return "execucao"
        return "observacao"

    def registrar(self, tipo, texto, estado=None):
        if not self.deve_registrar(tipo, texto):
            return None
        estado = estado or {}
        evento = {
            "quando": datetime.now().isoformat(timespec="seconds"),
            "tipo": _limpar(tipo),
            "categoria": _limpar(self.categoria_de(tipo, texto)),
            "mensagem": _limpar(texto),
            "estado": _limpar(estado.get("estado")),
            "detalhe": _limpar(estado.get("detalhe")),
            "ultima_fala": _limpar(estado.get("ultima_fala")),
            "ultima_resposta": _limpar(estado.get("ultima_resposta")),
            "falante": _limpar(estado.get("falante")),
        }
        with self._lock:
            self.caminho.parent.mkdir(parents=True, exist_ok=True)
            with self.caminho.open("a", encoding="utf-8") as arquivo:
                arquivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
        return evento

    def ultimos(self, limite=20):
        try:
            linhas = self.caminho.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        eventos = []
        for linha in reversed(linhas):
            try:
                item = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                eventos.append(item)
            if len(eventos) >= max(1, min(int(limite), 100)):
                break
        return eventos
