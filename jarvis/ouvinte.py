"""Microfone sempre aberto: detecta fala, transcreve e reconhece "Jarvis".

Por que não openWakeWord: o modelo pronto só reconhece "hey jarvis" (em
inglês), e o pedido é chamar só "Jarvis". Aqui o Silero VAD separa trechos
de fala, o faster-whisper (na GPU) transcreve cada trecho em português, e o
JARVIS só reage se a frase contém o nome. Bônus: dá para falar tudo de uma
vez — "Jarvis, abre o YouTube" — sem esperar o bipe.

Tudo roda local. Áudio que não contém "Jarvis" é descartado na hora.
"""
import collections
import os
import queue
import re
import threading
import time
import unicodedata

import numpy as np

SR = 16000
BLOCO = 512                      # 32 ms: o tamanho que o Silero VAD espera
PRE_ROLL_S = 0.4                 # guarda o começo da palavra, que o VAD perde
# A câmera Intelbras entrega a fala com pausas mais longas. Um fim de fala
# curto cortava frases no meio e fazia o Whisper inventar repetições para
# completar o trecho. Em uso real o usuário pensa entre frases: 1,8 s dá
# espaço pra ele respirar sem o microfone "perder a vez".
SILENCIO_FIM_S = 1.8
# O microfone some quando o Windows suspende, quando trocam de fone ou quando o
# driver cai. Sem religar sozinho, o JARVIS fica surdo até alguém reiniciar.
ESPERA_RECONEXAO_S = [1, 2, 5, 10, 20, 30]
# Permite frases longas sem cortar. Modo auscultação sobe isso pra muitos minutos.
FALA_MAX_S = 60
LIMIAR_INICIO = 0.35       # antes 0.50; webcam entrega sinal fraco
LIMIAR_SILENCIO = 0.20     # antes 0.30; mesma razão
PRE_GANHO = 30.0           # mic de webcam é muito baixo; amplifico antes do VAD

# Variações que o Whisper escreve ao ouvir "Jarvis" com sotaque brasileiro.
NOME = re.compile(r"\b(jarvis|jarves|jarvi|jarbas|jarviz|jarvys|djarvis|jarvas|jarbis|charvis|jervis)\b")


# A dica de vocabulário é o que mais derruba erro de transcrição aqui: medido no
# quarto do usuário, 11,6% -> 3,3% de erro só por trocar a dica curta por esta.
# Ela mostra ao Whisper as palavras que ESTE assistente ouve o tempo todo, então
# "contrato" para de virar "contato" e "agenda" para de virar "imaginando".
DICA_BASE = (
    "Conversa com o assistente Jarvis. Exemplos: Jarvis, que horas são? "
    "Jarvis, abre o YouTube. Jarvis, qual a temperatura do quarto? "
    "Jarvis, aumenta o volume. Jarvis, procura o arquivo do contrato. "
    "Jarvis, o que tenho na agenda hoje? Jarvis, muda de tela. "
    "Jarvis, toca uma música. Jarvis, suspende o computador. "
    "Jarvis, quais skills você tem? Jarvis, abre o Drive. "
    "Frase de liberação: Jarvis, liberar tela."
)
LIMITE_DICA = 900   # o initial_prompt do Whisper é curto; passar disso corta no meio


def montar_dica(programas=(), skills=()):
    """Junta à dica base os nomes que mudam de máquina para máquina.

    Assim um programa novo no config, ou uma skill nova, já entra no
    vocabulário do reconhecimento sem ninguém lembrar de atualizar nada.
    """
    extras = []
    if programas:
        extras.append("Programas: " + ", ".join(sorted(programas)) + ".")
    if skills:
        extras.append("Skills: " + ", ".join(sorted(skills)) + ".")
    return " ".join([DICA_BASE] + extras)[:LIMITE_DICA]


def texto_repetitivo(texto):
    """Detecta alucinação de repetição sem rejeitar frases normais.

    Em carga alta o decodificador às vezes devolve a mesma palavra ou bloco
    muitas vezes ("computador ... computador ..."). Esse texto não deve chegar
    ao cérebro como um comando novo, porque pode disparar uma ação errada.
    """
    palavras = re.findall(r"[\wÀ-ÿ]+", texto.casefold())
    if len(palavras) < 10:
        return False
    distintas = len(set(palavras)) / len(palavras)
    if distintas < 0.42:
        return True
    for tamanho in (2, 3):
        blocos = [tuple(palavras[i:i + tamanho])
                  for i in range(len(palavras) - tamanho + 1)]
        if blocos and max(collections.Counter(blocos).values()) >= 3:
            return True
    return False


