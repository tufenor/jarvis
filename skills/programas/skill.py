"""Instalar programas pelo winget, o gerenciador oficial do Windows.

Decisão do usuário em 21/10/2026: **só winget, nunca .exe solto da internet**.
O catálogo do winget é curado pela Microsoft e os pacotes são verificados — um
erro de transcrição aqui instala o programa errado, não um vírus.

Os freios:
1. Fonte travada em `--source winget`. Nada de msstore nem fonte de terceiro.
2. Instala por ID EXATO (`--id ... --exact`). "instala o chrome" não pode casar
   com um pacote de nome parecido.
3. Antes de instalar, o JARVIS consulta o pacote e FALA nome, fornecedor e
   versão. Só roda depois do "sim".
4. Desinstalar por voz ficou de fora: o ganho é pequeno e o estrago, grande.
"""
import asyncio
import re

from jarvis.ferramentas import ErroFerramenta, Ferramenta

TEMPO_BUSCA_S = 60
TEMPO_INSTALACAO_S = 600
MAX_RESULTADOS = 6
# IDs do winget são do tipo Fornecedor.Produto; nada fora disso chega à linha de comando.
ID_VALIDO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{1,100}$")
# O nome vai como argumento, não por shell, mas estes caracteres não existem em
# nome de programa e só apareceriam numa tentativa de enganar o reconhecimento.
CARACTERES_PROIBIDOS = set(';&|<>"\'`$\n\r')


