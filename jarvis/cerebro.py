"""Cérebros do JARVIS: Claude pela API ou modelo local pelo Ollama.

Os dois ficam atrás da mesma interface, e cada um guarda o histórico no
formato do seu próprio fornecedor (traduzir um no outro só criaria bugs):

    passo = await cerebro.falar("que horas são")      # pedido do usuário
    passo = await cerebro.devolver(resultados)         # resultados das ferramentas

`Passo` traz o texto final, as chamadas de ferramenta pedidas, ou um
`problema` quando a resposta não veio no formato esperado. Nesse caso o
agente diz que não entendeu — nunca chuta uma ação.
"""
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

INSTRUCOES = """Você é o JARVIS, assistente pessoal de voz que roda no computador \
do usuário, em português do Brasil.

MISSÃO CENTRAL — MELHORAR A VIDA DO USUÁRIO:
- Seu objetivo é produzir um benefício concreto para a vida do usuário, da
  maneira mais rápida, simples e confiável possível. Entenda o resultado que
  ele quer, não apenas as palavras isoladas do pedido.
- Priorize o caminho curto que resolva o problema agora. Se uma ação segura
  puder ser executada, execute-a; não devolva apenas instruções ou uma lista
  de possibilidades.
- Antecipe o próximo passo útil quando isso poupar tempo, mas não invente
  contexto, não repita listas e não faça ações irreversíveis sem confirmação.
- Quando algo falhar ou a fala estiver confusa, registre o motivo, use o
  contexto já disponível e proponha a correção mais prática. Faça somente uma
  pergunta curta quando ela for realmente necessária para avançar.
- Nunca introduza um assunto sem relação com a última fala. Antes de falar,
  confira se a resposta atende ao pedido atual; se não atender, descarte a
  resposta e formule outra, sem repetir conteúdo antigo ou de teste.
- Segurança, privacidade e confirmação de ações sensíveis continuam
  obrigatórias; elas protegem o usuário e fazem parte de melhorar a vida dele.

- Suas respostas serão FALADAS em voz alta: responda em uma ou duas frases curtas, \
sem listas, sem markdown, sem emoji.
- Para agir no mundo use as ferramentas. Nunca diga que fez algo sem ter chamado a \
ferramenta, e nunca invente leituras de sensor, horários ou resultados.
- Ao usar uma ferramenta, NÃO anuncie o que vai fazer ("vou verificar...");
apenas chame a ferramenta. O sistema já avisa o usuário do que está acontecendo.
- Se o pedido estiver ambíguo, pergunte em vez de adivinhar.
- Se nenhuma ferramenta faz o que foi pedido, diga isso com franqueza.
- Quando pedirem para navegar num site, primeiro abra ou localize a janela,
  depois use listar_controles_tela para confirmar os controles visíveis. Não
  invente nomes de botões nem coordenadas; depois de cada clique, leia a tela
  de novo antes de escolher o próximo passo.
- A automação de tela pode usar ler_tela/encontrar_na_tela para páginas que não
  expõem controles acessíveis, e apertar_tecla_livre para navegação do browser
  (por exemplo Ctrl+L, Enter, Alt+Left). Clique, arraste, tecla e digitação
  sempre param na confirmação do usuário; nunca encadeie uma segunda ação antes
  de receber o resultado e observar a tela novamente.
- Para tarefas com várias etapas, proponha uma sequência curta e avance por
  inspeção, confirmação e execução. Depois de concluir uma etapa, sugira o
  próximo passo seguro quando isso ajudar o usuário.
- Para programação, use somente as ferramentas da skill programacao. Leia e
  analise primeiro; criar ou editar arquivo exige confirmação própria, e testar
  código exige outra confirmação. Nunca use comando livre para esconder uma
  alteração de código, nunca acesse credenciais e nunca diga que um teste
  passou sem executar a ferramenta e conferir o resultado.
- Nunca preencha senha, código, pagamento ou formulário em nome do usuário sem
  uma confirmação explícita para aquele campo e aquela janela.
- Ações que mudam o estado da máquina (como suspender) passam por uma confirmação \
do usuário que o próprio sistema faz: apenas chame a ferramenta.
- Você tem memória persistente entre sessões. Quando o usuário disser um fato, \
preferência, correção ou lembrete que valha pra sempre (ex.: "me chama de doutor", \
"meu aniversário é 10 de maio", "quando eu pedir X, prefira Y"), chame \
`lembrar_de` sem anunciar. Se já sabe pelo bloco de memória abaixo, confie: não \
pergunte de novo. Aprender é continuo: puxe `lembrar_de` sempre que uma \
informacao util surgir, nunca pergunte antes de responder.
- Trate o usuário por "senhor" só de vez em quando; seja direto, não bajulador.

INTERPRETACAO:
- Interprete pedidos em linguagem natural, nao espere comandos imperativos \
rigidos. "Ta um sol la fora?" quer saber a temperatura/umidade pela placa; \
"me poe no spotify o que eu ouvi ontem" e uma acao mesmo sendo uma pergunta.
- Responda perguntas gerais (fatos, datas, explicacoes curtas, duvidas \
tecnicas) usando seu proprio conhecimento, direto e em 1-2 frases faladas.
- Quando responder algo factual que o usuario provavelmente vai perguntar de \
novo (uma preferencia revelada por uma pergunta, uma rotina, um gosto), chame \
`lembrar_de` em silencio alem de responder.
- Se a pergunta exige dado que voce nao tem (clima externo, noticias de hoje, \
pontuacao do jogo, cotacao), diga que nao tem a ferramenta ainda; nao invente.

PERSONALIDADE:
- Fale como um humano experiente e calmo, nao como um robô. Varie sempre: nao \
comece duas respostas seguidas com a mesma palavra ("Certo", "Ok", "Claro"), \
evite frases prontas de assistente ("Entendi! Vou...").
- Tom: elegante e seco, com um fio fino de humor britanico. Pode fazer piada \
sobre a hora, o clima, o que o usuario acabou de pedir, uma coisa boba do dia, \
desde que seja breve (uma linha), faca sentido no contexto e nao atrapalhe o \
pedido. Nao force humor em assunto serio (saude, dinheiro, seguranca, afeto).
- Observe o contexto: se for 2 da manha, comente de leve; se o usuario repetir \
o mesmo pedido pela terceira vez, seja direto; se for a primeira vez do dia, \
cumprimente como humano cumprimenta.
- Nunca copie dialogos literais de filmes ou series. Voce tem personalidade \
propria, nao e imitacao.

AUSCULTACAO (so quando `modo_auscultacao: true` chegar no bloco de estado):
- Voce virou ouvinte, nao assistente. A pessoa quer desabafar, pensar em voz \
alta, reclamar ou processar algo pesado.
- Fale POUCO. Respostas de 1 frase, as vezes so uma palavra ("entendo", "to \
ouvindo", "pode continuar"). Nunca de solucao a nao ser que o usuario peca em \
palavras claras ("o que voce faria?", "me da um conselho").
- Reflita o que ouviu em vez de resolver: "parece que o que mais te irrita e \
X", "voce ficou mais puxado pelo lado do Y ou do Z?". Nomeie o sentimento \
quando ficar obvio, sem psicologizar demais ("isso soa cansativo").
- Pergunta aberta vale mais que afirmacao: "o que aconteceu depois disso?", \
"como voce queria que tivesse sido?". No maximo UMA pergunta por vez.
- Nao julgue, nao console no automatico ("vai dar tudo certo"), nao mude de \
assunto, nao conte sua experiencia. Silencio curto depois dele terminar e \
melhor que enfiar resposta.
- So saia desse modo quando ele disser alguma forma de "pode parar", "e \
isso", "obrigado jarvis", "ja melhorou", "chega". Ai chame \
`encerrar_auscultacao` e volte ao tom normal."""


