"""O agente: recebe um pedido, consulta o cérebro, executa ferramentas, responde.

Três garantias que importam mais que esperteza:

1. Nada fora da lista de ferramentas roda, e argumento inválido não roda.
2. Ação perigosa só roda depois de um "sim" explícito do usuário.
3. Resposta fora do formato vira "não entendi", nunca um chute.
"""
import asyncio
import re
import threading
import time
import unicodedata
from contextvars import ContextVar

from . import dizeres
from .cerebro import Chamada, Resultado
from .ferramentas import ErroFerramenta, validar
from .narrador import Narrador
from .simulador import AgenteSimulado

ORIGEM_PEDIDO = ContextVar("origem_pedido", default="local")

MAX_RODADAS = 5            # cérebro ↔ ferramentas por pedido; evita laço infinito
VALIDADE_CONFIRMACAO_S = 60
CONVERSA_ESQUECE_APOS_S = 300

PALAVRAS_SIM = {"sim", "confirmo", "confirma", "confirmado", "pode", "claro", "isso", "manda", "positivo", "ok"}
PALAVRAS_NAO = {"nao", "nem", "negativo", "nunca"}

NAO_ENTENDI = "Não entendi o pedido com segurança. Pode repetir de outro jeito?"
# Para variação: usar `dizeres.escolher('nao_entendi')`. A constante fica para
# compatibilidade com testes antigos que comparam a string exata.

# Ferramentas que põem alguma coisa na tela: o que foi aberto fica na tela de
# chamada e o JARVIS se recolhe para a outra, para não tampar o que o usuário pediu.
ABREM_NA_TELA = {"abrir_programa", "abrir_site", "pesquisar_na_web", "abrir_arquivo",
                 "tocar_no_youtube", "abrir_do_drive", "capturar_tela"}

CONVERSA_ABERTA_S = 30   # conversa segue aberta (sem repetir "Jarvis") até esse silêncio
DIARIO_ESCUTA_S = 300    # modo diário: até cinco minutos entre trechos

ENCERRAR = re.compile(r"\b(obrigad[oa]|pode ir|dispensado|tchau|valeu|so isso|e so isso|encerra(r)? (a )?conversa)\b")
DIARIO_INICIAR = re.compile(r"\b(?:iniciar|abrir|comecar|comeca|modo|fazer|escrever|anotar)\s+(?:o\s+)?diario\b|\bdiario\s+(?:aberto|ligado)\b")
DIARIO_ENCERRAR = re.compile(r"\b(?:encerrar|fechar|terminar|parar|salvar|concluir)\s+(?:o\s+)?diario\b|\bdiario\s+(?:encerrado|fechado|terminado)\b")
APRENDER_VOZ = re.compile(r"\b(aprend[ea]|cadastr[ae]|grav[ae]|memoriz[ae]|conhec[ae])\b.*\bvoz\b")
ESQUECER_VOZ = re.compile(r"\b(esquec[ea]|apag[ae]|remov[ae]|delet[ae])\b.*\bvoz\b")
QUEM_SOU = re.compile(r"\bquem (sou eu|e que esta falando|esta falando|ta falando|fala)\b")
CANCELAR = re.compile(r"^\W*(cancela|cancelar|deixa pra la|esquece)\b")


def extrair_nome(texto):
    """'Meu nome é Ana Souza.' -> 'Ana Souza'."""
    t = re.sub(r"(?i)^\W*(o )?(meu nome (e|é)|eu sou o?a?|eu me chamo|me chamo|sou o?a?|pode me chamar de)\s+",
               "", texto.strip())
    palavras = re.findall(r"[A-Za-zÀ-ÿ]+", t)[:3]
    return " ".join(p.capitalize() for p in palavras)

# Troca de tela é comando de reflexo: resolvido aqui, sem gastar uma ida ao cérebro.
COMANDOS_TELA = [
    (re.compile(r"\b(primeira|principal)\b.*\btela\b|\btela (1|um|principal)\b"), "primeira"),
    (re.compile(r"\bsegunda\b.*\btela\b|\btela (2|dois)\b"), "segunda"),
    (re.compile(r"\bchega (pra|para) (la|o lado)\b|\bsai da frente\b|\b(muda|mude|troca|troque|passa|passe|vai|joga)\b.*\btela\b|\boutra tela\b"), "outra"),
]

# Só frases curtas e sem ambiguidade entram aqui. Recursos que ainda não têm
# ferramenta (como timer e volume) continuam no caminho normal do cérebro.
COMANDOS_RAPIDOS = [
    (re.compile(
        r"(?:que horas sao(?: agora)?|que hora e(?: agora)?|"
        r"qual (?:e )?a hora(?: agora)?|hora (?:atual|agora)|horario (?:atual|agora)|"
        r"me (?:diga|diz|fala|fale) (?:que horas sao|a hora)|"
        r"que dia (?:e )?hoje|qual (?:e )?a data(?: de hoje)?|data de hoje)"
    ), "hora_e_data"),
    (re.compile(
        r"(?:(?:qual|como|quanto|quanta)(?: (?:e|esta|ta|anda))? (?:a )?"
        r"(?:temperatura|umidade|movimento)(?: (?:do quarto|no quarto|aqui|agora|atual))?|"
        r"(?:me )?(?:diz|diga|fala|fale|ve|veja|verifica|verificar|consulta|consultar|"
        r"leia|ler|mostra|mostrar) (?:os )?(?:sensores?|(?:a )?(?:temperatura|umidade|movimento))|"
        r"(?:temperatura|umidade|movimento)(?: (?:do quarto|no quarto|aqui|agora|atual))?|"
        r"sensores?)"
    ), "ler_sensores"),
]


