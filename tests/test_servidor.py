import asyncio
import sys
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis.estado import Painel
from jarvis.placa import descrever_erro
from jarvis.servidor import criar_app

CONFIG = {
    "host": "127.0.0.1",
    "porta": 0,
    "placa": {"url": "http://placa.invalida", "intervalo_s": 3, "timeout_s": 1},
    "agente_energia": {"url": "http://agente.invalido", "intervalo_s": 10},
    "cerebro": {"tipo": "simulado", "modelo": "claude-haiku-5-5"},
}


class PlacaFalsa:
    def __init__(self, falhar=False):
        self.falhar = falhar
        self.acoes = []

    async def ler_status(self):
        return {"temperatura": 27, "umidade": 40, "movimento": False, "led": True, "led_manual": False}

    async def acao(self, nome):
        if self.falhar:
            raise httpx.ConnectTimeout("sem conexão")
        self.acoes.append(nome)

    async def fechar(self):
        pass


class ServidorTests(unittest.TestCase):
    def cliente(self, placa=None):
        self.placa = placa or PlacaFalsa()
        self.app = criar_app(CONFIG, placa=self.placa, iniciar_vigias=False)
        # O TestClient se apresenta como "testclient"; o porteiro só libera sem
        # senha quem vem de 127.0.0.1 (a própria janela do JARVIS).
        return TestClient(self.app, client=("127.0.0.1", 50000))

    def test_pagina_inicial_serve_a_interface(self):
        with self.cliente() as c:
            r = c.get("/")
            self.assertEqual(r.status_code, 200)
            self.assertIn("J.A.R.V.I.S.", r.text)
            self.assertEqual(c.get("/interface/nucleo.js").status_code, 200)

    def test_painel_mobile_e_manifesto_sao_instalaveis(self):
        with self.cliente() as c:
            r = c.get("/mobile")
            self.assertEqual(r.status_code, 200)
            self.assertIn("Controle o Jarvis do A53", r.text)
            self.assertEqual(c.get("/mobile-manifest.webmanifest").status_code, 200)
            self.assertEqual(c.get("/mobile-sw.js").status_code, 200)

    def test_presenca_mobile_arredonda_e_nao_expoe_coordenadas(self):
        with self.cliente() as c:
            r = c.post("/api/presenca", json={
                "presente": True, "origem": "a53", "evento": "movimento",
                "latitude": -23.550512, "longitude": -46.633308, "precisao_m": 12.34,
            })
            self.assertEqual(r.status_code, 200)
            self.assertNotIn("latitude", r.json())
            self.assertEqual(c.get("/api/presenca").json()["presente"], True)
            self.assertEqual(c.get("/api/presencas").json()["a53"]["presente"], True)

    def test_presencas_de_dois_aparelhos_ficam_separadas(self):
        with self.cliente() as c:
            for origem in ("a53", "iphone"):
                r = c.post("/api/presenca", json={"presente": True, "origem": origem})
                self.assertEqual(r.status_code, 200)
            dados = c.get("/api/presencas").json()
            self.assertEqual(set(dados), {"a53", "iphone"})

    def test_status_facial_fica_local_e_disponivel(self):
        with self.cliente() as c:
            r = c.get("/api/bloqueio/rosto/status")
            self.assertEqual(r.status_code, 200)
            self.assertIn("ativado", r.json())

    def test_websocket_entrega_o_retrato_ao_conectar(self):
        with self.cliente() as c, c.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            self.assertEqual(msg["tipo"], "estado")
            self.assertEqual(msg["agente"]["estado"], "repouso")
            self.assertIn("alertas", msg)

    def test_comando_vazio_e_recusado(self):
        with self.cliente() as c:
            self.assertEqual(c.post("/api/comando", json={"texto": "   "}).status_code, 400)

    def test_acao_fora_da_lista_e_recusada_sem_tocar_a_placa(self):
        with self.cliente() as c:
            self.assertEqual(c.post("/api/acao/formatar_disco").status_code, 404)
            self.assertEqual(self.placa.acoes, [])

    def test_acao_de_luz_chega_na_placa_e_vai_para_o_log(self):
        with self.cliente() as c:
            self.assertEqual(c.post("/api/acao/luz_ligar").status_code, 200)
            self.assertEqual(self.placa.acoes, ["luz_ligar"])
            self.assertEqual(self.app.state.painel.atividade[0]["tipo"], "acao")

    def test_falha_da_placa_vira_502_e_erro_no_log_em_vez_de_sucesso_falso(self):
        with self.cliente(PlacaFalsa(falhar=True)) as c:
            r = c.post("/api/acao/luz_desligar")
            self.assertEqual(r.status_code, 502)
            self.assertEqual(self.app.state.painel.atividade[0]["tipo"], "erro")

    def test_cancelar_volta_ao_repouso(self):
        with self.cliente() as c:
            c.post("/api/comando", json={"texto": "teste"})
            self.assertEqual(c.post("/api/cancelar").status_code, 200)
            self.assertEqual(self.app.state.painel.agente["estado"], "repouso")

    def test_demonstracao_desconhecida_404(self):
        with self.cliente() as c:
            self.assertEqual(c.post("/api/demonstracao/xyz").status_code, 404)


