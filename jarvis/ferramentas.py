"""O que o JARVIS sabe fazer no mundo.

Regra central: cada ferramenta é específica e limitada. NÃO existe "executar
qualquer comando" — um modelo de linguagem erra, e o estrago de um erro tem
que caber no que a ferramenta permite. Programas abríveis vêm de uma lista
fechada no config.json; sites só com http/https.

Ferramentas marcadas como `perigosa` mudam o estado da máquina e só rodam
depois de confirmação explícita do usuário (quem cuida disso é o agente).
"""
import asyncio
import inspect
import os
import re
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import quote_plus, urlparse

import httpx

from .placa import descrever_erro

DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


class ErroFerramenta(Exception):
    """Falha esperada, com mensagem que pode ser dita ao usuário."""


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    funcao: Callable[..., Awaitable[str]]
    propriedades: dict = field(default_factory=dict)
    obrigatorios: list = field(default_factory=list)
    perigosa: bool = False
    # Texto fixo, ou função que recebe os argumentos e monta a pergunta —
    # é assim que o comando livre mostra ao usuário o que vai rodar.
    pergunta_confirmacao: object = ""
    # Permite ao agente falar o retorno sem pedir ao modelo uma paráfrase.
    resposta_pronta: bool = False

    async def perguntar(self, argumentos):
        """Monta a pergunta de confirmação.

        Pode ser assíncrona: a instalação, por exemplo, consulta o catálogo
        para o usuário OUVIR o nome e a versão do que vai ser instalado, em
        vez de um identificador cru.
        """
        if not callable(self.pergunta_confirmacao):
            return self.pergunta_confirmacao
        pergunta = self.pergunta_confirmacao(argumentos)
        if inspect.isawaitable(pergunta):
            return await pergunta
        return pergunta

    def esquema(self):
        return {
            "type": "object",
            "properties": self.propriedades,
            "required": self.obrigatorios,
            "additionalProperties": False,
        }


def validar(ferramenta, argumentos):
    """Confere os argumentos contra o esquema. Devolve a mensagem de erro ou None.

    A API com `strict` já garante isso, mas o Ollama não: um modelo local pode
    inventar campo ou valor, e é aqui que isso para.
    """
    if not isinstance(argumentos, dict):
        return "argumentos não são um objeto"
    props = ferramenta.propriedades
    extras = set(argumentos) - set(props)
    if extras:
        return f"campos desconhecidos: {sorted(extras)}"
    for nome in ferramenta.obrigatorios:
        if nome not in argumentos:
            return f"falta o campo {nome}"
    for nome, valor in argumentos.items():
        regra = props[nome]
        tipo = regra.get("type")
        if tipo == "string" and not isinstance(valor, str):
            return f"{nome} deveria ser texto"
        if tipo == "string" and not valor.strip():
            return f"{nome} está vazio"
        if "enum" in regra and valor not in regra["enum"]:
            return f"{nome} fora das opções permitidas"
    return None


def _abrir_padrao(alvo):
    # os.startfile usa o ShellExecute do Windows: abre o programa ou a URL sem
    # passar por um shell, então não há como "injetar" um segundo comando.
    if alvo.startswith(("http://", "https://")):
        webbrowser.open(alvo)
    else:
        os.startfile(alvo)


def normalizar_site(endereco):
    endereco = endereco.strip()
    if "://" not in endereco:
        endereco = "https://" + endereco
    partes = urlparse(endereco)
    try:
        partes.port  # "javascript:alert(1)" vira host "javascript" com porta inválida
    except ValueError:
        raise ErroFerramenta("esse endereço não parece um site válido")
    host = partes.hostname or ""
    if (partes.scheme not in ("http", "https") or " " in endereco
            or not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host)):
        raise ErroFerramenta("esse endereço não parece um site válido")
    return endereco


def ler_token(caminho):
    try:
        return Path(caminho).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def criar_ferramentas_de_skills(skills):
    """Ferramentas que ligam e desligam as próprias skills, por voz."""

    async def listar_skills():
        partes = []
        for s in skills.resumo():
            estado = "ligada" if s["ativa"] else "desligada"
            if s["erro"]:
                estado = "com erro"
            partes.append(f"{s['nome']} ({estado})")
        return "Skills: " + "; ".join(partes) + "." if partes else "Nenhuma skill instalada."

    async def ligar_skill(skill, ligar):
        real = skills.ligar(skill, ligar)
        if real is None:
            raise ErroFerramenta(f"não achei nenhuma skill chamada '{skill}'")
        if ligar and skills.skills[real].erro:
            raise ErroFerramenta(f"a skill {real} tem um erro: {skills.skills[real].erro}")
        return f"Skill {real} {'ligada' if ligar else 'desligada'}."

    return [
        Ferramenta("listar_skills", "Diz quais skills existem e quais estão ligadas.",
                   listar_skills, resposta_pronta=True),
        Ferramenta("ligar_skill", "Liga ou desliga uma skill pelo nome.", ligar_skill,
                   {"skill": {"type": "string"}, "ligar": {"type": "boolean"}},
                   ["skill", "ligar"], resposta_pronta=True),
    ]


