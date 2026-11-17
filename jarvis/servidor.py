"""Servidor do centro de comando: interface estática + WebSocket + ações.

A interface só recebe dados pelo WebSocket (sem polling). Quem consulta a
placa em intervalo é o servidor, uma vez para todos os navegadores abertos.
"""
import asyncio
import contextlib
import json
import time

import psutil
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .acesso import ARQUIVO_BLOQUEIO, COOKIE, LOCAIS, Acesso
from .agente import Agente
from .cerebro import carregar_env, criar_cerebro
from .config import PASTA
from .diario import Diario
from .incidentes import Incidentes
from .estado import Painel, agora_iso
from .ferramentas import (ErroFerramenta, criar_ferramentas,
                          criar_ferramentas_de_skills, validar)
from .skills import Skills
from .placa import ACOES_LUZ, Placa, agente_energia_no_ar, descrever_erro
from .satelite import (FilaSatelite, PonteCelular,
                       carregar_ou_criar_token, criar_router as criar_router_satelite)
from .simulador import AgenteSimulado
from .energia import ControleBrilho, deve_economizar, ha_presenca_conhecida, segundos_desde_entrada

INTERFACE = PASTA / "interface"


class Comando(BaseModel):
    texto: str


class Entrada(BaseModel):
    senha: str


class CodigoBloqueio(BaseModel):
    codigo: str


class PresencaMobile(BaseModel):
    """Sinal efêmero do telefone companheiro.

    A aplicação pode enviar somente presença (mais econômico) ou uma posição
    aproximada. O servidor arredonda e nunca persiste coordenadas.
    """
    presente: bool | None = None
    origem: str = "a53"
    evento: str = "heartbeat"
    latitude: float | None = None
    longitude: float | None = None
    precisao_m: float | None = None


def endereco_de(pedido):
    """IP de quem está pedindo. Sem confiar em cabeçalho que o cliente escolhe:
    X-Forwarded-For é fácil de forjar e aqui não há proxy nenhum na frente."""
    return pedido.client.host if pedido.client else ""


ESPERA_PLACA_S = [3, 5, 10, 20, 30, 60]


async def vigiar_placa(painel, placa, intervalo_s):
    """Lê a placa e, quando ela cai, espera cada vez mais antes de tentar.

    O servidor HTTP da ESP32 atende uma conexão por vez; insistir de 3 em 3
    segundos numa placa travada só piora. Quando ela volta, o ritmo normal volta
    junto."""
    falhas = 0
    while True:
        antes = painel.placa["online"]
        try:
            painel.placa.update(await placa.ler_status(), online=True, erro=None,
                                ultimo_contato=agora_iso())
            falhas = 0
        except Exception as exc:
            painel.placa.update(online=False, erro=descrever_erro(exc))
            falhas += 1
            # Conexão pendurada não se cura sozinha: abre um cliente novo.
            if falhas == 3:
                await placa.reconectar()
                painel.registrar("placa", "Reabrindo a conexão com a placa")
        if antes != painel.placa["online"]:
            if painel.placa["online"]:
                painel.registrar("placa", "Placa conectada")
            else:
                painel.registrar("placa", f"Placa perdida: {painel.placa['erro']}")
        await painel.publicar()
        espera = intervalo_s if not falhas else ESPERA_PLACA_S[min(falhas - 1, len(ESPERA_PLACA_S) - 1)]
        await asyncio.sleep(espera)


async def vigiar_sistema(painel, url_agente, intervalo_s):
    while True:
        painel.sistema["cpu"] = psutil.cpu_percent(interval=None)
        painel.sistema["memoria"] = psutil.virtual_memory().percent
        painel.sistema["agente_energia"] = await agente_energia_no_ar(url_agente)
        await painel.publicar()
        await asyncio.sleep(intervalo_s)


