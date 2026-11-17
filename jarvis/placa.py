"""Conversa com a ESP32 e com o agente de energia pela rede."""
import httpx

# Rotas da ESP32 que a interface pode chamar direto. Lista fechada de propósito:
# nada de repassar caminho arbitrário vindo do navegador.
ACOES_LUZ = {"luz_ligar": "/led/on", "luz_desligar": "/led/off", "luz_auto": "/led/auto"}


class Placa:
    def __init__(self, url, timeout_s=2.5):
        self.url = url.rstrip("/")
        self.timeout = timeout_s
        # Um cliente só, reaproveitando conexão: o servidor HTTP da ESP32 é
        # de uma conexão por vez, e abrir socket novo a cada leitura pesa nela.
        self.cliente = httpx.AsyncClient(timeout=timeout_s)

    async def ler_status(self):
        r = await self.cliente.get(self.url + "/status")
        r.raise_for_status()
        d = r.json()
        return {
            "temperatura": d.get("temperature"),
            "umidade": d.get("humidity"),
            "movimento": d.get("motion"),
            "led": d.get("led"),
            "led_manual": d.get("manual_led"),
        }

    async def acao(self, nome):
        caminho = ACOES_LUZ[nome]
        r = await self.cliente.get(self.url + caminho)
        r.raise_for_status()

    async def acordar_pc(self):
        r = await self.cliente.get(self.url + "/acordar-pc", headers={"User-Agent": "curl/jarvis"})
        r.raise_for_status()
        return r.text.strip()

    async def reconectar(self):
        """Troca o cliente HTTP por um novo.

        Uma conexão que ficou pendurada (placa travada no meio de uma resposta)
        não volta sozinha: o jeito é abandonar e abrir outra."""
        antigo, self.cliente = self.cliente, httpx.AsyncClient(timeout=self.timeout)
        try:
            await antigo.aclose()
        except Exception:
            pass

    async def fechar(self):
        await self.cliente.aclose()


async def agente_energia_no_ar(url, timeout_s=2.0):
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as c:
            r = await c.get(url.rstrip("/") + "/health")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


def descrever_erro(exc):
    """Mensagem curta e humana para o painel; o traceback não ajuda ninguém ali."""
    if isinstance(exc, httpx.ConnectTimeout):
        return "não aceitou conexão (servidor da placa travado ou desligado)"
    if isinstance(exc, httpx.ReadTimeout):
        return "conectou mas não respondeu a tempo"
    if isinstance(exc, httpx.ConnectError):
        return "sem rota até a placa"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"respondeu HTTP {exc.response.status_code}"
    return type(exc).__name__
