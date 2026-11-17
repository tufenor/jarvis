"""Alerta de invasao: tela vermelha em tela cheia + aviso falado nas caixas do PC.

Roda como processo separado para nao travar a gravacao da webcam.
Uso:  python alerta_invasor.py "texto falado" segundos_na_tela
"""
import subprocess
import sys
import threading

TEXTO_PADRAO = ("O responsável foi comunicado da invasão, "
                "e voce esta sendo gravado.")


def falar(texto):
    """Fala pelo sintetizador do proprio Windows (sem instalar nada)."""
    # Escolhe uma voz em portugues quando existir; senao usa a padrao.
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$pt = $v.GetInstalledVoices() | Where-Object "
        "{ $_.VoiceInfo.Culture.Name -like 'pt*' } | Select-Object -First 1;"
        "if ($pt) { $v.SelectVoice($pt.VoiceInfo.Name) };"
        "$v.Volume = 100; $v.Rate = 0;"
        f"$v.Speak('{texto}');"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       timeout=60,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        print("Falha ao falar:", exc)


def tela_vermelha(texto, segundos):
    try:
        import tkinter as tk
    except ImportError:
        print("tkinter indisponivel; pulando a tela de alerta")
        return

    janela = tk.Tk()
    janela.title("ALERTA JARVIS")
    janela.attributes("-fullscreen", True)
    janela.attributes("-topmost", True)
    janela.configure(bg="#8b0000")

    tk.Label(janela, text="INVASOR DETECTADO", font=("Segoe UI", 72, "bold"),
             fg="white", bg="#8b0000").pack(expand=True)
    tk.Label(janela, text=texto, font=("Segoe UI", 26),
             fg="#ffd7d7", bg="#8b0000", wraplength=1100).pack(expand=True)
    tk.Label(janela, text="Gravacao em andamento - clique para fechar",
             font=("Segoe UI", 16), fg="#ffb3b3", bg="#8b0000").pack(pady=40)

    janela.bind("<Button-1>", lambda _e: janela.destroy())
    janela.bind("<Escape>", lambda _e: janela.destroy())
    janela.after(int(segundos * 1000), janela.destroy)
    janela.mainloop()


def main():
    texto = sys.argv[1] if len(sys.argv) > 1 else TEXTO_PADRAO
    segundos = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    # Fala e tela ao mesmo tempo.
    threading.Thread(target=falar, args=(texto,), daemon=True).start()
    tela_vermelha(texto, segundos)


if __name__ == "__main__":
    main()
