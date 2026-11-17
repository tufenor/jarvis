"""Todo arquivo do projeto tem que compilar e todo módulo tem que importar.

Um erro de sintaxe em `jarvis/__main__.py` derrubou o app em SILÊNCIO: o
registro de quedas só é ligado dentro de `main()`, que nunca chegou a rodar.
Os 200 testes passavam, porque nenhum deles importava aquele arquivo.
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

PASTAS = ["jarvis", "skills", "scripts", "tests"]
IGNORAR = {"__pycache__", ".venv", "_lixeira", "modelos"}


def arquivos_py():
    for pasta in PASTAS:
        for caminho in (RAIZ / pasta).rglob("*.py"):
            if not any(parte in IGNORAR for parte in caminho.parts):
                yield caminho


class CompilaTests(unittest.TestCase):
    def test_todo_arquivo_compila(self):
        quebrados = []
        for caminho in arquivos_py():
            try:
                ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
            except SyntaxError as exc:
                quebrados.append(f"{caminho.relative_to(RAIZ)}:{exc.lineno} {exc.msg}")
        self.assertEqual(quebrados, [])

    def test_todo_modulo_do_jarvis_importa(self):
        """Pega import quebrado e erro no corpo do módulo, não só sintaxe."""
        falhas = []
        for caminho in (RAIZ / "jarvis").glob("*.py"):
            if caminho.name == "__init__.py":
                continue
            nome = f"jarvis.{caminho.stem}"
            try:
                importlib.import_module(nome)
            except Exception as exc:
                falhas.append(f"{nome}: {type(exc).__name__}: {exc}")
        self.assertEqual(falhas, [])

    def test_o_ponto_de_entrada_compila(self):
        """O que roda o app todo dia; se ele quebra, nada sobe."""
        entrada = RAIZ / "jarvis" / "__main__.py"
        ast.parse(entrada.read_text(encoding="utf-8"), filename=str(entrada))

    def test_toda_skill_tem_a_funcao_criar(self):
        for pasta in (RAIZ / "skills").iterdir():
            if not (pasta / "skill.py").is_file():
                continue
            arvore = ast.parse((pasta / "skill.py").read_text(encoding="utf-8"))
            funcoes = [n.name for n in arvore.body if isinstance(n, ast.FunctionDef)]
            self.assertIn("criar", funcoes, f"skill {pasta.name} sem criar()")


if __name__ == "__main__":
    unittest.main()