async def vigiar_janela(agente, repouso_apos_s):
    """Parado por um tempo, a janela volta para a tela de repouso (a secundária)."""
    while True:
        await asyncio.sleep(2)
        if not getattr(agente, "janela", None) or agente.janela.bloqueada:
            continue
        parado = time.monotonic() - agente.ultima_atividade
        if agente.painel.agente["estado"] == "repouso" and parado > repouso_apos_s:
            await asyncio.to_thread(agente.janela.repousar)


async def vigiar_economia(agente, config, brilho=None, entrada=segundos_desde_entrada):
    """Minimiza e reduz brilho após inatividade, restaurando ao retorno local."""
    politica = config.get("economia_energia", {}) or {}
    if not politica.get("ativar", False) or not getattr(agente, "janela", None):
        return
    limite = max(60.0, float(politica.get("inatividade_apos_s", 300)))
    intervalo = max(2.0, float(politica.get("verificar_a_cada_s", 5)))
    brilho = brilho or ControleBrilho()
    economizado = False
    while True:
        await asyncio.sleep(intervalo)
        janela = agente.janela
        if janela.bloqueada:
            continue
        parado = time.monotonic() - agente.ultima_atividade
        entrada_s = entrada()
        presenca = (
            politica.get("respeitar_presenca_mobile", True)
            and ha_presenca_conhecida(agente.painel)
        )
        pode_economizar = deve_economizar(
            agente.painel.agente["estado"], parado, entrada_s, limite, presenca
        )
        if pode_economizar and not economizado:
            brilho.capturar(politica.get("brilho_retorno", 75))
            brilho_ok = brilho.definir(politica.get("brilho_ausente", 25))
            janela_ok = janela.minimizar()
            economizado = True
            if brilho_ok and janela_ok:
                agente.painel.registrar(
                    "energia", "Modo econômico: JARVIS minimizado e brilho reduzido"
                )
            else:
                partes = []
                if not brilho_ok:
                    partes.append("brilho não pôde ser ajustado neste monitor")
                if not janela_ok:
                    partes.append("janela não pôde ser minimizada")
                agente.painel.registrar(
                    "erro", "Modo econômico parcial: " + "; ".join(partes)
                )
            await agente.painel.publicar()
        elif economizado and not pode_economizar:
            brilho_ok = brilho.restaurar(politica.get("brilho_retorno", 75))
            janela_ok = janela.restaurar()
            economizado = False
            if brilho_ok and janela_ok:
                agente.painel.registrar(
                    "energia", "Modo econômico encerrado: atividade detectada"
                )
            else:
                partes = []
                if not brilho_ok:
                    partes.append("brilho não pôde ser restaurado")
                if not janela_ok:
                    partes.append("janela não pôde ser restaurada")
                agente.painel.registrar(
                    "erro", "Restauração do modo econômico parcial: " + "; ".join(partes)
                )
            await agente.painel.publicar()


ESPERA_CEREBRO_S = [10, 20, 30, 60, 120]


async def vigiar_cerebro(agente, painel):
    """Cérebro fora do ar volta sozinho quando a internet volta.

    Antes, uma queda da API deixava o JARVIS dizendo "estou sem cérebro" até
    alguém falar com ele de novo; agora ele mesmo percebe que voltou."""
    falhas = 0
    while True:
        if painel.cerebro.get("online", True):
            falhas = 0
            await asyncio.sleep(ESPERA_CEREBRO_S[0])
            continue
        await asyncio.sleep(ESPERA_CEREBRO_S[min(falhas, len(ESPERA_CEREBRO_S) - 1)])
        falhas += 1
        if await agente.verificar_cerebro():
            painel.registrar("sistema", "Cérebro de volta")
            falhas = 0