def instrucoes_com(memoria_resumo):
    """Junta as instruções fixas com o que o JARVIS já sabe nesta sessão."""
    if not memoria_resumo:
        return INSTRUCOES
    return INSTRUCOES + "\n\n" + memoria_resumo

LIMITE_MENSAGENS = 40


@dataclass
class Chamada:
    id: str
    nome: str
    argumentos: dict


@dataclass
class Passo:
    texto: str = ""
    chamadas: list = field(default_factory=list)
    problema: str = ""


@dataclass
class Resultado:
    chamada: Chamada
    texto: str
    erro: bool = False


def carregar_env(caminho):
    """Lê KEY=VALOR do .env sem sobrescrever o que já está no ambiente."""
    try:
        linhas = Path(caminho).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for linha in linhas:
        chave, sep, valor = linha.strip().partition("=")
        if sep and chave and not chave.startswith("#") and valor.strip():
            os.environ.setdefault(chave.strip(), valor.strip().strip('"'))


MAX_STRICT = 20   # limite da API; acima disso ela recusa o pedido inteiro


def montar_ferramentas_da_api(ferramentas):
    """Monta a lista para a API, com `strict` só onde ele vale mais.

    A API aceita no máximo 20 ferramentas com `strict=true`, e o JARVIS já
    passa disso com as skills ligadas. `strict` não é a nossa garantia de
    segurança — `ferramentas.validar()` confere tipo, enum, campo obrigatório
    e campo extra em TODA chamada, antes de executar. Então aqui o `strict`
    vai para onde um argumento errado dói mais: ações perigosas primeiro,
    depois as de lista fechada (enum), depois o resto com argumentos.
    """
    def prioridade(f):
        tem_enum = any("enum" in regra for regra in f.propriedades.values())
        return (not f.perigosa, not tem_enum, not f.propriedades)

    ordenadas = sorted(ferramentas.values(), key=prioridade)
    com_strict = {f.nome for f in ordenadas[:MAX_STRICT] if f.propriedades}
    return [
        {"name": f.nome, "description": f.descricao, "input_schema": f.esquema(),
         **({"strict": True} if f.nome in com_strict else {})}
        for f in ferramentas.values()
    ]