class AlertasTests(unittest.TestCase):
    def test_placa_offline_e_alerta_critico(self):
        p = Painel()
        p.placa.update(online=False, erro="sem rota")
        self.assertEqual(p.alertas()[0]["nivel"], "critico")

    def test_alertas_somem_quando_a_causa_some(self):
        p = Painel()
        p.placa.update(online=True, erro=None, temperatura=33, umidade=15, movimento=True)
        self.assertEqual(len(p.alertas()), 3)
        p.placa.update(temperatura=25, umidade=45, movimento=False)
        self.assertEqual(p.alertas(), [])

    def test_estado_desconhecido_e_recusado(self):
        with self.assertRaises(ValueError):
            Painel().mudar_agente("dancando")

    def test_erro_de_conexao_vira_mensagem_legivel(self):
        self.assertIn("travado", descrever_erro(httpx.ConnectTimeout("x")))


if __name__ == "__main__":
    unittest.main()


class PorteiroTests(unittest.TestCase):
    """Hoje qualquer um no Wi-Fi mandava comando. Isto fecha."""

    def montar(self, senha=None):
        import tempfile
        from jarvis.acesso import Acesso, definir_senha
        self.pasta = tempfile.TemporaryDirectory()
        arq = Path(self.pasta.name) / "painel.json"
        if senha:
            definir_senha(senha, arq)
        app = criar_app(CONFIG, placa=PlacaFalsa(), iniciar_vigias=False)
        app.state.acesso.arquivo = arq
        app.state.acesso.recarregar()
        return app

    def tearDown(self):
        if hasattr(self, "pasta"):
            self.pasta.cleanup()

    def de_fora(self, app):
        return TestClient(app, client=("192.168.50.77", 51000))

    def test_sem_senha_o_de_fora_nao_entra(self):
        app = self.montar()
        with self.de_fora(app) as c:
            self.assertEqual(c.post("/api/comando", json={"texto": "oi"}).status_code, 401)
            self.assertEqual(c.get("/", follow_redirects=False).status_code, 303)

    def test_senha_certa_abre_e_a_errada_nao(self):
        app = self.montar("segredo123")
        with self.de_fora(app) as c:
            self.assertEqual(c.post("/login", json={"senha": "errada"}).status_code, 401)
            self.assertEqual(c.post("/api/comando", json={"texto": "oi"}).status_code, 401)
            self.assertEqual(c.post("/login", json={"senha": "segredo123"}).status_code, 200)
            # o cookie fica no cliente; agora passa
            self.assertEqual(c.post("/api/comando", json={"texto": "oi"}).status_code, 200)

    def test_websocket_tambem_e_trancado(self):
        """O middleware HTTP não vê WebSocket — sem trava própria, o canal com
        todos os sensores ficaria aberto para a rede."""
        app = self.montar("segredo123")
        with self.de_fora(app) as c:
            with self.assertRaises(Exception):
                with c.websocket_connect("/ws"):
                    pass

    def test_a_propria_janela_nunca_precisa_de_senha(self):
        app = self.montar("segredo123")
        with TestClient(app, client=("127.0.0.1", 50000)) as c:
            self.assertEqual(c.post("/api/comando", json={"texto": "oi"}).status_code, 200)

    def test_saude_responde_sem_entrar_e_nao_conta_nada(self):
        app = self.montar("segredo123")
        with self.de_fora(app) as c:
            r = c.get("/api/saude")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json(), {"ok": True})

    def test_rota_nova_nasce_protegida(self):
        """O porteiro é um middleware: quem cria rota não precisa lembrar de nada."""
        app = self.montar("segredo123")

        @app.get("/api/inventada")
        async def inventada():
            return {"segredo": 1}
        with self.de_fora(app) as c:
            self.assertEqual(c.get("/api/inventada").status_code, 401)