# Nivelar pelo PICO não ajudava nada: um estalo manda no ganho da frase
# inteira. Nivelar pela ENERGIA MÉDIA (RMS) derrubou o erro de 14,1% para 9,1%
# em frases de fala comum, medido no quarto do usuário. Entre 0,06 e 0,16 o
# resultado é o mesmo; 0,10 fica no meio desse platô.
RMS_ALVO = 0.10
RMS_MINIMO = 0.00005  # mic de webcam entrega sinal muito baixo; preciso amplificar
GANHO_MAXIMO = 60.0   # teto para não virar ruído amplificado no silêncio


def energia_tipica(audio, bloco=BLOCO):
    """Energia da fala, ignorando estalo e silêncio.

    A média simples não serve: num trecho baixinho, UM estalo pode dobrar o
    RMS e derrubar o ganho da frase toda (foi um teste que pegou isso). A
    mediana dos blocos com som é imune a isso, e as pausas entre palavras não
    puxam o valor para baixo."""
    sobra = len(audio) % bloco
    quadros = (audio[:-sobra] if sobra else audio).reshape(-1, bloco)
    if not len(quadros):
        return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
    energias = np.sqrt(np.mean(quadros.astype(np.float64) ** 2, axis=1))
    # Percentil 90, não o máximo: um único bloco com estalo não pode definir
    # o que conta como "tem som" e empurrar o ganho da frase inteira.
    com_som = energias[energias > np.percentile(energias, 90) * 0.1]
    return float(np.median(com_som)) if len(com_som) else float(np.median(energias))


def normalizar(audio, alvo=RMS_ALVO):
    """Põe a fala num volume parecido, venha ela de perto ou de longe."""
    energia = energia_tipica(audio)
    if energia < RMS_MINIMO:
        return audio
    ganho = min(alvo / energia, GANHO_MAXIMO)
    return np.clip(audio * ganho, -1.0, 1.0).astype(np.float32)


def preparar_cuda():
    """Põe as DLLs do CUDA (pacotes pip nvidia-*) no caminho do Windows.

    O ctranslate2 carrega cublas64_12.dll pelo nome; sem isso a GPU falha com
    "cublas64_12.dll is not found" mesmo com tudo instalado.
    """
    import os
    import sys
    from pathlib import Path
    base = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    for pasta in base.glob("*/bin"):
        os.environ["PATH"] = str(pasta) + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(str(pasta))


class DetectorEco:
    """Separa "o JARVIS se ouvindo no alto-falante" de "alguém falando por cima".

    Impressão de voz não serve para isso (medido: a voz dele ouvida pelo
    microfone fica entre 0,71 e 0,81 de semelhança com ela mesma, e vozes de
    outras pessoas entre 0,59 e 0,81 — a acústica do quarto pesa mais que o
    timbre). Mas o JARVIS sabe exatamente o que está tocando: compara a
    energia que o microfone ouve com a energia esperada do próprio eco.

    O ganho (quanto do volume tocado volta ao microfone) é aprendido na hora,
    pela mediana das últimas leituras: depende do volume e do quarto, e muda.
    """

    def __init__(self, ganho=0.15, razao=1.6, blocos_min=6, historico_s=0.8, piso=0.004):
        self.ganho = ganho
        self.razao = razao
        self.blocos_min = blocos_min
        self.historico_s = historico_s
        self.piso = piso
        self.referencia = collections.deque()
        self.razoes = collections.deque(maxlen=100)
        self.acima = 0

    def registrar_referencia(self, rms, t=None):
        t = time.monotonic() if t is None else t
        self.referencia.append((t, rms))
        while self.referencia and t - self.referencia[0][0] > self.historico_s:
            self.referencia.popleft()

    def referencia_maxima(self):
        # Máximo da janela, não o valor de agora: o som leva ~0,1–0,3 s para
        # sair do alto-falante e voltar pelo microfone.
        return max((r for _, r in list(self.referencia)), default=0.0)

    def zerar(self):
        self.referencia.clear()
        self.acima = 0

    def processar(self, rms_mic, fala_no_bloco):
        """Um bloco do microfone enquanto o JARVIS fala. True = interrupção."""
        ref = self.referencia_maxima()
        esperado = self.ganho * ref + self.piso
        if fala_no_bloco and ref > 0.02:
            self.razoes.append(rms_mic / ref)
            if len(self.razoes) >= 30:
                self.ganho = min(0.5, max(0.01, float(np.median(self.razoes))))
        if fala_no_bloco and rms_mic > esperado * self.razao:
            self.acima += 1
        else:
            self.acima = max(0, self.acima - 1)
        return self.acima >= self.blocos_min


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def separar_chamado(texto):
    """Devolve (chamou, pedido). O pedido é o que vem depois do nome."""
    limpo = sem_acento(texto.lower())
    m = NOME.search(limpo)
    if not m:
        return False, ""
    # O nome no meio de uma conversa (TV, vídeo ou fala de terceiros) não é
    # um chamado confiável. Aceitamos apenas o início ou um vocativo curto.
    prefixo = limpo[:m.start()].strip(" ,.!?;:-")
    if prefixo:
        vocativo = re.fullmatch(
            r"(?:o|ei|oi|ola|hey|senhor|por favor|com licenca)(?:\s+(?:o|ei|oi|ola|hey|senhor))?",
            prefixo,
        )
        if not vocativo:
            return False, ""
    resto = texto[m.end():] if len(texto) == len(limpo) else limpo[m.end():]
    return True, resto.strip(" ,.!?;:-")


