import asyncio
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.agente import NAO_ENTENDI, Agente, comando_rapido, eh_confirmacao
from jarvis.cerebro import Chamada, CerebroAnthropic, CerebroOllama, Passo
from jarvis.estado import Painel
from jarvis.ferramentas import ErroFerramenta, criar_ferramentas, normalizar_site, validar

CONFIG = {
    "agente_energia": {"url": "http://agente.invalido", "token": "inexistente.txt"},
    "programas": {"calculadora": "calc.exe", "bloco de notas": "notepad.exe"},
}


class PlacaFalsa:
    def __init__(self):
        self.acoes = []

    async def ler_status(self):
        return {"temperatura": 27, "umidade": 40, "movimento": False, "led": True}

    async def acao(self, nome):
        self.acoes.append(nome)

    async def acordar_pc(self):
        return "PC acordando"


class CerebroFalso:
    """Devolve passos roteirizados e registra o que o agente mandou."""
    nome = "falso"

    def __init__(self, passos):
        self.passos = list(passos)
        self.historico = []
        self.devolvidos = []
        self.em_fluxo = None

    async def disponivel(self):
        return True, ""

    def marcar(self):
        return len(self.historico)

    def desfazer(self, marca):
        del self.historico[marca:]

    def novo_dialogo(self):
        self.historico = []

    def cheio(self):
        return False

    async def falar(self, texto, ao_texto=None):
        self.historico.append(("user", texto))
        self.em_fluxo = ao_texto
        return self._proximo()

    async def devolver(self, resultados, ao_texto=None):
        self.devolvidos.append(resultados)
        self.historico.append(("resultados", resultados))
        self.em_fluxo = ao_texto
        return self._proximo()

    def fechar_turno(self, resultados, texto):
        # Não entra em `devolvidos`: fechar o turno NÃO é uma segunda consulta.
        self.historico.append(("resultados", resultados))
        self.historico.append(("assistant", texto))

    def _proximo(self):
        p = self.passos.pop(0)
        if isinstance(p, Exception):
            raise p
        self.historico.append(("assistant", p))
        return p


def montar(passos, **agente_kwargs):
    painel = Painel()
    placa = PlacaFalsa()
    abertos = []
    ferramentas = criar_ferramentas(CONFIG, placa, abrir=abertos.append,
                                    agora=lambda: datetime(2026, 10, 21, 14, 5))
    executadas = []

    async def suspender_falso():
        executadas.append("suspender_pc")
        return "Suspendendo o computador."
    ferramentas["suspender_pc"].funcao = suspender_falso

    cerebro = CerebroFalso(passos)
    agente = Agente(painel, cerebro, ferramentas, **agente_kwargs)

    async def sem_espera(segundos, gerador):
        pass
    agente._niveis = sem_espera
    return agente, cerebro, painel, placa, abertos, executadas


def rodar(agente, *textos):
    async def tudo():
        for t in textos:
            await agente.processar(t)
    asyncio.run(tudo())


def chamada(nome, **args):
    return Passo(chamadas=[Chamada("id-" + nome, nome, args)])


