"""Diário local ditado ao JARVIS.

As entradas ficam somente em ``C:\\JARVIS\\dados\\diario`` (fora do git). Cada
sessão vira uma entrada no arquivo Markdown do dia; nada é enviado ao cérebro
ou a serviços externos.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import threading


class Diario:
    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self._lock = threading.Lock()

    def gravar(self, trechos, inicio=None):
        """Acrescenta uma sessão e devolve o arquivo usado."""
        textos = [str(t).strip() for t in (trechos or []) if str(t).strip()]
        if not textos:
            return None
        agora = datetime.now()
        arquivo = self.pasta / f"{agora:%Y-%m-%d}.md"
        inicio_txt = datetime.fromtimestamp(inicio).strftime("%H:%M") if inicio else agora.strftime("%H:%M")
        bloco = f"\n## {agora:%H:%M} — sessão iniciada às {inicio_txt}\n\n" + " ".join(textos) + "\n"
        with self._lock:
            self.pasta.mkdir(parents=True, exist_ok=True)
            with arquivo.open("a", encoding="utf-8") as f:
                f.write(bloco)
        return arquivo