class VAD:
    """Silero VAD em modo contínuo: guarda o estado da rede entre blocos."""

    def __init__(self):
        from faster_whisper.vad import get_vad_model
        self.sessao = get_vad_model().session
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.contexto = np.zeros(64, dtype=np.float32)

    def __call__(self, bloco):
        entrada = np.concatenate([self.contexto, bloco]).reshape(1, -1).astype(np.float32)
        prob, self.h, self.c = self.sessao.run(None, {"input": entrada, "h": self.h, "c": self.c})
        self.contexto = bloco[-64:]
        return float(prob.reshape(-1)[0])


class Ouvinte:
    """Threads de captura e transcrição. Fala com o resto por callbacks.

    ao_texto(texto, audio, falante) — cada transcrição; falante = nome cadastrado ou None
    ao_nivel(v)                     — volume 0..1 do microfone, ~30 vezes por segundo
    ao_interromper()                — alguém começou a falar por cima do JARVIS
    """

    def __init__(self, ao_texto, ao_nivel=None, microfone="Microphone (Realtek(R) Audio)",
                 microfones=None, automatico=False, modelo="medium", dispositivo="cuda",
                 beam=5, dica=None, confianca_minima=-1.0, sem_fala_maxima=0.7,
                 temperatura=(0.0, 0.2), compressao_maxima=2.4,
                 silencio_fim_s=SILENCIO_FIM_S, limiar_inicio=LIMIAR_INICIO,
                 limiar_silencio=LIMIAR_SILENCIO):
        self.ao_texto = ao_texto
        self.ao_nivel = ao_nivel
        nomes = microfones if microfones is not None else microfone
        if isinstance(nomes, str):
            nomes = [nomes]
        self.nomes_microfones = list(dict.fromkeys(
            str(nome).strip() for nome in (nomes or []) if str(nome).strip()
        ))
        if not self.nomes_microfones:
            self.nomes_microfones = ["Microphone (Realtek(R) Audio)"]
        self.nome_microfone = self.nomes_microfones[0]
        self.modo_microfone = "multi" if len(self.nomes_microfones) > 1 else "manual"
        self.microfone_prioritario = None
        self.microfones_automaticos = bool(automatico)
        self.nome_modelo = modelo
        self.dispositivo = dispositivo
        self.beam = beam
        self.dica = dica or DICA_BASE
        self.temperatura = tuple(temperatura)
        self.compressao_maxima = float(compressao_maxima)
        self.silencio_fim_s = float(silencio_fim_s)
        self.limiar_inicio = float(limiar_inicio)
        self.limiar_silencio = float(limiar_silencio)
        self.fala_max_s = float(FALA_MAX_S)
        # Guarda os valores "normais" para voltar depois do modo auscultação.
        self._silencio_fim_s_normal = self.silencio_fim_s
        self._fala_max_s_normal = self.fala_max_s
        self.modo_auscultacao = False
        # Transcrição com confiança baixa é chute do Whisper em cima de ruído:
        # "Eu acho." no lugar de "Jarvis, que horas são". Melhor descartar.
        self.confianca_minima = confianca_minima
        self.sem_fala_maxima = sem_fala_maxima
        self.blocos = queue.Queue(maxsize=400)
        self.filas_microfones = {
            nome: queue.Queue(maxsize=8) for nome in self.nomes_microfones
        }
        self.trechos = queue.Queue(maxsize=8)
        # Ligado enquanto o JARVIS fala. O microfone continua ouvindo (para poder
        # ser interrompido); o eco da própria voz é filtrado pelo DetectorEco.
        self.falando = threading.Event()
        self.locutores = None
        self.filtro_origem = None   # ignora o que vem do próprio PC (filme, vídeo)
        self.ao_interromper = None
        self.eco = DetectorEco()
        self.parar = threading.Event()
        self.erro = None
        # Diagnóstico (só em memória; nada do que é ouvido vai para disco).
        self.estado = {"microfone": "parado", "whisper": "parado", "trechos": 0,
                       "transcricoes": 0, "ultimo_texto": "", "ultimo_tempo_s": None,
                       "descartados_do_pc": 0, "descartados_sem_confianca": 0,
                       "ultima_confianca": None, "reconexoes": 0,
                       "microfones": list(self.nomes_microfones),
                       "microfones_ativos": [], "erros_microfones": {},
                       "ultimo_microfone": None, "blocos_por_microfone": {},
                       "modo_microfone": self.modo_microfone, "nivel": 0.0,
                       "descartados_repeticao": 0,
                       "fontes_cancelamento": [], "fontes_cancelamento_ativas": []}

    # ---- controle ----------------------------------------------------------

    def iniciar(self):
        self._preparar_microfones()
        threading.Thread(target=self._transcrever, name="whisper", daemon=True).start()
        threading.Thread(target=self._segmentar_continuamente, name="vad", daemon=True).start()
        if len(self.nomes_microfones) == 1:
            # Mantém o caminho antigo para uma única entrada e para a
            # reconexão já coberta pelos testes.
            threading.Thread(target=self._capturar, name="microfone", daemon=True).start()
        else:
            threading.Thread(target=self._misturar_blocos, name="misturador-microfones", daemon=True).start()
            for nome in self.nomes_microfones:
                threading.Thread(
                    target=self._capturar_fonte, args=(nome,),
                    name="microfone-" + str(len(nome)), daemon=True,
                ).start()

    @staticmethod
    def _parece_microfone_fisico(nome):
        """Evita capturar mixers virtuais como se fossem microfones reais."""
        nome = str(nome).lower()
        return not any(palavra in nome for palavra in (
            "steam streaming", "voicemeeter", "virtual", "cable", "stereo mix",
            "what u hear", "mapper", "mapeador", "wave",
        ))

    def _preparar_microfones(self):
        """Descobre entradas físicas MME quando o modo automático está ativo."""
        if not self.microfones_automaticos:
            return
        try:
            import sounddevice as sd
            nomes = []
            for dispositivo in sd.query_devices():
                if (dispositivo["hostapi"] == 0
                        and dispositivo["max_input_channels"] > 0
                        and self._parece_microfone_fisico(dispositivo["name"])):
                    nome = str(dispositivo["name"])
                    if nome not in nomes:
                        nomes.append(nome)
            if nomes:
                self.nomes_microfones = nomes
                self.nome_microfone = nomes[0]
                self.modo_microfone = "multi" if len(nomes) > 1 else "manual"
                self.microfone_prioritario = None
                self.filas_microfones = {
                    nome: queue.Queue(maxsize=8) for nome in nomes
                }
                self.estado["microfones"] = list(nomes)
        except Exception as exc:
            self.estado["erros_microfones"]["descoberta"] = f"{type(exc).__name__}: {exc}"

    def _segmentar_continuamente(self):
        try:
            vad = VAD()
            self.estado["vad"] = "pronto"
        except Exception as exc:
            self.erro = f"VAD: {type(exc).__name__}: {exc}"
            self.estado["vad"] = "erro: " + self.erro
            return
        self._segmentar(vad)

    def silenciar(self, ligado):
        """ligado=True enquanto o JARVIS fala."""
        if ligado:
            self.eco.zerar()
            self.falando.set()
        else:
            # Folga para o eco da última sílaba sair da sala antes de voltar ao normal.
            time.sleep(0.25)
            self.falando.clear()

    def ativar_auscultacao(self, silencio_fim_s=5.0, fala_max_s=1800.0):
        """Modo escuta longa: espera muito mais tempo entre frases antes de cortar.

        5 s de silêncio e até 30 min de trecho contínuo. Útil quando o usuário
        quer desabafar e vai pausar, pensar, voltar. O JARVIS só fecha o
        trecho quando pedirem: `desativar_auscultacao()`.
        """
        self.silencio_fim_s = float(silencio_fim_s)
        self.fala_max_s = float(fala_max_s)
        self.modo_auscultacao = True
        self.estado["modo_auscultacao"] = True

    def desativar_auscultacao(self):
        self.silencio_fim_s = self._silencio_fim_s_normal
        self.fala_max_s = self._fala_max_s_normal
        self.modo_auscultacao = False
        self.estado["modo_auscultacao"] = False

    def trocar_microfone(self, nome):
        """Escolhe uma fonte já aberta ou devolve a escolha ao modo multi.

        A captura fica aberta para as fontes configuradas desde a inicialização.
        Acrescentar uma entrada nova no meio do fluxo poderia deixá-la sem VAD;
        por isso, um periférico novo entra na próxima inicialização do JARVIS.
        """
        if nome in (None, "", "multi"):
            self.modo_microfone = "multi" if len(self.nomes_microfones) > 1 else "manual"
            self.microfone_prioritario = None
            self.estado["modo_microfone"] = self.modo_microfone
            return True
        if nome not in self.nomes_microfones:
            return False
        self.modo_microfone = "manual"
        self.microfone_prioritario = nome
        self.nome_microfone = nome
        self.estado["modo_microfone"] = "manual"
        self.estado["ultimo_microfone"] = nome
        return True

    # ---- captura + VAD ----------------------------------------------------------

    def _achar_microfone(self, sd, nome=None):
        # MME (hostapi 0) converte para 16 kHz sozinho; as outras APIs exigem a taxa nativa.
        nome = nome or self.nome_microfone
        for i, d in enumerate(sd.query_devices()):
            if (d["max_input_channels"] > 0 and d["hostapi"] == 0
                    and (d["name"] == nome or d["name"].startswith(nome[:20]))):
                return i
        return None

    def _capturar(self):
        """Mantém o microfone aberto, religando sozinho quando ele cai."""
        tentativa = 0
        while not self.parar.is_set():
            antes = self.estado["trechos"]
            self._abrir_microfone()
            if self.parar.is_set():
                return
            # Se chegou a ouvir alguma coisa, a queda foi nova: recomeça a espera.
            tentativa = 0 if self.estado["trechos"] > antes else tentativa + 1
            espera = ESPERA_RECONEXAO_S[min(tentativa, len(ESPERA_RECONEXAO_S) - 1)]
            self.estado["microfone"] = f"caiu ({self.erro}); religando em {espera}s"
            self.estado["reconexoes"] += 1
            time.sleep(espera)

    def _capturar_fonte(self, nome):
        """Mantém uma entrada específica aberta no modo multi-microfone."""
        fila = self.filas_microfones[nome]
        tentativa = 0
        while not self.parar.is_set():
            antes = self.estado["blocos_por_microfone"].get(nome, 0)
            self._abrir_microfone(nome, fila)
            if self.parar.is_set():
                return
            chegou = self.estado["blocos_por_microfone"].get(nome, 0) > antes
            tentativa = 0 if chegou else tentativa + 1
            espera = ESPERA_RECONEXAO_S[min(tentativa, len(ESPERA_RECONEXAO_S) - 1)]
            self.estado["reconexoes"] += 1
            time.sleep(espera)

    def _marcar_fonte(self, nome, ativa, erro=None):
        ativos = set(self.estado.get("microfones_ativos", []))
        if ativa:
            ativos.add(nome)
        else:
            ativos.discard(nome)
        self.estado["microfones_ativos"] = sorted(ativos)
        total = len(self.nomes_microfones)
        self.estado["microfone"] = f"aberto ({len(ativos)}/{total})"
        if erro:
            self.estado["erros_microfones"][nome] = erro

    def _abrir_microfone(self, nome=None, fila=None):
        import sounddevice as sd
        nome = nome or self.nome_microfone
        fila = fila or self.blocos
        try:
            dispositivo = self._achar_microfone(sd, nome)
            if dispositivo is None:
                raise RuntimeError(f"microfone não encontrado: {nome}")
            self._marcar_fonte(nome, True)

            def receber(indata, frames, tempo, status):
                try:
                    fila.put_nowait(indata[:, 0].copy())
                    contagem = self.estado["blocos_por_microfone"]
                    contagem[nome] = contagem.get(nome, 0) + 1
                except queue.Full:
                    pass  # transcrição atrasada: melhor perder áudio que travar a captura

            with sd.InputStream(samplerate=SR, blocksize=BLOCO, channels=1, dtype="float32",
                                device=dispositivo, callback=receber):
                while not self.parar.is_set():
                    time.sleep(0.2)
        except Exception as exc:  # microfone sumiu, driver recusou etc.
            self.erro = f"{type(exc).__name__}: {exc}"
            self.estado["microfone"] = "erro: " + self.erro
            self._marcar_fonte(nome, False, self.erro)

    def _misturar_blocos(self):
        """Usa todas as entradas, escolhendo o bloco com melhor sinal.

        Misturar amostras cruas de microfones separados pode cancelar a fala por
        causa do atraso acústico entre eles. Cada entrada continua aberta e é
        considerada a cada bloco de 32 ms; o trecho com maior energia típica é
        encaminhado ao VAD, evitando essa soma destrutiva.
        """
        while not self.parar.is_set():
            candidatos = []
            for nome, fila in self.filas_microfones.items():
                bloco = None
                try:
                    bloco = fila.get(timeout=0.04 if not candidatos else 0)
                    while True:
                        bloco = fila.get_nowait()
                except queue.Empty:
                    pass
                if bloco is not None:
                    candidatos.append((nome, bloco))
            if not candidatos:
                continue
            if len(candidatos) == 1:
                nome, combinado = candidatos[0]
            else:
                escolhidos = candidatos
                if self.modo_microfone == "manual" and self.microfone_prioritario:
                    manual = [item for item in candidatos if item[0] == self.microfone_prioritario]
                    if manual:
                        escolhidos = manual
                nome, combinado = max(escolhidos, key=lambda item: energia_tipica(item[1]))
            self.estado["ultimo_microfone"] = nome
            try:
                self.blocos.put_nowait(combinado)
            except queue.Full:
                pass

    def _do_proprio_pc(self, audio, inicio):
        if not self.filtro_origem:
            return False
        try:
            veio = self.filtro_origem.veio_do_pc(audio, inicio)
            referencia = self.filtro_origem.audio_do_pc
            self.estado["fontes_cancelamento"] = list(
                getattr(referencia, "nomes_fontes", [])
            )
            self.estado["fontes_cancelamento_ativas"] = list(
                getattr(referencia, "fontes_ativas", [])
            )
            return veio
        except Exception:
            # Na dúvida, deixa passar: perder um pedido é pior que gastar uma transcrição.
            return False

    def _segmentar(self, vad):
        pre = []
        inicio_trecho = time.monotonic()
        trecho = None
        silencio = 0
        n_pre = int(PRE_ROLL_S * SR / BLOCO)
        # n_fim e n_max são lidos por iteração pra que ativar_auscultacao()
        # mude o comportamento do VAD em tempo real, sem reiniciar.
        escuta = []                       # fala captada enquanto o JARVIS fala
        while not self.parar.is_set():
            try:
                bloco = self.blocos.get(timeout=0.5)
            except queue.Empty:
                continue
            bloco = np.clip(bloco * PRE_GANHO, -1.0, 1.0).astype(np.float32)
            nivel = min(1.0, float(np.sqrt(np.mean(bloco ** 2))) * 12)
            self.estado["nivel"] = nivel
            if self.ao_nivel:
                self.ao_nivel(nivel)
            p = vad(bloco)

            if self.falando.is_set():
                trecho, pre = None, []
                escuta.append(bloco)
                escuta = escuta[-int(1.5 * SR / BLOCO):]
                rms = float(np.sqrt(np.mean(bloco ** 2)))
                if self.eco.processar(rms, p >= self.limiar_silencio):
                    self.falando.clear()
                    if self.ao_interromper:
                        self.ao_interromper()
                    # O que a pessoa já disse vira o começo do próximo trecho.
                    trecho, silencio = list(escuta[-self.eco.blocos_min * 2:]), 0
                    escuta = []
                continue
            escuta = []

            if trecho is None:
                pre.append(bloco)
                pre = pre[-n_pre:]
                if p >= self.limiar_inicio:
                    trecho, silencio = list(pre), 0
                    # Hora em que a fala começou, descontando o pré-roll já guardado.
                    inicio_trecho = time.monotonic() - len(pre) * BLOCO / SR
            else:
                trecho.append(bloco)
                silencio = silencio + 1 if p < self.limiar_silencio else 0
                n_fim = int(self.silencio_fim_s * SR / BLOCO)
                n_max = int(self.fala_max_s * SR / BLOCO)
                if silencio >= n_fim or len(trecho) >= n_max:
                    if len(trecho) - silencio > 6:  # ignora estalos de menos de ~0,2 s
                        audio = np.concatenate(trecho)
                        if self._do_proprio_pc(audio, inicio_trecho):
                            # Filme, série, vídeo: nem transcreve, nem gasta API.
                            self.estado["descartados_do_pc"] += 1
                        else:
                            try:
                                self.trechos.put_nowait(audio)
                                self.estado["trechos"] += 1
                            except queue.Full:
                                pass
                    trecho, pre = None, []

    # ---- transcrição ------------------------------------------------------------

    def _transcrever(self):
        self.estado["whisper"] = "carregando"
        try:
            from faster_whisper import WhisperModel
            preparar_cuda()
            try:
                # GTX 1060 (Pascal) não tem float16 eficiente: int8 puro é o mais rápido nela.
                modelo = WhisperModel(self.nome_modelo, device=self.dispositivo, compute_type="int8")
                modelo.transcribe(np.zeros(SR, dtype=np.float32), language="pt")  # força carregar o CUDA agora
            except Exception:
                # Sem CUDA funcional, a CPU dá conta do "small", só que mais devagar.
                modelo = WhisperModel(self.nome_modelo, device="cpu", compute_type="int8")
        except Exception as exc:
            self.erro = f"Whisper: {type(exc).__name__}: {exc}"
            self.estado["whisper"] = "erro: " + self.erro
            return
        self.estado["whisper"] = f"pronto ({modelo.model.device})"
        while not self.parar.is_set():
            try:
                audio = self.trechos.get(timeout=0.5)
            except queue.Empty:
                continue
            inicio = time.monotonic()
            pasta_debug = os.environ.get("JARVIS_DEBUG_AUDIO")
            if pasta_debug:  # só para diagnóstico, nunca ligado no uso normal
                import wave
                with wave.open(os.path.join(pasta_debug, f"trecho_{self.estado['trechos']}.wav"), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
                    w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            audio = normalizar(audio)
            segmentos, _ = modelo.transcribe(
                audio, language="pt", beam_size=self.beam, vad_filter=False,
                condition_on_previous_text=False, temperature=self.temperatura,
                compression_ratio_threshold=self.compressao_maxima,
                log_prob_threshold=-1.0, no_speech_threshold=self.sem_fala_maxima,
                suppress_blank=True, without_timestamps=True,
                # A lista de comandos ajuda como hotwords, mas no prompt inicial
                # ela pode reaparecer como se tivesse sido falada no silêncio.
                initial_prompt="Transcrição de fala espontânea em português brasileiro.",
                hotwords=self.dica,
            )
            segmentos = list(segmentos)
            texto = " ".join(s.text for s in segmentos).strip()
            confianca = float(np.mean([s.avg_logprob for s in segmentos])) if segmentos else -9.0
            sem_fala = float(np.mean([s.no_speech_prob for s in segmentos])) if segmentos else 1.0
            self.estado["ultima_confianca"] = round(confianca, 2)
            repetitivo = bool(texto and texto_repetitivo(texto))
            if repetitivo:
                self.estado["descartados_repeticao"] += 1
                texto = ""
            if texto and (confianca < self.confianca_minima or sem_fala > self.sem_fala_maxima):
                self.estado["descartados_sem_confianca"] += 1
                texto = ""
            falante = None
            if texto and self.locutores and len(audio) >= SR // 2:
                falante, _ = self.locutores.identificar(audio)
            self.estado.update(transcricoes=self.estado["transcricoes"] + 1, ultimo_texto=texto,
                               ultimo_tempo_s=round(time.monotonic() - inicio, 2), ultimo_falante=falante)
            if texto:
                self.ao_texto(texto, audio, falante)
