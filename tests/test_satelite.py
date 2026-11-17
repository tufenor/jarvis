"""Testes do satélite: token, fila e endpoints."""
import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.satelite import (FilaSatelite, PonteCelular,
                             carregar_ou_criar_token)
from jarvis.servidor import criar_app


CONFIG = {
    "host": "127.0.0.1", "porta": 0,
    "placa": {"url": "http://placa.invalida", "intervalo_s": 3, "timeout_s": 1},
    "agente_energia": {"url": "http://agente.invalido", "intervalo_s": 10},
    "cerebro": {"tipo": "simulado", "modelo": "claude-haiku-5-5"},
}


class PlacaFalsa:
    async def ler_status(self):
        return {"temperatura": 20, "umidade": 40, "movimento": False, "led": False, "led_manual": False}

    async def acao(self, nome):
        pass

    async def fechar(self):
        pass


class TokenTests(unittest.TestCase):
    def test_gera_token_na_primeira_execucao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "token.txt"
            t1 = carregar_ou_criar_token(caminho)
            self.assertTrue(len(t1) >= 32)
            self.assertTrue(caminho.is_file())
            # Segunda chamada devolve o MESMO token (não regenera).
            t2 = carregar_ou_criar_token(caminho)
            self.assertEqual(t1, t2)

    def test_token_vazio_no_arquivo_e_recriado(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "token.txt"
            caminho.write_text("   \n", encoding="utf-8")
            t = carregar_ou_criar_token(caminho)
            self.assertTrue(t.strip())


class FilaTests(unittest.TestCase):
    def test_empurrar_e_drenar(self):
        fila = FilaSatelite()
        fila.empurrar("falar", {"texto": "oi"})
        fila.empurrar("avisar", {"titulo": "ei", "texto": ""})
        ordens = asyncio.run(fila.drenar(espera_s=0.1))
        self.assertEqual(len(ordens), 2)
        self.assertEqual(ordens[0]["tipo"], "falar")
        self.assertEqual(ordens[1]["tipo"], "avisar")
        # Drenou: a próxima volta vazia dentro do tempo curto.
        vazio = asyncio.run(fila.drenar(espera_s=0.1))
        self.assertEqual(vazio, [])

    def test_longpoll_acorda_ao_empurrar(self):
        fila = FilaSatelite()

        async def correr():
            tarefa = asyncio.create_task(fila.drenar(espera_s=3))
            await asyncio.sleep(0.05)
            fila.empurrar("falar", {"texto": "acordou"})
            return await tarefa

        ordens = asyncio.run(correr())
        self.assertEqual(len(ordens), 1)
        self.assertEqual(ordens[0]["texto"], "acordou")

    def test_ponte_rejeita_vazio(self):
        ponte = PonteCelular(FilaSatelite())
        with self.assertRaises(ValueError):
            ponte.falar("")
        with self.assertRaises(ValueError):
            ponte.avisar("")


class EndpointsTests(unittest.TestCase):
    def cliente(self):
        app = criar_app(CONFIG, placa=PlacaFalsa(), iniciar_vigias=False)
        self.token = app.state.satelite_token
        return TestClient(app, client=("127.0.0.1", 50000)), app

    def test_sem_token_bloqueia(self):
        c, _ = self.cliente()
        with c:
            r = c.post("/api/satelite/presenca", json={"presente": True})
            self.assertEqual(r.status_code, 401)

    def test_token_invalido_bloqueia(self):
        c, _ = self.cliente()
        with c:
            r = c.get("/api/satelite/ping",
                      headers={"X-Satelite-Token": "errado"})
            self.assertEqual(r.status_code, 401)

    def test_fluxo_completo_com_token(self):
        c, app = self.cliente()
        cabecalho = {"X-Satelite-Token": self.token}
        with c:
            # ping
            r = c.get("/api/satelite/ping", headers=cabecalho)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["ok"], True)
            # presença com bateria
            r = c.post("/api/satelite/presenca", headers=cabecalho, json={
                "presente": True, "origem": "a53", "bateria": 73, "carregando": False,
                "latitude": -23.5, "longitude": -46.6, "precisao_m": 18.0,
            })
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["ok"], True)
            # presença chegou ao painel
            retrato = c.get("/api/presencas").json()
            self.assertEqual(retrato["a53"]["presente"], True)
            self.assertEqual(retrato["a53"]["bateria"], 73)
            self.assertNotIn("latitude", retrato["a53"])
            # sms
            r = c.post("/api/satelite/sms", headers=cabecalho,
                       json={"remetente": "mãe", "texto": "chega cedo"})
            self.assertEqual(r.status_code, 200)
            # notificação
            r = c.post("/api/satelite/notificacao", headers=cabecalho,
                       json={"app": "whatsapp", "titulo": "Ana", "texto": "oi"})
            self.assertEqual(r.status_code, 200)

    def test_longpoll_devolve_ordens(self):
        c, app = self.cliente()
        cabecalho = {"X-Satelite-Token": self.token}
        with c:
            app.state.satelite_fila.empurrar("falar", {"texto": "olá"})
            r = c.get("/api/satelite/fila", headers=cabecalho)
            self.assertEqual(r.status_code, 200)
            ordens = r.json()["ordens"]
            self.assertEqual(len(ordens), 1)
            self.assertEqual(ordens[0]["tipo"], "falar")
            self.assertEqual(ordens[0]["texto"], "olá")

    def test_latitude_invalida(self):
        c, _ = self.cliente()
        cabecalho = {"X-Satelite-Token": self.token}
        with c:
            r = c.post("/api/satelite/presenca", headers=cabecalho,
                       json={"presente": True, "latitude": 999})
            self.assertEqual(r.status_code, 400)


class SkillCelularTests(unittest.TestCase):
    def test_skill_cria_duas_ferramentas_com_ponte(self):
        import importlib.util
        caminho = ROOT / "skills" / "celular" / "skill.py"
        spec = importlib.util.spec_from_file_location("celular_skill", caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fila = FilaSatelite()
        ponte = PonteCelular(fila)
        ferramentas = mod.criar({"celular": ponte})
        nomes = {f.nome for f in ferramentas}
        self.assertEqual(nomes, {"falar_no_celular", "avisar_no_celular"})
        # Chamar a ferramenta empurra na fila.
        fal = next(f for f in ferramentas if f.nome == "falar_no_celular")
        asyncio.run(fal.funcao(texto="oi celular"))
        self.assertEqual(fila.tamanho(), 1)

    def test_skill_sem_ponte_fica_vazia(self):
        import importlib.util
        caminho = ROOT / "skills" / "celular" / "skill.py"
        spec = importlib.util.spec_from_file_location("celular_skill_b", caminho)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.criar({}), [])


if __name__ == "__main__":
    unittest.main()