def comando_de_tela(texto):
    limpo = sem_acento(texto.lower())
    for padrao, qual in COMANDOS_TELA:
        if padrao.search(limpo):
            return qual
    return None


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def comando_rapido(texto):
    """Reconhece apenas consultas curtas atendidas por ferramentas existentes."""
    limpo = sem_acento(texto.lower()).strip()
    # Pelo /api/comando o texto chega inteiro ("jarvis, que horas são?"); pela
    # voz já vem só o pedido. Aqui descasco o chamado se ele vier junto.
    limpo = re.sub(r"^(?:ei\s+|oi\s+|ola\s+)?jarvis[\s,:.-]+", "", limpo)
    limpo = re.sub(r"[\s?!.,;:]+$", "", limpo).strip()
    for padrao, ferramenta in COMANDOS_RAPIDOS:
        if padrao.fullmatch(limpo):
            return ferramenta
    return None


def mesma_fala(falado, texto):
    """Compara ignorando espaços: o narrador junta as frases com um espaço só."""
    arruma = lambda t: re.sub(r"\s+", " ", t).strip()
    return arruma(falado) == arruma(texto)


def eh_confirmacao(texto):
    palavras = sem_acento(texto.lower()).replace(",", " ").replace(".", " ").replace("!", " ").split()
    if not palavras or "nao" in palavras:
        return False
    return palavras[0] in PALAVRAS_SIM


def resposta_sim_nao(texto):
    """Interpreta uma resposta curta sem mandar uma pergunta binária ao cérebro."""
    palavras = sem_acento(texto.lower()).replace(",", " ").replace(".", " ").split()
    if not palavras:
        return None
    if any(palavra in PALAVRAS_NAO for palavra in palavras):
        return False
    if any(palavra in PALAVRAS_SIM or palavra in {"quero", "aceito"} for palavra in palavras):
        return True
    return None


