"""Frases variáveis do JARVIS, para ele soar mais humano e menos repetitivo.

Tudo que o JARVIS fala por conta própria (não vem do cérebro) passa por aqui.
Cada "categoria" tem várias formas de dizer a mesma coisa, e `escolher()`
sorteia uma — sem repetir a última, para a variação ser percebida de verdade.

Regras:
- A voz do JARVIS: formal mas não bajuladora, meio seca, confiante, com um
  humor sutil só nas frases longas. Nada de emoji nem gíria.
- Nenhuma frase xinga, assusta ou brinca com coisas sérias.
- Cada categoria tem pelo menos 4 variantes para 5 pedidos seguidos não
  repetirem.
"""
import random
import re
import unicodedata

# ---- categorias de frase ----------------------------------------------------

DIZERES = {
    # "Pois não, senhor?" — resposta ao chamado por "Jarvis" sem pedido.
    "atender_chamado": [
        "Pois não, senhor?",
        "Sim, senhor.",
        "Estou aqui.",
        "Às ordens.",
        "Diga.",
        "Pode falar.",
        "Em que posso ajudar?",
    ],

    # "Às ordens." — fechamento da conversa ("tchau", "obrigado").
    "encerrar": [
        "Às ordens.",
        "Estou aqui quando precisar.",
        "Pode contar comigo.",
        "Disponha, senhor.",
        "Até já.",
        "Fico por perto.",
    ],

    # "Não entendi o pedido com segurança."
    "nao_entendi": [
        "Não entendi o pedido com segurança. Pode repetir de outro jeito?",
        "Não peguei bem, senhor. Pode dizer de novo?",
        "Me perdi um pouco aí. Pode reformular?",
        "Fiquei em dúvida. Repete com outras palavras?",
        "Desculpe, não ficou claro. Tenta de novo?",
    ],

    # "Pronto." — confirmação curta de ação simples.
    "ok": [
        "Pronto.",
        "Feito.",
        "Pode deixar.",
        "Resolvido.",
        "Tudo certo.",
        "Já está.",
    ],

    # "A skill X não está liberada para Y."
    "sem_permissao": [
        "A skill {skill} não está liberada para {quem}.",
        "Não posso rodar a {skill} com {quem}, senhor.",
        "{quem} não tem permissão para a skill {skill}.",
        "A {skill} está fora do alcance de {quem}.",
    ],

    # "Confirmação expirou; nada foi feito."
    "expirou": [
        "A confirmação demorou demais, senhor. Nada foi feito.",
        "O tempo passou e cancelei o pedido.",
        "Demorou para confirmar, então deixei de lado.",
        "Passou o prazo; não executei nada.",
    ],

    # "Interrompido: você começou a falar"
    "interrompido": [
        "Interrompido: você começou a falar.",
        "Entendi, pode falar.",
        "Pode continuar.",
        "Te escuto.",
    ],

    # "Entendido, senhor. A skill de X continua ligada."
    "nao_cancelado": [
        "Não confirmado, senhor. Nada feito.",
        "Sem confirmação; deixei como estava.",
        "Entendido, não vou mexer.",
        "Pode deixar como está.",
    ],
}


# ---- motor de escolha -------------------------------------------------------

_ultimas = {}      # categoria -> última frase escolhida
_rng = random.Random()


def escolher(categoria, **variaveis):
    """Devolve uma frase da categoria, sem repetir a última vez seguida.

    `variaveis` preenchem placeholders no estilo {nome}. Falta de uma variável
    volta para a primeira frase da categoria (a mais segura), em vez de quebrar.
    """
    opcoes = DIZERES.get(categoria)
    if not opcoes:
        raise KeyError(f"categoria '{categoria}' não existe em dizeres")
    anteriores = _ultimas.get(categoria)
    candidatos = [o for o in opcoes if o != anteriores] or list(opcoes)
    escolhida = _rng.choice(candidatos)
    try:
        frase = escolhida.format(**variaveis) if variaveis else escolhida
    except (KeyError, IndexError):
        frase = opcoes[0].format(**variaveis) if variaveis else opcoes[0]
    _ultimas[categoria] = escolhida
    return frase


