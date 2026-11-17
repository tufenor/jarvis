"""Agente simulado da etapa 1.

Ainda não há cérebro nem microfone. Este simulador percorre os estados reais
(ouvindo → pensando → executando → respondendo) com os mesmos tempos e
mensagens que o agente de verdade vai produzir, para a interface poder ser
julgada agora. Na etapa 2 ele é trocado pelo agente real, com a mesma
interface pública: processar(), escutar(), cancelar().
"""
import asyncio
import math
import random

from .estado import ESTADOS_AGENTE

FPS_NIVEL = 20


class AgenteSimulado:
    def __init__(self, painel):
        self.painel = painel
        self.tarefa = None

    # ---- entrada ----------------------------------------------------------

    def processar(self, texto):
        return self._iniciar(self._processar(texto))

    def escutar(self):
        return self._iniciar(self._escutar())

    def ciclo_demonstracao(self):
        return self._iniciar(self._ciclo())

    def simular_erro(self):
        return self._iniciar(self._erro("Falha simulada: cérebro não respondeu"))

    async def cancelar(self):
        if self.tarefa and not self.tarefa.done():
            self.tarefa.cancel()
            try:
                await self.tarefa
            except asyncio.CancelledError:
                pass
        if self.painel.agente["estado"] != "repouso":
            self.painel.registrar("sistema", "Cancelado pelo usuário")
        await self._mudar("repouso", "aguardando comando")

    # ---- interno ----------------------------------------------------------

    def _iniciar(self, corrotina):
        # Um pedido novo substitui o anterior: duas falas misturadas no
        # núcleo seriam piores que interromper a primeira.
        if self.tarefa and not self.tarefa.done():
            self.tarefa.cancel()
        self.tarefa = asyncio.create_task(corrotina)
        return self.tarefa

    async def _mudar(self, estado, detalhe):
        self.painel.mudar_agente(estado, detalhe)
        await self.painel.publicar()

    async def _niveis(self, segundos, gerador):
        passos = int(segundos * FPS_NIVEL)
        for i in range(passos):
            await self.painel.enviar_nivel(gerador(i / FPS_NIVEL))
            await asyncio.sleep(1 / FPS_NIVEL)
        await self.painel.enviar_nivel(0)

    async def _escutar(self):
        await self._mudar("ouvindo", "simulação: ouvindo o microfone")
        # Fala humana: rajadas de sílabas com pausas, não ruído uniforme.
        await self._niveis(2.6, lambda t: max(0.0, math.sin(t * 9) * 0.5 + random.uniform(-0.15, 0.45)))
        await self._processar("(simulação) que horas são?")

    async def _processar(self, texto):
        self.painel.agente["ultima_fala"] = texto
        self.painel.registrar("fala", texto)
        await self._mudar("pensando", "simulação: consultando o cérebro")
        await asyncio.sleep(1.4)
        await self._mudar("executando", "simulação: nenhuma ferramenta executada")
        await asyncio.sleep(1.0)
        resposta = f"Modo simulado. Recebi: {texto}. O cérebro entra na etapa 2."
        self.painel.agente["ultima_resposta"] = resposta
        self.painel.registrar("resposta", resposta)
        await self._mudar("respondendo", "simulação: falando")
        await self._niveis(2.4, lambda t: abs(math.sin(t * 7)) * random.uniform(0.4, 1.0))
        await self._mudar("repouso", "aguardando comando")

    async def _ciclo(self):
        self.painel.registrar("sistema", "Demonstração dos estados do núcleo")
        for estado in ESTADOS_AGENTE:
            await self._mudar(estado, f"demonstração: {estado}")
            if estado in ("ouvindo", "respondendo"):
                await self._niveis(3.0, lambda t: abs(math.sin(t * 6)) * random.uniform(0.3, 1.0))
            else:
                await asyncio.sleep(3.0)
        await self._mudar("repouso", "aguardando comando")

    async def _erro(self, texto):
        self.painel.registrar("erro", texto)
        await self._mudar("erro", texto)
        await asyncio.sleep(4)
        await self._mudar("repouso", "aguardando comando")
