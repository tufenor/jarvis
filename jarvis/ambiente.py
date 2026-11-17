"""Separar "o PC está tocando" de "alguém está falando com o JARVIS".

O JARVIS sabe exatamente o que sai pelos alto-falantes: basta capturar a saída
(loopback) e comparar com o que o microfone ouve. Filme, série, vídeo do
YouTube e música caem todos nessa conta — não importa o idioma nem quantas
vozes tem, porque a comparação é com o próprio áudio, não com o conteúdo.

A comparação é feita sobre o ENVELOPE (energia ao longo do tempo), não sobre a
forma de onda: o alto-falante colore o som, o quarto ecoa e o Bluetooth atrasa,
mas o ritmo de sobe-e-desce da fala sobrevive a tudo isso. O atraso é
descoberto por correlação cruzada, então serve para fone, caixa ou dispositivo Bluetooth.
"""
import threading
import time

import numpy as np

SR = 16000
BLOCO_ENVELOPE = 512          # 32 ms, igual ao bloco do VAD
ATRASO_MAXIMO_S = 0.6         # Bluetooth chega a 300 ms; sobra folga
HISTORICO_S = 30.0
FONTES_VIRTUAIS = (
    "steam streaming", "voicemeeter", "virtual", "cable", "mapper", "wave",
)


def envelope(audio, bloco=BLOCO_ENVELOPE):
    """Energia por bloco, em escala de decibéis (é assim que o ouvido compara)."""
    sobra = len(audio) % bloco
    if sobra:
        audio = audio[:-sobra]
    if len(audio) < bloco:
        return np.zeros(0, dtype=np.float32)
    quadros = audio.reshape(-1, bloco)
    rms = np.sqrt(np.mean(quadros.astype(np.float64) ** 2, axis=1))
    return (20 * np.log10(rms + 1e-7)).astype(np.float32)


def correlacao_maxima(a, b, atraso_max_blocos):
    """Maior correlação entre dois envelopes, procurando o melhor atraso."""
    if len(a) < 4 or len(b) < 4:
        return 0.0, 0
    a = a - a.mean()
    b = b - b.mean()
    if a.std() < 1e-6 or b.std() < 1e-6:
        return 0.0, 0
    melhor, melhor_atraso = -1.0, 0
    for atraso in range(-atraso_max_blocos, atraso_max_blocos + 1):
        if atraso >= 0:
            x, y = a[atraso:], b[: len(b) - atraso] if atraso else b
        else:
            x, y = a[: len(a) + atraso], b[-atraso:]
        n = min(len(x), len(y))
        if n < 4:
            continue
        x, y = x[:n], y[:n]
        denominador = np.linalg.norm(x) * np.linalg.norm(y)
        if denominador < 1e-9:
            continue
        valor = float(np.dot(x, y) / denominador)
        if valor > melhor:
            melhor, melhor_atraso = valor, atraso
    return max(0.0, melhor), melhor_atraso


def alinhar(a, b, atraso):
    """Corta os dois envelopes para o mesmo trecho de tempo, dado o atraso."""
    if atraso >= 0:
        a, b = a[atraso:], b
    else:
        a, b = a, b[-atraso:]
    n = min(len(a), len(b))
    return a[:n], b[:n]


