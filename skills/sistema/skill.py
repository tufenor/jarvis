"""Controle do Windows: volume, mídia, janelas, teclado, mouse e tela."""
import asyncio

from jarvis.ferramentas import ErroFerramenta, Ferramenta

TECLAS_PERMITIDAS = {
    "enter", "esc", "tab", "space", "backspace", "delete", "up", "down", "left", "right",
    "home", "end", "pageup", "pagedown", "f5", "f11",
    "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+y", "ctrl+a", "ctrl+s", "ctrl+f",
    "ctrl+w", "ctrl+t", "ctrl+shift+t", "alt+tab", "win+d", "win+e", "win+l",
}


def _volume():
    # pycaw novo (2026) já entrega o EndpointVolume pronto no AudioDevice.
    from pycaw.pycaw import AudioUtilities
    return AudioUtilities.GetSpeakers().EndpointVolume


def criar(contexto):
    import pyautogui
    # Sem a pausa padrão de 0,1 s entre ações: o assistente tem que parecer imediato.
    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True

    async def ajustar_volume(nivel):
        # A API recusa minimum/maximum em inteiro com strict; a faixa é garantida aqui.
        if not 0 <= nivel <= 100:
            raise ErroFerramenta("o volume vai de 0 a 100")
        vol = await asyncio.to_thread(_volume)
        await asyncio.to_thread(vol.SetMasterVolumeLevelScalar, nivel / 100, None)
        from jarvis import dizeres
        return dizeres.volume(nivel)

    async def volume_atual():
        vol = await asyncio.to_thread(_volume)
        atual = round(await asyncio.to_thread(vol.GetMasterVolumeLevelScalar) * 100)
        mudo = await asyncio.to_thread(vol.GetMute)
        from jarvis import dizeres
        frase = dizeres.volume(atual)
        return frase.rstrip(".") + (", mas está no mudo." if mudo else ".")

    async def silenciar(mudo):
        vol = await asyncio.to_thread(_volume)
        await asyncio.to_thread(vol.SetMute, 1 if mudo else 0, None)
        return "Som no mudo." if mudo else "Som de volta."

    async def controlar_midia(acao):
        tecla = {"tocar_pausar": "playpause", "proxima": "nexttrack",
                 "anterior": "prevtrack", "parar": "stop"}[acao]
        await asyncio.to_thread(pyautogui.press, tecla)
        return {"tocar_pausar": "Pronto.", "proxima": "Próxima.",
                "anterior": "Anterior.", "parar": "Parado."}[acao]

    async def listar_janelas():
        import pygetwindow
        titulos = [t for t in await asyncio.to_thread(pygetwindow.getAllTitles) if t.strip()]
        if not titulos:
            return "Nenhuma janela aberta."
        return "Janelas abertas: " + "; ".join(titulos[:15]) + "."

    async def focar_janela(titulo):
        import pygetwindow
        janelas = await asyncio.to_thread(pygetwindow.getWindowsWithTitle, titulo)
        if not janelas:
            raise ErroFerramenta(f"não achei nenhuma janela com '{titulo}'")
        janela = janelas[0]

        def trazer():
            if janela.isMinimized:
                janela.restore()
            janela.activate()
        try:
            await asyncio.to_thread(trazer)
        except Exception as exc:
            raise ErroFerramenta(f"o Windows recusou trazer a janela: {exc}")
        return f"Janela {janela.title} em primeiro plano."

    async def organizar_janela(como):
        # Atalhos nativos do Windows: funcionam na janela que está em foco.
        teclas = {"maximizar": ("win", "up"), "minimizar": ("win", "down"),
                  "esquerda": ("win", "left"), "direita": ("win", "right")}[como]
        await asyncio.to_thread(pyautogui.hotkey, *teclas)
        return "Pronto."

    async def digitar_texto(texto):
        await asyncio.to_thread(pyautogui.typewrite, texto, 0.005)
        return f"Digitei {len(texto)} caracteres."

    async def apertar_tecla(tecla):
        combinacao = tecla.lower().strip()
        if combinacao not in TECLAS_PERMITIDAS:
            raise ErroFerramenta(f"a tecla '{tecla}' não está na lista permitida")
        await asyncio.to_thread(pyautogui.hotkey, *combinacao.split("+"))
        return "Pronto."

    async def ler_area_de_transferencia():
        import pyperclip
        texto = (await asyncio.to_thread(pyperclip.paste) or "").strip()
        if not texto:
            return "A área de transferência está vazia."
        return texto[:1500]

    async def copiar_para_area_de_transferencia(texto):
        import pyperclip
        await asyncio.to_thread(pyperclip.copy, texto)
        return "Copiado."

    async def capturar_tela():
        from datetime import datetime
        from pathlib import Path
        destino = Path.home() / "Pictures" / f"jarvis_{datetime.now():%Y%m%d_%H%M%S}.png"
        destino.parent.mkdir(parents=True, exist_ok=True)
        imagem = await asyncio.to_thread(pyautogui.screenshot)
        await asyncio.to_thread(imagem.save, str(destino))
        return f"Capturei a tela em {destino.name}, na pasta Imagens."

    return [
        Ferramenta("ajustar_volume", "Põe o volume do Windows num valor de 0 a 100.",
                   ajustar_volume,
                   {"nivel": {"type": "integer", "description": "De 0 a 100."}},
                   ["nivel"], resposta_pronta=True),
        Ferramenta("volume_atual", "Diz qual é o volume agora.", volume_atual, resposta_pronta=True),
        Ferramenta("silenciar", "Põe o som no mudo ou tira do mudo.", silenciar,
                   {"mudo": {"type": "boolean"}}, ["mudo"], resposta_pronta=True),
        Ferramenta("controlar_midia",
                   "Controla o que está tocando (YouTube, Spotify, qualquer player).",
                   controlar_midia,
                   {"acao": {"type": "string", "enum": ["tocar_pausar", "proxima", "anterior", "parar"]}},
                   ["acao"], resposta_pronta=True),
        Ferramenta("listar_janelas", "Lista as janelas abertas no PC.", listar_janelas,
                   resposta_pronta=True),
        Ferramenta("focar_janela", "Traz uma janela para a frente pelo título (ou parte dele).",
                   focar_janela,
                   {"titulo": {"type": "string", "description": "Parte do título da janela."}},
                   ["titulo"], resposta_pronta=True),
        Ferramenta("organizar_janela",
                   "Maximiza, minimiza ou encosta a janela atual num lado da tela.",
                   organizar_janela,
                   {"como": {"type": "string", "enum": ["maximizar", "minimizar", "esquerda", "direita"]}},
                   ["como"], resposta_pronta=True),
        Ferramenta("digitar_texto", "Digita um texto onde o cursor estiver.", digitar_texto,
                   {"texto": {"type": "string"}}, ["texto"], perigosa=True,
                   pergunta_confirmacao=lambda a: (
                       f"Confirma digitar {len(a.get('texto', ''))} caracteres no campo atualmente focado?")),
        Ferramenta("apertar_tecla",
                   "Aperta uma tecla ou atalho da lista permitida (ex.: enter, ctrl+s, alt+tab).",
                   apertar_tecla,
                   {"tecla": {"type": "string", "enum": sorted(TECLAS_PERMITIDAS)}},
                   ["tecla"], perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma apertar {a.get('tecla')}?"),
        Ferramenta("ler_area_de_transferencia", "Lê o que está copiado na área de transferência.",
                   ler_area_de_transferencia),
        Ferramenta("copiar_para_area_de_transferencia", "Copia um texto para a área de transferência.",
                   copiar_para_area_de_transferencia,
                   {"texto": {"type": "string"}}, ["texto"], resposta_pronta=True),
        Ferramenta("capturar_tela", "Tira uma foto da tela e salva na pasta Imagens.",
                   capturar_tela, resposta_pronta=True),
    ]
