"""Programação local com escopo e confirmações explícitos.

Esta skill não é um terminal genérico. Ela só acessa arquivos de código dentro
da raiz configurada e só grava ou executa testes depois da confirmação normal
do agente. Testes são runners fixos; o modelo não fornece um shell arbitrário.
"""
import asyncio
import os
import sys
from pathlib import Path

from jarvis.ferramentas import ErroFerramenta, Ferramenta

RAIZ_PADRAO = Path("C:/JARVIS/projetos")
EXTENSOES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css",
    ".md", ".yaml", ".yml", ".ps1", ".bat",
}
PASTAS_IGNORADAS = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}
ARQUIVOS_SENSIVEIS = {
    ".env", "config_local.json", "token.txt", "alexa.json", "alexa_ca.pem",
}
MAX_LISTA = 120
MAX_LEITURA = 12000
MAX_ESCRITA = 200000
MAX_TESTE_S = 30


def _raiz(contexto):
    config = (contexto or {}).get("config") or {}
    caminho = (config.get("programacao") or {}).get("raiz", str(RAIZ_PADRAO))
    return Path(caminho).expanduser().resolve()


def _sensivel(alvo):
    nome = alvo.name.casefold()
    return nome in ARQUIVOS_SENSIVEIS or nome.startswith(".env.")


def _arquivo(raiz, caminho, exigir_extensao=True):
    texto = (caminho or "").strip()
    if not texto:
        raise ErroFerramenta("diga qual arquivo do projeto")
    alvo = Path(texto).expanduser()
    if not alvo.is_absolute():
        alvo = raiz / alvo
    try:
        alvo = alvo.resolve()
        alvo.relative_to(raiz)
    except (OSError, ValueError):
        raise ErroFerramenta("só posso acessar arquivos dentro da pasta de projetos permitida")
    if _sensivel(alvo):
        raise ErroFerramenta("não acesso arquivos de credenciais ou segredos por esta skill")
    if exigir_extensao and alvo.suffix.casefold() not in EXTENSOES:
        raise ErroFerramenta("essa extensão não está permitida para a skill de programação")
    return alvo


def _relativo(raiz, alvo):
    return str(alvo.relative_to(raiz)).replace("\\", "/")


def _listar(raiz, pasta):
    base = raiz if not pasta else _arquivo(raiz, pasta, exigir_extensao=False)
    if not base.exists():
        raise ErroFerramenta(f"não achei a pasta {pasta or raiz.name}")
    if not base.is_dir():
        raise ErroFerramenta(f"{pasta} não é uma pasta")
    itens = []
    for atual, dirs, arquivos in os.walk(base):
        dirs[:] = [d for d in dirs if d not in PASTAS_IGNORADAS and not d.startswith(".")]
        for nome in arquivos:
            alvo = Path(atual) / nome
            if alvo.suffix.casefold() in EXTENSOES and not _sensivel(alvo):
                itens.append(_relativo(raiz, alvo))
                if len(itens) >= MAX_LISTA:
                    return itens
    return sorted(itens)


def _conteudo(texto):
    if not isinstance(texto, str) or not texto.strip():
        raise ErroFerramenta("o conteúdo do código está vazio")
    if len(texto) > MAX_ESCRITA:
        raise ErroFerramenta(f"o arquivo excede o limite de {MAX_ESCRITA} caracteres")
    return texto


async def _executar_teste(raiz, alvo, modo):
    if modo == "sintaxe":
        if alvo.is_dir():
            raise ErroFerramenta("diga o arquivo Python ou JavaScript cuja sintaxe quer testar")
        if alvo.suffix.casefold() == ".py":
            comando = [sys.executable, "-m", "py_compile", str(alvo)]
        elif alvo.suffix.casefold() == ".js":
            comando = ["node", "--check", str(alvo)]
        else:
            return "Só há teste de sintaxe automático para Python e JavaScript."
    elif modo == "unittest":
        pasta_testes = raiz / "tests"
        if not pasta_testes.is_dir():
            raise ErroFerramenta("não achei a pasta tests dentro do projeto")
        comando = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
    else:
        raise ErroFerramenta("modo de teste inválido; use sintaxe ou unittest")
    try:
        processo = await asyncio.create_subprocess_exec(
            *comando, cwd=str(raiz), stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise ErroFerramenta("o executor necessário para esse teste não está instalado") from exc
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), MAX_TESTE_S)
    except asyncio.TimeoutError:
        processo.kill()
        await processo.wait()
        raise ErroFerramenta(f"o teste passou de {MAX_TESTE_S} segundos e foi interrompido")
    texto = (saida or b"").decode("utf-8", "replace").strip()
    if processo.returncode != 0:
        raise ErroFerramenta(f"o teste falhou ({processo.returncode}): {texto[-1200:]}")
    return texto[-1200:] or "Teste concluído sem saída."