class AgenteTests(unittest.TestCase):
    def test_resposta_simples_chega_ao_painel_e_volta_ao_repouso(self):
        agente, _, painel, *_ = montar([Passo(texto="Olá, senhor.")])
        rodar(agente, "oi")
        self.assertEqual(painel.agente["ultima_resposta"], "Olá, senhor.")
        self.assertEqual(painel.agente["estado"], "repouso")

    def test_modo_seguro_exige_novo_chamado_depois_da_resposta(self):
        agente, cerebro, painel, *_ = montar(
            [Passo(texto="Pronto.")], exigir_chamado_a_cada_frase=True
        )
        async def ouvir():
            await agente.ao_ouvir("Jarvis, diga olá", None, None)
            if agente.tarefa:
                await agente.tarefa
            self.antes = len([h for h in cerebro.historico if h[0] == "user"])
            await agente.ao_ouvir("uma frase captada da TV", None, None)
        asyncio.run(ouvir())
        depois = len([h for h in cerebro.historico if h[0] == "user"])
        self.assertEqual(depois, self.antes)
        self.assertIn("novo chamado", painel.atividade[0]["texto"])

    def test_hora_e_data_e_resolvida_sem_consultar_o_cerebro(self):
        agente, cerebro, painel, *_ = montar([])
        rodar(agente, "que horas são?")
        self.assertTrue("14:05" in painel.agente["ultima_resposta"] or "14 e 05" in painel.agente["ultima_resposta"], painel.agente["ultima_resposta"])
        self.assertEqual(cerebro.historico, [])
        self.assertEqual(cerebro.devolvidos, [])

    def test_temperatura_e_resolvida_sem_consultar_o_cerebro(self):
        agente, cerebro, painel, *_ = montar([])
        rodar(agente, "qual é a temperatura?")
        self.assertIn("27", painel.agente["ultima_resposta"])
        self.assertEqual(cerebro.historico, [])

    def test_falha_do_sensor_vira_mensagem_direta(self):
        agente, cerebro, painel, *_ = montar([])

        async def placa_morta():
            raise ErroFerramenta("a placa não respondeu")

        agente.ferramentas["ler_sensores"].funcao = placa_morta
        rodar(agente, "qual a temperatura?")
        self.assertIn("Não consegui ler os sensores", painel.agente["ultima_resposta"])
        self.assertEqual(cerebro.historico, [])

    def test_comando_sem_ferramenta_nao_vira_atalho(self):
        self.assertIsNone(comando_rapido("inicie um timer de cinco minutos"))
        self.assertIsNone(comando_rapido("aumenta o volume"))

    def test_ferramenta_com_frase_pronta_pula_consulta_final(self):
        agente, cerebro, painel, *_ = montar([chamada("abrir_site", endereco="youtube.com")])
        rodar(agente, "abre o YouTube")
        self.assertIn("youtube", painel.agente["ultima_resposta"].lower())
        self.assertEqual(cerebro.devolvidos, [], "não pode haver segunda consulta à API")
        # O turno fica COMPLETO no histórico (pergunta, tool_use, resultado e fala):
        # válido para a API e com o contexto preservado para um "fecha isso" depois.
        papeis = [h[0] for h in cerebro.historico]
        self.assertEqual(papeis, ["user", "assistant", "resultados", "assistant"])

    def test_ferramenta_sem_frase_pronta_devolve_resultado_ao_cerebro(self):
        agente, cerebro, painel, *_ = montar([
            chamada("abrir_site", endereco="youtube.com"), Passo(texto="São 14:05.")])
        agente.ferramentas["abrir_site"].resposta_pronta = False
        rodar(agente, "abre o YouTube")
        # Resposta variada; o importante é que o endereço aparece em alguma forma.
        self.assertIn("youtube", cerebro.devolvidos[0][0].texto.lower())
        self.assertEqual(painel.agente["ultima_resposta"], "São 14:05.")

    def test_ferramenta_inexistente_vira_nao_entendi_sem_executar_nada(self):
        agente, cerebro, painel, placa, abertos, _ = montar([chamada("rodar_comando", cmd="format c:")])
        rodar(agente, "formata tudo")
        self.assertTrue(any(w in painel.agente["ultima_resposta"].lower() for w in ["não entendi","não peguei","me perdi","fiquei em dúvida","não ficou claro"]), f"não variante: {painel.agente['ultima_resposta']!r}")
        self.assertEqual((placa.acoes, abertos), ([], []))
        self.assertEqual(cerebro.historico, [], "o turno recusado deve sair do histórico")

    def test_argumento_fora_da_lista_vira_nao_entendi(self):
        agente, _, painel, _, abertos, _ = montar([chamada("abrir_programa", programa="cmd.exe")])
        rodar(agente, "abre o cmd")
        self.assertTrue(any(w in painel.agente["ultima_resposta"].lower() for w in ["não entendi","não peguei","me perdi","fiquei em dúvida","não ficou claro"]), f"não variante: {painel.agente['ultima_resposta']!r}")
        self.assertEqual(abertos, [])

    def test_resposta_fora_do_formato_vira_nao_entendi(self):
        agente, _, painel, *_ = montar([Passo(problema="resposta vazia")])
        rodar(agente, "hm")
        self.assertTrue(any(w in painel.agente["ultima_resposta"].lower() for w in ["não entendi","não peguei","me perdi","fiquei em dúvida","não ficou claro"]), f"não variante: {painel.agente['ultima_resposta']!r}")

    def test_acao_perigosa_espera_o_sim_antes_de_rodar(self):
        agente, cerebro, painel, *_, executadas = montar(
            [chamada("suspender_pc"), Passo(texto="Boa noite.")])
        rodar(agente, "suspende o pc")
        self.assertEqual(executadas, [], "não pode suspender antes da confirmação")
        self.assertIn("Confirma", painel.agente["ultima_resposta"])
        rodar(agente, "sim, pode")
        self.assertEqual(executadas, ["suspender_pc"])
        self.assertEqual(painel.agente["ultima_resposta"], "Suspendendo o computador.")
        self.assertEqual(cerebro.devolvidos, [], "confirmado não gasta segunda consulta")
        # Turno completo: pedido, tool_use, resultado e a fala.
        self.assertEqual([h[0] for h in cerebro.historico],
                         ["user", "assistant", "resultados", "assistant"])

    def test_qualquer_coisa_diferente_de_sim_cancela_a_acao_perigosa(self):
        agente, cerebro, painel, *_, executadas = montar(
            [chamada("suspender_pc"), Passo(texto="Tudo bem, não suspendi.")])
        rodar(agente, "suspende o pc", "não, espera")
        self.assertEqual(executadas, [])
        self.assertIn("NÃO confirmou", cerebro.devolvidos[0][0].texto)

    def test_falha_de_ferramenta_e_devolvida_como_erro(self):
        agente, cerebro, *_ = montar([chamada("ler_sensores"), Passo(texto="A placa não respondeu.")])

        async def placa_morta():
            raise ErroFerramenta("a placa não respondeu")
        agente.ferramentas["ler_sensores"].funcao = placa_morta
        rodar(agente, "verifique a placa")
        self.assertTrue(cerebro.devolvidos[0][0].erro)

    def test_cerebro_fora_do_ar_mostra_erro_e_limpa_o_historico(self):
        agente, cerebro, painel, *_ = montar([httpx.ConnectError("sem rede")])

        async def tudo():
            original = asyncio.sleep

            async def rapido(_):
                await original(0)
            import jarvis.agente as mod
            mod.asyncio.sleep, antigo = rapido, mod.asyncio.sleep
            try:
                await agente.processar("oi")
            finally:
                mod.asyncio.sleep = antigo
        asyncio.run(tudo())
        self.assertTrue(any(a["tipo"] == "erro" for a in painel.atividade))
        self.assertFalse(any(a["tipo"] == "cerebro" for a in painel.atividade))
        self.assertEqual(cerebro.historico, [])

    def test_luz_chega_na_placa(self):
        agente, _, _, placa, *_ = montar([chamada("controlar_luz", modo="desligar"), Passo(texto="Apagada.")])
        rodar(agente, "apaga a luz")
        self.assertEqual(placa.acoes, ["luz_desligar"])


