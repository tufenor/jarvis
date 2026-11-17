import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.agente import Agente
from jarvis.estado import Painel


class CerebroContador:
    nome = "teste"

    def __init__(self):
        self.chamadas = 0

    def marcar(self):
        return 0

    def desfazer(self, _):
        pass

    def cheio(self):
        return False

    def novo_dialogo(self):
        pass

    def definir_contexto(self, _):
        pass

    async def disponivel(self):
        return True, ""

    async def falar(self, _texto, ao_texto=None):
        self.chamadas += 1
        return type("Passo", (), {"problema": "resposta vazia", "chamadas": [], "texto": ""})()


class LocutoresFalsos:
    def nomes(self):
        return ["Usuario"]


class FonteVozTests(unittest.TestCase):
    def test_voz_desconhecida_nao_chega_ao_cerebro(self):
        cerebro = CerebroContador()
        painel = Painel()
        agente = Agente(painel, cerebro, {}, exigir_voz_conhecida=True)
        agente.locutores = LocutoresFalsos()

        async def testar():
            await agente.ao_ouvir("Jarvis, abra o YouTube", None, None)

        asyncio.run(testar())
        self.assertEqual(cerebro.chamadas, 0)
        self.assertIn("voz não cadastrada", painel.atividade[0]["texto"])


if __name__ == "__main__":
    unittest.main()