def semear(semente):
    """Para testes: trava o sorteio num valor conhecido."""
    global _rng
    _rng = random.Random(semente)
    _ultimas.clear()


# ---- formadores de resposta variada para ferramentas ------------------------

def _limpar(nome):
    """Para encaixe em frase: 'calculadora', não 'Calculadora.exe'."""
    nome = re.sub(r"\.(exe|lnk|url)$", "", nome, flags=re.IGNORECASE)
    return nome.strip()


ABRIR_PROGRAMA = [
    "Abrindo {nome}.",
    "{nome_cap} aberto.",
    "Já abri {nome}.",
    "Pronto, {nome} no ar.",
    "Lá vai o {nome}.",
]

ABRIR_SITE = [
    "Abri {nome} no navegador.",
    "{nome_cap} no ar, no navegador.",
    "Pronto, {nome} aberto.",
    "Abri {nome} agora.",
]

VOLUME = [
    "Volume em {n} por cento.",
    "Volume no {n}.",
    "Pus o volume em {n} por cento.",
    "Está {n} por cento agora.",
]

LUZ_LIGADA = [
    "Luz ligada.",
    "Acendi.",
    "Pronto, iluminado.",
    "Luz acesa.",
]

LUZ_DESLIGADA = [
    "Luz desligada.",
    "Apaguei.",
    "Está escuro agora.",
    "Pronto, luz fora.",
]


def abrir_programa(nome):
    base = _rng.choice(ABRIR_PROGRAMA)
    limpo = _limpar(nome)
    return base.format(nome=limpo, nome_cap=limpo.capitalize())


def abrir_site(endereco):
    base = _rng.choice(ABRIR_SITE)
    return base.format(nome=endereco, nome_cap=endereco)


def volume(nivel):
    return _rng.choice(VOLUME).format(n=nivel)


def luz(acesa):
    return _rng.choice(LUZ_LIGADA if acesa else LUZ_DESLIGADA)


# ---- hora e temperatura em formas humanizadas ------------------------------

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo"]


def hora_falada(quando):
    """Hora e data em português falado natural, variando o estilo."""
    horas, minutos = quando.hour, quando.minute
    if minutos == 0:
        tempo = f"exatamente {horas} horas"
    elif minutos == 30:
        tempo = f"{horas} e meia"
    elif minutos == 15:
        tempo = f"{horas} e quinze"
    else:
        tempo = f"{horas} e {minutos:02d}"

    dia = DIAS_SEMANA[quando.weekday()]
    data = f"{quando.day} de {MESES[quando.month - 1]}"

    moldes = [
        f"São {tempo}, {dia}, {data}.",
        f"{dia.capitalize()}, {data}. {tempo.capitalize()}.",
        f"Agora são {tempo}. Estamos em {dia}, {data}.",
        f"Marca {tempo}, senhor. Hoje é {dia}, {data}.",
    ]
    return _rng.choice(moldes)


def temperatura_falada(temp, umid, movimento=None):
    """Comenta a leitura em vez de apenas repetir os números."""
    moldes_temp = [
        f"Temperatura {temp} graus, umidade {umid} por cento",
        f"Está em {temp} graus no quarto, com {umid} por cento de umidade",
        f"Marca {temp} graus, umidade de {umid}",
        f"O quarto está com {temp} graus e {umid} por cento",
    ]
    base = _rng.choice(moldes_temp)
    if temp is not None and temp >= 32:
        base += " — bem quente"
    elif temp is not None and temp <= 18:
        base += " — fresco"
    if umid is not None and umid < 25:
        base += ". O ar está seco"
    if movimento:
        base += ". Há movimento no sensor"
    return base + "."


def sem_acento(texto):
    """Para comparação sem acento nos testes."""
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")