class ConfirmacaoTests(unittest.TestCase):
    def test_sim_e_variacoes(self):
        for t in ["sim", "Sim, pode", "pode sim", "Confirmo.", "OK"]:
            self.assertTrue(eh_confirmacao(t), t)

    def test_nao_e_ambiguos(self):
        for t in ["não", "nao pode", "sim, não", "talvez", "", "espera"]:
            self.assertFalse(eh_confirmacao(t), t)


class FerramentasTests(unittest.TestCase):
    def setUp(self):
        self.f = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda a: None)

    def test_campo_extra_e_recusado(self):
        self.assertIsNotNone(validar(self.f["controlar_luz"], {"modo": "ligar", "forca": "max"}))

    def test_so_abre_sites_http(self):
        for ruim in ["javascript:alert(1)", "file:///c:/windows", "ftp://x.com", "a b.com"]:
            with self.assertRaises(ErroFerramenta, msg=ruim):
                normalizar_site(ruim)
        self.assertEqual(normalizar_site("youtube.com"), "https://youtube.com")

    def test_programa_abre_o_executavel_da_lista(self):
        abertos = []
        f = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=abertos.append)
        asyncio.run(f["abrir_programa"].funcao(programa="calculadora"))
        self.assertEqual(abertos, ["calc.exe"])

    def test_nao_existe_ferramenta_de_comando_livre(self):
        for nome in self.f:
            self.assertNotIn("comando", nome)
            self.assertNotIn("shell", nome)

    def test_suspender_sem_token_falha_com_mensagem(self):
        with self.assertRaises(ErroFerramenta):
            asyncio.run(self.f["suspender_pc"].funcao())


