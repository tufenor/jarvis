"""Ponte opcional da Alexa, sem abrir portas do PC na internet."""
import asyncio
import json
import logging
import re
import time
from pathlib import Path

from .alexa_protocolo import assinar, verificar

CONFIGURACAO = Path(__file__).resolve().parents[1] / "dados" / "alexa.json"


class PonteAlexa:
    def __init__(self, config, agente, painel, arquivo_ids=None):
        self.config, self.agente, self.painel = config, agente, painel
        self.arquivo_ids = arquivo_ids or CONFIGURACAO.with_name("alexa_recebidos.json")
        self.cliente = None
        self.tarefas = set()
        self.resultados = {}
        self.trava = asyncio.Lock()
        self.estado = {"configurada": True, "conectada": False}
        try:
            self.ids = list(json.loads(self.arquivo_ids.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            self.ids = []

    def responder(self, pedido_id, texto, estado):
        resultado = {"texto": texto[:1800], "estado": estado}
        self.resultados[pedido_id] = resultado
        if len(self.resultados) > 128:
            self.resultados.pop(next(iter(self.resultados)))
        if self.cliente:
            topico = self.config["topico"] + "/respostas"
            self.cliente.publish(topico, assinar(topico, self.config["chave"],
                pedido_id, "resposta", texto=resultado["texto"], estado=estado), qos=1)
        return resultado

    def reservar(self, pedido_id):
        self.ids = (self.ids + [pedido_id])[-256:]
        self.arquivo_ids.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo_ids.with_suffix(".tmp")
        temporario.write_text(json.dumps(self.ids), encoding="utf-8")
        temporario.replace(self.arquivo_ids)

    async def tratar(self, mensagem, topico):
        if topico != self.config["topico"] + "/comandos":
            return
        try:
            pedido = verificar(mensagem, topico, self.config["chave"],
                               {"abrir", "status", "consultar", "comando"})
        except (ValueError, TypeError, KeyError):
            return
        pedido_id = pedido["id"]
        if pedido_id in self.ids:
            anterior = self.resultados.get(pedido_id, {"texto":
                "Este pedido já foi recebido. Verifique o resultado no computador.", "estado": "recebido"})
            return self.responder(pedido_id, **anterior)
        try:
            self.reservar(pedido_id)
        except OSError:
            return self.responder(pedido_id, "Não consegui registrar este pedido no computador.", "erro")
        janela = getattr(self.agente, "janela", None)
        if janela and janela.bloqueada:
            return self.responder(pedido_id, "O computador está disponível, mas o Jarvis está bloqueado. Libere a tela com seu código ou sua voz cadastrada no computador.", "bloqueado")
        acao = pedido["acao"]
        if acao == "status":
            return self.responder(pedido_id, "Jarvis conectado e pronto no computador.", "pronto")
        if acao == "consultar":
            resultado = self.resultados.get(pedido["texto"], {"texto":
                "Ainda não tenho uma resposta para esse pedido.", "estado": "aguardando"})
            return self.responder(pedido_id, **resultado)
        if acao == "abrir":
            if janela:
                await asyncio.to_thread(janela.chamar)
            self.agente.ultima_atividade = time.monotonic()
            self.painel.registrar("sistema", "JARVIS chamado pela skill pessoal da Alexa")
            await self.painel.publicar()
            return self.responder(pedido_id, "Jarvis conectado. Pode dizer executar, seguido do seu pedido.", "pronto")
        tarefa = getattr(self.agente, "tarefa", None)
        if self.trava.locked() or (tarefa and not tarefa.done()):
            return self.responder(pedido_id, "Estou atendendo outro pedido. Tente novamente em alguns instantes.", "ocupado")
        if not pedido["texto"].strip():
            return self.responder(pedido_id, "Não recebi um comando.", "erro")
        async with self.trava:
            from .agente import ORIGEM_PEDIDO
            marca = ORIGEM_PEDIDO.set("alexa")
            self.responder(pedido_id, "O Jarvis está processando. Diga consultar resposta em alguns instantes.", "processando")
            try:
                await asyncio.wait_for(self.agente.processar(pedido["texto"]), timeout=60)
                estado = "confirmacao" if self.agente.pendente else "resposta"
                return self.responder(pedido_id, self.painel.agente["ultima_resposta"]
                                      or "Pedido concluído.", estado)
            except asyncio.CancelledError:
                raise
            except Exception:
                return self.responder(pedido_id, "Não consegui concluir esse pedido no computador.", "erro")
            finally:
                ORIGEM_PEDIDO.reset(marca)

    async def executar(self):
        from integracoes.alexa.mqtt_conexao import criar_cliente
        loop = asyncio.get_running_loop()
        try:
            cliente = self.cliente = criar_cliente(self.config, "pc-" + self.config["topico"].split("/")[1])
            def conectado(c, _u, _f, codigo, _p):
                self.estado["conectada"] = codigo == 0
                if codigo == 0:
                    c.subscribe(self.config["topico"] + "/comandos", qos=1)
            def desconectado(_c, _u, _flags, _codigo, _p):
                self.estado["conectada"] = False
            def finalizar(tarefa):
                self.tarefas.discard(tarefa)
                if tarefa.cancelled():
                    return
                try:
                    tarefa.exception()
                except Exception:
                    logging.exception("falha ao tratar pedido da Alexa")

            def agendar(payload, topico):
                if len(self.tarefas) >= 8:
                    return
                tarefa = asyncio.create_task(self.tratar(payload, topico))
                self.tarefas.add(tarefa)
                tarefa.add_done_callback(finalizar)
            def recebido(_c, _u, msg):
                if len(msg.payload) <= 8192:
                    loop.call_soon_threadsafe(agendar, msg.payload, msg.topic)
            cliente.on_connect, cliente.on_disconnect = conectado, desconectado
            cliente.on_message = recebido
            cliente.connect_async(self.config["broker"]["host"], 8883, keepalive=20)
            cliente.loop_start()
            await asyncio.Future()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.warning("ponte Alexa indisponível; confira a configuração local")
            self.estado["conectada"] = False
        finally:
            for tarefa in list(self.tarefas):
                tarefa.cancel()
            if self.tarefas:
                await asyncio.gather(*list(self.tarefas), return_exceptions=True)
            if self.cliente:
                self.cliente.disconnect()
                await asyncio.to_thread(self.cliente.loop_stop)


def carregar_ponte(agente, painel, arquivo=CONFIGURACAO):
    if not arquivo.exists():
        return None
    try:
        from integracoes.alexa.mqtt_conexao import validar_config
        config = json.loads(arquivo.read_text(encoding="utf-8"))
        validar_config(config)
        if not re.fullmatch(r"[a-f0-9]{64}", config.get("chave", "")):
            raise ValueError("chave não configurada")
        return PonteAlexa(config, agente, painel)
    except (OSError, ValueError, TypeError):
        logging.warning("configuração da ponte Alexa inválida")
        return None