async def _winget(argumentos, tempo_s):
    try:
        processo = await asyncio.create_subprocess_exec(
            "winget", *argumentos,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        raise ErroFerramenta("o winget não está instalado neste Windows")
    try:
        saida, _ = await asyncio.wait_for(processo.communicate(), tempo_s)
    except asyncio.TimeoutError:
        processo.kill()
        raise ErroFerramenta(f"o winget passou de {tempo_s // 60} minutos e eu parei")
    except asyncio.CancelledError:
        # Sem isto o winget fica rodando órfão depois do cancelamento —
        # aconteceu de verdade no primeiro teste de instalação.
        processo.kill()
        raise
    return processo.returncode, (saida or b"").decode("utf-8", "replace")


def posicoes_das_colunas(cabecalho):
    """Onde cada coluna começa, pela posição no cabeçalho.

    Não dá para separar por espaços: quando o nome preenche a coluna inteira
    sobra UM espaço só ("VLC media player VideoLAN.VLC"). A tabela do winget é
    de largura fixa, então a posição do cabeçalho é a única referência certa.
    """
    posicoes = []
    for i, c in enumerate(cabecalho):
        if c != " " and (i == 0 or cabecalho[i - 1] == " "):
            posicoes.append(i)
    return posicoes


def ler_tabela(texto):
    """Lê a tabela do winget sem depender do idioma dos cabeçalhos.

    Em português os títulos são Nome/ID/Versão, em inglês Name/Id/Version —
    por isso vale a posição da coluna, não o nome dela.
    """
    linhas = [l.rstrip() for l in texto.splitlines()]
    corte = next((i for i, l in enumerate(linhas)
                  if set(l.strip()) == {"-"} and len(l.strip()) > 5), None)
    if corte is None or corte == 0:
        return []
    posicoes = posicoes_das_colunas(linhas[corte - 1])
    if len(posicoes) < 2:
        return []
    limites = list(zip(posicoes, posicoes[1:] + [None]))
    itens = []
    for linha in linhas[corte + 1:]:
        if not linha.strip():
            continue
        colunas = [linha[a:b].strip() for a, b in limites]
        if len(colunas) < 2 or not colunas[0] or not colunas[1]:
            continue
        itens.append({"nome": colunas[0], "id": colunas[1],
                      "versao": colunas[2] if len(colunas) > 2 and colunas[2] else "?"})
    return itens


async def ja_instalado(id_pacote):
    """Pergunta ao Windows se o pacote está instalado.

    Vale mais que o código de saída do winget: ele devolve 0x8A15002B
    ("nenhuma versão mais recente disponível") quando o programa JÁ está lá, e
    isso não é falha nenhuma. Conferir o resultado real evita dizer que falhou
    quando na verdade deu certo.
    """
    codigo, saida = await _winget(
        ["list", "--id", id_pacote, "--exact", "--source", "winget",
         "--accept-source-agreements"], TEMPO_BUSCA_S)
    return any(i["id"].lower() == id_pacote.lower() for i in ler_tabela(saida))


async def achar_pacote(procurado):
    """Resolve um NOME ou um identificador num pacote do catálogo.

    Aceitar o nome evita um vai e volta: "instala o VLC" resolve numa chamada
    só. O risco de pegar o pacote errado é coberto pela confirmação, que fala
    o nome e a versão escolhidos antes de instalar.
    """
    procurado = (procurado or "").strip()
    if not procurado:
        raise ErroFerramenta("não disseram qual programa instalar")

    if ID_VALIDO.match(procurado) and "." in procurado:
        codigo, saida = await _winget(
            ["search", "--id", procurado, "--exact", "--source", "winget",
             "--accept-source-agreements"], TEMPO_BUSCA_S)
        itens = [i for i in ler_tabela(saida) if i["id"].lower() == procurado.lower()]
        if itens:
            return itens[0]

    if any(c in procurado for c in CARACTERES_PROIBIDOS):
        raise ErroFerramenta("esse nome de programa tem caractere que eu não aceito")
    codigo, saida = await _winget(
        ["search", procurado, "--source", "winget", "--accept-source-agreements"],
        TEMPO_BUSCA_S)
    itens = ler_tabela(saida)
    if not itens:
        raise ErroFerramenta(f"não achei '{procurado}' no catálogo do winget")
    # Nome exato ganha de "parecido"; senão, o primeiro, que o winget já ordena
    # por relevância. Em todo caso o usuário ouve o nome antes de confirmar.
    exatos = [i for i in itens if i["nome"].lower() == procurado.lower()
              or i["id"].lower() == procurado.lower()]
    return (exatos or itens)[0]


def criar(contexto):
    async def procurar_programa(nome):
        codigo, saida = await _winget(
            ["search", nome, "--source", "winget", "--accept-source-agreements"], TEMPO_BUSCA_S)
        itens = ler_tabela(saida)
        if not itens:
            return f"Não achei nenhum programa chamado '{nome}' no catálogo do winget."
        partes = [f"{i['nome']} (identificador {i['id']}, versão {i['versao']})"
                  for i in itens[:MAX_RESULTADOS]]
        extra = f" e mais {len(itens) - MAX_RESULTADOS}" if len(itens) > MAX_RESULTADOS else ""
        return f"Achei {len(itens)}: " + "; ".join(partes) + extra + "."

    async def instalar_programa(programa):
        pacote = await achar_pacote(programa)
        codigo, saida = await _winget(
            ["install", "--id", pacote["id"], "--exact", "--source", "winget",
             "--accept-package-agreements", "--accept-source-agreements",
             "--disable-interactivity"], TEMPO_INSTALACAO_S)
        if codigo != 0:
            # O winget reclama quando o programa já está instalado e atualizado.
            # Confere o estado real antes de chamar de falha.
            if await ja_instalado(pacote["id"]):
                return f"{pacote['nome']} já estava instalado."
            ultima = next((l.strip() for l in reversed(saida.splitlines()) if l.strip()), "")
            raise ErroFerramenta(f"a instalação falhou: {ultima[:200]}")
        return f"{pacote['nome']} instalado, versão {pacote['versao']}."

    async def listar_atualizacoes():
        codigo, saida = await _winget(
            ["upgrade", "--source", "winget", "--accept-source-agreements"], TEMPO_BUSCA_S)
        itens = ler_tabela(saida)
        if not itens:
            return "Todos os programas estão atualizados."
        nomes = "; ".join(f"{i['nome']} ({i['id']})" for i in itens[:MAX_RESULTADOS])
        extra = f" e mais {len(itens) - MAX_RESULTADOS}" if len(itens) > MAX_RESULTADOS else ""
        return f"{len(itens)} com atualização: {nomes}{extra}."

    async def atualizar_programa(id_pacote):
        if not ID_VALIDO.match(id_pacote or ""):
            raise ErroFerramenta("esse identificador de pacote não parece válido")
        codigo, saida = await _winget(
            ["upgrade", "--id", id_pacote, "--exact", "--source", "winget",
             "--accept-package-agreements", "--accept-source-agreements",
             "--disable-interactivity"], TEMPO_INSTALACAO_S)
        if codigo != 0:
            ultima = next((l.strip() for l in reversed(saida.splitlines()) if l.strip()), "")
            if "disponív" in ultima or "available" in ultima.lower():
                return f"{id_pacote} já está na última versão."
            raise ErroFerramenta(f"a atualização falhou: {ultima[:200]}")
        return f"{id_pacote} atualizado."

    async def perguntar_instalacao(argumentos):
        """Consulta o catálogo para o usuário ouvir o que vai ser instalado."""
        try:
            p = await achar_pacote(argumentos.get("programa", ""))
        except ErroFerramenta as exc:
            # Sem o pacote no catálogo a instalação vai falhar de qualquer jeito;
            # a pergunta tem que deixar isso claro antes de alguém dizer "sim".
            return f"{exc}. A instalação vai falhar. Quer tentar assim mesmo?"
        return f"Vou instalar {p['nome']}, versão {p['versao']}, do catálogo oficial. Confirma?"

    return [
        Ferramenta("procurar_programa",
                   "Procura um programa no catálogo oficial do winget. Use ANTES de instalar, "
                   "para descobrir o identificador exato do pacote.",
                   procurar_programa, {"nome": {"type": "string"}}, ["nome"]),
        Ferramenta("instalar_programa",
                   "Instala um programa do catálogo oficial do Windows. Aceita o NOME "
                   "(ex.: VLC) ou o identificador (ex.: VideoLAN.VLC). O usuário ouve o "
                   "nome e a versão e confirma antes de instalar.",
                   instalar_programa,
                   {"programa": {"type": "string",
                                 "description": "Nome ou identificador, ex.: VLC ou VideoLAN.VLC"}},
                   ["programa"],
                   perigosa=True, pergunta_confirmacao=perguntar_instalacao,
                   resposta_pronta=True),
        Ferramenta("listar_atualizacoes",
                   "Diz quais programas do PC têm atualização disponível.",
                   listar_atualizacoes, resposta_pronta=True),
        Ferramenta("atualizar_programa", "Atualiza um programa já instalado.",
                   atualizar_programa,
                   {"id_pacote": {"type": "string"}}, ["id_pacote"],
                   perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma atualizar {a.get('id_pacote')}?",
                   resposta_pronta=True),
    ]
