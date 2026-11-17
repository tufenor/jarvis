"""Leitura local e somente leitura do histórico de vídeos dos navegadores.

Chrome, Edge e Brave mantêm o histórico em SQLite, normalmente bloqueado pelo
navegador. O JARVIS copia o arquivo para um temporário, consulta a cópia e a
remove logo depois. Nenhum histórico é enviado para a rede ou salvo pelo
JARVIS.
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse


EPOCA_WEBKIT = 11_644_473_600
_PERFIS = re.compile(r"^Profile .+$")
_MARCADORES_MUSICA = (
    "music", "musica", "música", "official audio", "official video", "lyric",
    "lyrics", "song", "remix", "cover", "playlist", "sertanejo", "funk",
    "rock", "rap", "samba", "pagode", "lofi", "dj", "ao vivo", "live",
)


@dataclass(frozen=True)
class VideoHistorico:
    url: str
    titulo: str
    navegador: str
    visitado_em: datetime | None = None


def _raizes_padrao():
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    return (
        ("Chrome", local / "Google" / "Chrome" / "User Data"),
        ("Edge", local / "Microsoft" / "Edge" / "User Data"),
        ("Brave", local / "BraveSoftware" / "Brave-Browser" / "User Data"),
    )


def _perfis(raiz):
    if not raiz.is_dir():
        return []
    candidatos = [raiz / "Default"]
    candidatos.extend(sorted(p for p in raiz.iterdir() if p.is_dir() and _PERFIS.match(p.name)))
    return [p for p in candidatos if (p / "History").is_file()]


def _copiar_para_temporario(origem):
    fd, destino = tempfile.mkstemp(prefix="jarvis_history_", suffix=".db")
    os.close(fd)
    try:
        shutil.copyfile(origem, destino)
    except OSError:
        try:
            Path(destino).unlink()
        except OSError:
            pass
        return None
    return Path(destino)


def _video_da_url(url):
    try:
        partes = urlparse(url)
    except ValueError:
        return None
    host = (partes.hostname or "").lower().removeprefix("www.")
    if host not in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        return None
    if partes.path != "/watch":
        return None
    video_id = parse_qs(partes.query).get("v", [""])[0].strip()
    if not video_id or len(video_id) > 100 or not re.fullmatch(r"[A-Za-z0-9_-]+", video_id):
        return None
    return video_id


def _data_webkit(valor):
    try:
        micros = int(valor)
        if micros <= 0:
            return None
        return datetime.fromtimestamp(micros / 1_000_000 - EPOCA_WEBKIT, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _ler_banco(caminho, navegador, limite):
    copia = _copiar_para_temporario(caminho)
    if copia is None:
        return []
    try:
        with sqlite3.connect(str(copia)) as banco:
            linhas = banco.execute(
                """
                SELECT url, title, last_visit_time
                  FROM urls
                 WHERE url LIKE '%youtube.com/watch?v=%'
                 ORDER BY last_visit_time DESC
                 LIMIT ?
                """,
                (limite,),
            ).fetchall()
    except (OSError, sqlite3.DatabaseError):
        return []
    finally:
        try:
            copia.unlink()
        except OSError:
            pass

    vistos = set()
    resultado = []
    for url, titulo, ultima_visita in linhas:
        video_id = _video_da_url(url or "")
        if not video_id or video_id in vistos:
            continue
        vistos.add(video_id)
        resultado.append(VideoHistorico(
            url=url,
            titulo=(titulo or "").strip(),
            navegador=navegador,
            visitado_em=_data_webkit(ultima_visita),
        ))
    return resultado


def ler_historico_youtube(raizes=None, limite_por_banco=100):
    """Retorna vídeos assistidos, do mais recente para o mais antigo.

    ``raizes`` existe para diagnóstico e testes: uma sequência de pares
    ``(nome_do_navegador, pasta_User_Data)``. No uso normal os três navegadores
    locais são detectados automaticamente.
    """
    registros = []
    for navegador, raiz in (raizes or _raizes_padrao()):
        for perfil in _perfis(Path(raiz)):
            registros.extend(_ler_banco(perfil / "History", navegador, limite_por_banco))
    registros.sort(key=lambda item: item.visitado_em or datetime.min.replace(tzinfo=timezone.utc),
                   reverse=True)
    return registros


def ultimo_video(raizes=None):
    """Devolve o último vídeo do YouTube ou ``None`` quando não há histórico."""
    return next(iter(ler_historico_youtube(raizes=raizes, limite_por_banco=30)), None)


def escolher_musica(raizes=None):
    """Escolhe uma entrada recente do histórico que pareça música.

    O histórico do navegador não informa o gênero. A escolha usa o título e,
    se nenhum título tiver marcador musical, devolve o vídeo mais recente como
    fallback local; assim a rotina continua útil sem inventar uma música nem
    consultar uma conta externa.
    """
    videos = ler_historico_youtube(raizes=raizes, limite_por_banco=100)
    if not videos:
        return None
    for video in videos:
        texto = f"{video.titulo} {video.url}".casefold()
        if any(marcador in texto for marcador in _MARCADORES_MUSICA):
            return video
    return videos[0]
