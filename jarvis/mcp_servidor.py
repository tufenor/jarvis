"""Conector MCP: deixa o Claude Desktop (ou outro cliente MCP) operar o JARVIS.

Não é um segundo JARVIS. É uma ponte fina: cada ferramenta vira uma chamada
HTTP para o JARVIS que já está rodando na máquina (127.0.0.1), aproveitando a
validação, o registro no painel e as skills que já existem.

O que NÃO passa por aqui:
- Ação perigosa (suspender o PC, comando livre, instalar programa, apagar
  arquivo). A confirmação do JARVIS é FALADA, e quem chama de fora não pode
  dar esse "sim" no lugar do dono. Para isso, fale com o JARVIS.
- Qualquer coisa se o JARVIS não estiver aberto: a ponte não sobe um JARVIS.

Para ligar no Claude Desktop, veja `docs/MCP.md`.
"""
import asyncio
import json
import os
import sys

import httpx

URL = os.environ.get("JARVIS_URL", "http://127.0.0.1:8080")
TIMEOUT_S = 30.0


async def _pedir(metodo, caminho, corpo=None):
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as c:
        try:
            r = await c.request(metodo, URL + caminho, json=corpo)
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"não consegui falar com o JARVIS em {URL} ({type(exc).__name__}). "
                "Ele está aberto?"
            )
    if r.status_code >= 400:
        detalhe = ""
        try:
            detalhe = r.json().get("detail") or r.text
        except ValueError:
            detalhe = r.text
        raise RuntimeError(f"o JARVIS recusou ({r.status_code}): {str(detalhe)[:300]}")
    return r.json()


async def listar_ferramentas():
    """Tudo que o JARVIS sabe fazer agora, com os argumentos de cada ferramenta.

    A lista muda conforme as skills ligadas, então consulte antes de agir."""
    ferramentas = await _pedir("GET", "/api/ferramentas")
    return json.dumps(ferramentas, ensure_ascii=False, indent=2)


async def executar(nome: str, argumentos: dict | None = None):
    """Executa UMA ferramenta do JARVIS direto, sem passar pelo cérebro dele.

    Use quando souber exatamente o que quer (ver `listar_ferramentas`).
    Ação perigosa é recusada: ela exige confirmação falada do dono."""
    r = await _pedir("POST", f"/api/ferramenta/{nome}", argumentos or {})
    return r["resultado"]


async def falar(texto: str):
    """Manda um pedido em português para o JARVIS, como se tivesse sido falado.

    Ele escolhe a ferramenta sozinho e responde. Use para pedidos abertos;
    para algo específico, `executar` é mais direto e mais barato."""
    await _pedir("POST", "/api/comando", {"texto": texto})
    # O comando é assíncrono no JARVIS: espera a resposta aparecer no painel.
    for _ in range(60):
        await asyncio.sleep(0.5)
        estado = await _pedir("GET", "/api/estado")
        if estado["agente"]["estado"] in ("repouso", "ouvindo", "erro"):
            return estado["agente"]["ultima_resposta"] or "(sem resposta)"
    return "(o JARVIS ainda está trabalhando; veja o painel)"


async def estado():
    """Como está o JARVIS agora: sensores do quarto, sistema, alertas e skills."""
    e = await _pedir("GET", "/api/estado")
    resumo = {
        "agente": e["agente"]["estado"],
        "placa": e["placa"],
        "sistema": e["sistema"],
        "alertas": e["alertas"],
        "skills": [s["nome"] for s in e["skills"] if s["ativa"]],
        "vozes_conhecidas": e["vozes"],
    }
    return json.dumps(resumo, ensure_ascii=False, indent=2)


def criar_servidor():
    from mcp.server.mcpserver import MCPServer

    servidor = MCPServer(
        name="jarvis",
        instructions=(
            "Opera o JARVIS, o assistente de voz que roda no PC do usuário. "
            "Comece por `listar_ferramentas` para saber o que ele pode fazer agora "
            "(a lista muda conforme as skills ligadas). Use `executar` para uma ação "
            "específica e `falar` para um pedido em português. Ações que mudam o "
            "estado da máquina são recusadas aqui de propósito: elas exigem "
            "confirmação falada do dono."
        ),
    )
    for funcao in (listar_ferramentas, executar, falar, estado):
        servidor.add_tool(funcao)
    return servidor


def main():
    try:
        criar_servidor().run()
    except Exception as exc:        # o Claude Desktop só mostra o stderr
        print(f"conector do JARVIS falhou: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
