"""Reconhecer quem está falando (e distinguir a própria voz do JARVIS).

Cada voz vira uma "impressão" (embedding de 256 números) pelo modelo
WeSpeaker ResNet34 via sherpa-onnx, local e sem torch. Comparação por cosseno.

Privacidade: só as impressões ficam em disco (dados/vozes.json, fora do git);
o áudio usado no cadastro é descartado. "Esquece minha voz" apaga a impressão.
"""
import json
import threading
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
MODELO_PADRAO = RAIZ / "modelos" / "locutor" / "wespeaker_en_voxceleb_resnet34_LM.onnx"
ARQUIVO_PADRAO = RAIZ / "dados" / "vozes.json"
SR = 16000


def normalizar(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


class Locutores:
    def __init__(self, modelo=MODELO_PADRAO, arquivo=ARQUIVO_PADRAO, limiar=0.55, extrator=None):
        self.arquivo = Path(arquivo)
        self.limiar = limiar
        self.trava = threading.Lock()
        if extrator is None:
            import sherpa_onnx
            cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(modelo), num_threads=2)
            extrator = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        self.extrator = extrator
        self.pessoas = self._carregar()

    # ---- persistência ----------------------------------------------------------

    def _carregar(self):
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {nome: normalizar(v) for nome, v in dados.items()}

    def _salvar(self):
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        dados = {nome: [round(float(x), 6) for x in v] for nome, v in self.pessoas.items()}
        self.arquivo.write_text(json.dumps(dados), encoding="utf-8")

    # ---- impressões ------------------------------------------------------------

    def impressao(self, audio):
        """audio: float32 mono 16 kHz. Precisa de ~0,5 s ou mais para ser confiável."""
        with self.trava:  # o extrator não é seguro para duas threads ao mesmo tempo
            s = self.extrator.create_stream()
            s.accept_waveform(SR, np.asarray(audio, dtype=np.float32))
            s.input_finished()
            return normalizar(self.extrator.compute(s))

    def identificar(self, audio):
        """Devolve (nome, semelhança) ou (None, melhor semelhança)."""
        if not self.pessoas:
            return None, 0.0
        e = self.impressao(audio)
        nome, sim = max(((n, float(v @ e)) for n, v in self.pessoas.items()), key=lambda x: x[1])
        return (nome, sim) if sim >= self.limiar else (None, sim)

    def cadastrar(self, nome, audios):
        # A média de várias frases é bem mais estável que uma frase só.
        media = normalizar(np.mean([self.impressao(a) for a in audios], axis=0))
        self.pessoas[nome] = media
        self._salvar()

    def esquecer(self, nome):
        if self.pessoas.pop(nome, None) is not None:
            self._salvar()
            return True
        return False

    def nomes(self):
        return sorted(self.pessoas)
