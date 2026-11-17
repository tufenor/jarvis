import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.agente import Agente
from jarvis.diario import Diario
from jarvis.estado import Painel


class CerebroInerte:
    nome = "inerte"


class DiarioTests(unittest.TestCase):
    def test_grava_uma_sessao_no_arquivo_do_dia(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Diario(pasta).gravar(["Hoje foi um dia bom.", "Tive uma ideia."], 0)
            self.assertIsNotNone(arquivo)
            texto = Path(arquivo).read_text(encoding="utf-8")
            self.assertIn("Hoje foi um dia bom.", texto)
            self.assertIn("Tive uma ideia.", texto)

    def test_modo_diario_estende_escuta_e_so_salva_ao_encerrar(self):
        async def fluxo():
            with tempfile.TemporaryDirectory() as pasta:
                agente = Agente(Painel(), CerebroInerte(), {},
                                conversa_s=0, diario=Diario(pasta), diario_s=300)

                async def sem_espera(*_):
                    return None
                agente._niveis = sem_espera

                await agente.ao_ouvir("Jarvis, iniciar diário")
                if agente.tarefa:
                    await agente.tarefa
                await agente.ao_ouvir("Hoje foi um dia bom")
                self.assertIsNotNone(agente.diario_sessao)
                self.assertEqual(list(Path(pasta).glob("*.md")), [])
                await agente.ao_ouvir("Jarvis, encerrar diário")
                arquivos = list(Path(pasta).glob("*.md"))
                self.assertEqual(len(arquivos), 1)
                self.assertIn("Hoje foi um dia bom", arquivos[0].read_text(encoding="utf-8"))

        asyncio.run(fluxo())


if __name__ == "__main__":
    unittest.main()
