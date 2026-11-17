import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from jarvis.rosto import AutenticadorFacial, ResultadoRosto


class RostoLocalTests(unittest.TestCase):
    def test_comparacao_de_vetores_normalizados(self):
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([2.0, 0.0, 0.0], dtype=np.float32)
        c = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        self.assertAlmostEqual(AutenticadorFacial._comparar(a, b), 1.0)
        self.assertAlmostEqual(AutenticadorFacial._comparar(a, c), 0.0)

    def test_diagnostico_nao_leva_foto(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "rosto.json"
            arquivo.write_text(json.dumps({"nome": "Usuario", "embedding": [1, 0, 0]}), encoding="utf-8")
            autenticador = AutenticadorFacial(arquivo_perfil=arquivo)
            info = autenticador.diagnostico()
            self.assertTrue(info["perfil"])
            self.assertNotIn("imagem", info)

    def test_resultado_padrao_fica_negado(self):
        resultado = ResultadoRosto(False, motivo="rosto não confirmado")
        self.assertFalse(resultado.reconhecido)
        self.assertFalse(resultado.prova_vida)


if __name__ == "__main__":
    unittest.main()