def criar_agente(config, painel, placa, cerebro=None, abrir=None, voz=None, ouvinte=None,
                 janela=None, ponte_celular=None):
    if config["cerebro"]["tipo"] == "simulado" and cerebro is None:
        return AgenteSimulado(painel)
    extras = {"abrir": abrir} if abrir else {}
    ferramentas = criar_ferramentas(config, placa, janela=janela, **extras)
    # Skills entram por cima das ferramentas básicas. Uma skill quebrada é
    # desligada sozinha pelo carregador, sem derrubar o resto.
    from .ferramentas import _abrir_padrao
    from .memoria import Memoria
    memoria = Memoria(PASTA.parent / "dados" / "memoria.json")
    diario = Diario(PASTA.parent / "dados" / "diario")
    contexto = {"config": config, "placa": placa, "janela": janela,
                "painel": painel, "abrir": abrir or _abrir_padrao,
                "memoria": memoria, "celular": ponte_celular,
                "ouvinte": ouvinte}
    skills = Skills(contexto)
    ferramentas.update(skills.ferramentas())
    ferramentas.update({f.nome: f for f in criar_ferramentas_de_skills(skills)})
    painel.skills = skills.resumo()

    cerebro = cerebro or criar_cerebro(config["cerebro"], ferramentas)
    painel.cerebro["nome"] = cerebro.nome
    return Agente(painel, cerebro, ferramentas, voz=voz, ouvinte=ouvinte, janela=janela,
                  conversa_s=config.get("conversa", {}).get("aberta_s", 30), skills=skills,
                  exigir_voz_conhecida=config.get("conversa", {}).get("exigir_voz_conhecida", False),
                  exigir_chamado_a_cada_frase=config.get("conversa", {}).get(
                      "exigir_chamado_a_cada_frase", False),
                  memoria=memoria, diario=diario,
                  diario_s=config.get("diario", {}).get("escuta_s", 300))


