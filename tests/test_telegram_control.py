import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "seguranca"))

from telegram_control import processar_mensagem


class RespostaHTTP:
    def __init__(self, payload=None, status=200):
        self.payload = payload or {}
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self.payload


class SessaoHTTP:
    def __init__(self, resposta=None):
        self.resposta = resposta or RespostaHTTP({
            "temperature": 24, "humidity": 55,
            "motion": False, "led": True,
        })
        self.gets = []

    def get(self, url, timeout):
        self.gets.append((url, timeout))
        return self.resposta


def mensagem(texto, chat_id=42, remetente=42, tipo="private"):
    return {"message": {
        "chat": {"id": chat_id, "type": tipo},
        "from": {"id": remetente},
        "text": texto,
    }}


class TelegramControlTests(unittest.TestCase):
    def setUp(self):
        self.config = {"telegram_chat_id": "42", "ip_da_placa": "192.168.50.20"}
        self.sessao = SessaoHTTP()

    def test_recusa_grupo_e_usuario_que_nao_e_dono_sem_chamar_placa(self):
        grupo = mensagem("/status", chat_id=-100, remetente=42, tipo="group")
        outro = mensagem("/status", chat_id=42, remetente=99)

        self.assertIsNone(processar_mensagem(grupo, self.config, self.sessao))
        self.assertIsNone(processar_mensagem(outro, self.config, self.sessao))
        self.assertEqual(self.sessao.gets, [])

    def test_status_responde_com_estado_da_esp32(self):
        resposta = processar_mensagem(mensagem("/status"), self.config,
                                      self.sessao)

        self.assertEqual(resposta,
                         "Temperatura: 24 °C\nUmidade: 55%\n"
                         "Movimento: não detectado\nLuz: ligada")
        self.assertEqual(self.sessao.gets,
                         [("http://192.168.50.20/status", 4)])

    def test_comandos_de_luz_mapeiam_somente_rotas_fixas(self):
        resultados = [processar_mensagem(mensagem(comando), self.config,
                                         self.sessao)
                      for comando in ("/luz_ligar", "/luz_desligar", "/luz_auto")]

        self.assertEqual(resultados, ["Luz ligada.", "Luz desligada.",
                                      "Luz em modo automático."])
        self.assertEqual([url for url, _ in self.sessao.gets], [
            "http://192.168.50.20/led/on",
            "http://192.168.50.20/led/off",
            "http://192.168.50.20/led/auto",
        ])

    def test_texto_livre_e_comando_desconhecido_nao_sao_executados(self):
        resposta = processar_mensagem(mensagem("/powershell Remove-Item"),
                                      self.config, self.sessao)
        self.assertIn("Comandos disponíveis", resposta)
        self.assertEqual(self.sessao.gets, [])

    def test_comando_enderecado_ao_bot_e_aceito(self):
        resposta = processar_mensagem(mensagem("/ajuda@jarvis_casa_bot"),
                                      self.config, self.sessao)
        self.assertIn("/status", resposta)
        self.assertEqual(self.sessao.gets, [])

    def test_erro_de_rede_responde_sem_revelar_detalhes_da_excecao(self):
        class Falha:
            def get(self, *_args, **_kwargs):
                raise RuntimeError("URL contem credencial privada")

        resposta = processar_mensagem(mensagem("/status"), self.config, Falha())
        self.assertEqual(resposta, "Não consegui consultar a ESP32 agora.")
        self.assertNotIn("credencial", resposta)


if __name__ == "__main__":
    unittest.main()