class Agente(AgenteSimulado):
    def __init__(self, painel, cerebro, ferramentas, voz=None, ouvinte=None, janela=None,
                 conversa_s=CONVERSA_ABERTA_S, skills=None, exigir_voz_conhecida=False,
                 memoria=None, diario=None, diario_s=DIARIO_ESCUTA_S,
                 exigir_chamado_a_cada_frase=False):
        super().__init__(painel)
        self.cerebro = cerebro
        self.ferramentas = ferramentas
        self.voz = voz
        self.ouvinte = ouvinte
        self.janela = janela
        self.skills = skills
        self.memoria = memoria
        self.diario = diario
        self.diario_s = max(30.0, float(diario_s))
        self.diario_sessao = None
        self.locutores = getattr(ouvinte, "locutores", None)
        self.conversa_s = conversa_s
        # Com vozes cadastradas, conversa entre pessoas (e TV) deixa de virar pedido.
        self.exigir_voz_conhecida = exigir_voz_conhecida
        # Em ambientes com TV, Alexa ou eco, cada frase normal precisa começar
        # por "Jarvis". Diário e confirmações continuam sendo fluxos locais.
        self.exigir_chamado_a_cada_frase = bool(exigir_chamado_a_cada_frase)
        self.pendente = None
        self.ultimo_pedido = 0.0
        # Conversa aberta: depois do primeiro "Jarvis", o microfone segue valendo
        # sem repetir o nome até ficar `conversa_s` em silêncio. "dono" é quem
        # chamou: se a voz dele é conhecida, só ele continua a conversa.
        self.conversa = None
        self.falante_atual = None
        self.cadastro = None
        self.pergunta_ativa = None
        self.ultima_atividade = time.monotonic()
        # Nome da ferramenta em execução. Enquanto houver uma, um pedido novo
        # NÃO cancela: uma instalação morta no meio deixa o PC em meio-termo.
        self.executando = None
        self.loop = None
        self.audio_chamado = None
        self.audio_bip = None
        self.narrador = None

    # ---- voz: ligação com as threads do microfone ----------------------------

    def ligar_voz(self, loop):
        """Chamado dentro do loop do servidor: liga o microfone às corrotinas."""
        self.loop = loop
        self.painel.vozes = self.locutores.nomes() if self.locutores else []
        if self.ouvinte:
            self.ouvinte.ao_texto = lambda t, a=None, f=None: loop.call_soon_threadsafe(
                self._ao_ouvir_na_thread, t, a, f)
            self.ouvinte.ao_nivel = self._nivel_do_microfone
            self.ouvinte.ao_interromper = lambda: loop.call_soon_threadsafe(self._interrompido)
        asyncio.ensure_future(self._preparar_voz())

    async def _preparar_voz(self):
        if self.voz:
            # Pré-sintetiza a resposta ao chamado: ela precisa sair na hora.
            # Pré-sintetiza a resposta ao chamado: ela precisa sair na hora.
            # O audio_chamado é só um dos jeitos de dizer "sim" — o fluxo
            # normal usa `dizeres.escolher('atender_chamado')` por voz.
            self.audio_chamado = await asyncio.to_thread(self.voz.sintetizar, "Pois não, senhor?")
            from .fala import bip
            self.audio_bip = bip(self.voz.sr)
        if self.ouvinte:
            self.ouvinte.iniciar()

    def _ao_ouvir_na_thread(self, texto, audio=None, falante=None):
        asyncio.ensure_future(self.ao_ouvir(texto, audio, falante))

    def _nivel_do_microfone(self, valor):
        # Só interessa ao núcleo enquanto ele está de fato ouvindo.
        if self.loop and self.painel.agente["estado"] == "ouvindo":
            asyncio.run_coroutine_threadsafe(self.painel.enviar_nivel(valor), self.loop)

    def _interrompido(self):
        if self.voz:
            self.voz.parar()
        if self.narrador:
            self.narrador.cancelar()
        self.painel.registrar("sistema", "Interrompido: você começou a falar")
        self._renovar_conversa()

    # ---- conversa ------------------------------------------------------------------

    def conversa_ativa(self):
        return bool(self.conversa) and time.monotonic() < self.conversa["ate"]

    def _renovar_conversa(self, dono=None):
        dono = dono or (self.conversa or {}).get("dono")
        duracao = self.diario_s if self.diario_sessao is not None else self.conversa_s
        self.conversa = {"dono": dono, "ate": time.monotonic() + duracao}

    async def _fechar_conversa_quando_parada(self):
        while self.conversa_ativa():
            await asyncio.sleep(max(0.2, self.conversa["ate"] - time.monotonic()))
        if self.diario_sessao:
            await self._encerrar_diario("tempo de escuta encerrado")
            return
        if self.conversa and self.painel.agente["estado"] == "ouvindo":
            self.conversa = None
            await self._mudar("repouso", "aguardando comando")

    async def _ouvindo_em_conversa(self):
        detalhe = ("aguardando novo chamado — diga Jarvis novamente"
                   if self.exigir_chamado_a_cada_frase
                   else "conversa aberta — pode falar sem dizer Jarvis")
        await self._mudar("ouvindo", detalhe)
        asyncio.ensure_future(self._fechar_conversa_quando_parada())

    async def _tratar_bloqueio(self, texto, falante=None):
        """Enquanto o overlay está ativo, somente a frase fixa pode liberar.

        Todo o restante é descartado antes de conversa, confirmação, skill ou
        cérebro. Assim uma fala captada na tela de bloqueio nunca vira comando.
        """
        if not self.janela or not getattr(self.janela, "bloqueada", False):
            return False
        from .ouvinte import separar_chamado
        chamou, pedido = separar_chamado(texto)
        voz_confere = getattr(self.janela, "voz_de_liberacao_confere", lambda _: True)
        if (chamou and self.janela.frase_de_liberacao_confere(pedido)
                and voz_confere(falante)):
            if await asyncio.to_thread(self.janela.desbloquear):
                await self._responder("Tela do JARVIS liberada.")
        return True

    async def ao_ouvir(self, texto, audio=None, falante=None):
        from .ouvinte import separar_chamado
        if await self._tratar_bloqueio(texto, falante):
            return
        # Fluxos locais (por exemplo a pergunta de boas-vindas) aceitam apenas
        # sim/não e não exigem a palavra "Jarvis". Fala que não é resposta
        # binária fica fora do agente e o temporizador continua correndo.
        if self.pergunta_ativa and not self.pergunta_ativa.done():
            if resposta_sim_nao(texto) is not None:
                self.pergunta_ativa.set_result(texto.strip())
            return
        chamou, pedido = separar_chamado(texto)
        vozes_cadastradas = bool(self.locutores and self.locutores.nomes())
        if (self.exigir_voz_conhecida and vozes_cadastradas
                and falante is None and not self.cadastro):
            self.painel.registrar(
                "sistema",
                "Fala ignorada: voz não cadastrada (possível TV, Alexa, vídeo ou eco do JARVIS)"
            )
            return
        if (self.exigir_chamado_a_cada_frase and not chamou and not self.pendente
                and not self.cadastro and not self.diario_sessao):
            self.conversa = None
            self.painel.registrar(
                "sistema",
                "Fala ignorada: novo chamado 'Jarvis' necessário (proteção contra áudio ambiente)"
            )
            return
        if self.executando and not CANCELAR.search(sem_acento(texto.lower())):
            # Ocupado: ignora o que chegou em vez de matar a ação pela metade.
            self.painel.registrar(
                "sistema", f"Ignorei '{texto[:40]}': {self.executando} ainda está rodando")
            return
        aberta = self.conversa_ativa() or self.pendente or self.cadastro or self.diario_sessao
        if not chamou:
            if not aberta:
                return  # conversa da sala, TV, etc.: não é com o JARVIS
            dono = (self.conversa or {}).get("dono")
            if dono and falante and falante != dono and not self.cadastro:
                return  # outra pessoa conhecida falando: a conversa é de quem chamou
            if (self.exigir_voz_conhecida and not self.cadastro
                    and self.locutores and self.locutores.nomes() and falante is None):
                return  # voz que não conheço sem dizer o nome: TV, visita, conversa alheia
            pedido = texto.strip()
        self.ultima_atividade = time.monotonic()
        self.falante_atual = falante
        self.painel.agente["falante"] = falante
        self._renovar_conversa(falante if chamou else None)
        if chamou and self.janela:
            await asyncio.to_thread(self.janela.chamar)

        if self.cadastro:
            await self._passo_cadastro(pedido, audio)
            return
        if self.diario_sessao is not None:
            if DIARIO_ENCERRAR.search(sem_acento(pedido.lower())):
                await self._encerrar_diario("comando do usuário")
                return
            if pedido.strip():
                self.diario_sessao["trechos"].append(pedido.strip())
                self._renovar_conversa(falante if chamou else None)
                self.painel.registrar("diario", f"Trecho recebido ({len(pedido.strip())} caracteres)")
            return
        if ENCERRAR.search(sem_acento(pedido.lower())) and len(pedido.split()) <= 5:
            self.conversa = None
            await self._responder(dizeres.escolher("encerrar"))
            return
        if not pedido:
            await self._esperar_pedido()
            return
        self.processar(pedido)

    async def _esperar_pedido(self):
        if not self.conversa_ativa():
            self._renovar_conversa()
        await self._mudar("ouvindo", "pode falar")
        if self.voz and self.audio_chamado is not None:
            await self._tocar(self.audio_chamado)
        await self._ouvindo_em_conversa()

    async def _tocar(self, audio):
        def nivel(v):
            asyncio.run_coroutine_threadsafe(self.painel.enviar_nivel(v), self.loop)
        if self.ouvinte:
            self.ouvinte.silenciar(True)
        try:
            referencia = self.ouvinte.eco.registrar_referencia if self.ouvinte else None
            await asyncio.to_thread(self.voz.tocar, audio, nivel, referencia)
        finally:
            if self.ouvinte:
                await asyncio.to_thread(self.ouvinte.silenciar, False)

    # ---- vozes conhecidas ------------------------------------------------------------

    async def _comando_de_voz(self, texto):
        """Cadastro, esquecimento e 'quem sou eu'. Devolve True se tratou."""
        limpo = sem_acento(texto.lower())
        if APRENDER_VOZ.search(limpo):
            if not self.locutores or not self.ouvinte:
                await self._responder("O cadastro de voz só funciona com o microfone ligado.")
            else:
                self.cadastro = {"etapa": "nome", "nome": None, "audios": []}
                await self._responder("Claro. Qual é o seu nome?")
            return True
        if ESQUECER_VOZ.search(limpo):
            if self.locutores and self.falante_atual and self.locutores.esquecer(self.falante_atual):
                self.painel.vozes = self.locutores.nomes()
                self.painel.registrar("sistema", f"Voz de {self.falante_atual} apagada")
                await self._responder(f"Pronto, esqueci a voz de {self.falante_atual}.")
            else:
                await self._responder("Não reconheci sua voz, então não há nada para esquecer.")
            return True
        if QUEM_SOU.search(limpo):
            if self.falante_atual:
                await self._responder(f"Pela voz, é {self.falante_atual}.")
            else:
                await self._responder("Não reconheço essa voz. Diga: Jarvis, aprende minha voz.")
            return True
        return False

    async def _comando_de_diario(self, texto):
        """Abre o modo de ditado prolongado, sem enviar cada trecho ao cérebro."""
        if not self.diario or not DIARIO_INICIAR.search(sem_acento(texto.lower())):
            return False
        self.diario_sessao = {"inicio": time.time(), "trechos": []}
        self._renovar_conversa(self.falante_atual)
        self.painel.registrar("diario", f"Sessão aberta por até {self.diario_s:.0f} s")
        await self._responder(
            f"Diário aberto. Pode falar; tenho até {int(self.diario_s // 60)} minutos de escuta. "
            "Diga encerrar diário quando terminar."
        )
        return True

    async def _encerrar_diario(self, motivo):
        sessao, self.diario_sessao = self.diario_sessao, None
        self.conversa = None
        if not sessao or not sessao["trechos"]:
            self.painel.registrar("diario", f"Sessão encerrada sem texto ({motivo})")
            await self._responder("Não gravei nada no diário porque não recebi texto.")
            return
        try:
            arquivo = await asyncio.to_thread(self.diario.gravar, sessao["trechos"], sessao["inicio"])
        except Exception as exc:
            self.painel.registrar("erro", f"Diário não foi salvo: {type(exc).__name__}")
            await self._responder("Não consegui salvar o diário local.")
            return
        self.painel.registrar("diario", f"Sessão salva em {arquivo.name} ({motivo})")
        await self._responder("Pronto. Salvei esta sessão no seu diário local.")

    async def _passo_cadastro(self, texto, audio):
        c = self.cadastro
        if CANCELAR.search(sem_acento(texto.lower())):
            self.cadastro = None
            await self._responder("Cadastro cancelado.")
            return
        if c["etapa"] == "nome":
            nome = extrair_nome(texto)
            if not nome:
                await self._responder("Não entendi o nome. Pode repetir?")
                return
            c.update(etapa="frases", nome=nome)
            if audio is not None and len(audio) >= 16000:
                c["audios"].append(audio)
            await self._responder(f"Prazer, {nome}. Agora diga três frases quaisquer, uma de cada vez.")
            return
        if audio is None or len(audio) < 16000:
            await self._responder("Fale um pouco mais longo, por favor.")
            return
        c["audios"].append(audio)
        faltam = 4 - len(c["audios"])
        if faltam > 0:
            await self._responder("Mais uma." if faltam == 1 else "Ótimo. Outra frase.")
            return
        await asyncio.to_thread(self.locutores.cadastrar, c["nome"], c["audios"])
        self.cadastro = None
        self.falante_atual = c["nome"]
        self.painel.vozes = self.locutores.nomes()
        self.painel.registrar("sistema", f"Voz de {c['nome']} cadastrada")
        await self._responder(f"Pronto, {c['nome']}. A partir de agora reconheço a sua voz.")

    async def preparar_cerebro(self):
        """Confere e aquece: a primeira pergunta do dia não paga o custo de abrir tudo."""
        if not await self.verificar_cerebro():
            return
        try:
            inicio = time.monotonic()
            await self.cerebro.aquecer()
            self.painel.registrar("sistema", f"Cérebro aquecido em {time.monotonic() - inicio:.1f} s")
        except Exception as exc:
            # Aquecer é otimização: falhar aqui não pode impedir o JARVIS de subir.
            self.painel.registrar("sistema", f"Não deu para aquecer o cérebro: {type(exc).__name__}")

    async def verificar_cerebro(self):
        ok, motivo = await self.cerebro.disponivel()
        self.painel.cerebro.update(nome=self.cerebro.nome, online=ok, motivo=motivo)
        if not ok:
            self.painel.registrar("erro", f"Cérebro indisponível: {motivo}")
        await self.painel.publicar()
        return ok

    async def cancelar(self):
        if self.voz:
            self.voz.parar()
        self.conversa = None
        self.cadastro = None
        if self.pergunta_ativa and not self.pergunta_ativa.done():
            self.pergunta_ativa.cancel()
        self.pergunta_ativa = None
        if self.pendente:
            self.cerebro.desfazer(self.pendente["marca"])
            self.pendente = None
        # Fecha o narrador aqui também: no shutdown do app, super().cancelar()
        # não é suficiente — o loop asyncio é destruído com a tarefa viva, e
        # o log fica com "Task was destroyed but it is pending".
        if self.narrador:
            self.narrador.cancelar()
            try:
                if self.narrador.tarefa:
                    await self.narrador.tarefa
            except (asyncio.CancelledError, Exception):
                pass
            self.narrador = None
        await super().cancelar()

    async def perguntar_sim_nao(self, pergunta, timeout_s=5):
        """Fala uma pergunta curta e espera sim/não sem consultar o cérebro.

        É usado apenas por rotinas locais iniciadas pelo próprio aplicativo.
        A resposta não é senha, não é gravada e expira automaticamente.
        """
        if not self.voz or not self.ouvinte or self.loop is None:
            return None
        if self.pergunta_ativa is not None:
            return None
        futuro = self.loop.create_future()
        self.pergunta_ativa = futuro
        self.painel.registrar("sistema", f"Pergunta local: {pergunta}")
        try:
            await self._responder(pergunta, detalhe_final="aguardando resposta")
            try:
                return await asyncio.wait_for(futuro, timeout=float(timeout_s))
            except asyncio.TimeoutError:
                self.painel.registrar("sistema", "Pergunta local expirou sem resposta")
                return None
        finally:
            if self.pergunta_ativa is futuro:
                self.pergunta_ativa = None

    async def _escutar(self):
        # Botão MIC = o mesmo que dizer "Jarvis" sozinho.
        if self.ouvinte:
            await self._esperar_pedido()
            return
        self.painel.registrar("sistema", "Microfone desligado neste modo; use a barra de comando.")
        await self._mudar("repouso", "microfone desligado — use a barra de comando")

    # ---- pedido ----------------------------------------------------------

    def _confirmar_escuta(self):
        """Toque imediato de "ouvi": a espera pelo modelo deixa de parecer travada."""
        if ORIGEM_PEDIDO.get() == "local" and self.voz and self.audio_bip is not None:
            threading.Thread(target=self.voz.tocar_paralelo, args=(self.audio_bip,), daemon=True).start()

    def _iniciar(self, corrotina):
        # Pedido novo: o narrador do anterior não pode ficar esperando texto que
        # nunca vem ("Task was destroyed but it is pending" aparecia no log).
        if self.narrador:
            self.narrador.cancelar()
            self.narrador = None
        return super()._iniciar(corrotina)

    async def _processar(self, texto):
        try:
            await self._processar_pedido(texto)
        finally:
            # Há caminhos que saem sem passar por _responder (não entendi,
            # permissão negada, passo vazio). Nenhum pode vazar tarefa.
            await self._fechar_narrador()

    async def _processar_pedido(self, texto):
        self.painel.agente["ultima_fala"] = texto
        self.painel.registrar("fala", texto)
        self._confirmar_escuta()

        if self.pendente and time.monotonic() - self.pendente["quando"] > VALIDADE_CONFIRMACAO_S:
            self.cerebro.desfazer(self.pendente["marca"])
            self.pendente = None
            self.painel.registrar("sistema", "Confirmação expirou; nada foi feito")

        if self.pendente:
            if self.pendente.get("origem", "local") != ORIGEM_PEDIDO.get():
                await self._responder("Confirme ou cancele o pedido no mesmo canal em que ele foi feito.")
                return
            await self._resolver_confirmacao(texto)
            return

        if await self._comando_de_voz(texto):
            return

        if await self._comando_de_diario(texto):
            return

        qual = comando_de_tela(texto) if self.janela else None
        if qual:
            inicio = time.monotonic()
            numero = await asyncio.to_thread(self.janela.mudar, qual)
            self.painel.registrar("acao", f"Janela para a tela {numero}")
            self.painel.registrar(
                "sistema", f"Atalho local mudar_tela em {time.monotonic() - inicio:.3f} s"
            )
            await self._responder("Pronto.")
            return

        nome_rapido = comando_rapido(texto)
        if nome_rapido and nome_rapido in self.ferramentas:
            ferramenta = self.ferramentas[nome_rapido]
            if ferramenta.resposta_pronta:
                chamada = Chamada("atalho-local", nome_rapido, {})
                invalida = self._primeira_chamada_invalida([chamada])
                if invalida:
                    self.painel.registrar("erro", f"Atalho recusado: {invalida}")
                    await self._responder(dizeres.escolher('nao_entendi'))
                    return
                self.ultimo_pedido = time.monotonic()
                inicio = time.monotonic()
                try:
                    resultados = await self._executar([chamada])
                    resposta = self._resposta_pronta(resultados)
                    if resposta is None:
                        resposta = self._frase_direta_dos_resultados(resultados)
                    self.painel.registrar(
                        "sistema", f"Atalho local {nome_rapido} em {time.monotonic() - inicio:.3f} s"
                    )
                    await self._responder(resposta)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await self._falha(exc)
                return

        # Cérebro fora (sem chave, sem internet, Ollama parado): dizer o motivo
        # é mais útil que um erro genérico depois de esperar o timeout.
        if not self.painel.cerebro.get("online", True):
            await self._mudar("pensando", f"verificando {self.cerebro.nome}")
            if not await self.verificar_cerebro():
                await self._responder(f"Estou sem cérebro agora: {self.painel.cerebro['motivo']}.")
                return

        if time.monotonic() - self.ultimo_pedido > CONVERSA_ESQUECE_APOS_S or self.cerebro.cheio():
            self.cerebro.novo_dialogo()
        self.ultimo_pedido = time.monotonic()
        if self.memoria or getattr(self.painel, "modo_auscultacao", False):
            extras = []
            if self.memoria:
                resumo = self.memoria.resumo_para_prompt()
                if resumo:
                    extras.append(resumo)
            if getattr(self.painel, "modo_auscultacao", False):
                extras.append("ESTADO: modo_auscultacao: true (siga a sessao AUSCULTACAO das instrucoes).")
            if hasattr(self.cerebro, "definir_contexto"):
                self.cerebro.definir_contexto("\n\n".join(extras))

        marca = self.cerebro.marcar()
        try:
            await self._mudar("pensando", f"consultando {self.cerebro.nome}")
            # O nome de quem fala vai junto: o modelo pode tratar cada um pelo nome.
            entrada = f"[{self.falante_atual}] {texto}" if self.falante_atual else texto
            passo = await self._consultar(self.cerebro.falar(entrada, self._abrir_narrador()))
            await self._rodadas(passo, marca)
        except asyncio.CancelledError:
            # Interrompido no meio: o histórico não pode ficar com pergunta sem resposta.
            self.cerebro.desfazer(marca)
            raise
        except Exception as exc:
            self.cerebro.desfazer(marca)
            await self._falha(exc)

    async def _consultar(self, corrotina):
        inicio = time.monotonic()
        passo = await corrotina
        self.painel.registrar("cerebro", f"{self.cerebro.nome} respondeu em {time.monotonic() - inicio:.1f} s")
        return passo

    async def _rodadas(self, passo, marca):
        for _ in range(MAX_RODADAS):
            if passo is None:
                return
            if passo.problema:
                self.cerebro.desfazer(marca)
                self.painel.registrar("erro", f"Resposta fora do formato: {passo.problema}")
                await self._responder(dizeres.escolher('nao_entendi'))
                return
            if not passo.chamadas:
                await self._responder(passo.texto)
                return

            invalida = self._primeira_chamada_invalida(passo.chamadas)
            if invalida:
                self.cerebro.desfazer(marca)
                self.painel.registrar("erro", f"Chamada recusada: {invalida}")
                await self._responder(dizeres.escolher('nao_entendi'))
                return

            bloqueio = self._bloqueio_de_permissao(passo.chamadas)
            if bloqueio:
                self.cerebro.desfazer(marca)
                self.painel.registrar("sistema", bloqueio)
                await self._responder(bloqueio)
                return

            perigosas = [c for c in passo.chamadas if self.ferramentas[c.nome].perigosa]
            if perigosas:
                self.pendente = {"chamadas": passo.chamadas, "marca": marca,
                                 "quando": time.monotonic(), "origem": ORIGEM_PEDIDO.get()}
                pergunta = await self.ferramentas[perigosas[0].nome].perguntar(perigosas[0].argumentos)
                self.painel.registrar("sistema", f"Aguardando confirmação: {perigosas[0].nome}")
                await self._responder(pergunta + " Diga sim ou não.", detalhe_final="aguardando confirmação")
                return

            resultados = await self._executar(passo.chamadas)
            resposta = self._resposta_pronta(resultados)
            if resposta is not None:
                # Fecha o turno com o resultado e a fala: histórico válido (todo
                # tool_use tem seu tool_result) e o contexto do pedido preservado.
                self.cerebro.fechar_turno(resultados, resposta)
                self.painel.registrar("sistema", "Ferramenta respondeu sem nova consulta ao cérebro")
                await self._responder(resposta)
                return
            await self._mudar("pensando", f"consultando {self.cerebro.nome}")
            passo = await self._consultar(self.cerebro.devolver(resultados, self._abrir_narrador()))

        self.cerebro.desfazer(marca)
        self.painel.registrar("erro", "Muitas rodadas de ferramentas; parei por segurança")
        await self._responder("Me perdi nesse pedido. Pode repetir mais simples?")

    def _primeira_chamada_invalida(self, chamadas):
        for c in chamadas:
            if c.nome not in self.ferramentas:
                return f"ferramenta inexistente '{c.nome}'"
            erro = validar(self.ferramentas[c.nome], c.argumentos)
            if erro:
                return f"{c.nome}: {erro}"
        return None

    def _bloqueio_de_permissao(self, chamadas):
        """Skill restrita a certas vozes: recusa com motivo, em vez de "não entendi"."""
        if not self.skills:
            return None
        for c in chamadas:
            skill = self.skills.dona_da_ferramenta(c.nome)
            if skill and not skill.pode_usar(self.falante_atual):
                quem = self.falante_atual or "uma voz que não reconheço"
                return f"A skill {skill.nome} não está liberada para {quem}."
        return None

    def _resposta_pronta(self, resultados):
        if not resultados or any(
            r.erro or not self.ferramentas[r.chamada.nome].resposta_pronta for r in resultados
        ):
            return None
        frases = [r.texto.strip() for r in resultados if r.texto.strip()]
        return " ".join(frases) or None

    @staticmethod
    def _frase_direta_dos_resultados(resultados):
        frases = []
        for resultado in resultados:
            if not resultado.erro:
                frases.append(resultado.texto)
                continue
            detalhe = re.sub(r"^falhou:\s*", "", resultado.texto, flags=re.IGNORECASE).rstrip(".")
            if resultado.chamada.nome == "ler_sensores":
                frases.append(f"Não consegui ler os sensores: {detalhe}.")
            else:
                frases.append(f"Não consegui concluir o pedido: {detalhe}.")
        return " ".join(frases)

    async def _sair_da_frente(self, chamadas):
        """Abriu algo? Então o JARVIS sai da tela de chamada e vai para a outra."""
        if not self.janela:
            return
        if any(c.nome in ABREM_NA_TELA for c in chamadas):
            await asyncio.to_thread(self.janela.repousar)
            self.painel.registrar("sistema", "Saí da frente: o que abri fica na tela da frente")

    async def _executar(self, chamadas):
        resultados = []
        for c in chamadas:
            await self._mudar("executando", f"ferramenta: {c.nome}")
            self.executando = c.nome
            try:
                texto = await self.ferramentas[c.nome].funcao(**c.argumentos)
                resultados.append(Resultado(c, texto))
                self.painel.registrar("acao", f"{c.nome} → {texto}")
            except ErroFerramenta as exc:
                resultados.append(Resultado(c, f"falhou: {exc}", erro=True))
                self.painel.registrar("erro", f"{c.nome} falhou: {exc}")
            finally:
                self.executando = None
        # Só sai da frente do que deu certo.
        await self._sair_da_frente([r.chamada for r in resultados if not r.erro])
        return resultados

    async def _resolver_confirmacao(self, texto):
        try:
            await self._resolver(texto)
        finally:
            await self._fechar_narrador()

    async def _resolver(self, texto):
        pendente, self.pendente = self.pendente, None
        if eh_confirmacao(texto):
            self.painel.registrar("sistema", "Confirmado pelo usuário")
            resultados = await self._executar(pendente["chamadas"])
            resposta = self._resposta_pronta(resultados)
            if resposta is not None:
                # A ação está concluída; fecha o turno para a próxima chamada
                # começar com um histórico válido, sem perder o contexto.
                self.cerebro.fechar_turno(resultados, resposta)
                self.painel.registrar("sistema", "Ferramenta respondeu sem nova consulta ao cérebro")
                await self._responder(resposta)
                return
        else:
            self.painel.registrar("sistema", "Não confirmado; nada foi feito")
            resultados = [Resultado(c, "o usuário NÃO confirmou; nada foi feito") for c in pendente["chamadas"]]
        try:
            await self._mudar("pensando", f"consultando {self.cerebro.nome}")
            passo = await self._consultar(self.cerebro.devolver(resultados))
            await self._rodadas(passo, pendente["marca"])
        except asyncio.CancelledError:
            self.cerebro.desfazer(pendente["marca"])
            raise
        except Exception as exc:
            self.cerebro.desfazer(pendente["marca"])
            await self._falha(exc)

    def _abrir_narrador(self):
        """Prepara a fala em fluxo. Devolve o callback de texto, ou None sem voz."""
        if ORIGEM_PEDIDO.get() != "local" or not self.voz:
            return None

        async def respondendo():
            await self._mudar("respondendo", "falando")

        self.narrador = Narrador(self.voz, self._tocar, respondendo)
        self.narrador.comecar()
        return self.narrador.engolir

    async def _fechar_narrador(self):
        """Devolve o que já foi falado em fluxo (e esvazia o narrador)."""
        narrador, self.narrador = self.narrador, None
        if narrador is None:
            return ""
        try:
            return await narrador.terminar()
        except asyncio.CancelledError:
            raise
        except Exception:
            return ""   # fechar o narrador nunca pode derrubar o pedido

    async def _depois_de_falar(self, detalhe_final):
        if (self.exigir_chamado_a_cada_frase and not self.pendente
                and not self.cadastro and not self.diario_sessao):
            self.conversa = None
            await self._mudar("repouso", detalhe_final)
            return
        if self.conversa is not None or self.pendente or self.cadastro:
            self._renovar_conversa()
            await self._ouvindo_em_conversa()
        else:
            await self._mudar("repouso", detalhe_final)

    async def _responder(self, texto, detalhe_final="aguardando comando"):
        self.painel.agente["ultima_resposta"] = texto
        self.painel.registrar("resposta", texto)
        self.ultima_atividade = time.monotonic()
        if ORIGEM_PEDIDO.get() != "local":
            # O Echo fala a resposta; não duplicar no alto-falante do notebook.
            await self._mudar("repouso", detalhe_final)
            return
        if self.voz:
            ja_falado = await self._fechar_narrador()
            if ja_falado.strip() and mesma_fala(ja_falado, texto):
                # O narrador já disse isto enquanto o modelo ainda escrevia.
                await self._depois_de_falar(detalhe_final)
                return
            audio = await asyncio.to_thread(self.voz.sintetizar, texto)
            await self._mudar("respondendo", "falando")
            await self._tocar(audio)
            await self._depois_de_falar(detalhe_final)
            return
        await self._fechar_narrador()
        await self._mudar("respondendo", "respondendo (sem voz neste modo)")
        # Sem voz ainda: o núcleo fica no estado "respondendo" o tempo que a
        # frase levaria para ser falada, para o ritmo já ser o de verdade.
        await self._niveis(min(1.2 + len(texto) / 18, 8), lambda t: 0.35)
        await self._mudar("repouso", detalhe_final)


    async def _falha(self, exc):
        """Erro de rede/API vira estado de erro visível, nunca silêncio."""
        self.pendente = None
        if self.narrador:
            # Sem isto a tarefa do narrador fica pendurada esperando texto que não vem.
            self.narrador.cancelar()
            await self._fechar_narrador()
        bruto = getattr(exc, "message", None) or str(exc)
        detalhe = "o cérebro não respondeu — veja ATIVIDADE"
        # Os casos comuns ganham frase que diz o que fazer; o resto vai cru para o log.
        if "credit balance" in bruto:
            detalhe = "conta da API sem crédito — console.anthropic.com → Billing"
        elif "authentication" in bruto.lower() or "api_key" in bruto:
            detalhe = "chave da API ausente ou inválida no .env"
        self.painel.registrar("erro", f"Cérebro falhou: {detalhe} ({type(exc).__name__}: {bruto})"[:300])
        await self._mudar("erro", detalhe)
        await asyncio.sleep(3)
        await self._mudar("repouso", "aguardando comando")