class CerebroAnthropicTests(unittest.TestCase):
    def cerebro(self, resposta):
        chamadas = []

        async def create(**kw):
            chamadas.append(kw)
            return resposta
        cliente = SimpleNamespace(messages=SimpleNamespace(create=create))
        self.ferramentas = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda a: None)
        return CerebroAnthropic({"modelo": "claude-haiku-5-5"}, self.ferramentas, cliente=cliente), chamadas

    def test_le_chamada_de_ferramenta_e_texto(self):
        resp = SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="text", text="Vou ver."),
            SimpleNamespace(type="tool_use", id="t1", name="ler_sensores", input={}),
        ])
        c, chamadas = self.cerebro(resp)
        passo = asyncio.run(c.falar("temperatura?"))
        self.assertEqual(passo.chamadas[0].nome, "ler_sensores")
        self.assertEqual(passo.texto, "Vou ver.")
        # strict vai só nas mais sensíveis (a API limita a 20); a garantia de
        # argumento válido é o validar() do agente, que roda em toda chamada.
        enviadas = chamadas[0]["tools"]
        perigosas = {f.nome for f in self.ferramentas.values() if f.perigosa and f.propriedades}
        com_strict = {t["name"] for t in enviadas if t.get("strict")}
        self.assertTrue(perigosas <= com_strict, "ação perigosa tem que ir com strict")
        self.assertIs(c.historico[-1]["content"], resp.content, "histórico guarda o conteúdo inteiro")

    def test_frase_pronta_pula_consulta_e_remove_turno_tool_use_pendente(self):
        resp = SimpleNamespace(stop_reason="tool_use", content=[
            SimpleNamespace(type="tool_use", id="t1", name="abrir_site",
                            input={"endereco": "youtube.com"}),
        ])
        c, chamadas = self.cerebro(resp)
        ferramentas = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda _: None)
        painel = Painel()
        agente = Agente(painel, c, ferramentas)

        async def sem_espera(_segundos, _gerador):
            pass
        agente._niveis = sem_espera

        async def executar():
            await agente.processar("abre o YouTube")
        asyncio.run(executar())

        self.assertEqual(len(chamadas), 1, "não deve haver consulta final para parafrasear")
        self.assertIn("youtube", painel.agente["ultima_resposta"].lower())
        # O histórico tem que continuar aceitável pela API: todo tool_use com o
        # seu tool_result. E o pedido tem que sobreviver, para um "fecha isso".
        usos, resultados = set(), set()
        for m in c.historico:
            for bloco in m["content"] if isinstance(m["content"], list) else []:
                tipo = getattr(bloco, "type", None) or (bloco.get("type") if isinstance(bloco, dict) else None)
                if tipo == "tool_use":
                    usos.add(bloco.id)
                elif tipo == "tool_result":
                    resultados.add(bloco["tool_use_id"])
        self.assertEqual(usos, resultados, "todo tool_use precisa do seu tool_result")
        self.assertIn("abre o YouTube", [m["content"] for m in c.historico if isinstance(m["content"], str)])

    def test_recusa_vira_problema(self):
        c, _ = self.cerebro(SimpleNamespace(stop_reason="refusal", content=[]))
        self.assertTrue(asyncio.run(c.falar("x")).problema)


