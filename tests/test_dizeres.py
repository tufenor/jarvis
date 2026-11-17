"""Testes das variações de resposta do JARVIS."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis import dizeres


class EscolherTests(unittest.TestCase):
    def test_pega_so_de_categoria_existente(self):
        with self.assertRaises(KeyError):
            dizeres.escolher("categoria_inventada")

    def test_nao_repete_a_mesma_frase_duas_vezes_seguidas(self):
        dizeres.semear(1)
        prev = None
        for _ in range(20):
            frase = dizeres.escolher("ok")
            self.assertNotEqual(frase, prev, "duas chamadas seguidas tem a MESMA frase — perdeu a variação")
            prev = frase

    def test_todas_as_categorias_tem_pelo_menos_quatro_variantes(self):
        """Com só 2-3 frases, 5 pedidos seguidos repetem o padrão depressa."""
        for nome, lista in dizeres.DIZERES.items():
            self.assertGreaterEqual(len(lista), 4, f"'{nome}' tem apenas {len(lista)} variante(s)")

    def test_variaveis_entram_na_frase(self):
        dizeres.semear(0)
        frase = dizeres.escolher("sem_permissao", skill="arquivos", quem="Visitante")
        self.assertIn("arquivos", frase)
        self.assertIn("Visitante", frase)

    def test_faltar_variavel_cai_num_fallback_seguro_sem_crashar(self):
        # Se um dia someção com {nome} e eu esquecer de passar, não pode quebrar.
        resp = dizeres.escolher("sem_permissao")   # sem skill nem quem
        self.assertIsInstance(resp, str)
        self.assertTrue(resp)


class FerramentasTests(unittest.TestCase):
    """As respostas prontas das ferramentas também variam."""

    def coletar(self, func, n=8, **kw):
        dizeres.semear(42)
        return {func(**kw) for _ in range(n)}

    def test_abrir_programa_tem_formas_diferentes(self):
        formas = self.coletar(dizeres.abrir_programa, nome="calculadora")
        self.assertGreaterEqual(len(formas), 3, formas)
        for f in formas:
            self.assertIn("calculadora", f.lower())

    def test_abrir_site_mostra_sempre_o_endereco(self):
        formas = self.coletar(dizeres.abrir_site, endereco="youtube.com")
        self.assertGreaterEqual(len(formas), 2)
        for f in formas:
            self.assertIn("youtube", f.lower(), f"frase perdeu o endereço: {f!r}")

    def test_volume_mostra_sempre_o_nivel(self):
        formas = self.coletar(dizeres.volume, nivel=42)
        self.assertGreaterEqual(len(formas), 2)
        for f in formas:
            self.assertIn("42", f)

    def test_luz_varia_e_distingue_ligada_de_apagada(self):
        dizeres.semear(0)
        ligadas = {dizeres.luz(True) for _ in range(10)}
        apagadas = {dizeres.luz(False) for _ in range(10)}
        self.assertFalse(ligadas & apagadas, "frase de luz acesa apareceu entre as apagadas")
        self.assertGreaterEqual(len(ligadas), 2)
        self.assertGreaterEqual(len(apagadas), 2)


class HoraFaladaTests(unittest.TestCase):
    def test_minutos_redondos_falam_natural(self):
        dizeres.semear(0)
        frases = {dizeres.hora_falada(datetime(2026, 11, 4, 15, 0)) for _ in range(6)}
        for f in frases:
            self.assertIn("15", f)
            self.assertIn("quarta", f.lower())

    def test_meia_e_quinze_tem_forma_humana(self):
        dizeres.semear(1)
        # Em algum dos sorteios "meia" tem que aparecer (não "30").
        achou = False
        for _ in range(12):
            if "meia" in dizeres.hora_falada(datetime(2026, 11, 4, 15, 30)):
                achou = True; break
        self.assertTrue(achou, "nunca falou 'meia' em 12 tentativas")


class TemperaturaFaladaTests(unittest.TestCase):
    def test_sempre_inclui_numeros(self):
        dizeres.semear(0)
        for _ in range(8):
            f = dizeres.temperatura_falada(27, 40, movimento=False)
            self.assertIn("27", f)
            self.assertIn("40", f)

    def test_comenta_quando_esta_quente(self):
        dizeres.semear(0)
        self.assertIn("quente", dizeres.temperatura_falada(35, 50).lower())

    def test_comenta_quando_esta_seco(self):
        dizeres.semear(0)
        self.assertIn("seco", dizeres.temperatura_falada(24, 15).lower())

    def test_valores_nulos_nao_quebram(self):
        # A placa às vezes manda None num dos campos.
        f = dizeres.temperatura_falada(None, None)
        self.assertIsInstance(f, str)


if __name__ == "__main__":
    unittest.main()