class RecuperacaoTests(unittest.TestCase):
    """Rede, placa e API caem. O JARVIS tem que voltar sozinho."""

    def test_placa_espera_cada_vez_mais_e_reabre_a_conexao(self):
        from jarvis.servidor import vigiar_placa
        from jarvis.estado import Painel

        class PlacaMorta:
            def __init__(self):
                self.reconexoes = 0

            async def ler_status(self):
                raise httpx.ConnectTimeout("travada")

            async def reconectar(self):
                self.reconexoes += 1

        painel, placa = Painel(), PlacaMorta()
        esperas = []

        async def tudo():
            import jarvis.servidor as mod
            original = mod.asyncio.sleep

            async def anotar(s):
                if s:                      # 0 s vem do publicar(), não é espera
                    esperas.append(s)
                if len(esperas) >= 4:
                    raise asyncio.CancelledError
                await original(0)
            mod.asyncio.sleep = anotar
            try:
                await vigiar_placa(painel, placa, 3)
            except asyncio.CancelledError:
                pass
            finally:
                mod.asyncio.sleep = original
        asyncio.run(tudo())
        self.assertEqual(esperas, sorted(esperas), "a espera tem que crescer, não encurtar")
        self.assertGreater(esperas[-1], esperas[0])
        self.assertEqual(placa.reconexoes, 1, "depois de 3 falhas, abre conexão nova")

    def test_placa_que_volta_retoma_o_ritmo_normal(self):
        from jarvis.servidor import vigiar_placa
        from jarvis.estado import Painel

        class PlacaIntermitente:
            def __init__(self):
                self.chamadas = 0

            async def ler_status(self):
                self.chamadas += 1
                if self.chamadas <= 2:
                    raise httpx.ConnectTimeout("travada")
                return {"temperatura": 25, "umidade": 50, "movimento": False, "led": False}

            async def reconectar(self):
                pass

        painel = Painel()
        esperas = []

        async def tudo():
            import jarvis.servidor as mod
            original = mod.asyncio.sleep

            async def anotar(s):
                if s:
                    esperas.append(s)
                if len(esperas) >= 3:
                    raise asyncio.CancelledError
                await original(0)
            mod.asyncio.sleep = anotar
            try:
                await vigiar_placa(painel, PlacaIntermitente(), 3)
            except asyncio.CancelledError:
                pass
            finally:
                mod.asyncio.sleep = original
        asyncio.run(tudo())
        self.assertEqual(esperas[-1], 3, "voltou: tem que usar o intervalo normal")
        self.assertTrue(painel.placa["online"])

    def test_cerebro_offline_e_reconferido_ate_voltar(self):
        from jarvis.servidor import vigiar_cerebro
        from jarvis.estado import Painel

        painel = Painel()
        painel.cerebro["online"] = False
        tentativas = []

        class AgenteFalso:
            painel = None

            async def verificar_cerebro(self):
                tentativas.append(1)
                if len(tentativas) >= 3:
                    painel.cerebro["online"] = True
                    raise asyncio.CancelledError
                return False

        async def tudo():
            import jarvis.servidor as mod
            original = mod.asyncio.sleep

            async def rapido(_s):
                await original(0)
            mod.asyncio.sleep = rapido
            try:
                await vigiar_cerebro(AgenteFalso(), painel)
            except asyncio.CancelledError:
                pass
            finally:
                mod.asyncio.sleep = original
        asyncio.run(tudo())
        self.assertEqual(len(tentativas), 3, "tem que insistir até voltar")

    def test_cerebro_online_nao_e_ficado_conferindo(self):
        from jarvis.servidor import vigiar_cerebro
        from jarvis.estado import Painel

        painel = Painel()
        tentativas = []

        class AgenteFalso:
            async def verificar_cerebro(self):
                tentativas.append(1)
                return True

        async def tudo():
            import jarvis.servidor as mod
            original = mod.asyncio.sleep
            voltas = []

            async def contar(s):
                if s:
                    voltas.append(1)
                if len(voltas) >= 3:
                    raise asyncio.CancelledError
                await original(0)
            mod.asyncio.sleep = contar
            try:
                await vigiar_cerebro(AgenteFalso(), painel)
            except asyncio.CancelledError:
                pass
            finally:
                mod.asyncio.sleep = original
        asyncio.run(tudo())
        self.assertEqual(tentativas, [], "cérebro no ar não precisa de checagem")


class MicrofoneQueVoltaTests(unittest.TestCase):
    def test_capturar_religa_depois_de_cair(self):
        """Microfone some ao suspender o Windows ou ao trocar de fone.
        Sem religar sozinho, o JARVIS fica surdo até alguém reiniciar."""
        import time as t
        from jarvis.ouvinte import Ouvinte

        o = Ouvinte(lambda *a: None)
        aberturas = []

        def abrir_que_cai():
            aberturas.append(1)
            o.erro = "driver sumiu"
            if len(aberturas) >= 3:
                o.parar.set()
        o._abrir_microfone = abrir_que_cai
        dormidas = []
        original = t.sleep
        try:
            import jarvis.ouvinte as mod
            mod.time.sleep = lambda s: dormidas.append(s)
            o._capturar()
        finally:
            mod.time.sleep = original
        self.assertEqual(len(aberturas), 3, "tinha que tentar de novo")
        self.assertEqual(dormidas, sorted(dormidas), "a espera tem que crescer")
        self.assertGreater(o.estado["reconexoes"], 0)