class CerebroOllamaTests(unittest.TestCase):
    def cerebro(self, mensagem):
        def responder(req):
            return httpx.Response(200, json={"message": mensagem})
        cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
        f = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda a: None)
        return CerebroOllama({}, f, cliente=cliente)

    def test_le_tool_calls(self):
        c = self.cerebro({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "controlar_luz", "arguments": {"modo": "ligar"}}}]})
        passo = asyncio.run(c.falar("liga a luz"))
        self.assertEqual((passo.chamadas[0].nome, passo.chamadas[0].argumentos),
                         ("controlar_luz", {"modo": "ligar"}))

    def test_argumentos_ilegiveis_viram_problema(self):
        c = self.cerebro({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "controlar_luz", "arguments": "{modo: ligar"}}]})
        self.assertTrue(asyncio.run(c.falar("liga")).problema)


if __name__ == "__main__":
    unittest.main()


from jarvis.agente import comando_de_tela
from jarvis.ouvinte import separar_chamado


class JanelaFalsa:
    def __init__(self):
        self.movimentos = []

    def mudar(self, qual):
        self.movimentos.append(qual)
        return 2

    def chamar(self):
        self.movimentos.append("chamar")


class ChamadoTests(unittest.TestCase):
    def test_reconhece_o_nome_e_separa_o_pedido(self):
        self.assertEqual(separar_chamado("Jarvis, abre o YouTube."), (True, "abre o YouTube"))
        self.assertEqual(separar_chamado("Ô Jarbas, que horas são?"), (True, "que horas são"))
        self.assertEqual(separar_chamado("Jarvis."), (True, ""))

    def test_conversa_sem_o_nome_nao_e_chamado(self):
        self.assertEqual(separar_chamado("passa o sal por favor"), (False, ""))

    def test_comandos_de_tela(self):
        casos = {"muda de tela": "outra", "chega pra lá": "outra", "vai pra segunda tela": "segunda",
                 "joga na primeira tela": "primeira", "abre o youtube": None, "qual a temperatura": None}
        for frase, esperado in casos.items():
            self.assertEqual(comando_de_tela(frase), esperado, frase)


class OuvirTests(unittest.TestCase):
    def montar_com_janela(self, passos):
        agente, cerebro, painel, *_ = montar(passos)
        agente.janela = JanelaFalsa()
        return agente, cerebro, painel

    def ouvir(self, agente, *frases):
        async def tudo():
            for f in frases:
                await agente.ao_ouvir(f)
                if agente.tarefa:
                    await agente.tarefa
        asyncio.run(tudo())

    def test_fala_da_sala_sem_o_nome_e_ignorada(self):
        agente, cerebro, painel = self.montar_com_janela([])
        self.ouvir(agente, "vamos almoçar agora")
        self.assertEqual(cerebro.historico, [])
        self.assertEqual(agente.janela.movimentos, [])

    def test_nome_mais_pedido_chama_a_janela_e_processa(self):
        agente, cerebro, painel = self.montar_com_janela([Passo(texto="São 14:05.")])
        self.ouvir(agente, "Jarvis, que horas são?")
        self.assertEqual(agente.janela.movimentos[0], "chamar")
        self.assertEqual(cerebro.historico, [])
        self.assertTrue("14:05" in painel.agente["ultima_resposta"] or "14 e 05" in painel.agente["ultima_resposta"], painel.agente["ultima_resposta"])

    def test_chega_pra_la_move_a_janela_sem_consultar_o_cerebro(self):
        agente, cerebro, painel = self.montar_com_janela([])
        self.ouvir(agente, "Jarvis, chega pra lá")
        self.assertIn("outra", agente.janela.movimentos)
        self.assertEqual(cerebro.historico, [])

    def test_resposta_da_confirmacao_vale_sem_repetir_o_nome(self):
        agente, cerebro, painel = self.montar_com_janela([chamada("suspender_pc"), Passo(texto="Ok.")])
        executadas = []

        async def suspender():
            executadas.append(1)
            return "Suspendendo."
        agente.ferramentas["suspender_pc"].funcao = suspender
        self.ouvir(agente, "Jarvis, suspende o computador", "sim")
        self.assertEqual(executadas, [1])