class AudioDoPC:
    """Grava o loopback de várias saídas do Windows em paralelo.

    Se ``alto_falantes`` não for informado, procura saídas físicas e ignora
    mixers virtuais. Isso cobre o alto-falante Realtek do notebook e um Echo
    Dot que esteja pareado como saída do Windows. Uma Alexa independente, sem
    áudio passando pelo Windows, não pode ser cancelada por este loopback.
    """

    def __init__(self, sr=SR, historico_s=HISTORICO_S, alto_falantes=None):
        self.sr = sr
        self.historico_s = historico_s
        if isinstance(alto_falantes, str):
            alto_falantes = [alto_falantes]
        self.alto_falantes = list(dict.fromkeys(
            str(nome).strip() for nome in (alto_falantes or []) if str(nome).strip()
        ))
        self.nomes_fontes = []
        self.fontes = {}
        self.amostras = np.zeros(0, dtype=np.float32)
        self.fim = None          # instante (monotonic) da última amostra guardada
        self.trava = threading.Lock()
        self.parar = threading.Event()
        self.erro = None
        self.ligado = False

    @staticmethod
    def _parece_saida_fisica(nome):
        nome = str(nome).lower()
        return not any(palavra in nome for palavra in FONTES_VIRTUAIS)

    def _descobrir_fontes(self):
        if self.alto_falantes:
            return list(self.alto_falantes)
        try:
            import soundcard
            nomes = [str(s.nome) for s in soundcard.all_speakers()
                     if self._parece_saida_fisica(s.nome)]
            if nomes:
                return list(dict.fromkeys(nomes))
            return [str(soundcard.default_speaker().name)]
        except Exception:
            return []

    def iniciar(self):
        self.nomes_fontes = self._descobrir_fontes()
        self.fontes = {
            nome: {"amostras": np.zeros(0, dtype=np.float32), "fim": None,
                   "ligado": False, "erro": None}
            for nome in self.nomes_fontes
        }
        for nome in self.nomes_fontes:
            threading.Thread(
                target=self._gravar, args=(nome,), name="loopback-" + str(len(nome)),
                daemon=True,
            ).start()

    def _gravar(self, nome):
        fonte = self.fontes[nome]
        try:
            import soundcard
            entrada = soundcard.get_microphone(nome, include_loopback=True)
            with entrada.recorder(samplerate=self.sr, channels=1, blocksize=1024) as gravador:
                fonte["ligado"] = True
                self._atualizar_estado()
                while not self.parar.is_set():
                    bloco = gravador.record(numframes=2048)[:, 0].astype(np.float32)
                    self._guardar(nome, bloco)
        except Exception as exc:
            # Sem loopback o JARVIS continua funcionando, só sem este filtro.
            fonte["erro"] = f"{type(exc).__name__}: {exc}"
            self.erro = fonte["erro"]
        finally:
            fonte["ligado"] = False
            self._atualizar_estado()

    def _atualizar_estado(self):
        with self.trava:
            self.ligado = any(fonte["ligado"] for fonte in self.fontes.values())
            erros = [fonte["erro"] for fonte in self.fontes.values() if fonte["erro"]]
            self.erro = erros[0] if erros else None

    def _guardar(self, nome, bloco):
        agora = time.monotonic()
        with self.trava:
            limite = int(self.historico_s * self.sr)
            fonte = self.fontes[nome]
            fonte["amostras"] = np.concatenate([fonte["amostras"], bloco])[-limite:]
            fonte["fim"] = agora
            # Mantém os campos antigos para consumidores que só conhecem uma
            # fonte, usando a primeira saída configurada como compatibilidade.
            if not self.amostras.size or nome == self.nomes_fontes[0]:
                self.amostras = fonte["amostras"].copy()
                self.fim = agora

    def trechos(self, inicio_s, duracao_s):
        """Retorna o trecho de cada saída física, separado por nome."""
        referencias = {}
        with self.trava:
            folga = int(ATRASO_MAXIMO_S * self.sr)
            n = int(duracao_s * self.sr)
            for nome, fonte in self.fontes.items():
                amostras, fim = fonte["amostras"], fonte["fim"]
                if fim is None or len(amostras) == 0:
                    continue
                comeco_do_buffer = fim - len(amostras) / self.sr
                i = int((inicio_s - comeco_do_buffer) * self.sr)
                i0 = max(0, i - folga)
                i1 = min(len(amostras), i + n + folga)
                if i1 > i0:
                    referencias[nome] = amostras[i0:i1].copy()
        return referencias

    def trecho(self, inicio_s, duracao_s):
        """O que saiu pelos alto-falantes num intervalo, pelo relógio monotônico."""
        referencias = self.trechos(inicio_s, duracao_s)
        if not referencias:
            return np.zeros(0, dtype=np.float32)
        if len(referencias) == 1:
            return next(iter(referencias.values()))
        n = min(map(len, referencias.values()))
        # O filtro trabalha no envelope. RMS de energia combinada evita que
        # duas saídas independentes se anulem por estarem fora de fase.
        blocos = np.stack([audio[:n] for audio in referencias.values()])
        return np.sqrt(np.max(blocos * blocos, axis=0)).astype(np.float32)

    @property
    def fontes_ativas(self):
        with self.trava:
            return sorted(nome for nome, fonte in self.fontes.items() if fonte["ligado"])