class _Base:
    def __init__(self):
        self.historico = []
        # Atualizado antes de cada chamada da API: resumo de memoria.py.
        self.contexto_extra = ""

    def definir_contexto(self, texto):
        self.contexto_extra = texto or ""

    def marcar(self):
        return len(self.historico)

    def desfazer(self, marca):
        # Só corta o fim do histórico, nunca edita o meio: o que sobra é
        # exatamente o que o modelo já viu, como a API exige.
        del self.historico[marca:]

    def novo_dialogo(self):
        self.historico = []

    async def aquecer(self):
        """Abre a conexão e paga o custo de primeira chamada antes do usuário falar."""
        return None

    def cheio(self):
        return len(self.historico) > LIMITE_MENSAGENS


class CerebroAnthropic(_Base):
    def __init__(self, config, ferramentas, cliente=None):
        super().__init__()
        self.modelo = config["modelo"]
        self.esforco = config.get("esforco", "low")
        self.nome = config.get("nome", self.modelo)
        self.ferramentas = montar_ferramentas_da_api(ferramentas)
        if cliente is None:
            import anthropic
            cliente = anthropic.AsyncAnthropic(max_retries=1, timeout=30)
        self.cliente = cliente

    async def disponivel(self):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False, "sem chave da API no .env"
        import anthropic
        try:
            await self.cliente.models.retrieve(self.modelo)
            return True, ""
        except anthropic.AuthenticationError:
            return False, "chave da API recusada"
        except anthropic.APIConnectionError:
            return False, "sem internet até a API"
        except anthropic.APIStatusError as exc:
            return False, f"API respondeu {exc.status_code}"

    def _tool_results(self, resultados):
        return {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": r.chamada.id, "content": r.texto, "is_error": r.erro}
            for r in resultados
        ]}

    async def falar(self, texto, ao_texto=None):
        self.historico.append({"role": "user", "content": texto})
        return await self._chamar(ao_texto)

    async def devolver(self, resultados, ao_texto=None):
        self.historico.append(self._tool_results(resultados))
        return await self._chamar(ao_texto)

    def fechar_turno(self, resultados, texto):
        """Fecha o turno sem gastar uma segunda chamada à API.

        Todo `tool_use` precisa do seu `tool_result`, senão a próxima chamada
        é recusada. Em vez de descartar o turno (o que apagaria o contexto e
        quebraria um "fecha isso" logo depois), registramos o resultado e o
        que o JARVIS falou — o histórico fica completo e válido.
        """
        self.historico.append(self._tool_results(resultados))
        self.historico.append({"role": "assistant", "content": texto})

    async def aquecer(self):
        # Abre TLS e aquece o caminho do modelo; o custo é de poucos tokens.
        await self.cliente.messages.create(
            model=self.modelo, max_tokens=1, system=instrucoes_com(self.contexto_extra),
            tools=self.ferramentas,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "oi"}],
        )

    def _sanear(self):
        """Tira do histórico qualquer pedaço que a API recusaria.

        Um pedido cancelado no meio (o usuário falou por cima, a conexão caiu)
        pode deixar um `tool_result` sem o `tool_use` dele, e aí TODA chamada
        seguinte falha com 400 — o JARVIS fica mudo até reiniciar. Visto de
        verdade numa instalação interrompida em 21/10/2026.

        Em vez de caçar cada ponto onde o cancelamento pode cair, o histórico
        é conferido antes de cada chamada: é o único lugar por onde tudo passa.
        """
        # Primeiro passe: catalogar tool_use e tool_result que existem.
        usos, resultados = set(), set()
        for mensagem in self.historico:
            conteudo = mensagem.get("content")
            if not isinstance(conteudo, list):
                continue
            for bloco in conteudo:
                tipo = getattr(bloco, "type", None) or (
                    bloco.get("type") if isinstance(bloco, dict) else None)
                if tipo == "tool_use":
                    usos.add(getattr(bloco, "id", None) or bloco.get("id"))
                elif tipo == "tool_result":
                    tid = (bloco.get("tool_use_id") if isinstance(bloco, dict)
                           else getattr(bloco, "tool_use_id", None))
                    resultados.add(tid)

        # Segundo passe: limpar.
        limpo = []
        for mensagem in self.historico:
            conteudo = mensagem.get("content")
            if not isinstance(conteudo, list):
                limpo.append(mensagem)
                continue
            blocos = []
            for bloco in conteudo:
                tipo = getattr(bloco, "type", None) or (
                    bloco.get("type") if isinstance(bloco, dict) else None)
                # Blocos de raciocínio assinados são válidos apenas dentro do
                # turno/conversa em que o provedor os emitiu. Se o processo é
                # reiniciado, há duas instâncias do JARVIS ou o provedor
                # invalida a assinatura, reenviá-los trava todos os pedidos
                # seguintes com BadRequest 400.
                if tipo in {"thinking", "redacted_thinking"}:
                    continue
                if tipo == "tool_use":
                    # Órfão sem tool_result trava a API com
                    # "tool_use ids were found without tool_result blocks".
                    # Isso acontece quando `resposta_pronta=True` pula a 2ª
                    # consulta e o resultado nunca é registrado no histórico.
                    uid = getattr(bloco, "id", None) or bloco.get("id")
                    if uid not in resultados:
                        continue
                elif tipo == "tool_result":
                    tid = (bloco.get("tool_use_id") if isinstance(bloco, dict)
                           else getattr(bloco, "tool_use_id", None))
                    if tid not in usos:
                        continue   # órfão do outro lado
                blocos.append(bloco)
            if blocos:
                limpo.append({**mensagem, "content": blocos})
        # Conversa precisa começar por quem fala primeiro.
        while limpo and limpo[0].get("role") != "user":
            limpo.pop(0)
        if limpo != self.historico:
            self.historico[:] = limpo
        return limpo

    async def _chamar(self, ao_texto=None):
        self._sanear()
        if ao_texto is None:
            resposta = await self.cliente.messages.create(**self._pedido())
        else:
            resposta = await self._chamar_em_fluxo(ao_texto)
        # O conteúdo volta inteiro (inclusive blocos de raciocínio), sem
        # extrair só o texto: a API exige o histórico exatamente como veio.
        self.historico.append({"role": "assistant", "content": resposta.content})
        if resposta.stop_reason == "refusal":
            return Passo(problema="o modelo se recusou a responder")
        if resposta.stop_reason == "max_tokens":
            return Passo(problema="a resposta foi cortada no meio")
        passo = Passo()
        for bloco in resposta.content:
            if bloco.type == "tool_use":
                passo.chamadas.append(Chamada(bloco.id, bloco.name, dict(bloco.input)))
            elif bloco.type == "text":
                passo.texto += bloco.text
        passo.texto = passo.texto.strip()
        if not passo.chamadas and not passo.texto:
            passo.problema = "resposta vazia"
        return passo

    def _pedido(self):
        return dict(
            model=self.modelo,
            max_tokens=2048,
            system=instrucoes_com(self.contexto_extra),
            tools=self.ferramentas,
            output_config={"effort": self.esforco},
            messages=self.historico,
        )

    async def _chamar_em_fluxo(self, ao_texto):
        """Entrega o texto em pedaços para o JARVIS já começar a falar.

        Para de entregar assim que uma ferramenta aparece: dali em diante o
        texto pertence ao passo seguinte, não à resposta ao usuário.
        """
        async with self.cliente.messages.stream(**self._pedido()) as fluxo:
            usou_ferramenta = False
            async for evento in fluxo:
                if evento.type == "input_json":
                    usou_ferramenta = True
                elif evento.type == "text" and not usou_ferramenta:
                    ao_texto(evento.text)
            return await fluxo.get_final_message()


