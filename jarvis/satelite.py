"""Satélite do JARVIS no celular (Galaxy A53).

O celular é um ponto de sentido e de voz a mais, não um usuário web: ele fala
com o JARVIS por HTTP com um **token** no cabeçalho `X-Satelite-Token`, fora
do fluxo de login do painel. O token mora em `dados/satelite_token.txt`
(gerado na primeira execução, fora do git).

O que entra pelo satélite:
- `/api/satelite/presenca`: bateria, GPS opcional, mesma política da presença
  do navegador (nunca persistida, arredondada).
- `/api/satelite/sms` e `/api/satelite/notificacao`: eventos efêmeros, apenas
  registram linha no diário do painel.
- `/api/satelite/fila`: long-poll do celular pedindo o que o JARVIS quer que
  ele faça — falar algo (TTS no próprio telefone) ou mostrar notificação.
  Não envia áudio nenhum; o conteúdo é só texto curto, para o Termux resolver.

O que sai pelo satélite (o JARVIS pedindo para o celular agir): use as
ferramentas da skill `celular` — elas empilham ordens aqui.
"""
from __future__ import annotations

import asyncio
import secrets
import time
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .estado import agora_iso


LIMITE_FILA = 50          # ordens pendentes que o celular ainda não buscou
LIMITE_TEXTO = 400        # tamanho máximo de SMS/notificação para evitar flood
LIMITE_LONGPOLL_S = 25    # quanto o /fila espera antes de voltar vazio


def carregar_ou_criar_token(caminho: Path) -> str:
    """Token estável entre reinícios. Primeira execução gera e grava."""
    caminho = Path(caminho)
    if caminho.is_file():
        texto = caminho.read_text(encoding="utf-8").strip()
        if texto:
            return texto
    token = secrets.token_urlsafe(32)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(token, encoding="utf-8")
    try:
        # Não precisa ser lido por outros usuários da máquina.
        caminho.chmod(0o600)
    except OSError:
        pass
    return token


class FilaSatelite:
    """Fila de ordens para o celular (falar/avisar).

    Thread-safe por natureza (deque + asyncio.Event). O long-poll acorda
    no primeiro `empurrar` e devolve tudo que chegou até ali.
    """

    def __init__(self, limite: int = LIMITE_FILA):
        self._itens: deque[dict] = deque(maxlen=limite)
        self._evento = asyncio.Event()

    def empurrar(self, tipo: str, dados: dict) -> dict:
        item = {"id": secrets.token_hex(6), "tipo": tipo, "quando": agora_iso(), **dados}
        self._itens.append(item)
        self._evento.set()
        return item

    async def drenar(self, espera_s: float = LIMITE_LONGPOLL_S) -> list[dict]:
        """Devolve as ordens pendentes. Se não há, espera `espera_s`."""
        if not self._itens:
            try:
                await asyncio.wait_for(self._evento.wait(), timeout=espera_s)
            except asyncio.TimeoutError:
                return []
        ordens = list(self._itens)
        self._itens.clear()
        self._evento.clear()
        return ordens

    def tamanho(self) -> int:
        return len(self._itens)


class PresencaSatelite(BaseModel):
    presente: bool | None = None
    origem: str = "a53"
    evento: str = "heartbeat"
    bateria: int | None = None
    carregando: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    precisao_m: float | None = None


class SmsSatelite(BaseModel):
    remetente: str
    texto: str
    quando: str | None = None


class NotificacaoSatelite(BaseModel):
    app: str
    titulo: str = ""
    texto: str = ""


def _normalizar_origem(origem: str | None) -> str:
    base = (origem or "a53").strip().lower().replace(" ", "-")[:40]
    return base or "a53"


