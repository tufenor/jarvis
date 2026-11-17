import json
import os
from pathlib import Path
import sys

PASTA = Path(__file__).resolve().parent
RAIZ_RUNTIME = (Path(sys.executable).resolve().parent
                if getattr(sys, "frozen", False) else PASTA.parent)
ARQUIVO_PADRAO = Path(os.environ.get(
    "JARVIS_CONFIG", str(RAIZ_RUNTIME / "config.json" if getattr(sys, "frozen", False)
                        else PASTA / "config.json")
))


def carregar(caminho=ARQUIVO_PADRAO):
    # O PowerShell pode gravar JSON com BOM UTF-8. Aceitá-lo evita que uma
    # alteração de configuração impeça o JARVIS de iniciar.
    with open(caminho, encoding="utf-8-sig") as f:
        return json.load(f)
