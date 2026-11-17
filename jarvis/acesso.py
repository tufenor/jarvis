"""Quem pode usar o painel.

Hoje qualquer um no Wi-Fi abre o painel e manda comando — abrir site, rodar
ferramenta, ver os sensores do quarto. Isto fecha isso, e precisa existir ANTES
de qualquer acesso de fora de casa.

As regras:
- A própria janela do JARVIS fala de 127.0.0.1 e entra sem senha. Quem já está
  na máquina tem tudo mesmo; exigir senha ali só atrapalharia.
- Qualquer outro endereço precisa da senha.
- SEM senha configurada, acesso de fora é RECUSADO (não liberado). Falhar
  fechado: um painel aberto por esquecimento é pior que um painel inacessível.
- A senha é guardada como hash scrypt com sal; o texto nunca toca o disco.
- A sessão é um cookie assinado com validade, sem estado no servidor.
"""
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

RAIZ = (Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1])
ARQUIVO = RAIZ / "dados" / "painel.json"
ARQUIVO_BLOQUEIO = RAIZ / "dados" / "bloqueio.json"
VALIDADE_S = 30 * 24 * 3600      # 30 dias: é o celular do dono, não um banco
COOKIE = "jarvis_sessao"
LOCAIS = {"127.0.0.1", "::1", "localhost"}

# scrypt com os parâmetros recomendados para senha interativa.
CUSTO_N, CUSTO_R, CUSTO_P = 2 ** 14, 8, 1


def _hash(senha, sal):
    return hashlib.scrypt(senha.encode("utf-8"), salt=bytes.fromhex(sal),
                          n=CUSTO_N, r=CUSTO_R, p=CUSTO_P, dklen=32).hex()


def definir_senha(senha, arquivo=ARQUIVO):
    if len(senha) < 6:
        raise ValueError("a senha precisa ter ao menos 6 caracteres")
    sal = secrets.token_hex(16)
    dados = {"sal": sal, "hash": _hash(senha, sal), "segredo": secrets.token_hex(32)}
    arquivo = Path(arquivo)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados), encoding="utf-8")
    try:                      # só o dono lê; no Windows é dica, não garantia
        os.chmod(arquivo, 0o600)
    except OSError:
        pass
    return dados


class Acesso:
    def __init__(self, arquivo=ARQUIVO):
        self.arquivo = Path(arquivo)
        self.dados = self._carregar()

    def _carregar(self):
        try:
            return json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def recarregar(self):
        self.dados = self._carregar()

    @property
    def tem_senha(self):
        return bool(self.dados and self.dados.get("hash"))

    # ---- senha ----------------------------------------------------------------

    def conferir_senha(self, senha):
        if not self.tem_senha:
            return False
        esperado = self.dados["hash"]
        # compare_digest: o tempo da comparação não pode entregar a senha.
        return hmac.compare_digest(_hash(senha or "", self.dados["sal"]), esperado)

    # ---- sessão ---------------------------------------------------------------

    def criar_sessao(self, agora=None):
        agora = agora or time.time()
        expira = int(agora + VALIDADE_S)
        return f"{expira}.{self._assinar(expira)}"

    def _assinar(self, expira):
        return hmac.new(self.dados["segredo"].encode(), str(expira).encode(),
                        hashlib.sha256).hexdigest()

    def sessao_valida(self, cookie, agora=None):
        if not cookie or not self.tem_senha:
            return False
        expira, _, assinatura = (cookie or "").partition(".")
        if not assinatura or not expira.isdigit():
            return False
        if not hmac.compare_digest(self._assinar(int(expira)), assinatura):
            return False
        return int(expira) > (agora or time.time())

    # ---- decisão --------------------------------------------------------------

    def liberado(self, endereco, cookie, agora=None):
        """Devolve (pode_entrar, motivo). O motivo é para o log, não para a tela."""
        if endereco in LOCAIS:
            return True, "local"
        if not self.tem_senha:
            # Fail-closed de propósito: sem senha, ninguém de fora entra.
            return False, "sem senha configurada"
        if self.sessao_valida(cookie, agora):
            return True, "sessão válida"
        return False, "sem sessão"
