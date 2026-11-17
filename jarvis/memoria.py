"""Memória persistente do JARVIS.

O cérebro é sem estado entre turnos — cada pedido vai à API carregando só o
histórico da conversa atual. Para "aprender" com o usuário entre sessões,
guardamos fatos num JSON local e injetamos um resumo no system prompt a cada
chamada. O cérebro vê sempre o que já sabe.

Regras de higiene:
- Nunca guardar senhas, códigos, tokens, cartões. A skill valida.
- Cada item tem id, texto, categoria, quando, quem (falante, quando conhecido).
- O resumo para o prompt tem limite (`LIMITE_RESUMO`) para não roubar contexto
  da conversa; os mais recentes ganham prioridade.
"""
import json
import re
import threading
import time
import uuid
from pathlib import Path

CATEGORIAS = {"fato", "preferencia", "lembrete", "correcao", "aprendizado"}
LIMITE_RESUMO = 1800      # caracteres — cabe em ~450 tokens
LIMITE_ITENS = 500        # a partir disso, poda os mais antigos de 'lembrete'
SENHA = re.compile(r"\b(?:senha|password|token|api[_\s-]?key|cvv|cart[aã]o)\b", re.I)


class Memoria:
    def __init__(self, caminho):
        self.caminho = Path(caminho)
        self._lock = threading.Lock()
        self.itens = self._carregar()
        # Callback chamado depois de cada salvamento. A skill do Google
        # registra aqui o upload automático para o Drive.
        self.ao_salvar = None

    def _carregar(self):
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [i for i in dados if isinstance(i, dict) and "texto" in i]

    def _salvar(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.itens, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.caminho)
        if self.ao_salvar:
            try:
                self.ao_salvar()
            except Exception:
                # Sync externo (Drive) é esforço extra: nunca derruba a gravação local.
                pass

    def lembrar(self, texto, categoria="fato", falante=None):
        texto = (texto or "").strip()
        if not texto:
            raise ValueError("texto vazio")
        if len(texto) > 500:
            raise ValueError("fato longo demais; resuma em até 500 caracteres")
        if SENHA.search(texto):
            raise ValueError("não guardo senhas, tokens ou dados de cartão")
        categoria = categoria if categoria in CATEGORIAS else "fato"
        with self._lock:
            # Mesmo texto, mesma categoria: não duplica — atualiza o timestamp.
            for item in self.itens:
                if item["texto"].casefold() == texto.casefold() and item["categoria"] == categoria:
                    item["quando"] = time.time()
                    self._salvar()
                    return item["id"]
            item = {"id": uuid.uuid4().hex[:8], "texto": texto, "categoria": categoria,
                    "quando": time.time(), "quem": falante}
            self.itens.append(item)
            # Poda: remove lembretes antigos quando a lista cresce demais.
            if len(self.itens) > LIMITE_ITENS:
                self.itens.sort(key=lambda i: (i["categoria"] != "lembrete", -i["quando"]))
                self.itens = self.itens[:LIMITE_ITENS]
            self._salvar()
            return item["id"]

    def esquecer(self, descricao):
        alvo = (descricao or "").strip().casefold()
        if not alvo:
            return 0
        with self._lock:
            antes = len(self.itens)
            self.itens = [i for i in self.itens if alvo not in i["texto"].casefold()
                          and i["id"] != alvo]
            apagados = antes - len(self.itens)
            if apagados:
                self._salvar()
            return apagados

    def buscar(self, consulta="", categoria=None, limite=10):
        termos = [t for t in (consulta or "").casefold().split() if t]
        candidatos = self.itens
        if categoria in CATEGORIAS:
            candidatos = [i for i in candidatos if i["categoria"] == categoria]
        if termos:
            candidatos = [i for i in candidatos
                          if all(t in i["texto"].casefold() for t in termos)]
        return sorted(candidatos, key=lambda i: -i["quando"])[:limite]

    def resumo_para_prompt(self, limite=LIMITE_RESUMO):
        """Texto curto para o system prompt, priorizando o que importa mais."""
        if not self.itens:
            return ""
        ordem = {"preferencia": 0, "correcao": 1, "fato": 2, "aprendizado": 3, "lembrete": 4}
        por_relevancia = sorted(self.itens, key=lambda i: (ordem.get(i["categoria"], 9), -i["quando"]))
        linhas = []
        total = 0
        for item in por_relevancia:
            linha = f"- ({item['categoria']}) {item['texto']}"
            if total + len(linha) + 1 > limite:
                break
            linhas.append(linha)
            total += len(linha) + 1
        if not linhas:
            return ""
        return "O que você sabe sobre o usuário e sobre interações anteriores:\n" + "\n".join(linhas)

    def como_json(self):
        return json.dumps(self.itens, ensure_ascii=False, indent=2)

    def substituir(self, outros):
        """Para quando a cópia do Drive é mais nova que a local."""
        with self._lock:
            self.itens = [i for i in outros if isinstance(i, dict) and "texto" in i]
            self._salvar()