def criar(contexto):
    raiz = _raiz(contexto)

    async def listar_projeto(pasta=""):
        itens = await asyncio.to_thread(_listar, raiz, pasta)
        if not itens:
            return "Não achei arquivos de código nessa pasta do projeto."
        extra = " A lista foi limitada." if len(itens) >= MAX_LISTA else ""
        return "Arquivos de código: " + "; ".join(itens) + "." + extra

    async def ler_codigo(caminho):
        alvo = _arquivo(raiz, caminho)
        if not alvo.is_file():
            raise ErroFerramenta(f"não achei o arquivo {_relativo(raiz, alvo)}")
        texto = await asyncio.to_thread(alvo.read_text, encoding="utf-8", errors="replace")
        return f"Arquivo {_relativo(raiz, alvo)}:\n{texto[:MAX_LEITURA]}"

    async def criar_codigo(caminho, conteudo):
        alvo = _arquivo(raiz, caminho)
        conteudo = _conteudo(conteudo)
        if alvo.exists():
            raise ErroFerramenta("esse arquivo já existe; peça para editar em vez de criar")
        await asyncio.to_thread(alvo.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(alvo.write_text, conteudo, encoding="utf-8", newline="\n")
        return f"Criei {_relativo(raiz, alvo)} com {len(conteudo)} caracteres."

    async def editar_codigo(caminho, conteudo):
        alvo = _arquivo(raiz, caminho)
        conteudo = _conteudo(conteudo)
        if not alvo.is_file():
            raise ErroFerramenta(f"não achei o arquivo {_relativo(raiz, alvo)}")
        await asyncio.to_thread(alvo.write_text, conteudo, encoding="utf-8", newline="\n")
        return f"Atualizei {_relativo(raiz, alvo)} com {len(conteudo)} caracteres."

    async def testar_codigo(caminho="", modo="sintaxe"):
        alvo = raiz if not caminho else _arquivo(raiz, caminho)
        if caminho and not alvo.is_file():
            raise ErroFerramenta(f"não achei o arquivo {_relativo(raiz, alvo)}")
        return await _executar_teste(raiz, alvo, modo)

    confirmar_criacao = lambda a: (
        f"Confirma criar o arquivo {a.get('caminho')} na pasta de projetos?"
    )
    confirmar_edicao = lambda a: (
        f"Confirma editar o arquivo {a.get('caminho')} na pasta de projetos?"
    )
    return [
        Ferramenta(
            "listar_projeto", "Lista arquivos de código na pasta de projetos permitida.",
            listar_projeto, {"pasta": {"type": "string"}}, resposta_pronta=False,
        ),
        Ferramenta(
            "ler_codigo", "Lê um arquivo de código permitido para análise, sem alterá-lo.",
            ler_codigo, {"caminho": {"type": "string"}}, ["caminho"], resposta_pronta=False,
        ),
        Ferramenta(
            "criar_codigo", "Cria um novo arquivo de código dentro da pasta permitida.",
            criar_codigo, {"caminho": {"type": "string"}, "conteudo": {"type": "string"}},
            ["caminho", "conteudo"], perigosa=True, pergunta_confirmacao=confirmar_criacao,
            resposta_pronta=True,
        ),
        Ferramenta(
            "editar_codigo", "Substitui o conteúdo de um arquivo de código permitido.",
            editar_codigo, {"caminho": {"type": "string"}, "conteudo": {"type": "string"}},
            ["caminho", "conteudo"], perigosa=True, pergunta_confirmacao=confirmar_edicao,
            resposta_pronta=True,
        ),
        Ferramenta(
            "testar_codigo", "Executa somente teste de sintaxe ou unittest dentro do projeto.",
            testar_codigo,
            {"caminho": {"type": "string"}, "modo": {"type": "string", "enum": ["sintaxe", "unittest"]}},
            [], perigosa=True,
            pergunta_confirmacao=lambda a: f"Confirma testar código no projeto no modo {a.get('modo', 'sintaxe')}?",
            resposta_pronta=False,
        ),
    ]
