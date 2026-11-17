"""Carregador de skills: cada pasta em `skills/` vira um conjunto de ferramentas.

Uma skill é uma pasta com `skill.json` (nome, descrição, se está ativa, quem
pode usar) e `skill.py` com uma função `criar(contexto)` que devolve uma lista
de `Ferramenta`.

Por que não é uma loja aberta como a da Alexa: skill aqui é código rodando na
máquina do usuário, com as permissões dele. Então as skills são do projeto,
revisadas, e qualquer uma pode ser desligada por voz ou pelo painel.
"""
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA_SKILLS = RAIZ / "skills"
ARQUIVO_ESTADO = RAIZ / "dados" / "skills.json"


@dataclass
class Skill:
    nome: str
    descricao: str
    pasta: Path
    ativa: bool = True
    # Vazio = todo mundo. Com nomes, só essas vozes cadastradas podem usar.
    permitido: list = field(default_factory=list)
    ferramentas: dict = field(default_factory=dict)
    erro: str = ""

    def pode_usar(self, falante):
        if not self.permitido:
            return True
        return falante in self.permitido


def _ler_estado():
    """Quais skills o usuário desligou (persiste entre reinícios)."""
    try:
        return json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _salvar_estado(estado):
    ARQUIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def _importar(pasta):
    """Importa skill.py sem poluir o pacote jarvis nem o sys.path."""
    arquivo = pasta / "skill.py"
    nome_modulo = f"jarvis_skill_{pasta.name}"
    spec = importlib.util.spec_from_file_location(nome_modulo, arquivo)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_modulo] = modulo
    spec.loader.exec_module(modulo)
    return modulo


class Skills:
    def __init__(self, contexto, pasta=PASTA_SKILLS, estado=None):
        self.contexto = contexto
        self.pasta = Path(pasta)
        self.estado = _ler_estado() if estado is None else estado
        self.skills = {}
        self.carregar()

    def carregar(self):
        self.skills = {}
        if not self.pasta.is_dir():
            return
        for sub in sorted(self.pasta.iterdir()):
            if not (sub / "skill.json").is_file():
                continue
            try:
                meta = json.loads((sub / "skill.json").read_text(encoding="utf-8"))
            except ValueError as exc:
                self.skills[sub.name] = Skill(sub.name, "", sub, False, erro=f"skill.json inválido: {exc}")
                continue
            nome = meta.get("nome", sub.name)
            skill = Skill(
                nome=nome,
                descricao=meta.get("descricao", ""),
                pasta=sub,
                ativa=self.estado.get(nome, meta.get("ativa", True)),
                permitido=meta.get("permitido", []),
            )
            if skill.ativa:
                try:
                    skill.ferramentas = {f.nome: f for f in _importar(sub).criar(self.contexto)}
                except Exception as exc:
                    # Uma skill quebrada não pode derrubar o JARVIS inteiro.
                    skill.ativa = False
                    skill.erro = f"{type(exc).__name__}: {exc}"
            self.skills[nome] = skill

    # ---- uso ------------------------------------------------------------------

    def ferramentas(self, falante=None):
        """Ferramentas visíveis ao modelo agora, já filtradas por quem está falando."""
        resultado = {}
        for skill in self.skills.values():
            if skill.ativa and skill.pode_usar(falante):
                resultado.update(skill.ferramentas)
        return resultado

    def dona_da_ferramenta(self, nome_ferramenta):
        for skill in self.skills.values():
            if nome_ferramenta in skill.ferramentas:
                return skill
        return None

    def ligar(self, nome, ligada):
        """Liga/desliga por nome (ou parte dele). Devolve o nome real ou None."""
        alvo = self._achar(nome)
        if alvo is None:
            return None
        self.estado[alvo] = ligada
        _salvar_estado(self.estado)
        self.carregar()
        return alvo

    def _achar(self, nome):
        procurado = nome.strip().lower()
        for real in self.skills:
            if real.lower() == procurado:
                return real
        for real in self.skills:
            if procurado in real.lower():
                return real
        return None

    def resumo(self):
        return [
            {"nome": s.nome, "descricao": s.descricao, "ativa": s.ativa,
             "ferramentas": sorted(s.ferramentas), "permitido": s.permitido, "erro": s.erro}
            for s in self.skills.values()
        ]
