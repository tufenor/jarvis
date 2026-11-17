"""Automação de controles visíveis do Windows via UI Automation.

Leitura e escrita são separadas de propósito: ler a árvore de controles não
altera a máquina; clicar e preencher um formulário sempre passa pela
confirmação falada do agente.
"""
import asyncio
import time
from contextlib import contextmanager

from jarvis.ferramentas import ErroFerramenta, Ferramenta

INTERATIVOS = {
    "Button", "CheckBox", "ComboBox", "Edit", "Hyperlink", "ListItem",
    "MenuItem", "RadioButton", "TabItem", "TreeItem", "Document",
}
LIMITE_LEITURA_S = 3.0
LIMITE_CONTROLES = 80


def _desktop():
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise ErroFerramenta(
            "a automação visual não está instalada; instale pywinauto e reinicie o JARVIS"
        ) from exc
    return Desktop(backend="uia")


@contextmanager
def _com_thread():
    """Inicializa COM no worker usado pelo asyncio.to_thread.

    UI Automation exige um apartamento COM por thread. Sem isso, WebView2 e
    outros controles podem devolver access violation em vez de uma exceção
    Python quando a skill é chamada pelo próprio JARVIS.
    """
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        pythoncom = None
    try:
        yield
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def _janela(titulo):
    alvo = (titulo or "").strip().casefold()
    if not alvo:
        raise ErroFerramenta("diga o título ou parte do título da janela")
    candidatas = []
    for janela in _desktop().windows(visible_only=True):
        try:
            nome = janela.window_text().strip()
        except Exception:
            continue
        if nome and alvo in nome.casefold():
            candidatas.append(janela)
    if not candidatas:
        raise ErroFerramenta(f"não achei a janela visível '{titulo}'")
    if len(candidatas) > 1:
        nomes = ", ".join(j.window_text().strip() for j in candidatas[:4])
        raise ErroFerramenta(f"há mais de uma janela correspondente: {nomes}")
    return candidatas[0]


def _controles(janela, nome=None, tipo=None):
    esperado = (nome or "").strip().casefold()
    tipo_original = (tipo or "").strip()
    tipo = tipo_original.casefold()
    if not esperado and not tipo:
        raise ErroFerramenta(
            "para não travar o Windows, informe o nome ou o tipo do controle"
        )
    janela_obj = _janela(janela)
    encontrados = []
    inicio = time.monotonic()
    filtros = {"depth": 8}
    if tipo:
        filtros["control_type"] = tipo_original
    try:
        controles = janela_obj.iter_descendants(**filtros)
    except (AttributeError, TypeError):
        controles = iter(janela_obj.descendants(**filtros))
    for controle in controles:
        if time.monotonic() - inicio > LIMITE_LEITURA_S:
            break
        try:
            info = controle.element_info
            texto = (info.name or "").strip()
            classe = (info.control_type or "").strip()
            if classe not in INTERATIVOS:
                continue
            if esperado and esperado not in texto.casefold():
                continue
            if tipo and tipo != classe.casefold():
                continue
            if not controle.is_visible() or not controle.is_enabled():
                continue
            encontrados.append(controle)
            if len(encontrados) >= LIMITE_CONTROLES:
                break
        except Exception:
            continue
    return encontrados


def _listar_textos(janela, nome, tipo):
    with _com_thread():
        return [_descricao(c) for c in _controles(janela, nome, tipo)[:80]]


def _clicar(janela, nome, tipo):
    with _com_thread():
        controles = _controles(janela, nome, tipo)
        if not controles:
            raise ErroFerramenta("não achei esse controle visível")
        if len(controles) > 1:
            opcoes = "; ".join(_descricao(c) for c in controles[:4])
            raise ErroFerramenta(f"o alvo não é único: {opcoes}")
        try:
            controles[0].click_input()
        except Exception as exc:
            raise ErroFerramenta(f"o Windows recusou o clique: {type(exc).__name__}") from exc
        return f"Cliquei em {_descricao(controles[0])}."


def _preencher(janela, nome, texto, tipo):
    with _com_thread():
        controles = _controles(janela, nome, tipo)
        if not controles:
            raise ErroFerramenta("não achei esse campo visível")
        if len(controles) > 1:
            opcoes = "; ".join(_descricao(c) for c in controles[:4])
            raise ErroFerramenta(f"o campo não é único: {opcoes}")
        try:
            controles[0].set_edit_text(texto)
        except Exception as exc:
            raise ErroFerramenta(f"não consegui preencher o campo: {type(exc).__name__}") from exc
        return f"Preenchi {_descricao(controles[0])}."


def _descricao(controle):
    info = controle.element_info
    texto = (info.name or "").strip().replace("\n", " ")
    # Não devolve texto de campos de senha nem o valor digitado pelo usuário.
    if (info.control_type or "").casefold() == "edit" and getattr(info, "is_password", False):
        texto = "campo protegido"
    return f"{info.control_type or 'controle'} '{texto[:100]}'"


def criar(_contexto):
    async def listar_controles(titulo, nome="", tipo=""):
        linhas = await asyncio.to_thread(_listar_textos, titulo, nome, tipo)
        if not linhas:
            return "Nenhum controle visível corresponde a esse filtro."
        return "Controles visíveis: " + "; ".join(linhas) + "."

    async def clicar_controle(titulo, nome, tipo=""):
        return await asyncio.to_thread(_clicar, titulo, nome, tipo)

    async def preencher_controle(titulo, nome, texto, tipo="Edit"):
        return await asyncio.to_thread(_preencher, titulo, nome, texto, tipo)

    return [
        Ferramenta(
            "listar_controles_tela",
            "Lê nomes e tipos dos controles visíveis numa janela, sem clicar nem alterar nada.",
            listar_controles,
            {"titulo": {"type": "string", "description": "Título ou parte do título da janela."},
             "nome": {"type": "string", "description": "Texto do controle, se quiser filtrar."},
             "tipo": {"type": "string", "description": "Tipo opcional: Button, Edit, Hyperlink ou outro."}},
            ["titulo"],
        ),
        Ferramenta(
            "clicar_controle_tela",
            "Clica num controle visível identificado pelo título da janela e pelo texto do controle.",
            clicar_controle,
            {"titulo": {"type": "string"}, "nome": {"type": "string"},
             "tipo": {"type": "string"}},
            ["titulo", "nome"], perigosa=True,
            pergunta_confirmacao=lambda a: f"Confirma clicar em {a.get('nome')} na janela {a.get('titulo')}?",
        ),
        Ferramenta(
            "preencher_controle_tela",
            "Preenche um campo Edit visível. Nunca lê nem repete o valor do campo.",
            preencher_controle,
            {"titulo": {"type": "string"}, "nome": {"type": "string"},
             "texto": {"type": "string"}, "tipo": {"type": "string"}},
            ["titulo", "nome", "texto"], perigosa=True,
            pergunta_confirmacao=lambda a: f"Confirma preencher o campo {a.get('nome')} na janela {a.get('titulo')}?",
        ),
    ]