def criar_app(config, placa=None, iniciar_vigias=True, cerebro=None, abrir=None,
              voz=None, ouvinte=None, janela=None, rosto=None):
    # A chave da API mora no .env (fora do git); precisa estar no ambiente
    # antes de o cliente da Anthropic ser criado.
    carregar_env(PASTA.parent / ".env")
    acesso = Acesso()
    bloqueio_acesso = Acesso(ARQUIVO_BLOQUEIO)
    incidentes = Incidentes(PASTA.parent / "dados" / "incidentes.jsonl")
    painel = Painel(nome_cerebro=config["cerebro"]["tipo"], incidentes=incidentes)
    placa = placa or Placa(config["placa"]["url"], config["placa"]["timeout_s"])
    # Token do satélite é separado do login do painel: o celular manda tudo
    # com um cabeçalho em vez de carregar cookie.
    token_satelite = carregar_ou_criar_token(PASTA.parent / "dados" / "satelite_token.txt")
    fila_satelite = FilaSatelite()
    ponte_celular = PonteCelular(fila_satelite)
    agente = criar_agente(config, painel, placa, cerebro, abrir, voz, ouvinte, janela,
                          ponte_celular=ponte_celular)
    luz_ligada = config.get("recursos", {}).get("luz", True)
    painel.recursos = {"luz": luz_ligada, "voz": voz is not None, "microfone": ouvinte is not None}

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(app):
        tarefas = []
        app.state.ponte_alexa = None
        if iniciar_vigias:
            from .alexa import carregar_ponte
            app.state.ponte_alexa = carregar_ponte(agente, painel)
            if app.state.ponte_alexa:
                tarefas.append(asyncio.create_task(app.state.ponte_alexa.executar()))
        painel.registrar("sistema", f"JARVIS iniciado — cérebro: {painel.cerebro['nome']}")
        if iniciar_vigias:
            if isinstance(agente, Agente):
                tarefas.append(asyncio.create_task(agente.preparar_cerebro()))
                agente.ligar_voz(asyncio.get_running_loop())
                boas_vindas = config.get("boas_vindas", {})
                if (not janela or not janela.bloqueada) and boas_vindas.get("ativar", False) \
                        and agente.voz and agente.ouvinte:
                    from .entretenimento import executar as executar_boas_vindas
                    from .ferramentas import _abrir_padrao
                    tarefas.append(asyncio.create_task(
                        executar_boas_vindas(agente, _abrir_padrao, boas_vindas)
                    ))
                if janela:
                    tarefas.append(asyncio.create_task(
                        vigiar_janela(agente, config.get("janela", {}).get("repouso_apos_s", 60))))
                    tarefas.append(asyncio.create_task(vigiar_economia(agente, config)))
            tarefas.append(asyncio.create_task(
                vigiar_placa(painel, placa, config["placa"]["intervalo_s"])))
            tarefas.append(asyncio.create_task(
                vigiar_sistema(painel, config["agente_energia"]["url"],
                               config["agente_energia"]["intervalo_s"])))
            if isinstance(agente, Agente):
                tarefas.append(asyncio.create_task(vigiar_cerebro(agente, painel)))
        yield
        for t in tarefas:
            t.cancel()
        if tarefas:
            await asyncio.gather(*tarefas, return_exceptions=True)
        await agente.cancelar()
        await placa.fechar()

    app = FastAPI(title="JARVIS", lifespan=ciclo_de_vida)
    app.state.painel = painel
    app.state.incidentes = incidentes
    app.state.agente = agente
    app.state.acesso = acesso
    # `skills` fica em `agente.skills` quando ele é o Agente real; no simulado é None.
    app.state.skills = getattr(agente, "skills", None)
    if rosto is None and config.get("reconhecimento_facial", {}).get("ativar", False):
        try:
            from .rosto import AutenticadorFacial
            facial = config.get("reconhecimento_facial", {})
            rosto = AutenticadorFacial(
                camera=facial.get("camera", 0),
                limiar=facial.get("limiar", 0.363),
                exigir_prova_vida=facial.get("exigir_prova_vida", True),
                nome=facial.get("nome", "usuario"),
            )
        except Exception:
            # Diagnóstico facial não pode impedir o painel ou o código local.
            rosto = None
    app.state.rosto = rosto

    LIVRES = {"/login", "/bloqueio", "/interface/login.css",
              "/interface/bloqueio.css", "/api/saude",
              "/api/bloqueio/status", "/api/bloqueio/desbloquear",
              "/api/bloqueio/microfones", "/api/bloqueio/microfone",
              "/api/bloqueio/rosto/status"}
    # O satélite se autentica por token no cabeçalho, não pelo cookie do painel.
    PREFIXOS_LIVRES = ("/api/satelite/",)
    LEITURAS_DURANTE_BLOQUEIO = {"/api/saude", "/api/diagnostico",
                                 "/api/bloqueio/status", "/api/bloqueio/desbloquear"}

    @app.middleware("http")
    async def exigir_acesso(pedido: Request, seguir):
        """Um porteiro só, para TODAS as rotas.

        Protege por omissão: rota nova nasce protegida, em vez de alguém ter
        que lembrar de marcar cada uma."""
        if pedido.url.path in LIVRES or pedido.url.path.startswith(PREFIXOS_LIVRES):
            return await seguir(pedido)
        pode, motivo = acesso.liberado(endereco_de(pedido), pedido.cookies.get(COOKIE))
        if pode:
            if (janela and janela.bloqueada and pedido.url.path.startswith("/api/")
                    and pedido.url.path not in LEITURAS_DURANTE_BLOQUEIO):
                return JSONResponse(
                    {"erro": "JARVIS bloqueado; liberação por voz ou código local"},
                    status_code=423,
                )
            return await seguir(pedido)
        if pedido.url.path.startswith("/api/"):
            return JSONResponse({"erro": "precisa entrar", "motivo": motivo}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    @app.get("/login")
    async def tela_de_login():
        return FileResponse(INTERFACE / "login.html")

    @app.post("/login")
    async def entrar(dados: Entrada, pedido: Request):
        acesso.recarregar()   # senha trocada não exige reiniciar o JARVIS
        if not acesso.tem_senha:
            raise HTTPException(503, "ainda não há senha definida neste JARVIS")
        if not acesso.conferir_senha(dados.senha):
            painel.registrar("sistema", f"Tentativa de entrada recusada de {endereco_de(pedido)}")
            # Atraso curto: deixa a tentativa em massa cara sem travar o servidor.
            await asyncio.sleep(1.0)
            raise HTTPException(401, "senha errada")
        painel.registrar("sistema", f"Entrada liberada para {endereco_de(pedido)}")
        resposta = JSONResponse({"ok": True})
        resposta.set_cookie(COOKIE, acesso.criar_sessao(), httponly=True,
                            samesite="lax", max_age=30 * 24 * 3600)
        return resposta

    @app.get("/api/saude")
    async def saude():
        """Única rota aberta: responde se o JARVIS está de pé, sem contar nada."""
        return {"ok": True}

    @app.get("/")
    async def inicio():
        return FileResponse(INTERFACE / "index.html")

    @app.get("/bloqueio")
    async def tela_de_bloqueio():
        return FileResponse(INTERFACE / "bloqueio.html")

    @app.get("/mobile")
    async def painel_mobile():
        """Painel instalável (PWA) para o Galaxy A53."""
        return FileResponse(INTERFACE / "mobile.html")

    @app.get("/mobile-manifest.webmanifest")
    async def manifest_mobile():
        return FileResponse(INTERFACE / "mobile-manifest.webmanifest",
                            media_type="application/manifest+json")

    @app.get("/mobile-sw.js")
    async def service_worker_mobile():
        return FileResponse(INTERFACE / "mobile-sw.js",
                            media_type="application/javascript")

    @app.get("/api/bloqueio/status")
    async def status_do_bloqueio():
        bloqueio_acesso.recarregar()
        return {
            "bloqueada": bool(janela and janela.bloqueada),
            "codigo_configurado": bloqueio_acesso.tem_senha,
            "frase_liberar": janela.frase_liberar if janela else "liberar tela",
            "voz_conhecida_exigida": bool(janela and janela.exigir_voz_conhecida),
        }

    @app.get("/api/bloqueio/rosto/status")
    async def status_do_rosto(pedido: Request):
        if endereco_de(pedido) not in LOCAIS:
            raise HTTPException(403, "somente nesta máquina")
        autenticador = getattr(app.state, "rosto", None)
        if autenticador is None:
            return {"ativado": False, "status": "reconhecimento facial desligado"}
        return autenticador.diagnostico()

    @app.post("/api/bloqueio/desbloquear")
    async def desbloquear_por_codigo(codigo: CodigoBloqueio, pedido: Request):
        # O campo é uma recuperação local do overlay, não uma porta remota.
        if endereco_de(pedido) not in LOCAIS:
            raise HTTPException(403, "o código só pode ser usado nesta máquina")
        if not janela or not janela.bloqueada:
            return {"ok": True, "ja_liberado": True}
        bloqueio_acesso.recarregar()
        if not bloqueio_acesso.tem_senha:
            raise HTTPException(503, "código local ainda não configurado")
        if not codigo.codigo.isdigit():
            raise HTTPException(400, "use somente dígitos")
        if not bloqueio_acesso.conferir_senha(codigo.codigo):
            painel.registrar("sistema", "Tentativa de código local recusada")
            await asyncio.sleep(0.6)
            raise HTTPException(401, "código local incorreto")
        await asyncio.to_thread(janela.desbloquear)
        painel.registrar("sistema", "Tela de bloqueio liberada por código local")
        await painel.publicar()
        return {"ok": True}

    def retrato_audio(ouv):
        estado = getattr(ouv, "estado", {})
        return {
            "microfones": list(getattr(ouv, "nomes_microfones", [])),
            "modo": estado.get("modo_microfone", "manual"),
            "selecionado": getattr(ouv, "microfone_prioritario", None),
            "ultimo": estado.get("ultimo_microfone"),
            "ativos": estado.get("microfones_ativos", []),
            "nivel": estado.get("nivel", 0.0),
        }

    def obter_ouvinte():
        ouv = getattr(agente, "ouvinte", None)
        if not ouv:
            raise HTTPException(503, "microfone ainda está iniciando")
        return ouv

    async def alterar_microfone(nome):
        ouv = obter_ouvinte()
        if not isinstance(nome, str):
            raise HTTPException(400, "microfone não disponível")
        if await asyncio.to_thread(ouv.trocar_microfone, nome):
            painel.registrar("sistema", "Modo multi-microfone ativado" if nome == "multi"
                             else f"Microfone alterado para: {nome}")
            await painel.publicar()
            return {"ok": True, **retrato_audio(ouv)}
        raise HTTPException(400, "esse microfone exige reiniciar o JARVIS")

    @app.get("/api/audio/microfones")
    async def listar_microfones():
        return retrato_audio(obter_ouvinte())

    @app.post("/api/audio/microfone")
    async def trocar_microfone(dados: dict):
        return await alterar_microfone(dados.get("nome"))

    @app.get("/api/bloqueio/microfones")
    async def microfones_no_bloqueio(pedido: Request):
        if endereco_de(pedido) not in LOCAIS:
            raise HTTPException(403, "somente nesta máquina")
        return retrato_audio(obter_ouvinte())

    @app.post("/api/bloqueio/microfone")
    async def trocar_microfone_no_bloqueio(dados: dict, pedido: Request):
        if endereco_de(pedido) not in LOCAIS:
            raise HTTPException(403, "somente nesta máquina")
        return await alterar_microfone(dados.get("nome"))

    @app.websocket("/ws")
    async def canal(ws: WebSocket):
        # O middleware HTTP não vê WebSocket: a porta tem que ser trancada aqui.
        if janela and janela.bloqueada:
            await ws.close(code=4423)
            return
        pode, _ = acesso.liberado(ws.client.host if ws.client else "",
                                  ws.cookies.get(COOKIE))
        if not pode:
            await ws.close(code=4401)
            return
        await ws.accept()
        painel.clientes.add(ws)
        try:
            await ws.send_text(json.dumps(painel.retrato(), ensure_ascii=False))
            while True:
                # O canal é só de saída; ler mantém a conexão e detecta o fechamento.
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            painel.clientes.discard(ws)

    @app.get("/api/estado")
    async def estado_agora():
        """O mesmo retrato que vai pelo WebSocket, para quem prefere pedir."""
        return painel.retrato()

    @app.get("/api/presenca")
    async def presenca_mobile():
        return dict(painel.presenca_mobile)

    @app.get("/api/presencas")
    async def presencas_moveis():
        """Presença efêmera separada por aparelho companheiro."""
        return {k: dict(v) for k, v in painel.presencas_moveis.items()}

    @app.post("/api/presenca")
    async def atualizar_presenca_mobile(dados: PresencaMobile):
        """Recebe um heartbeat efêmero do telefone companheiro.

        A posição é arredondada para cerca de 100 m e não é persistida nem
        devolvida ao navegador. O estado é usado apenas para decidir presença.
        """
        origem = (dados.origem or "a53").strip()[:40] or "a53"
        evento = (dados.evento or "heartbeat").strip()[:40] or "heartbeat"
        origem = origem.lower().replace(" ", "-")
        presente = dados.presente
        if dados.latitude is not None and not -90 <= dados.latitude <= 90:
            raise HTTPException(400, "latitude inválida")
        if dados.longitude is not None and not -180 <= dados.longitude <= 180:
            raise HTTPException(400, "longitude inválida")
        precisao = None if dados.precisao_m is None else max(0.0, min(float(dados.precisao_m), 100000.0))
        anterior = painel.presencas_moveis.get(origem, {}).get("presente")
        painel.presenca_mobile = {
            "presente": presente,
            "origem": origem,
            "evento": evento,
            "quando": agora_iso(),
            "precisao_m": round(precisao, 1) if precisao is not None else None,
        }
        painel.presencas_moveis[origem] = dict(painel.presenca_mobile)
        if anterior != presente:
            estado = "presente" if presente else "ausente" if presente is False else "indeterminada"
            painel.registrar("presença", f"{origem}: {estado}")
        await painel.publicar()
        return dict(painel.presenca_mobile)

    @app.get("/api/ferramentas")
    async def listar_ferramentas():
        """O que o JARVIS sabe fazer, para quem o controla de fora (MCP)."""
        return [
            {"nome": f.nome, "descricao": f.descricao, "argumentos": f.esquema(),
             "perigosa": f.perigosa,
             "skill": (app.state.skills.dona_da_ferramenta(f.nome).nome
                       if app.state.skills and app.state.skills.dona_da_ferramenta(f.nome)
                       else "base")}
            for f in agente.ferramentas.values()
        ]

    @app.post("/api/ferramenta/{nome}")
    async def executar_ferramenta(nome: str, argumentos: dict | None = None):
        """Executa UMA ferramenta direto, sem passar pelo cérebro.

        Ação perigosa NÃO roda por aqui: a confirmação do JARVIS é falada, e
        quem chama de fora não tem como dar esse "sim" pelo usuário. Quem
        quiser suspender o PC fala com o JARVIS.
        """
        ferramenta = agente.ferramentas.get(nome)
        if ferramenta is None:
            raise HTTPException(404, f"não existe a ferramenta {nome}")
        if ferramenta.perigosa:
            raise HTTPException(
                403, f"{nome} muda o estado da máquina e exige confirmação falada; "
                     "peça isso ao JARVIS por voz")
        argumentos = argumentos or {}
        erro = validar(ferramenta, argumentos)
        if erro:
            raise HTTPException(400, erro)
        try:
            texto = await ferramenta.funcao(**argumentos)
        except ErroFerramenta as exc:
            raise HTTPException(502, str(exc))
        painel.registrar("acao", f"{nome} (por MCP) → {texto}")
        await painel.publicar()
        return {"resultado": texto}

    @app.get("/api/incidentes")
    async def incidentes_recentes(limite: int = 20):
        """Handoff local para revisar falhas e pedidos que não foram entendidos."""
        return {"incidentes": incidentes.ultimos(limite)}

    @app.get("/api/diagnostico")
    async def diagnostico():
        ouv = getattr(agente, "ouvinte", None)
        return {"ouvinte": ouv.estado if ouv else None, "estado": painel.agente["estado"]}

    @app.post("/api/comando")
    async def comando(c: Comando):
        texto = c.texto.strip()
        if not texto:
            raise HTTPException(400, "comando vazio")
        agente.processar(texto)
        return {"ok": True}

    @app.post("/api/escutar")
    async def escutar():
        agente.escutar()
        return {"ok": True}

    @app.post("/api/cancelar")
    async def cancelar():
        await agente.cancelar()
        return {"ok": True}

    @app.post("/api/demonstracao/{nome}")
    async def demonstracao(nome: str):
        if nome == "ciclo":
            agente.ciclo_demonstracao()
        elif nome == "erro":
            agente.simular_erro()
        else:
            raise HTTPException(404, "demonstração desconhecida")
        return {"ok": True}

    @app.post("/api/acao/{nome}")
    async def acao(nome: str):
        if nome not in ACOES_LUZ or not luz_ligada:
            raise HTTPException(404, "ação desconhecida")
        try:
            await placa.acao(nome)
        except Exception as exc:
            msg = f"Falhou {nome.replace('_', ' ')}: {descrever_erro(exc)}"
            painel.registrar("erro", msg)
            await painel.publicar()
            raise HTTPException(502, msg)
        painel.registrar("acao", nome.replace("_", " ").capitalize())
        await painel.publicar()
        return {"ok": True}

    app.include_router(criar_router_satelite(token_satelite, painel, fila_satelite))
    app.state.satelite_token = token_satelite
    app.state.satelite_fila = fila_satelite
    app.mount("/interface", StaticFiles(directory=INTERFACE), name="interface")
    return app
