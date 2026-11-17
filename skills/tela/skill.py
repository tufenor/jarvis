"""Leitura visual da tela com Claude Vision e controle livre de mouse e teclado.

A automacao_visual é mais segura para controles identificáveis por texto
(botão "Enviar" etc.). Esta skill cobre o resto: apontar o olho na tela e agir
por coordenadas quando o layout não expõe UI Automation (Electron, jogos,
desenho, canvas etc.).
"""
import asyncio
import base64
import io
import json
import os

from jarvis.ferramentas import ErroFerramenta, Ferramenta

MODELO_VISAO = os.environ.get("JARVIS_MODELO_VISAO", "claude-haiku-5-5")
LIMITE_LARGURA = 1600          # a API da Anthropic recomenda imagem não grande
TAMANHO_TELA_PX = None         # preenchido no primeiro uso


def _cliente():
    try:
        import anthropic
    except ImportError as exc:
        raise ErroFerramenta("falta o pacote anthropic; pip install anthropic") from exc
    return anthropic.AsyncAnthropic(max_retries=1, timeout=60)


def _tela_png():
    import pyautogui
    from PIL import Image
    global TAMANHO_TELA_PX
    imagem = pyautogui.screenshot()
    TAMANHO_TELA_PX = imagem.size
    if imagem.width > LIMITE_LARGURA:
        proporcao = LIMITE_LARGURA / imagem.width
        imagem = imagem.resize((LIMITE_LARGURA, int(imagem.height * proporcao)), Image.LANCZOS)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _coord_valida(x, y):
    import pyautogui
    larg, alt = pyautogui.size()
    if not (0 <= x < larg and 0 <= y < alt):
        raise ErroFerramenta(f"coordenada ({x}, {y}) fora da tela ({larg}x{alt})")