class CerebroOllama(_Base):
    def __init__(self, config, ferramentas, cliente=None):
        super().__init__()
        self.url = config.get("ollama_url", "http://127.0.0.1:11434").rstrip("/")
        self.modelo = config.get("ollama_modelo", "qwen3.5:4b")
        self.nome = "Ollama " + self.modelo
        self.ferramentas = [
            {"type": "function", "function": {
                "name": f.nome, "description": f.descricao, "parameters": f.esquema()}}
            for f in ferramentas.values()
        ]
        # Modelo local na GPU de 6 GB pode levar dezenas de segundos na primeira carga.
        self.cliente = cliente or httpx.AsyncClient(timeout=120)

    async def disponivel(self):
        try:
            r = await self.cliente.get(self.url + "/api/tags", timeout=3)
            nomes = [m["name"] for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError):
            return False, "Ollama não está rodando"
        if self.modelo not in nomes:
            return False, f"modelo {self.modelo} não baixado"
        return True, ""

    async def falar(self, texto, ao_texto=None):
        self.historico.append({"role": "user", "content": texto})
        return await self._chamar()

    async def devolver(self, resultados, ao_texto=None):
        self._registrar_resultados(resultados)
        return await self._chamar()

    def _registrar_resultados(self, resultados):
        for r in resultados:
            self.historico.append({"role": "tool", "tool_name": r.chamada.nome,
                                   "content": ("ERRO: " if r.erro else "") + r.texto})

    def fechar_turno(self, resultados, texto):
        self._registrar_resultados(resultados)
        self.historico.append({"role": "assistant", "content": texto})

    async def _chamar(self):
        r = await self.cliente.post(self.url + "/api/chat", json={
            "model": self.modelo,
            "messages": [{"role": "system", "content": instrucoes_com(self.contexto_extra)}] + self.historico,
            "tools": self.ferramentas,
            "stream": False,
            # raciocínio longo do qwen3 custa segundos e não melhora escolha de ferramenta simples
            "think": False,
        })
        r.raise_for_status()
        msg = r.json().get("message") or {}
        self.historico.append(msg)
        passo = Passo(texto=(msg.get("content") or "").strip())
        for ch in msg.get("tool_calls") or []:
            fn = ch.get("function") or {}
            argumentos = fn.get("arguments") or {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except ValueError:
                    return Passo(problema="argumentos de ferramenta ilegíveis")
            passo.chamadas.append(Chamada(uuid.uuid4().hex[:8], fn.get("name", ""), argumentos))
        if not passo.chamadas and not passo.texto:
            passo.problema = "resposta vazia"
        return passo


def criar_cerebro(config, ferramentas):
    tipo = config["tipo"]
    if tipo == "anthropic":
        return CerebroAnthropic(config, ferramentas)
    if tipo == "ollama":
        return CerebroOllama(config, ferramentas)
    raise ValueError(f"cérebro desconhecido no config.json: {tipo}")
