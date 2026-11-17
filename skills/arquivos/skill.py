"""Arquivos do usuário: procurar, abrir, criar pasta, renomear, mandar para a lixeira.

Fica dentro das pastas pessoais (Documentos, Downloads, Imagens, Vídeos, Música,
Área de Trabalho). Pastas do Windows e de programas ficam de fora: um erro de
transcrição não pode encostar em C:\\Windows.

Apagar NUNCA é definitivo — vai para a Lixeira, de onde o usuário desfaz.
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path

from jarvis.ferramentas import ErroFerramenta, Ferramenta

LIMITE_LISTA = 20
LIMITE_LEITURA = 4000
TEXTO = {".txt", ".md", ".py", ".json", ".csv", ".log", ".ini", ".yaml", ".yml", ".bat", ".js", ".html", ".css"}


def pastas_permitidas():
    casa = Path.home()
    nomes = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music",
             "Área de Trabalho", "Documentos", "Imagens", "Vídeos", "Músicas"]
    return [casa / n for n in nomes if (casa / n).is_dir()]


def dentro_do_permitido(caminho, permitidas):
    try:
        resolvido = Path(caminho).expanduser().resolve()
    except OSError:
        return None
    for raiz in permitidas:
        try:
            resolvido.relative_to(raiz.resolve())
            return resolvido
        except ValueError:
            continue
    return None


def descrever(p):
    try:
        tamanho = p.stat().st_size
        quando = datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m")
    except OSError:
        return p.name
    if p.is_dir():
        return f"{p.name} (pasta)"
    if tamanho >= 1024 * 1024:
        medida = f"{tamanho / 1024 / 1024:.1f} MB"
    else:
        medida = f"{max(1, tamanho // 1024)} KB"
    return f"{p.name} ({medida}, {quando})"


def criar(contexto):
    permitidas = pastas_permitidas()
    nomes_amigaveis = ", ".join(p.name for p in permitidas)

    def _resolver(caminho):
        alvo = dentro_do_permitido(caminho, permitidas)
        if alvo is None:
            raise ErroFerramenta(f"só posso mexer nas suas pastas pessoais ({nomes_amigaveis})")
        return alvo

    async def procurar_arquivo(nome, pasta=None):
        raizes = [_resolver(pasta)] if pasta else permitidas

        def varrer():
            achados = []
            procurado = nome.lower()
            for raiz in raizes:
                for atual, dirs, arquivos in os.walk(raiz):
                    dirs[:] = [d for d in dirs if not d.startswith(".")][:40]
                    for a in arquivos:
                        if procurado in a.lower():
                            achados.append(Path(atual) / a)
                            if len(achados) >= LIMITE_LISTA:
                                return achados
            return achados
        achados = await asyncio.to_thread(varrer)
        if not achados:
            return f"Não achei nenhum arquivo com '{nome}' nas suas pastas."
        lista = "; ".join(f"{p.name} em {p.parent.name}" for p in achados[:8])
        extra = f" e mais {len(achados) - 8}" if len(achados) > 8 else ""
        return f"Achei {len(achados)}: {lista}{extra}."

    async def listar_pasta(pasta):
        alvo = _resolver(pasta)
        if not alvo.is_dir():
            raise ErroFerramenta(f"{alvo.name} não é uma pasta")
        itens = await asyncio.to_thread(lambda: sorted(alvo.iterdir())[:LIMITE_LISTA])
        if not itens:
            return f"A pasta {alvo.name} está vazia."
        return f"Em {alvo.name}: " + "; ".join(descrever(p) for p in itens) + "."

    async def abrir_arquivo(caminho):
        alvo = _resolver(caminho)
        if not alvo.exists():
            raise ErroFerramenta(f"não achei {alvo.name}")
        await asyncio.to_thread(os.startfile, str(alvo))
        return f"Abri {alvo.name}."

    async def ler_arquivo_de_texto(caminho):
        alvo = _resolver(caminho)
        if not alvo.is_file():
            raise ErroFerramenta(f"não achei o arquivo {alvo.name}")
        if alvo.suffix.lower() not in TEXTO:
            raise ErroFerramenta(f"{alvo.suffix} não é um arquivo de texto que eu saiba ler")
        conteudo = await asyncio.to_thread(alvo.read_text, encoding="utf-8", errors="replace")
        return conteudo[:LIMITE_LEITURA] or "O arquivo está vazio."

    async def criar_pasta(caminho):
        alvo = _resolver(caminho)
        if alvo.exists():
            raise ErroFerramenta(f"{alvo.name} já existe")
        await asyncio.to_thread(alvo.mkdir, parents=True)
        return f"Criei a pasta {alvo.name}."

    async def renomear(caminho, novo_nome):
        alvo = _resolver(caminho)
        if not alvo.exists():
            raise ErroFerramenta(f"não achei {alvo.name}")
        if any(c in novo_nome for c in '\\/:*?"<>|'):
            raise ErroFerramenta("esse nome tem caractere que o Windows não aceita")
        destino = alvo.with_name(novo_nome)
        if destino.exists():
            raise ErroFerramenta(f"já existe algo chamado {novo_nome}")
        await asyncio.to_thread(alvo.rename, destino)
        return f"Renomeei para {novo_nome}."

    async def mandar_para_lixeira(caminho):
        from send2trash import send2trash
        alvo = _resolver(caminho)
        if not alvo.exists():
            raise ErroFerramenta(f"não achei {alvo.name}")
        await asyncio.to_thread(send2trash, str(alvo))
        return f"Mandei {alvo.name} para a Lixeira. Dá para restaurar de lá."

    return [
        Ferramenta("procurar_arquivo",
                   "Procura um arquivo pelo nome nas pastas pessoais do usuário.",
                   procurar_arquivo,
                   {"nome": {"type": "string", "description": "Parte do nome do arquivo."},
                    "pasta": {"type": "string", "description": "Opcional: onde procurar."}},
                   ["nome"], resposta_pronta=True),
        Ferramenta("listar_pasta", "Lista o que tem dentro de uma pasta.", listar_pasta,
                   {"pasta": {"type": "string"}}, ["pasta"], resposta_pronta=True),
        Ferramenta("abrir_arquivo", "Abre um arquivo no programa padrão do Windows.", abrir_arquivo,
                   {"caminho": {"type": "string"}}, ["caminho"], resposta_pronta=True),
        Ferramenta("ler_arquivo_de_texto",
                   "Lê o conteúdo de um arquivo de texto para o JARVIS poder comentar.",
                   ler_arquivo_de_texto, {"caminho": {"type": "string"}}, ["caminho"]),
        Ferramenta("criar_pasta", "Cria uma pasta nova.", criar_pasta,
                   {"caminho": {"type": "string"}}, ["caminho"], resposta_pronta=True),
        Ferramenta("renomear", "Renomeia um arquivo ou pasta.", renomear,
                   {"caminho": {"type": "string"}, "novo_nome": {"type": "string"}},
                   ["caminho", "novo_nome"], resposta_pronta=True),
        Ferramenta("mandar_para_lixeira",
                   "Manda um arquivo ou pasta para a Lixeira do Windows (dá para restaurar).",
                   mandar_para_lixeira, {"caminho": {"type": "string"}}, ["caminho"],
                   perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma mandar {Path(a['caminho']).name} para a Lixeira?",
                   resposta_pronta=True),
    ]
