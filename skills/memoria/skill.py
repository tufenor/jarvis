"""Ferramentas de memória do JARVIS: o que aprender fica no system prompt."""
import asyncio

from jarvis.ferramentas import ErroFerramenta, Ferramenta
from jarvis.memoria import CATEGORIAS


def criar(contexto):
    memoria = contexto.get("memoria")
    if memoria is None:
        return []

    async def lembrar_de(fato, categoria="fato"):
        try:
            id_ = await asyncio.to_thread(memoria.lembrar, fato, categoria)
        except ValueError as exc:
            raise ErroFerramenta(str(exc))
        return f"Anotado: {fato[:80]}."

    async def recordar(sobre="", categoria=""):
        cat = categoria if categoria in CATEGORIAS else None
        itens = memoria.buscar(consulta=sobre, categoria=cat, limite=6)
        if not itens:
            return "Não tenho nada guardado sobre isso."
        partes = [i["texto"] for i in itens]
        return "Lembro de: " + "; ".join(partes) + "."

    async def esquecer_de(trecho):
        n = await asyncio.to_thread(memoria.esquecer, trecho)
        if not n:
            return "Não achei esse registro."
        return f"Apaguei {n} registro." if n == 1 else f"Apaguei {n} registros."

    async def listar_memorias(categoria=""):
        cat = categoria if categoria in CATEGORIAS else None
        itens = memoria.buscar(categoria=cat, limite=20)
        if not itens:
            return "A memória está vazia."
        partes = [f"{i['categoria']}: {i['texto']}" for i in itens[:10]]
        return "Guardados: " + "; ".join(partes) + "."

    return [
        Ferramenta("lembrar_de",
                   "Guarda um fato, preferência, correção ou aprendizado do usuário para as "
                   "próximas conversas. Categorias: fato, preferencia, lembrete, correcao, aprendizado.",
                   lembrar_de,
                   {"fato": {"type": "string", "description": "O que lembrar, curto e direto."},
                    "categoria": {"type": "string",
                                  "enum": ["fato", "preferencia", "lembrete", "correcao", "aprendizado"]}},
                   ["fato"], resposta_pronta=True),
        Ferramenta("recordar",
                   "Procura algo na memória do JARVIS. Sem argumentos, traz os mais recentes.",
                   recordar,
                   {"sobre": {"type": "string"},
                    "categoria": {"type": "string",
                                  "enum": ["fato", "preferencia", "lembrete", "correcao", "aprendizado"]}},
                   [], resposta_pronta=True),
        Ferramenta("listar_memorias",
                   "Lista o que está guardado. Filtra por categoria se o usuário pedir.",
                   listar_memorias,
                   {"categoria": {"type": "string",
                                  "enum": ["fato", "preferencia", "lembrete", "correcao", "aprendizado"]}},
                   [], resposta_pronta=True),
        Ferramenta("esquecer_de",
                   "Apaga da memória qualquer registro que contenha este trecho.",
                   esquecer_de,
                   {"trecho": {"type": "string"}}, ["trecho"],
                   perigosa=True,
                   pergunta_confirmacao=lambda a: f"Confirma apagar da memória tudo que fale de '{a.get('trecho')}'?",
                   resposta_pronta=True),
    ]
