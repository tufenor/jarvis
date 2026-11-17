"""Economia de energia local para a sessão do JARVIS.

O módulo não suspende nem desliga o computador. Ele apenas acompanha a
inatividade local e, quando configurado, reduz o brilho via WMI e minimiza a
janela do JARVIS. A restauração acontece quando o usuário volta a interagir ou
quando um telefone marcado como presente reaparece.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes


def segundos_desde_entrada():
    """Retorna segundos desde teclado/mouse do Windows, ou ``None`` fora dele."""
    if os.name != "nt":
        return None

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        agora = ctypes.windll.kernel32.GetTickCount64()
        return max(0.0, (agora - info.dwTime) / 1000.0)
    except (AttributeError, OSError):
        return None


def ha_presenca_conhecida(painel):
    """Indica se algum telefone companheiro está marcado como presente."""
    aparelhos = getattr(painel, "presencas_moveis", {}) or {}
    return any(dados.get("presente") is True for dados in aparelhos.values())


def deve_economizar(estado, parado_s, entrada_s, limite_s, presenca=False):
    """Política pura: só economiza parado, sem conversa e sem presença."""
    if estado != "repouso" or parado_s <= limite_s or presenca:
        return False
    return entrada_s is None or entrada_s > limite_s


class ControleBrilho:
    """Controle best-effort do brilho dos monitores WMI do Windows."""

    def __init__(self, executar=None):
        self._executar = executar or subprocess.run
        self.anterior = None
        self.nivel = None

    def _powershell(self, comando):
        return self._executar(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, timeout=8, check=False,
            stdin=subprocess.DEVNULL,
        )

    def capturar(self, fallback=75):
        if self.anterior is not None:
            return self.anterior
        try:
            resultado = self._powershell(
                "(Get-CimInstance -Namespace root/WMI -ClassName "
                "WmiMonitorBrightness | Select-Object -First 1 -ExpandProperty "
                "CurrentBrightness)"
            )
            valor = int((resultado.stdout or "").strip())
            if 0 <= valor <= 100:
                self.anterior = valor
        except (OSError, ValueError, subprocess.SubprocessError):
            self.anterior = None
        return self.anterior if self.anterior is not None else int(fallback)

    def definir(self, nivel):
        try:
            nivel = max(5, min(100, int(nivel)))
        except (TypeError, ValueError):
            return False
        try:
            resultado = self._powershell(
                "Get-CimInstance -Namespace root/WMI -ClassName "
                f"WmiMonitorBrightnessMethods | ForEach-Object {{ "
                f"$_.WmiSetBrightness(1,{nivel}) }}"
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if resultado.returncode == 0:
            self.nivel = nivel
            return True
        return False

    def restaurar(self, fallback=75):
        alvo = self.anterior if self.anterior is not None else fallback
        return self.definir(alvo)
