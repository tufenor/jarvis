"""Falar frase a frase enquanto o modelo ainda está gerando o resto.

Sem isto, o JARVIS espera a resposta inteira chegar, depois sintetiza tudo e
só então abre a boca — 2 a 4 s de silêncio em respostas longas. Aqui a
primeira frase já é falada enquanto a segunda está sendo escrita.
"""
import asyncio
import re

# Fim de frase: pontuação seguida de espaço e de algo que começa frase nova.
# O `[^\d]` antes da pontuação evita cortar "28.5" ou "12.42" no meio.
FIM_DE_FRASE = re.compile(r"(?<=[^\d][.!?…])\s+(?=[\"'(\[]?[A-ZÀ-ÝÇ0-9])")
MINIMO_PARA_FALAR = 12   # frases menores esperam a próxima: "Ok." sozinho soa picado


def cortar_frases(buffer, forcar=False):
    """Devolve (frases_prontas, resto_do_buffer).

    `forcar` entrega o que sobrou mesmo sem pontuação final (fim do fluxo).
    """
    partes = FIM_DE_FRASE.split(buffer)
    if forcar:
        prontas = [p.strip() for p in partes if p.strip()]
        return prontas, ""
    if len(partes) < 2:
        return [], buffer
    resto = partes[-1]
    prontas, acumulado = [], ""
    for parte in partes[:-1]:
        acumulado = (acumulado + " " + parte).strip() if acumulado else parte.strip()
        if len(acumulado) >= MINIMO_PARA_FALAR:
            prontas.append(acumulado)
            acumulado = ""
    if acumulado:
        resto = (acumulado + " " + resto).strip()
    return prontas, resto


class Narrador:
    """Recebe pedaços de texto, fala as frases completas na ordem.

    Síntese e reprodução correm numa tarefa só, em fila: enquanto uma frase
    toca, a seguinte já está sendo sintetizada pelo Piper.
    """

    def __init__(self, voz, tocar, ao_mudar_estado=None):
        self.voz = voz
        self.tocar = tocar                      # corrotina tocar(audio)
        self.ao_mudar_estado = ao_mudar_estado  # corrotina chamada antes da 1ª frase
        self.buffer = ""
        self.fila = asyncio.Queue()
        self.tarefa = None
        self.falado = []
        self.cancelado = False

    def comecar(self):
        self.tarefa = asyncio.create_task(self._consumir())

    def engolir(self, trecho):
        """Chamado a cada pedaço de texto que chega do modelo."""
        if self.cancelado:
            return
        self.buffer += trecho
        frases, self.buffer = cortar_frases(self.buffer)
        for f in frases:
            self.fila.put_nowait(f)

    async def terminar(self):
        """Fecha o fluxo: fala o que sobrou e espera acabar. Devolve o texto falado."""
        if self.cancelado:
            return " ".join(self.falado)
        frases, self.buffer = cortar_frases(self.buffer, forcar=True)
        for f in frases:
            self.fila.put_nowait(f)
        self.fila.put_nowait(None)   # sentinela de fim
        if self.tarefa:
            await self.tarefa
        return " ".join(self.falado)

    def cancelar(self):
        """Interrompido pelo usuário: joga fora o que ainda não foi falado."""
        self.cancelado = True
        self.buffer = ""
        while not self.fila.empty():
            try:
                self.fila.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.fila.put_nowait(None)

    async def _consumir(self):
        primeira = True
        while True:
            frase = await self.fila.get()
            if frase is None or self.cancelado:
                return
            audio = await asyncio.to_thread(self.voz.sintetizar, frase)
            if self.cancelado:
                return
            if primeira and self.ao_mudar_estado:
                await self.ao_mudar_estado()
                primeira = False
            self.falado.append(frase)
            await self.tocar(audio)
