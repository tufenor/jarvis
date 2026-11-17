import asyncio
import datetime
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jarvis.alexa import PonteAlexa
from jarvis.alexa_protocolo import assinar, verificar
from jarvis.ouvinte import Ouvinte


RAIZ = Path(__file__).resolve().parents[1]
CHAVE_PC = "1" * 64
CHAVE_ESP = "2" * 64
TOPICO = "jarvis/" + "a" * 32


def configuracao():
    return {"topico": TOPICO, "chave": CHAVE_PC,
            "broker": {"host": "mqtt.exemplo.local", "porta": 8883,
                       "usuario": "u", "senha": "s"}}


class ClienteFalso:
    def __init__(self):
        self.publicados = []

    def publish(self, topico, mensagem, qos=0, retain=False):
        self.publicados.append((topico, mensagem, qos, retain))


class PainelFalso:
    def __init__(self):
        self.agente = {"ultima_resposta": ""}
        self.registros = []

    def registrar(self, tipo, texto):
        self.registros.append((tipo, texto))

    async def publicar(self):
        return None


class JanelaFalsa:
    def __init__(self, bloqueada=False):
        self.bloqueada = bloqueada
        self.chamadas = 0

    def chamar(self):
        self.chamadas += 1


class AgenteFalso:
    def __init__(self, janela=None, confirmacao=False):
        self.janela = janela or JanelaFalsa()
        self.tarefa = None
        self.pendente = None
        self.confirmacao = confirmacao
        self.ultima_atividade = 0
        self.pedidos = []
        self.painel = None

    async def processar(self, texto):
        self.pedidos.append(texto)
        self.painel.agente["ultima_resposta"] = "Resposta: " + texto
        if self.confirmacao:
            self.pendente = {"origem": "alexa"}


class PonteAlexaTests(unittest.TestCase):
    def ponte(self, diretorio, bloqueada=False, confirmacao=False):
        painel = PainelFalso()
        agente = AgenteFalso(JanelaFalsa(bloqueada), confirmacao)
        agente.painel = painel
        ponte = PonteAlexa(configuracao(), agente, painel, Path(diretorio) / "ids.json")
        ponte.cliente = ClienteFalso()
        return ponte, agente

    def pedido(self, acao, texto="", pedido_id="b" * 32):
        return assinar(TOPICO + "/comandos", CHAVE_PC, pedido_id, acao, texto=texto)

    def resposta_publicada(self, ponte):
        topico, mensagem, *_ = ponte.cliente.publicados[-1]
        return verificar(mensagem, topico, CHAVE_PC, {"resposta"})

    def test_comando_assinado_e_resposta(self):
        with tempfile.TemporaryDirectory() as diretorio:
            ponte, agente = self.ponte(diretorio)
            asyncio.run(ponte.tratar(self.pedido("comando", "que horas são?"), TOPICO + "/comandos"))
            self.assertEqual(agente.pedidos, ["que horas são?"])
            resposta = self.resposta_publicada(ponte)
            self.assertEqual(resposta["estado"], "resposta")
            self.assertIn("que horas", resposta["texto"])

    def test_pedido_repetido_nao_reexecuta(self):
        with tempfile.TemporaryDirectory() as diretorio:
            ponte, agente = self.ponte(diretorio)
            pedido = self.pedido("comando", "teste", "c" * 32)
            asyncio.run(ponte.tratar(pedido, TOPICO + "/comandos"))
            asyncio.run(ponte.tratar(pedido, TOPICO + "/comandos"))
            self.assertEqual(agente.pedidos, ["teste"])

    def test_bloqueio_nao_e_burlado(self):
        with tempfile.TemporaryDirectory() as diretorio:
            ponte, agente = self.ponte(diretorio, bloqueada=True)
            asyncio.run(ponte.tratar(self.pedido("comando", "abra o navegador"), TOPICO + "/comandos"))
            self.assertEqual(agente.pedidos, [])
            self.assertEqual(self.resposta_publicada(ponte)["estado"], "bloqueado")

    def test_pedido_com_confirmacao_mantem_estado(self):
        with tempfile.TemporaryDirectory() as diretorio:
            ponte, _ = self.ponte(diretorio, confirmacao=True)
            asyncio.run(ponte.tratar(self.pedido("comando", "suspender"), TOPICO + "/comandos"))
            self.assertEqual(self.resposta_publicada(ponte)["estado"], "confirmacao")


class ProtocoloTests(unittest.TestCase):
    def test_rejeita_acao_que_nao_e_texto(self):
        mensagem = assinar(TOPICO, CHAVE_PC, "d" * 32, 42)
        with self.assertRaises(ValueError):
            verificar(mensagem, TOPICO, CHAVE_PC, {"comando"})

    def test_rejeita_expiracao_e_alteracao(self):
        mensagem = assinar(TOPICO, CHAVE_PC, "e" * 32, "comando", agora=100, validade=2)
        with self.assertRaises(ValueError):
            verificar(mensagem, TOPICO, CHAVE_PC, {"comando"}, agora=102)
        pacote = json.loads(mensagem)
        pacote["corpo"] = pacote["corpo"].replace("comando", "abrir")
        with self.assertRaises(ValueError):
            verificar(json.dumps(pacote), TOPICO, CHAVE_PC, {"abrir"}, agora=100)


class FirmwareWakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        caminho = str(RAIZ / "firmware" / "micropython")
        if caminho not in sys.path:
            sys.path.insert(0, caminho)
        caminho_jarvis = str(RAIZ / "jarvis")
        if caminho_jarvis not in sys.path:
            sys.path.insert(0, caminho_jarvis)
        cls.modulo = importlib.import_module("alexa_wake")

    def test_despertar_assinado_so_uma_vez(self):
        chamadas, publicados = [], []
        config = {"topico": TOPICO, "chave": CHAVE_ESP}
        receptor = self.modulo.ReceptorWake(config, lambda: (chamadas.append(True) or True, ""),
                                             lambda t, m: publicados.append((t, m)))
        pedido = assinar(TOPICO + "/acordar", CHAVE_ESP, "f" * 32, "acordar")
        self.assertTrue(receptor.receber(TOPICO + "/acordar", pedido))
        self.assertFalse(receptor.receber(TOPICO + "/acordar", pedido))
        self.assertEqual(len(chamadas), 1)
        self.assertEqual(verificar(publicados[0][1], TOPICO + "/respostas", CHAVE_ESP, {"resposta"})["estado"], "acordando")

    def test_wake_invalido_nao_chama_placa(self):
        chamadas = []
        receptor = self.modulo.ReceptorWake({"topico": TOPICO, "chave": CHAVE_ESP},
                                             lambda: (chamadas.append(True), ""), lambda *_: None)
        self.assertFalse(receptor.receber(TOPICO + "/acordar", b"{}"))
        self.assertEqual(chamadas, [])


class ModeloAlexaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modulo = importlib.import_module("integracoes.alexa.lambda_function")

    def evento(self, nome, atributos=None, texto=""):
        agora = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        slots = {"pedido": {"value": texto}} if texto else {}
        return {"context": {"System": {"application": {"applicationId": "skill"},
                                        "user": {"userId": "usuario"}}},
                "session": {"attributes": atributos or {}},
                "request": {"type": "IntentRequest", "requestId": "pedido-1", "timestamp": agora,
                            "intent": {"name": nome, "slots": slots}}}

    def config(self):
        return {"skill_id": "skill", "usuarios_permitidos": ["usuario"]}

    def test_comando_e_confirmacao_por_sessao(self):
        chamadas = []
        def transporte(_config, pedido_id, acao, texto):
            chamadas.append((pedido_id, acao, texto))
            return {"estado": "confirmacao", "texto": "Confirma?"}
        resposta = self.modulo.tratar(self.evento("ComandoIntent", texto="suspender"), self.config(), transporte)
        self.assertTrue(resposta["sessionAttributes"]["confirmacao_pendente"])
        self.modulo.tratar(self.evento("AMAZON.YesIntent", {"confirmacao_pendente": True}), self.config(), transporte)
        self.assertEqual(chamadas[-1][1:], ("comando", "sim"))

    def test_usuario_nao_autorizado_nao_chama_transporte(self):
        evento = self.evento("ConectarIntent")
        evento["context"]["System"]["user"]["userId"] = "intruso"
        resposta = self.modulo.tratar(evento, self.config(), lambda *_: self.fail("não deve chamar"))
        self.assertTrue(resposta["response"]["shouldEndSession"])

    def test_lancamento_abrir_jarvis_dispara_ponte(self):
        evento = self.evento("ConectarIntent")
        evento["request"] = {
            "type": "LaunchRequest",
            "requestId": "pedido-launch",
            "timestamp": evento["request"]["timestamp"],
        }
        chamadas = []
        resposta = self.modulo.tratar(
            evento, self.config(),
            lambda _config, pedido_id, acao, texto: (
                chamadas.append((pedido_id, acao, texto))
                or {"estado": "pronto", "texto": "Jarvis conectado."}
            ),
        )
        self.assertEqual(chamadas[0][1:], ("abrir", ""))
        self.assertIn("Jarvis conectado", resposta["response"]["outputSpeech"]["text"])


class MicrofoneTests(unittest.TestCase):
    def test_troca_manual_nao_adiciona_dispositivo_sem_vad(self):
        ouvinte = Ouvinte(lambda *_: None, microfones=["Mic A", "Mic B"])
        self.assertTrue(ouvinte.trocar_microfone("Mic B"))
        self.assertEqual(ouvinte.modo_microfone, "manual")
        self.assertEqual(ouvinte.microfone_prioritario, "Mic B")
        self.assertFalse(ouvinte.trocar_microfone("Mic novo"))
        self.assertTrue(ouvinte.trocar_microfone("multi"))
        self.assertEqual(ouvinte.modo_microfone, "multi")

