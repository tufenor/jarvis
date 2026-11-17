import asyncio
import tempfile
import unittest
from pathlib import Path

from jarvis.acesso import Acesso, definir_senha
from jarvis.janela import Janela, normalizar_frase


class BloqueioFraseTests(unittest.TestCase):
    def test_frase_e_normalizada_sem_acento(self):
        self.assertEqual(normalizar_frase("  LIBERAR, TELA! "), "liberar tela")

    def test_janela_inicia_bloqueada_e_so_aceita_frase_exata(self):
        janela = Janela({
            "bloqueio_pos_login": {"ativar": True, "frase_liberar": "liberar tela"}
        })
        self.assertTrue(janela.bloqueada)
        self.assertTrue(janela.frase_de_liberacao_confere("LIBERAR TELA"))
        self.assertFalse(janela.frase_de_liberacao_confere("liberar tela agora"))

    def test_pode_exigir_voz_cadastrada_alem_da_frase(self):
        janela = Janela({
            "bloqueio_pos_login": {
                "ativar": True,
                "exigir_voz_conhecida": True,
                "vozes_permitidas": ["Usuario"],
            }
        })
        self.assertTrue(janela.voz_de_liberacao_confere("usuario"))
        self.assertFalse(janela.voz_de_liberacao_confere("visita"))
        self.assertFalse(janela.voz_de_liberacao_confere(None))


class CodigoLocalTests(unittest.TestCase):
    def test_codigo_e_guardado_como_hash_e_nao_em_claro(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "bloqueio.json"
            definir_senha("codigo-local-123", arquivo)
            texto = arquivo.read_text(encoding="utf-8")
            self.assertNotIn("codigo-local-123", texto)
            acesso = Acesso(arquivo)
            self.assertTrue(acesso.conferir_senha("codigo-local-123"))
            self.assertFalse(acesso.conferir_senha("outro-codigo"))


class TravaDeVozTests(unittest.TestCase):
    def test_fala_sem_frase_de_liberacao_e_descartada(self):
        from jarvis.agente import Agente

        class JanelaFalsa:
            bloqueada = True
            liberou = False

            def frase_de_liberacao_confere(self, frase):
                return frase == "liberar tela"

            def desbloquear(self):
                self.liberou = True
                self.bloqueada = False
                return True

        agente = Agente.__new__(Agente)
        agente.janela = JanelaFalsa()
        tratado = asyncio.run(agente._tratar_bloqueio("Jarvis, abrir o navegador"))
        self.assertTrue(tratado)
        self.assertTrue(agente.janela.bloqueada)

    def test_frase_de_liberacao_nao_consulta_o_cerebro(self):
        from jarvis.agente import Agente

        class JanelaFalsa:
            bloqueada = True

            def frase_de_liberacao_confere(self, frase):
                return frase == "liberar tela"

            def desbloquear(self):
                self.bloqueada = False
                return True

        agente = Agente.__new__(Agente)
        agente.janela = JanelaFalsa()
        agente._responder = lambda texto: asyncio.sleep(0)
        tratado = asyncio.run(agente._tratar_bloqueio("Jarvis, liberar tela", "Usuario"))
        self.assertTrue(tratado)
        self.assertFalse(agente.janela.bloqueada)


if __name__ == "__main__":
    unittest.main()
