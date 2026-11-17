import unittest

from jarvis.energia import deve_economizar, ha_presenca_conhecida


class PainelFalso:
    def __init__(self, presencas):
        self.presencas_moveis = presencas


class EnergiaTests(unittest.TestCase):
    def test_so_economiza_em_repouso_e_sem_entrada(self):
        self.assertTrue(deve_economizar("repouso", 301, 301, 300))
        self.assertFalse(deve_economizar("ouvindo", 301, 301, 300))
        self.assertFalse(deve_economizar("repouso", 301, 30, 300))

    def test_presenca_de_qualquer_telefone_bloqueia_economia(self):
        painel = PainelFalso({"a53": {"presente": True}, "iphone": {"presente": False}})
        self.assertTrue(ha_presenca_conhecida(painel))
        self.assertFalse(deve_economizar("repouso", 400, 400, 300, True))


if __name__ == "__main__":
    unittest.main()
