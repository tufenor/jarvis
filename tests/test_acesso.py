import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.acesso import Acesso, definir_senha


class AcessoTests(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.arq = Path(self.pasta.name) / "painel.json"

    def tearDown(self):
        self.pasta.cleanup()

    def com_senha(self, senha="segredo123"):
        definir_senha(senha, self.arq)
        return Acesso(self.arq)

    # ---- sem senha: fecha para fora, abre só para a própria máquina ----------

    def test_sem_senha_ninguem_de_fora_entra(self):
        a = Acesso(self.arq)
        self.assertFalse(a.tem_senha)
        pode, motivo = a.liberado("192.168.50.50", None)
        self.assertFalse(pode, "sem senha o padrão tem que ser FECHADO")
        self.assertIn("sem senha", motivo)

    def test_a_propria_janela_entra_sempre(self):
        for endereco in ("127.0.0.1", "::1", "localhost"):
            self.assertTrue(Acesso(self.arq).liberado(endereco, None)[0], endereco)

    # ---- senha ----------------------------------------------------------------

    def test_senha_certa_e_errada(self):
        a = self.com_senha()
        self.assertTrue(a.conferir_senha("segredo123"))
        self.assertFalse(a.conferir_senha("segredo124"))
        self.assertFalse(a.conferir_senha(""))
        self.assertFalse(a.conferir_senha(None))

    def test_senha_nao_fica_em_texto_no_disco(self):
        self.com_senha("minhaSenhaSecreta")
        bruto = self.arq.read_text(encoding="utf-8")
        self.assertNotIn("minhaSenhaSecreta", bruto)
        self.assertEqual(set(json.loads(bruto)), {"sal", "hash", "segredo"})

    def test_senha_curta_e_recusada(self):
        with self.assertRaises(ValueError):
            definir_senha("123", self.arq)

    def test_duas_contas_com_a_mesma_senha_tem_hash_diferente(self):
        outro = Path(self.pasta.name) / "outro.json"
        a = definir_senha("mesmaSenha", self.arq)
        b = definir_senha("mesmaSenha", outro)
        self.assertNotEqual(a["hash"], b["hash"], "falta sal")

    # ---- sessão ---------------------------------------------------------------

    def test_sessao_valida_libera_de_fora(self):
        a = self.com_senha()
        self.assertTrue(a.liberado("192.168.50.50", a.criar_sessao())[0])

    def test_sessao_expirada_nao_vale(self):
        a = self.com_senha()
        antiga = a.criar_sessao(agora=time.time() - 40 * 24 * 3600)
        self.assertFalse(a.sessao_valida(antiga))

    def test_cookie_forjado_nao_vale(self):
        a = self.com_senha()
        futuro = int(time.time() + 9999)
        for falso in [f"{futuro}.0000", f"{futuro}.", "qualquer", "", None,
                      f"naoNumero.{'a' * 64}"]:
            self.assertFalse(a.sessao_valida(falso), repr(falso))

    def test_cookie_de_outro_jarvis_nao_vale(self):
        a = self.com_senha()
        outro = Path(self.pasta.name) / "outro.json"
        definir_senha("segredo123", outro)
        self.assertFalse(a.sessao_valida(Acesso(outro).criar_sessao()),
                         "segredo diferente tem que invalidar")

    def test_trocar_a_senha_derruba_as_sessoes_antigas(self):
        a = self.com_senha()
        antiga = a.criar_sessao()
        definir_senha("outraSenha456", self.arq)
        a.recarregar()
        self.assertFalse(a.sessao_valida(antiga))


if __name__ == "__main__":
    unittest.main()
