"""YouTube pelo yt-dlp: procura o vídeo e abre direto, sem passar pela busca.

Gratuito e sem login. O yt-dlp só é usado para DESCOBRIR o endereço; quem toca
é o navegador, como se o usuário tivesse clicado. Nada é baixado.
"""
import asyncio

from jarvis.ferramentas import ErroFerramenta, Ferramenta
from jarvis.historico import escolher_musica, ultimo_video

OPCOES = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    "extract_flat": "in_playlist",
    "default_search": "ytsearch",
    "socket_timeout": 10,
}


def _procurar(termo, quantos=1):
    import yt_dlp
    with yt_dlp.YoutubeDL({**OPCOES, "playlist_items": f"1-{quantos}"}) as ydl:
        dados = ydl.extract_info(f"ytsearch{quantos}:{termo}", download=False)
    return dados.get("entries") or []


def _duracao(segundos):
    if not segundos:
        return ""
    minutos, s = divmod(int(segundos), 60)
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h{minutos:02d}" if horas else f"{minutos}:{s:02d}"


def criar(contexto):
    abrir = contexto["abrir"]

    async def tocar_no_youtube(busca):
        try:
            achados = await asyncio.to_thread(_procurar, busca, 1)
        except Exception as exc:
            raise ErroFerramenta(f"a busca no YouTube falhou: {type(exc).__name__}")
        if not achados:
            raise ErroFerramenta(f"não achei nada no YouTube para '{busca}'")
        video = achados[0]
        url = video.get("url") or f"https://www.youtube.com/watch?v={video['id']}"
        await asyncio.to_thread(abrir, url)
        tempo = _duracao(video.get("duration"))
        return f"Tocando {video.get('title', busca)}" + (f", {tempo}." if tempo else ".")

    async def procurar_no_youtube(busca):
        try:
            achados = await asyncio.to_thread(_procurar, busca, 5)
        except Exception as exc:
            raise ErroFerramenta(f"a busca no YouTube falhou: {type(exc).__name__}")
        if not achados:
            return f"Não achei nada para '{busca}'."
        linhas = []
        for i, v in enumerate(achados, 1):
            tempo = _duracao(v.get("duration"))
            linhas.append(f"{i}. {v.get('title', 'sem título')}" + (f" ({tempo})" if tempo else ""))
        return "Achei: " + "; ".join(linhas) + "."

    async def continuar_ultimo_video():
        video = await asyncio.to_thread(ultimo_video)
        if video is None:
            raise ErroFerramenta("não encontrei vídeo do YouTube no histórico do navegador")
        await asyncio.to_thread(abrir, video.url)
        return f"Continuando {video.titulo or 'o último vídeo do histórico'}."

    async def tocar_musica_do_historico():
        video = await asyncio.to_thread(escolher_musica)
        if video is None:
            raise ErroFerramenta("não encontrei música do YouTube no histórico do navegador")
        await asyncio.to_thread(abrir, video.url)
        return f"Escolhi {video.titulo or 'uma música do histórico'}."

    return [
        Ferramenta("tocar_no_youtube",
                   "Procura no YouTube e abre o primeiro resultado no navegador. "
                   "Use para 'toca tal música' ou 'põe tal vídeo'.",
                   tocar_no_youtube,
                   {"busca": {"type": "string", "description": "Música, artista ou assunto."}},
                   ["busca"], resposta_pronta=True),
        Ferramenta("procurar_no_youtube",
                   "Lista os 5 primeiros resultados do YouTube, sem abrir nada.",
                   procurar_no_youtube, {"busca": {"type": "string"}}, ["busca"],
                   resposta_pronta=True),
        Ferramenta("continuar_ultimo_video",
                   "Abre o último vídeo do YouTube registrado no histórico local do navegador.",
                   continuar_ultimo_video, resposta_pronta=True),
        Ferramenta("tocar_musica_do_historico",
                   "Escolhe e abre uma música recente do histórico local do navegador.",
                   tocar_musica_do_historico, resposta_pronta=True),
    ]