def criar_ferramentas(config, placa, abrir=_abrir_padrao, agora=datetime.now, janela=None):
    programas = config.get("programas", {})
    url_agente = config["agente_energia"]["url"].rstrip("/")
    caminho_token = config["agente_energia"].get("token", "./agente/TOKEN.txt")

    async def hora_e_data():
        from . import dizeres
        return dizeres.hora_falada(agora())

    async def abrir_programa(programa):
        from . import dizeres
        abrir(programas[programa])
        return dizeres.abrir_programa(programa)

    async def abrir_site(endereco):
        from . import dizeres
        url = normalizar_site(endereco)
        abrir(url)
        return dizeres.abrir_site(endereco)

    async def pesquisar_na_web(termo):
        abrir("https://www.google.com/search?q=" + quote_plus(termo))
        # Varia a frase para não soar robótico depois de 5 buscas seguidas.
        import random
        frases = [
            f"Pesquisando '{termo}' no Google.",
            f"Busquei '{termo}' para você.",
            f"Abri a pesquisa por '{termo}'.",
            f"'{termo}' no navegador, senhor.",
        ]
        return random.choice(frases)

    async def ler_sensores():
        from . import dizeres
        try:
            s = await placa.ler_status()
        except Exception as exc:
            raise ErroFerramenta(f"a placa não respondeu: {descrever_erro(exc)}")
        return dizeres.temperatura_falada(
            s.get("temperatura"), s.get("umidade"), s.get("movimento"))

    async def controlar_luz(modo):
        from . import dizeres
        nome = {"ligar": "luz_ligar", "desligar": "luz_desligar", "automatico": "luz_auto"}[modo]
        try:
            await placa.acao(nome)
        except Exception as exc:
            raise ErroFerramenta(f"a placa não respondeu: {descrever_erro(exc)}")
        if modo == "automatico":
            import random
            return random.choice([
                "Luz no automático.",
                "Deixei no automático.",
                "Agora é automática.",
            ])
        return dizeres.luz(modo == "ligar")

    async def acordar_pc():
        try:
            return await placa.acordar_pc()
        except Exception as exc:
            raise ErroFerramenta(f"a placa não respondeu: {descrever_erro(exc)}")

    async def suspender_pc():
        token = ler_token(caminho_token)
        if not token:
            raise ErroFerramenta("não achei o token do agente de energia")
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.post(url_agente + "/sleep", content="confirm=SLEEP",
                                 headers={"Authorization": "Bearer " + token})
        except httpx.HTTPError as exc:
            raise ErroFerramenta(f"o agente de energia não respondeu: {descrever_erro(exc)}")
        if r.status_code != 202:
            raise ErroFerramenta(f"o agente de energia recusou (HTTP {r.status_code})")
        return "Suspendendo o computador."

    lista = [
        Ferramenta("hora_e_data", "Diz a hora e a data atuais.", hora_e_data, resposta_pronta=True),
        Ferramenta(
            "abrir_programa", "Abre um programa instalado no PC, escolhido da lista permitida.",
            abrir_programa,
            {"programa": {"type": "string", "enum": sorted(programas),
                          "description": "Nome do programa, exatamente como na lista."}},
            ["programa"], resposta_pronta=True),
        Ferramenta(
            "abrir_site", "Abre um site no navegador.", abrir_site,
            {"endereco": {"type": "string", "description": "Endereço do site, ex.: youtube.com"}},
            ["endereco"], resposta_pronta=True),
        Ferramenta(
            "pesquisar_na_web", "Abre uma pesquisa no Google com o termo pedido.", pesquisar_na_web,
            {"termo": {"type": "string", "description": "O que pesquisar."}},
            ["termo"], resposta_pronta=True),
        Ferramenta("ler_sensores",
                   "Lê temperatura, umidade, movimento e o estado da luz na placa ESP32 do quarto.",
                   ler_sensores, resposta_pronta=True),
        Ferramenta(
            "controlar_luz", "Liga, desliga ou põe no automático a luz ligada à placa ESP32.",
            controlar_luz,
            {"modo": {"type": "string", "enum": ["ligar", "desligar", "automatico"]}},
            ["modo"], resposta_pronta=True),
        Ferramenta("acordar_pc", "Manda o sinal Wake-on-LAN para acordar o PC suspenso.",
                   acordar_pc, resposta_pronta=True),
        Ferramenta("suspender_pc", "Suspende (põe para dormir) este computador.", suspender_pc,
                   perigosa=True, pergunta_confirmacao="Confirma suspender o computador agora?",
                   resposta_pronta=True),
    ]
    if janela is not None:
        async def mudar_tela(tela):
            numero = await asyncio.to_thread(janela.mudar, tela)
            return f"Janela na tela {numero}."
        lista.append(Ferramenta(
            "mudar_tela", "Move a janela do JARVIS para outro monitor (primeira, segunda ou a outra).",
            mudar_tela, {"tela": {"type": "string", "enum": ["primeira", "segunda", "outra"]}},
            ["tela"], resposta_pronta=True))
    fora = set()
    if not programas:
        fora.add("abrir_programa")
    if not config.get("recursos", {}).get("luz", True):
        fora.add("controlar_luz")  # LED desligado da placa: oferecer a ferramenta só geraria erro
    lista = [f for f in lista if f.nome not in fora]
    return {f.nome: f for f in lista}
