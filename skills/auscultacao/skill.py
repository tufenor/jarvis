"""Auscultação: o JARVIS vira ouvinte paciente, não um assistente de tarefa.

Quando o usuário quer desabafar, pensar em voz alta ou reclamar à vontade,
este modo:

- estica o fim-de-fala do microfone pra 5 s (pausas longas não cortam);
- deixa o trecho ir até ~30 min contínuos sem fechar;
- muda o estilo do cérebro: escuta ativa, nada de solução não pedida.

O cérebro lê o estado `painel.modo_auscultacao` e altera o próprio tom.
Encerra com `encerrar_auscultacao` ou um "pode parar, Jarvis" / "obrigado".
"""
from jarvis.ferramentas import Ferramenta


def criar(contexto):
    ouvinte = contexto.get("ouvinte")
    painel = contexto.get("painel")
    if ouvinte is None or painel is None:
        return []

    async def auscultar(duracao_min=30.0):
        try:
            d = max(1.0, min(120.0, float(duracao_min)))
        except (TypeError, ValueError):
            d = 30.0
        ouvinte.ativar_auscultacao(silencio_fim_s=5.0, fala_max_s=d * 60.0)
        painel.modo_auscultacao = True
        return (
            "Estou te ouvindo. Fala à vontade — pausa, respira, volta quando quiser. "
            "Não vou cortar nem te apressar. Quando terminar, me diz 'pode parar'."
        )

    async def encerrar_auscultacao():
        ouvinte.desativar_auscultacao()
        painel.modo_auscultacao = False
        return "Fechei a escuta. Estou aqui se precisar voltar."

    return [
        Ferramenta(
            "auscultar",
            "Entra no modo escuta ativa: o JARVIS se cala, não interrompe e não "
            "sugere solução a não ser que o usuário peça. Use quando a pessoa "
            "quer desabafar, pensar em voz alta, reclamar ou processar algo. "
            "Mantém o microfone aberto por até duracao_min minutos de fala contínua.",
            auscultar,
            {"duracao_min": {"type": "number",
                             "description": "Minutos de tolerância máxima. Padrão 30."}},
            [], resposta_pronta=True,
        ),
        Ferramenta(
            "encerrar_auscultacao",
            "Fecha o modo de escuta e volta ao microfone normal. Chame quando o "
            "usuário disser 'pode parar', 'obrigado', 'é isso' ou equivalente.",
            encerrar_auscultacao, {}, [], resposta_pronta=True,
        ),
    ]
