"""Comando livre do Windows — a única ferramenta sem lista fechada.

O usuário pediu acesso amplo em 21/10/2026, ciente do risco, e escolheu o
caminho com freio. O freio é este, e não pode ser afrouxado sem ele mandar:

1. O comando aparece ESCRITO no painel e é FALADO antes de rodar.
2. Só roda depois de um "sim" explícito (`perigosa=True`).
3. Nada de shell: o comando é quebrado em argumentos (`shlex`), então um
   "; apaga tudo" grudado no fim vira texto, não um segundo comando.
4. Uma lista curta de comandos destrutivos é recusada de saída — eles apagam
   sem passar pela Lixeira, e um erro de transcrição aqui não tem volta.
5. Tem tempo máximo e a saída volta cortada.

Para ligar e desligar esta skill: "Jarvis, desativa a skill de comando".
"""
import asyncio
import shlex

from jarvis.ferramentas import ErroFerramenta, Ferramenta

TEMPO_MAXIMO_S = 30
LIMITE_SAIDA = 1200

# Apagam sem passar pela Lixeira, formatam ou derrubam a máquina.
# Para apagar arquivos existe `mandar_para_lixeira`, que dá para desfazer.
RECUSADOS = {
    "format", "diskpart", "fdisk", "vol", "label",
    "del", "erase", "rd", "rmdir", "rm",
    "shutdown", "bcdedit", "reg", "regedit", "cipher", "sfc",
    "takeown", "icacls", "cacls", "attrib", "net", "netsh", "schtasks", "sc",
}
ARGUMENTOS_RECUSADOS = {"-recurse", "/s", "/q", "-force", "/f"}


def analisar(comando):
    """Devolve (programa, argumentos) ou levanta ErroFerramenta explicando."""
    texto = comando.strip()
    if not texto:
        raise ErroFerramenta("o comando está vazio")
    try:
        partes = shlex.split(texto, posix=False)
    except ValueError as exc:
        raise ErroFerramenta(f"não consegui entender o comando: {exc}")
    if not partes:
        raise ErroFerramenta("o comando está vazio")
    programa = partes[0].strip('"').lower()
    programa = programa.rsplit("\\", 1)[-1]
    if programa.endswith(".exe"):
        programa = programa[:-4]
    if programa in RECUSADOS:
        raise ErroFerramenta(
            f"não rodo '{programa}' por voz: apaga ou mexe no sistema sem volta. "
            "Para apagar arquivo, peça para mandar para a Lixeira"
        )
    # "powershell -c rm -r x" esconderia um apagar dentro de outro programa.
    minusculas = {p.lower() for p in partes[1:]}
    if programa in {"powershell", "pwsh", "cmd", "wscript", "cscript"}:
        if minusculas & {r.lower() for r in RECUSADOS} or minusculas & ARGUMENTOS_RECUSADOS:
            raise ErroFerramenta("esse comando esconde uma operação destrutiva; recusei")
    return partes[0].strip('"'), partes[1:]


def criar(contexto):
    async def executar_comando(comando):
        programa, argumentos = analisar(comando)
        try:
            processo = await asyncio.create_subprocess_exec(
                programa, *argumentos,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError:
            raise ErroFerramenta(f"não achei o programa '{programa}'")
        except OSError as exc:
            raise ErroFerramenta(f"o Windows recusou: {exc}")
        try:
            saida, _ = await asyncio.wait_for(processo.communicate(), TEMPO_MAXIMO_S)
        except asyncio.TimeoutError:
            processo.kill()
            raise ErroFerramenta(f"passou de {TEMPO_MAXIMO_S} segundos e eu parei")
        except asyncio.CancelledError:
            processo.kill()   # não deixar processo órfão quando o pedido é trocado
            raise
        texto = (saida or b"").decode("utf-8", "replace").strip()
        if processo.returncode != 0:
            raise ErroFerramenta(f"o comando terminou com erro {processo.returncode}: {texto[:300]}")
        return texto[:LIMITE_SAIDA] or "Comando executado, sem saída."

    def perguntar(argumentos):
        return f"Vou rodar: {argumentos.get('comando', '')}. Confirma?"

    return [
        Ferramenta(
            "executar_comando",
            "Roda um comando do Windows. Use só quando NENHUMA outra ferramenta serve. "
            "O usuário vê e confirma o comando antes de rodar.",
            executar_comando,
            {"comando": {"type": "string", "description": "O comando completo, como se digitasse."}},
            ["comando"],
            perigosa=True,
            pergunta_confirmacao=perguntar,
        ),
    ]
