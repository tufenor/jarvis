"""Rotina opcional de boas-vindas para YouTube, sem credenciais externas."""

from __future__ import annotations

import asyncio

from .historico import escolher_musica, ultimo_video


async def _abrir(abrir, url):
    await asyncio.to_thread(abrir, url)


async def _falar(agente, texto):
    await agente._responder(texto, detalhe_final="boas-vindas concluídas")


async def _esperar_voz(agente, limite_s=60):
    """Espera o Whisper ficar pronto sem impedir o aplicativo de subir."""
    ouvinte = getattr(agente, "ouvinte", None)
    if ouvinte is None:
        return False
    for _ in range(limite_s):
        estado = str(ouvinte.estado.get("whisper", ""))
        if estado.startswith("pronto"):
            return True
        if estado.startswith("erro"):
            return False
        await asyncio.sleep(1)
    return False


async def executar(agente, abrir, config):
    """Executa a conversa de música uma vez depois do login do Windows.

    A primeira resposta negativa ou ausente encerra a rotina. Depois de aceitar
    música, a segunda pergunta decide entre o último vídeo e a escolha recente
    do histórico musical; sem resposta em cinco segundos a segunda opção é usada.
    """
    if not config.get("ativar", False):
        return
    if not getattr(agente, "voz", None) or not getattr(agente, "ouvinte", None):
        return
    try:
        atraso = max(0.0, float(config.get("atraso_s", 8)))
        if atraso:
            await asyncio.sleep(atraso)
        if not await _esperar_voz(agente, int(config.get("esperar_voz_s", 60))):
            agente.painel.registrar("sistema", "Boas-vindas: voz indisponível; rotina não iniciada")
            return

        timeout = max(1.0, float(config.get("timeout_s", 5)))
        primeira = await agente.perguntar_sim_nao("Quer escutar uma música?", timeout)
        from .agente import resposta_sim_nao
        if resposta_sim_nao(primeira or "") is not True:
            return

        await _abrir(abrir, "https://www.youtube.com")
        continuar = await agente.perguntar_sim_nao(
            "Quer continuar vendo o que estava assistindo?", timeout
        )
        if resposta_sim_nao(continuar or "") is True:
            video = await asyncio.to_thread(ultimo_video)
            if video is None:
                await _falar(agente, "Não encontrei um vídeo recente no histórico do navegador.")
                return
            await _abrir(abrir, video.url)
            titulo = video.titulo or "o último vídeo do histórico"
            await _falar(agente, f"Vou continuar {titulo}.")
            return

        musica = await asyncio.to_thread(escolher_musica)
        if musica is None:
            await _falar(agente, "Não encontrei uma música no histórico do navegador.")
            return
        await _abrir(abrir, musica.url)
        titulo = musica.titulo or "uma música do seu histórico"
        await _falar(agente, f"Escolhi {titulo} para você.")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        agente.painel.registrar("erro", f"Boas-vindas de música falharam: {type(exc).__name__}")