class FiltroDeOrigem:
    """Decide se um trecho ouvido pelo microfone veio do próprio PC.

    Não basta "os dois parecem", porque uma pessoa falando POR CIMA do filme
    também pareceria. A pergunta certa é: o áudio do PC explica TUDO o que o
    microfone ouviu? Alinha os dois pelo atraso, aprende o quanto do volume
    volta ao microfone e procura blocos em que o microfone ouviu bem mais que
    o esperado — esses blocos são outra fonte, ou seja, gente falando.
    """

    def __init__(self, audio_do_pc, correlacao_minima=0.72, margem_db=9.0,
                 fracao_explicada=0.85, energia_minima_db=-50, piso_db=-48):
        self.audio_do_pc = audio_do_pc
        self.correlacao_minima = correlacao_minima
        self.margem_db = margem_db
        self.fracao_explicada = fracao_explicada
        self.energia_minima_db = energia_minima_db
        self.piso_db = piso_db
        self.ultimo = {}
        self.ultimos = {}

    def _avaliar_uma(self, audio_mic, saida):
        vazio = {"correlacao": 0.0, "explicado": 0.0, "pc_tocando": False, "atraso_blocos": 0}
        if len(saida) < BLOCO_ENVELOPE * 4:
            return vazio
        env_pc = envelope(saida)
        env_mic = envelope(audio_mic)
        if env_pc.size < 4 or env_mic.size < 4:
            return vazio
        if float(np.max(env_pc)) < self.energia_minima_db:
            return vazio  # PC em silêncio não explica nada

        atraso_max = int(ATRASO_MAXIMO_S * SR / BLOCO_ENVELOPE)
        correlacao, atraso = correlacao_maxima(env_mic, env_pc, atraso_max)
        a, b = alinhar(env_mic, env_pc, atraso)
        if len(a) < 4:
            return vazio

        # Quanto do volume do PC chega ao microfone (muda com volume e quarto).
        fortes = b > (np.max(b) - 25)
        ganho_db = float(np.median(a[fortes] - b[fortes])) if fortes.sum() >= 3 else float(np.median(a - b))
        sobra = a - (b + ganho_db)
        # Só interessam os blocos em que o microfone de fato ouviu alguma coisa.
        audiveis = a > self.piso_db
        if audiveis.sum() < 3:
            return {"correlacao": correlacao, "explicado": 1.0, "pc_tocando": True,
                    "atraso_blocos": atraso}
        de_fora = (sobra > self.margem_db) & audiveis
        explicado = 1.0 - float(de_fora.sum()) / float(audiveis.sum())
        return {"correlacao": correlacao, "explicado": explicado, "pc_tocando": True,
                "atraso_blocos": atraso}

    def avaliar(self, audio_mic, inicio_s):
        """Devolve a melhor comparação entre as saídas monitoradas."""
        vazio = {"correlacao": 0.0, "explicado": 0.0, "pc_tocando": False, "atraso_blocos": 0}
        if not self.audio_do_pc or not getattr(self.audio_do_pc, "ligado", False):
            self.ultimos = {}
            self.ultimo = vazio
            return vazio
        buscar = getattr(self.audio_do_pc, "trechos", None)
        if callable(buscar):
            referencias = buscar(inicio_s, len(audio_mic) / SR)
        else:
            referencias = {"": self.audio_do_pc.trecho(inicio_s, len(audio_mic) / SR)}
        if not referencias:
            self.ultimos = {}
            self.ultimo = vazio
            return vazio
        resultados = {
            nome: dict(self._avaliar_uma(audio_mic, saida), fonte=nome)
            for nome, saida in referencias.items()
        }
        self.ultimos = resultados
        self.ultimo = max(
            resultados.values(),
            key=lambda item: (item["correlacao"] * item["explicado"], item["correlacao"]),
        )
        return self.ultimo

    def veio_do_pc(self, audio_mic, inicio_s):
        self.avaliar(audio_mic, inicio_s)
        return any(
            resultado["pc_tocando"]
            and resultado["correlacao"] >= self.correlacao_minima
            and resultado["explicado"] >= self.fracao_explicada
            for resultado in self.ultimos.values()
        )
