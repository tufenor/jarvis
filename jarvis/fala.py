"""Voz do JARVIS: Piper (local, pt-BR) com um tratamento leve de "assistente".

O objetivo é o ESTILO do JARVIS dublado — grave, calmo, pausado, com um
leve brilho metálico —, não a voz de nenhuma pessoa real. Nada aqui é
treinado ou clonado a partir de gravações de alguém.
"""
import threading
import sys
from pathlib import Path

import numpy as np

_RAIZ_MODELOS = (Path(sys.executable).resolve().parent
                 if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1])
_BASE_MODELOS = (_RAIZ_MODELOS / "modelos" if (_RAIZ_MODELOS / "modelos").is_dir()
                 else _RAIZ_MODELOS / "_internal" / "modelos")
PASTA_MODELOS = _BASE_MODELOS / "piper"
QUADRO_NIVEL_S = 0.05


def _filtro_passa_altas(x, sr, corte_hz):
    # Tira o "ronco" grave que embola no alto-falante do notebook.
    from scipy.signal import butter, lfilter
    b, a = butter(2, corte_hz / (sr / 2), btype="highpass")
    return lfilter(b, a, x)


def tratar(audio, sr, intensidade=1.0):
    """Tratamento "IA de filme": eco metálico curtíssimo + sala pequena, bem baixos.

    Ecos de 11 e 17 ms criam o brilho metálico (filtro pente); a cauda de
    ~0,3 s dá a sensação de voz vinda de um sistema, sem virar caverna.
    """
    if intensidade <= 0:
        return audio
    seco = _filtro_passa_altas(audio, sr, 90.0)
    saida = seco.copy()
    for atraso_s, ganho in ((0.011, 0.22), (0.017, 0.14)):
        n = int(sr * atraso_s)
        saida[n:] += seco[:-n] * ganho * intensidade
    rng = np.random.default_rng(7)  # semente fixa: a mesma frase soa sempre igual
    cauda = int(sr * 0.3)
    ir = rng.standard_normal(cauda) * np.exp(-np.linspace(0, 6, cauda))
    ir *= 0.025 * intensidade / max(np.abs(ir).max(), 1e-9)
    sala = np.convolve(seco, ir)[: len(seco)]
    saida += sala
    pico = np.abs(saida).max()
    return saida / pico * 0.9 if pico > 0 else saida


def bip(sr=22050, duracao=0.07):
    """Toque curto de "ouvi você", no lugar do silêncio enquanto o modelo pensa.

    Dois harmônicos com queda rápida: audível, mas curto demais (70 ms) para
    o DetectorEco confundir com alguém falando.
    """
    t = np.arange(int(sr * duracao)) / sr
    envelope = np.exp(-t * 38)
    onda = np.sin(2 * np.pi * 1320 * t) * 0.6 + np.sin(2 * np.pi * 1980 * t) * 0.25
    return (onda * envelope * 0.25).astype(np.float32)


def engrossar(audio, sr, fator):
    """Abaixa o tom sem mudar a duração nem a qualidade.

    Esticar a onda abaixa o tom E alonga a fala. Para a duração não mudar, a
    síntese já sai mais rápida na mesma proporção (ver `Fala.__init__`), e aqui
    só se estica de volta. Não há perda: o Piper gera nativamente e o estica é
    uma reamostragem. As formantes descem junto, o que é o que dá a impressão
    de voz "maior", não só mais baixa.
    """
    if fator >= 0.999:
        return audio
    from fractions import Fraction
    from scipy.signal import resample_poly
    razao = Fraction(fator).limit_denominator(200)
    return resample_poly(audio, razao.denominator, razao.numerator).astype(np.float32)


class Fala:
    def __init__(self, voz="pt_BR-cadu-medium", velocidade=1.08, efeito=1.0,
                 gravidade=1.0, usar_cuda=False):
        from piper import PiperVoice, SynthesisConfig

        self.voz = PiperVoice.load(PASTA_MODELOS / f"{voz}.onnx", use_cuda=usar_cuda)
        self.sr = self.voz.config.sample_rate
        # gravidade < 1 baixa o tom; a síntese compensa falando mais rápido,
        # para o esticão devolver a duração original.
        self.gravidade = max(0.75, min(1.0, gravidade))
        # length_scale > 1 deixa a fala mais pausada, como o JARVIS fala.
        self.config = SynthesisConfig(length_scale=velocidade * self.gravidade,
                                      noise_scale=0.55, noise_w_scale=0.7)
        self.efeito = efeito
        self.parar_evento = threading.Event()

    def sintetizar(self, texto):
        partes = [c.audio_int16_array for c in self.voz.synthesize(texto, syn_config=self.config)]
        if not partes:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(partes).astype(np.float32) / 32768.0
        audio = engrossar(audio, self.sr, self.gravidade)
        return tratar(audio, self.sr, self.efeito).astype(np.float32)

    def tocar(self, audio, ao_nivel=None, ao_referencia=None):
        """Toca bloqueando a thread; chama ao_nivel(0..1) a cada 50 ms para o núcleo.

        ao_referencia(rms) recebe a energia real do que está saindo, para o
        ouvinte saber o quanto de eco esperar no microfone."""
        import sounddevice as sd

        self.parar_evento.clear()
        passo = int(self.sr * QUADRO_NIVEL_S)
        with sd.OutputStream(samplerate=self.sr, channels=1, dtype="float32") as saida:
            for i in range(0, len(audio), passo):
                if self.parar_evento.is_set():
                    break
                bloco = audio[i:i + passo]
                rms = float(np.sqrt(np.mean(bloco ** 2)))
                if ao_referencia:
                    ao_referencia(rms)
                if ao_nivel:
                    ao_nivel(min(1.0, rms * 4.5))
                saida.write(bloco.reshape(-1, 1))
        if ao_nivel:
            ao_nivel(0.0)

    def tocar_paralelo(self, audio):
        """Toca um som curto sem mexer no parar_evento da fala principal."""
        import sounddevice as sd
        try:
            sd.play(audio, self.sr, blocking=True)
        except Exception:
            pass  # placa de som ocupada: o bip é enfeite, nunca derruba o pedido

    def parar(self):
        self.parar_evento.set()
