"""Ferramentas para o JARVIS pedir algo ao celular (satélite no A53).

As ordens vão para uma fila que o Termux consome por long-poll. O JARVIS não
sabe se o celular está online ou não: ele só empilha; se o aparelho aparecer
depois, pega tudo acumulado — se não aparecer, envelhece na fila (tamanho
limitado) e desaparece. Esse desacoplamento é de propósito: o painel nunca
trava esperando um celular que foi para o bolso.
"""
import asyncio

from jarvis.ferramentas import ErroFerramenta, Ferramenta


def criar(contexto):
    ponte = contexto.get("celular")
    if ponte is None:
        return []

    async def falar_no_celular(texto):
        try:
            await asyncio.to_thread(ponte.falar, texto)
        except ValueError as exc:
            raise ErroFerramenta(str(exc))
        return "Mandei o celular falar."

    async def avisar_no_celular(titulo, texto=""):
        try:
            await asyncio.to_thread(ponte.avisar, titulo, texto)
        except ValueError as exc:
            raise ErroFerramenta(str(exc))
        return "Notificação empilhada para o celular."

    return [
        Ferramenta(
            "falar_no_celular",
            "Faz o celular do usuário (A53) falar uma mensagem em voz alta. Use quando o "
            "usuário está longe do PC e pede para avisar/dizer algo pelo telefone.",
            falar_no_celular,
            {"texto": {"type": "string", "description": "O que o celular deve falar."}},
            ["texto"], resposta_pronta=True),
        Ferramenta(
            "avisar_no_celular",
            "Mostra uma notificação no celular do usuário. Para lembretes curtos sem áudio.",
            avisar_no_celular,
            {"titulo": {"type": "string"},
             "texto": {"type": "string", "description": "Corpo opcional."}},
            ["titulo"], resposta_pronta=True),
    ]
