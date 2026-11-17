import unittest

from jarvis.cerebro import INSTRUCOES, instrucoes_com


class DiretrizCerebroTests(unittest.TestCase):
    def test_missao_central_prioriza_beneficio_pratico(self):
        self.assertIn("MISSÃO CENTRAL", INSTRUCOES)
        self.assertIn("benefício concreto", INSTRUCOES)
        self.assertIn("maneira mais rápida", INSTRUCOES)
        self.assertIn("Segurança, privacidade", INSTRUCOES)

    def test_memoria_continua_depois_da_diretriz(self):
        prompt = instrucoes_com("MEMÓRIA DE TESTE")
        self.assertTrue(prompt.startswith(INSTRUCOES))
        self.assertIn("MEMÓRIA DE TESTE", prompt)


if __name__ == "__main__":
    unittest.main()