class RecursosTests(unittest.TestCase):
    def test_luz_desligada_tira_a_ferramenta(self):
        cfg = dict(CONFIG, recursos={"luz": False})
        self.assertNotIn("controlar_luz", criar_ferramentas(cfg, PlacaFalsa(), abrir=lambda a: None))

    def test_ferramenta_de_tela_so_existe_com_janela(self):
        self.assertNotIn("mudar_tela", criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda a: None))
        f = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda a: None, janela=JanelaFalsa())
        self.assertEqual(asyncio.run(f["mudar_tela"].funcao(tela="outra")), "Janela na tela 2.")


class SairDaFrenteTests(unittest.TestCase):
    """Abriu algo na tela de chamada? O JARVIS se recolhe para a outra tela."""

    def montar_com_janela(self, passos):
        agente, cerebro, painel, placa, abertos, _ = montar(passos)
        agente.janela = JanelaFalsa()
        agente.janela.repousar = lambda: agente.janela.movimentos.append("repousar")
        return agente, painel

    def test_abrir_site_faz_o_jarvis_sair_da_frente(self):
        agente, _ = self.montar_com_janela(
            [chamada("abrir_site", endereco="youtube.com"), Passo(texto="Pronto.")])
        rodar(agente, "abre o youtube")
        self.assertIn("repousar", agente.janela.movimentos)

    def test_pedido_que_nao_abre_nada_deixa_a_janela_onde_esta(self):
        agente, _ = self.montar_com_janela([chamada("hora_e_data"), Passo(texto="São 14h.")])
        rodar(agente, "que horas são")
        self.assertNotIn("repousar", agente.janela.movimentos)

    def test_se_falhou_ao_abrir_nao_sai_da_frente(self):
        agente, _ = self.montar_com_janela(
            [chamada("abrir_site", endereco="youtube.com"), Passo(texto="Falhou.")])

        async def quebrado(**_):
            raise ErroFerramenta("navegador não abriu")
        agente.ferramentas["abrir_site"].funcao = quebrado
        rodar(agente, "abre o youtube")
        self.assertNotIn("repousar", agente.janela.movimentos)


class OcupadoTests(unittest.TestCase):
    """Pedido novo não pode matar uma ação em andamento.

    Achado num teste real: a instalação do VLC foi cancelada no meio por uma
    fala captada do quarto, e o winget ficou rodando órfão."""

    def montar_executando(self):
        agente, cerebro, painel, *_ = montar([])
        agente.executando = "instalar_programa"
        agente.conversa = {"dono": None, "ate": 1e18}
        return agente, cerebro, painel

    def ouvir(self, agente, texto):
        async def tudo():
            await agente.ao_ouvir(texto, None, None)
            if agente.tarefa:
                await agente.tarefa
        asyncio.run(tudo())

    def test_fala_qualquer_nao_derruba_a_acao_em_andamento(self):
        agente, cerebro, painel = self.montar_executando()
        self.ouvir(agente, "abre o google para mim")
        self.assertEqual(cerebro.historico, [], "não podia nem chegar ao cérebro")
        self.assertIn("ainda está rodando", painel.atividade[0]["texto"])

    def test_pedido_explicito_de_cancelar_ainda_passa(self):
        agente, cerebro, painel = self.montar_executando()
        self.ouvir(agente, "cancela isso")
        self.assertNotEqual(painel.atividade[0]["texto"][:7], "Ignorei")

    def test_sem_nada_executando_o_pedido_passa_normal(self):
        agente, cerebro, painel, *_ = montar([Passo(texto="ok")])
        agente.conversa = {"dono": None, "ate": 1e18}
        # "que horas são" não serve: vira atalho local e não chega ao cérebro.
        self.ouvir(agente, "me conta uma curiosidade")
        self.assertTrue(any(h[0] == "user" for h in cerebro.historico))

    def test_executando_e_limpo_mesmo_quando_a_ferramenta_falha(self):
        agente, cerebro, painel, *_ = montar([chamada("ler_sensores"), Passo(texto="falhou")])

        async def quebrado(**_):
            raise ErroFerramenta("placa morta")
        agente.ferramentas["ler_sensores"].funcao = quebrado
        rodar(agente, "qual a temperatura")
        self.assertIsNone(agente.executando, "senão o JARVIS fica surdo para sempre")


