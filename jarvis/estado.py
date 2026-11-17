"""Estado central do JARVIS.

Tudo que a interface mostra mora aqui. Quem muda alguma coisa chama
`publicar()`, e cada navegador conectado recebe o retrato completo pelo
WebSocket. Mandar o retrato inteiro (alguns KB) é mais simples e mais robusto
que mandar diferenças: um cliente que perdeu uma mensagem se corrige sozinho
na seguinte.
"""
import asyncio
import json
import time
from collections import deque
from datetime import datetime

ESTADOS_AGENTE = ("repouso", "ouvindo", "pensando", "executando", "respondendo", "erro")


def agora_iso():
    return datetime.now().isoformat(timespec="seconds")


class Painel:
    def __init__(self, nome_cerebro="simulado", incidentes=None):
        self.inicio = time.time()
        self.agente = {
            "estado": "repouso",
            "detalhe": "aguardando comando",
            "ultima_fala": "",
            "ultima_resposta": "",
            "falante": None,
            "desde": agora_iso(),
        }
        self.cerebro = {"nome": nome_cerebro, "online": True, "motivo": ""}
        self.placa = {
            "online": False,
            "ultimo_contato": None,
            "temperatura": None,
            "umidade": None,
            "movimento": None,
            "led": None,
            "led_manual": None,
            "erro": "ainda não consultada",
        }
        self.sistema = {"cpu": None, "memoria": None, "agente_energia": None}
        self.atividade = deque(maxlen=60)
        self.incidentes = incidentes
        self.clientes = set()
        self.recursos = {"luz": True, "voz": False, "microfone": False}
        self.vozes = []
        self.skills = []
        # Presença do telefone companheiro (por omissão, desconhecida).
        # Fica apenas em memória; coordenadas nunca entram no retrato.
        self.presenca_mobile = {
            "presente": None,
            "origem": "desconhecida",
            "evento": "nenhum",
            "quando": None,
            "precisao_m": None,
        }
        # Presença por aparelho companheiro (A53, iPhone, etc.).
        # Mantemos o último registro em presenca_mobile por compatibilidade.
        self.presencas_moveis = {}
        # Modo auscultação: ligado por skills.auscultacao. O cérebro lê isso
        # e troca o tom (escuta ativa, nada de solução não pedida).
        self.modo_auscultacao = False

    # ---- mudanças -------------------------------------------------------

    def mudar_agente(self, estado, detalhe=""):
        if estado not in ESTADOS_AGENTE:
            raise ValueError(f"estado desconhecido: {estado}")
        self.agente["estado"] = estado
        self.agente["detalhe"] = detalhe
        self.agente["desde"] = agora_iso()

    def registrar(self, tipo, texto):
        self.atividade.appendleft({"quando": agora_iso(), "tipo": tipo, "texto": texto})
        if self.incidentes:
            try:
                self.incidentes.registrar(tipo, texto, self.agente)
            except Exception:
                # Diagnóstico nunca pode derrubar o agente principal.
                pass

    # ---- leitura ----------------------------------------------------------

    def alertas(self):
        """Alertas são derivados do estado, não guardados.

        Assim um alerta some sozinho quando a causa some, sem ninguém ter que
        lembrar de apagá-lo.
        """
        lista = []
        p = self.placa
        if not p["online"]:
            lista.append({"nivel": "critico", "texto": f"Placa sem resposta: {p['erro']}"})
        else:
            if p["movimento"]:
                lista.append({"nivel": "atencao", "texto": "Movimento detectado"})
            if p["temperatura"] is not None and p["temperatura"] >= 32:
                lista.append({"nivel": "atencao", "texto": f"Temperatura alta: {p['temperatura']} °C"})
            if p["umidade"] is not None and p["umidade"] < 20:
                lista.append({"nivel": "atencao", "texto": f"Ar muito seco: {p['umidade']} %"})
        if not self.cerebro["online"]:
            lista.append({"nivel": "critico", "texto": f"Cérebro indisponível: {self.cerebro.get('motivo', '')}"})
        if self.sistema["agente_energia"] is False:
            lista.append({"nivel": "atencao", "texto": "Agente de energia do PC fora do ar"})
        if self.agente["estado"] == "erro":
            lista.append({"nivel": "critico", "texto": self.agente["detalhe"] or "Erro no agente"})
        return lista

    def retrato(self):
        return {
            "tipo": "estado",
            "agente": dict(self.agente),
            "cerebro": dict(self.cerebro),
            "placa": dict(self.placa),
            "sistema": {**self.sistema, "ligado_ha_s": int(time.time() - self.inicio)},
            "recursos": dict(self.recursos),
            "vozes": list(self.vozes),
            "skills": list(self.skills),
            "presenca_mobile": dict(self.presenca_mobile),
            "presencas_moveis": {k: dict(v) for k, v in self.presencas_moveis.items()},
            "modo_auscultacao": bool(self.modo_auscultacao),
            "alertas": self.alertas(),
            "atividade": list(self.atividade),
        }

    # ---- transmissão ------------------------------------------------------

    async def publicar(self):
        await self.enviar_a_todos(json.dumps(self.retrato(), ensure_ascii=False))

    async def enviar_nivel(self, valor):
        """Volume do microfone/voz, para o núcleo pulsar. Mensagem leve e frequente."""
        await self.enviar_a_todos(json.dumps({"tipo": "nivel", "valor": round(valor, 3)}))

    async def enviar_a_todos(self, texto):
        mortos = []
        for ws in list(self.clientes):
            try:
                await ws.send_text(texto)
            except Exception:
                mortos.append(ws)
        for ws in mortos:
            self.clientes.discard(ws)
        await asyncio.sleep(0)