def criar_router(token: str, painel, fila: FilaSatelite) -> APIRouter:
    """Monta as rotas do satélite com dependência de token.

    Fica em módulo separado para o `servidor.py` não crescer mais.
    """
    router = APIRouter(prefix="/api/satelite", tags=["satelite"])

    def exigir(cabecalho: str | None):
        if not cabecalho or not secrets.compare_digest(cabecalho, token):
            raise HTTPException(401, "token do satélite inválido")

    @router.post("/presenca")
    async def presenca(dados: PresencaSatelite,
                       x_satelite_token: str = Header(default="")):
        exigir(x_satelite_token)
        origem = _normalizar_origem(dados.origem)
        if dados.latitude is not None and not -90 <= dados.latitude <= 90:
            raise HTTPException(400, "latitude inválida")
        if dados.longitude is not None and not -180 <= dados.longitude <= 180:
            raise HTTPException(400, "longitude inválida")
        bateria = None if dados.bateria is None else max(0, min(100, int(dados.bateria)))
        precisao = (None if dados.precisao_m is None
                    else max(0.0, min(float(dados.precisao_m), 100000.0)))
        anterior = painel.presencas_moveis.get(origem, {}).get("presente")
        painel.presenca_mobile = {
            "presente": dados.presente,
            "origem": origem,
            "evento": (dados.evento or "heartbeat")[:40],
            "quando": agora_iso(),
            "precisao_m": round(precisao, 1) if precisao is not None else None,
            "bateria": bateria,
            "carregando": dados.carregando,
        }
        painel.presencas_moveis[origem] = dict(painel.presenca_mobile)
        if anterior != dados.presente:
            estado = ("presente" if dados.presente else "ausente"
                      if dados.presente is False else "indeterminada")
            painel.registrar("presença", f"{origem}: {estado}")
        await painel.publicar()
        return {"ok": True, "pendentes": fila.tamanho()}

    @router.post("/sms")
    async def sms(dados: SmsSatelite, x_satelite_token: str = Header(default="")):
        exigir(x_satelite_token)
        remetente = (dados.remetente or "")[:80].strip() or "desconhecido"
        texto = (dados.texto or "")[:LIMITE_TEXTO].strip()
        if not texto:
            raise HTTPException(400, "texto vazio")
        painel.registrar("sms", f"{remetente}: {texto}")
        await painel.publicar()
        return {"ok": True}

    @router.post("/notificacao")
    async def notificacao(dados: NotificacaoSatelite,
                          x_satelite_token: str = Header(default="")):
        exigir(x_satelite_token)
        app_nome = (dados.app or "")[:40].strip() or "app"
        titulo = (dados.titulo or "")[:120].strip()
        texto = (dados.texto or "")[:LIMITE_TEXTO].strip()
        descricao = " · ".join(p for p in [titulo, texto] if p) or "(sem texto)"
        painel.registrar("celular", f"{app_nome}: {descricao}")
        await painel.publicar()
        return {"ok": True}

    @router.get("/fila")
    async def obter_fila(x_satelite_token: str = Header(default="")):
        exigir(x_satelite_token)
        ordens = await fila.drenar()
        return {"ordens": ordens, "quando": agora_iso()}

    @router.get("/ping")
    async def ping(x_satelite_token: str = Header(default="")):
        exigir(x_satelite_token)
        return {"ok": True, "quando": agora_iso(), "pendentes": fila.tamanho()}

    return router


class PonteCelular:
    """Portal que a skill `celular` usa para empurrar ordens."""

    def __init__(self, fila: FilaSatelite):
        self.fila = fila

    def falar(self, texto: str) -> dict:
        texto = (texto or "").strip()[:LIMITE_TEXTO]
        if not texto:
            raise ValueError("texto vazio")
        return self.fila.empurrar("falar", {"texto": texto})

    def avisar(self, titulo: str, texto: str = "") -> dict:
        titulo = (titulo or "").strip()[:120]
        texto = (texto or "").strip()[:LIMITE_TEXTO]
        if not titulo:
            raise ValueError("título vazio")
        return self.fila.empurrar("avisar", {"titulo": titulo, "texto": texto})