class HistoricoAposFalhaTests(unittest.TestCase):
    """Ferramenta perigosa que FALHA depois do "sim" não pode deixar o
    histórico inválido. Visto de verdade: a API recusou com
    "unexpected tool_use_id found in tool_result blocks"."""

    def montar(self):
        enviados = []

        async def create(**kw):
            enviados.append([dict(m) for m in kw["messages"]])
            return SimpleNamespace(stop_reason="end_turn", content=[
                SimpleNamespace(type="text", text="Não consegui instalar.")])

        cliente = SimpleNamespace(messages=SimpleNamespace(create=create))
        ferramentas = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda _: None)

        async def falha(**_):
            raise ErroFerramenta("a instalação falhou")
        ferramentas["suspender_pc"].funcao = falha
        cerebro = CerebroAnthropic({"modelo": "claude-haiku-5-5"}, ferramentas, cliente=cliente)
        painel = Painel()
        agente = Agente(painel, cerebro, ferramentas)

        async def sem_espera(_s, _g):
            pass
        agente._niveis = sem_espera
        return agente, cerebro, enviados

    def test_historico_continua_valido_depois_da_falha(self):
        agente, cerebro, enviados = self.montar()

        async def tudo():
            await agente.processar("suspende o pc")
            await agente.processar("sim")
        asyncio.run(tudo())

        # Todo tool_result enviado precisa ter o tool_use dele na mesma conversa.
        for mensagens in enviados:
            usos = {b.id for m in mensagens if isinstance(m["content"], list)
                    for b in m["content"] if getattr(b, "type", None) == "tool_use"}
            resultados = {b["tool_use_id"] for m in mensagens if isinstance(m["content"], list)
                          for b in m["content"]
                          if isinstance(b, dict) and b.get("type") == "tool_result"}
            self.assertTrue(resultados <= usos,
                            f"tool_result sem tool_use: {resultados - usos}")


class SanearHistoricoTests(unittest.TestCase):
    """Histórico quebrado por cancelamento não pode emudecer o JARVIS.

    O erro real foi: "unexpected tool_use_id found in tool_result blocks" em
    TODA chamada seguinte, até reiniciar o app."""

    def cerebro(self):
        f = criar_ferramentas(CONFIG, PlacaFalsa(), abrir=lambda _: None)
        return CerebroAnthropic({"modelo": "claude-haiku-5-5"}, f, cliente=None)

    def test_tool_result_orfao_e_removido(self):
        c = self.cerebro()
        c.historico = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "sumiu", "content": "x"}]},
            {"role": "user", "content": "e agora?"},
        ]
        limpo = c._sanear()
        self.assertEqual([m["content"] for m in limpo], ["e agora?"])

    def test_tool_result_com_dono_na_conversa_fica(self):
        c = self.cerebro()
        c.historico = [
            {"role": "user", "content": "que horas são"},
            {"role": "assistant", "content": [
                SimpleNamespace(type="tool_use", id="t1", name="hora_e_data", input={})]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "14h"}]},
        ]
        self.assertEqual(len(c._sanear()), 3, "turno completo não pode ser mexido")

    def test_conversa_sempre_comeca_pelo_usuario(self):
        c = self.cerebro()
        c.historico = [
            {"role": "assistant", "content": "sobrou daqui"},
            {"role": "user", "content": "oi"},
        ]
        self.assertEqual(c._sanear()[0]["role"], "user")

    def test_historico_bom_nao_e_alterado(self):
        c = self.cerebro()
        c.historico = [{"role": "user", "content": "oi"},
                       {"role": "assistant", "content": "olá"}]
        antes = list(c.historico)
        self.assertEqual(c._sanear(), antes)

    def test_raciocinio_assinado_invalido_e_removido(self):
        c = self.cerebro()
        c.historico = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "assinatura antiga", "signature": "invalida"},
                SimpleNamespace(type="text", text="olá"),
            ]},
        ]
        limpo = c._sanear()
        blocos = limpo[1]["content"]
        self.assertEqual([getattr(b, "type", None) for b in blocos], ["text"])
