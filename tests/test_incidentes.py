import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.estado import Painel
from jarvis.incidentes import Incidentes


class IncidentesTests(unittest.TestCase):
    def test_registra_erro_e_redige_segredo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "incidentes.jsonl"
            painel = Painel(incidentes=Incidentes(caminho))
            painel.agente["ultima_fala"] = "minha senha: segredo"
            painel.registrar("erro", "não consegui concluir token=abc123")
            item = json.loads(caminho.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(item["tipo"], "erro")
            self.assertNotIn("abc123", item["mensagem"])
            self.assertNotIn("segredo", item["ultima_fala"])

    def test_resposta_de_nao_entendimento_vira_incidente(self):
        with tempfile.TemporaryDirectory() as pasta:
            registro = Incidentes(Path(pasta) / "incidentes.jsonl")
            self.assertTrue(registro.deve_registrar("resposta", "Não entendi o pedido."))
            self.assertFalse(registro.deve_registrar("fala", "não entendi você"))

    def test_classifica_entendimento_e_execucao(self):
        self.assertEqual(
            Incidentes.categoria_de("resposta", "Não entendi o comando"),
            "entendimento",
        )
        self.assertEqual(
            Incidentes.categoria_de("erro", "Falhou ao abrir o programa"),
            "execucao",
        )