def criar(_contexto):
    import pyautogui
    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True   # canto superior esquerdo aborta: segurança

    async def ler_tela(pergunta=""):
        pergunta = (pergunta or "O que está na tela agora?").strip()
        png = await asyncio.to_thread(_tela_png)
        cliente = _cliente()
        try:
            resposta = await cliente.messages.create(
                model=MODELO_VISAO,
                max_tokens=600,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png",
                            "data": base64.b64encode(png).decode(),
                        }},
                        {"type": "text", "text":
                         f"Responda em português do Brasil, em até 3 frases curtas, "
                         f"somente com o que estiver visível na imagem. Pergunta: {pergunta}"},
                    ],
                }],
            )
        except Exception as exc:
            raise ErroFerramenta(f"a API da Anthropic recusou a leitura: {type(exc).__name__}")
        partes = [b.text for b in resposta.content if getattr(b, "type", "") == "text"]
        texto = " ".join(partes).strip()
        return texto or "A tela está em branco."

    async def encontrar_na_tela(descricao):
        png = await asyncio.to_thread(_tela_png)
        larg_imagem, alt_imagem = TAMANHO_TELA_PX  # tamanho REAL da tela
        cliente = _cliente()
        prompt = (
            "Procure na imagem o elemento descrito e devolva SÓ um JSON "
            '{"x": int, "y": int, "o_que": "texto curto"} com as coordenadas em pixels '
            "no centro do elemento. Se não achar, devolva {\"x\": null, \"y\": null, \"o_que\": \"não achei\"}. "
            f"A imagem tem {larg_imagem} por {alt_imagem} pixels. "
            f"Descrição: {descricao}"
        )
        try:
            resposta = await cliente.messages.create(
                model=MODELO_VISAO, max_tokens=120,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": "image/png",
                            "data": base64.b64encode(png).decode(),
                        }},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
        except Exception as exc:
            raise ErroFerramenta(f"a API da Anthropic recusou: {type(exc).__name__}")
        bruto = next((b.text for b in resposta.content if getattr(b, "type", "") == "text"), "")
        inicio, fim = bruto.find("{"), bruto.rfind("}")
        if inicio < 0 or fim < 0:
            raise ErroFerramenta(f"a visão não devolveu coordenadas: {bruto[:120]}")
        try:
            dados = json.loads(bruto[inicio:fim + 1])
        except json.JSONDecodeError:
            raise ErroFerramenta("a visão devolveu JSON inválido")
        x, y = dados.get("x"), dados.get("y")
        if x is None or y is None:
            return f"Não achei '{descricao}' na tela."
        return f"Achei em ({int(x)}, {int(y)}): {dados.get('o_que', descricao)}."

    async def mover_mouse(x, y):
        _coord_valida(x, y)
        await asyncio.to_thread(pyautogui.moveTo, x, y, 0.1)
        return f"Mouse em ({x}, {y})."

    async def clicar_em(x, y, botao="esquerdo"):
        _coord_valida(x, y)
        mapa = {"esquerdo": "left", "direito": "right", "meio": "middle"}
        botao_py = mapa.get(botao, "left")
        await asyncio.to_thread(pyautogui.click, x, y, button=botao_py)
        return f"Cliquei ({botao}) em ({x}, {y})."

    async def clique_duplo(x, y):
        _coord_valida(x, y)
        await asyncio.to_thread(pyautogui.doubleClick, x, y)
        return f"Clique duplo em ({x}, {y})."

    async def arrastar(x_inicio, y_inicio, x_fim, y_fim):
        _coord_valida(x_inicio, y_inicio)
        _coord_valida(x_fim, y_fim)

        def executar():
            pyautogui.moveTo(x_inicio, y_inicio, 0.1)
            pyautogui.dragTo(x_fim, y_fim, 0.3, button="left")
        await asyncio.to_thread(executar)
        return f"Arrastei de ({x_inicio}, {y_inicio}) para ({x_fim}, {y_fim})."

    async def rolar(direcao, quantidade=3):
        if not 1 <= quantidade <= 20:
            raise ErroFerramenta("rolagem fica entre 1 e 20 passos")
        passos = quantidade * (1 if direcao == "cima" else -1)
        await asyncio.to_thread(pyautogui.scroll, passos * 100)
        return f"Rolei {quantidade} passos para {direcao}."

    async def apertar_tecla_livre(tecla):
        combinacao = (tecla or "").strip().lower()
        if not combinacao:
            raise ErroFerramenta("diga qual tecla apertar")
        # Partes: separa por + e confere contra o set do pyautogui. Isso impede
        # strings aleatórias que o pyautogui interpretaria como digitação.
        partes = [p.strip() for p in combinacao.split("+") if p.strip()]
        import pyautogui as pag
        validas = set(pag.KEYBOARD_KEYS)
        ruins = [p for p in partes if p not in validas]
        if ruins:
            raise ErroFerramenta(f"tecla desconhecida: {', '.join(ruins)}")
        await asyncio.to_thread(pyautogui.hotkey, *partes)
        return f"Apertei {combinacao}."

    async def digitar_texto_livre(texto):
        if not isinstance(texto, str) or not texto:
            raise ErroFerramenta("nada para digitar")
        if len(texto) > 2000:
            raise ErroFerramenta("texto grande demais; máximo 2000 caracteres")
        await asyncio.to_thread(pyautogui.typewrite, texto, 0.005)
        return f"Digitei {len(texto)} caracteres."

    return [
        Ferramenta("ler_tela",
                   "Olha a tela e responde em uma ou duas frases o que está visível. "
                   "Opcional: 'pergunta' direciona o que procurar (ex.: 'resumir este email').",
                   ler_tela, {"pergunta": {"type": "string"}}, [], resposta_pronta=True),
        Ferramenta("encontrar_na_tela",
                   "Procura visualmente um elemento e devolve suas coordenadas (x, y). "
                   "Use antes de clicar em algo sem saber a posição.",
                   encontrar_na_tela, {"descricao": {"type": "string"}},
                   ["descricao"], resposta_pronta=True),
        Ferramenta("mover_mouse", "Move o mouse até a coordenada.",
                   mover_mouse, {"x": {"type": "integer"}, "y": {"type": "integer"}},
                   ["x", "y"], resposta_pronta=True),
        Ferramenta("clicar_em",
                   "Clica numa coordenada da tela. Botão: esquerdo (padrão), direito ou meio.",
                   clicar_em,
                   {"x": {"type": "integer"}, "y": {"type": "integer"},
                    "botao": {"type": "string", "enum": ["esquerdo", "direito", "meio"]}},
                   ["x", "y"], perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma clicar em ({a.get('x')}, {a.get('y')})?"),
        Ferramenta("clique_duplo", "Clique duplo numa coordenada.", clique_duplo,
                   {"x": {"type": "integer"}, "y": {"type": "integer"}},
                   ["x", "y"], perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma o clique duplo em ({a.get('x')}, {a.get('y')})?"),
        Ferramenta("arrastar", "Arrasta de uma coordenada a outra com botão esquerdo pressionado.",
                   arrastar,
                   {"x_inicio": {"type": "integer"}, "y_inicio": {"type": "integer"},
                    "x_fim": {"type": "integer"}, "y_fim": {"type": "integer"}},
                   ["x_inicio", "y_inicio", "x_fim", "y_fim"], perigosa=True,
                   pergunta_confirmacao=lambda a: (
                       f"Confirma arrastar de ({a.get('x_inicio')}, {a.get('y_inicio')}) "
                       f"para ({a.get('x_fim')}, {a.get('y_fim')})?")),
        Ferramenta("rolar",
                   "Rola a janela sob o mouse. Direção: cima ou baixo. Quantidade em passos (1 a 20).",
                   rolar,
                   {"direcao": {"type": "string", "enum": ["cima", "baixo"]},
                    "quantidade": {"type": "integer"}},
                   ["direcao"], resposta_pronta=True),
        Ferramenta("apertar_tecla_livre",
                   "Aperta qualquer tecla ou atalho reconhecido pelo pyautogui "
                   "(ex.: f3, ctrl+alt+del, win+shift+s).",
                   apertar_tecla_livre, {"tecla": {"type": "string"}},
                   ["tecla"], perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma apertar {a.get('tecla')}?"),
        Ferramenta("digitar_texto_livre",
                   "Digita qualquer texto onde o cursor estiver. Máximo 2000 caracteres.",
                   digitar_texto_livre, {"texto": {"type": "string"}},
                   ["texto"], perigosa=True,
                   pergunta_confirmacao=lambda a: (
                       f"Confirma digitar {len(a.get('texto', ''))} caracteres no campo atualmente focado?")),
    ]
