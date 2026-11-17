"""Sobe o JARVIS.

    python -m jarvis               aplicativo completo: janela + microfone + voz
    python -m jarvis --servidor    só o servidor (painel no navegador/celular), sem voz
"""
import argparse
import asyncio
import os
import socket
import threading
import time

import uvicorn

from .config import carregar
from .servidor import criar_app


def ip_na_rede():
    # Só descobre qual interface sairia para a rede; nenhum pacote é enviado.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.168.50.1", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def esperar_porta(porta, limite_s=20):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.2)
    return False


def registrar_quedas():
    """Queda do aplicativo deixa rastro em jarvis.log, mesmo quando é falha nativa
    (driver de áudio, WebView2) que não passa pelo Python."""
    import faulthandler
    import logging
    import sys
    caminho = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jarvis.log")
    arquivo = open(caminho, "a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        # Aberto sem console (pythonw, inicialização do Windows): sem isso o
        # uvicorn quebra ao configurar o log ("NoneType has no isatty").
        sys.stdout = sys.stderr = arquivo
    faulthandler.enable(arquivo)
    logging.basicConfig(stream=arquivo, level=logging.WARNING,
                        format="%(asctime)s %(threadName)s %(levelname)s %(message)s")
    logging.warning("JARVIS iniciando")

    def excecao_em_thread(args):
        logging.error("thread %s caiu", args.thread.name if args.thread else "?",
                      exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = excecao_em_thread
    sys.excepthook = lambda t, v, tb: logging.critical("queda", exc_info=(t, v, tb))


def definir_senha_do_painel():
    """Pergunta a senha sem ecoar e guarda só o hash."""
    import getpass
    from .acesso import ARQUIVO, definir_senha
    print("Senha para abrir o painel do JARVIS fora deste PC.")
    print("De dentro do PC (a janela do JARVIS) nunca é pedida senha.\n")
    while True:
        senha = getpass.getpass("Senha nova: ")
        if senha != getpass.getpass("Repita: "):
            print("  as duas não bateram, tente de novo\n")
            continue
        try:
            definir_senha(senha)
        except ValueError as exc:
            print(f"  {exc}\n")
            continue
        print(f"\nPronto. Guardado em {ARQUIVO} (fora do git).")
        print("Reinicie o JARVIS para a senha valer.")
        return


def definir_codigo_de_bloqueio():
    """Define localmente o código do overlay, guardando somente o hash.

    O valor nunca é argumento de linha de comando, log ou arquivo de código.
    Isso permite trocar um código que tenha sido exposto sem transformá-lo em
    senha do Windows e sem o JARVIS digitá-lo na tela de login.
    """
    import getpass
    from .acesso import ARQUIVO_BLOQUEIO, definir_senha
    print("Código local para liberar a tela do JARVIS (não é a senha do Windows).")
    while True:
        codigo = getpass.getpass("Código novo: ")
        if codigo != getpass.getpass("Repita: "):
            print("  os dois códigos não bateram, tente de novo\n")
            continue
        if not codigo.isdigit():
            print("  use somente dígitos\n")
            continue
        try:
            definir_senha(codigo, ARQUIVO_BLOQUEIO)
        except ValueError as exc:
            print(f"  {exc}\n")
            continue
        print(f"\nPronto. Guardado somente como hash em {ARQUIVO_BLOQUEIO}.")
        return


def cadastrar_rosto(config):
    """Inscreve o rosto localmente, sem guardar fotografias."""
    from .rosto import AutenticadorFacial, RostoIndisponivel

    facial = config.get("reconhecimento_facial", {}) or {}
    autenticador = AutenticadorFacial(
        camera=facial.get("camera", 0),
        limiar=facial.get("limiar", 0.363),
        exigir_prova_vida=facial.get("exigir_prova_vida", True),
        nome=facial.get("nome", "usuario"),
    )
    print("Cadastro facial local do JARVIS")
    print("Olhe para a câmera, com luz no rosto. Nenhuma foto será salva.")
    try:
        dados = autenticador.cadastrar()
    except RostoIndisponivel as exc:
        raise SystemExit(f"Não foi possível cadastrar o rosto: {exc}") from exc
    print(f"Perfil de {dados['nome']} salvo em dados/rosto.json.")


def apagar_rosto():
    from .rosto import ARQUIVO_PERFIL
    try:
        ARQUIVO_PERFIL.unlink()
        print("Perfil facial local apagado.")
    except FileNotFoundError:
        print("Nenhum perfil facial estava cadastrado.")


def inicializar_rosto_em_background(config, app, janela):
    """Liga o fallback facial depois que o servidor e o overlay existem."""
    import logging

    facial = config.get("reconhecimento_facial", {}) or {}
    if not facial.get("ativar", False):
        return
    try:
        from .rosto import AutenticadorFacial, MonitorFacial
        autenticador = AutenticadorFacial(
            camera=facial.get("camera", 0),
            limiar=facial.get("limiar", 0.363),
            exigir_prova_vida=facial.get("exigir_prova_vida", True),
        nome=facial.get("nome", "usuario"),
        )
    except Exception as exc:
        logging.warning("reconhecimento facial indisponível: %s", exc)
        return
    app.state.rosto = autenticador
    if not autenticador.perfil_configurado:
        autenticador.ultimo_status = "perfil facial não cadastrado"
        return

    def ao_reconhecer(resultado):
        agente = app.state.agente

        def liberar():
            if not janela.bloqueada:
                return
            if janela.desbloquear():
                texto = f"Identificação visual confirmada. Bem-vindo, {resultado.nome}."
                app.state.painel.registrar("sistema", texto)
                loop = getattr(agente, "loop", None)
                if loop and getattr(agente, "voz", None):
                    asyncio.create_task(agente._responder(texto, "sessão liberada"))
                else:
                    app.state.pending_face_greeting = texto
                if loop:
                    asyncio.create_task(app.state.painel.publicar())

        loop = getattr(agente, "loop", None)
        if loop and loop.is_running():
            loop.call_soon_threadsafe(liberar)
        else:
            liberar()

    monitor = MonitorFacial(autenticador, lambda: janela.bloqueada, ao_reconhecer)
    app.state.rosto_monitor = monitor
    monitor.iniciar()


def _nomes_de_skills():
    """Nomes das skills instaladas, para entrarem no vocabulário do Whisper."""
    pasta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")
    try:
        return [n for n in os.listdir(pasta) if os.path.isdir(os.path.join(pasta, n))]
    except OSError:
        return []


def inicializar_audio_em_background(config, app):
    """Carrega voz e microfone depois que o overlay já pode aparecer.

    O bloqueio pós-login não depende do modelo de voz para ser desenhado nem
    para aceitar o código local. Assim, uma inicialização lenta do Whisper,
    Piper ou do dispositivo de áudio não deixa o Windows sem a tela do JARVIS.
    Quando os objetos ficam prontos, eles são ligados ao agente dentro do loop
    do servidor.
    """
    def carregar_audio():
        import logging

        try:
            from .fala import Fala
            from .ouvinte import Ouvinte, montar_dica

            v = config["voz"]
            voz = Fala(v["modelo"], velocidade=v["velocidade"], efeito=v["efeito"],
                       gravidade=v.get("gravidade", 1.0))
            m = config["microfone"]
            usar_multiplos = bool(config.get("microfones_simultaneos", False))
            microfones = m.get("nomes") if usar_multiplos else [m.get("nome")]
            ouvinte = Ouvinte(
                ao_texto=lambda *a: None, microfone=m.get("nome"),
                microfones=microfones, automatico=m.get("automatico", False) and usar_multiplos,
                modelo=m["whisper"],
                beam=m.get("beam", 5),
                dica=montar_dica(config.get("programas", {}), _nomes_de_skills()),
                confianca_minima=m.get("confianca_minima", -1.0),
                temperatura=m.get("temperatura", [0.0, 0.2]),
                compressao_maxima=m.get("compressao_maxima", 2.4),
                silencio_fim_s=m.get("silencio_fim_s", 0.95),
                limiar_inicio=m.get("limiar_inicio", 0.50),
                limiar_silencio=m.get("limiar_silencio", 0.30),
            )
            try:
                from .locutores import Locutores
                cv = config.get("vozes", {})
                ouvinte.locutores = Locutores(limiar=cv.get("limiar", 0.55))
                ouvinte.eco.razao = cv.get("razao_interrupcao", 1.6)
            except Exception as exc:
                # Sem o modelo de voz, o código local continua disponível.
                logging.warning("reconhecimento de voz desligado: %s", exc)
            ambiente = config.get("ambiente", {})
            usar_loopback = config.get(
                "loopback_cancellation", ambiente.get("ignorar_audio_do_pc", True)
            )
            if usar_loopback:
                from .ambiente import AudioDoPC, FiltroDeOrigem
                audio_do_pc = AudioDoPC(
                    alto_falantes=ambiente.get("alto_falantes")
                )
                audio_do_pc.iniciar()
                ouvinte.filtro_origem = FiltroDeOrigem(audio_do_pc)
                ouvinte.estado["fontes_cancelamento"] = list(audio_do_pc.nomes_fontes)
                ouvinte.estado["fontes_cancelamento_ativas"] = list(audio_do_pc.fontes_ativas)
            else:
                logging.info("Loopback de áudio desativado pela configuração")
        except Exception:
            logging.exception("voz e microfone não puderam ser carregados")
            return

        agente = app.state.agente
        limite = time.monotonic() + 60
        while getattr(agente, "loop", None) is None and time.monotonic() < limite:
            time.sleep(0.1)
        loop = getattr(agente, "loop", None)
        if loop is None or not hasattr(agente, "ligar_voz"):
            logging.warning("voz pronta, mas o loop do agente não está disponível")
            return

        def conectar():
            agente.voz = voz
            agente.ouvinte = ouvinte
            agente.locutores = getattr(ouvinte, "locutores", None)
            app.state.painel.recursos.update(voz=True, microfone=True)
            agente.ligar_voz(loop)
            app.state.painel.registrar("sistema", "Voz e microfone prontos")
            pendente = getattr(app.state, "pending_face_greeting", None)
            if pendente and not getattr(agente.janela, "bloqueada", False):
                app.state.pending_face_greeting = None
                asyncio.create_task(agente._responder(pendente, "sessão liberada"))

        loop.call_soon_threadsafe(conectar)

    threading.Thread(target=carregar_audio, name="carregar-audio", daemon=True).start()


def main():
    registrar_quedas()
    parser = argparse.ArgumentParser(prog="jarvis")
    parser.add_argument("--servidor", action="store_true", help="sem janela, sem microfone e sem voz")
    parser.add_argument("--senha", action="store_true",
                        help="define a senha de acesso ao painel de fora deste PC")
    parser.add_argument("--codigo-bloqueio", action="store_true",
                        help="define localmente o código do bloqueio pós-login")
    parser.add_argument("--cadastrar-rosto", action="store_true",
                        help="cadastra o rosto local para liberar o overlay")
    parser.add_argument("--apagar-rosto", action="store_true",
                        help="apaga o perfil facial local")
    parser.add_argument("--sem-bloqueio", action="store_true",
                        help="inicia uma vez sem o overlay pós-login, para recuperação")
    args = parser.parse_args()

    if args.senha:
        definir_senha_do_painel()
        return
    if args.codigo_bloqueio:
        definir_codigo_de_bloqueio()
        return

    config = carregar()
    if args.cadastrar_rosto:
        cadastrar_rosto(config)
        return
    if args.apagar_rosto:
        apagar_rosto()
        return
    if args.sem_bloqueio:
        config.setdefault("bloqueio_pos_login", {})["ativar"] = False
    porta = config["porta"]
    print(f"JARVIS no ar:  http://localhost:{porta}   (celular: http://{ip_na_rede()}:{porta})")

    if args.servidor:
        uvicorn.run(criar_app(config), host=config["host"], port=porta, log_level="warning")
        return

    from .janela import Janela
    config_janela = dict(config.get("janela", {}))
    config_janela["bloqueio_pos_login"] = config.get("bloqueio_pos_login", {})
    janela = Janela(config_janela)

    # O servidor e o overlay sobem sem esperar modelos de voz. O carregamento
    # de Piper/Whisper continua em paralelo e liga o microfone quando terminar.
    app = criar_app(config, voz=None, ouvinte=None, janela=janela, rosto=None)
    servidor = uvicorn.Server(uvicorn.Config(app, host=config["host"], port=porta, log_level="warning"))
    threading.Thread(target=servidor.run, name="servidor", daemon=True).start()
    if not esperar_porta(porta):
        raise SystemExit("O servidor não subiu na porta %d (outro JARVIS já aberto?)" % porta)

    # A janela do pywebview precisa da thread principal.
    import webview
    url = f"http://127.0.0.1:{porta}/"
    if janela.bloqueio_ativo:
        # A janela normal fica carregada, mas escondida; ao liberar por voz ou
        # pelo código local ela aparece sem reiniciar o servidor.
        janela.criar(url, ocultar=True)
        janela.criar_bloqueio(f"http://127.0.0.1:{porta}/bloqueio")
    else:
        janela.criar(url)
        # Mover antes de a janela existir na tela não tem efeito: espera o "shown".
        janela.janela.events.shown += lambda: janela.ir_para(janela.tela_repouso)
    inicializar_rosto_em_background(config, app, janela)
    inicializar_audio_em_background(config, app)
    webview.start()
    # Janela fechada = aplicativo encerrado (as threads de áudio são daemon).
    import logging
    logging.warning("janela fechada; encerrando")
    servidor.should_exit = True
    os._exit(0)


if __name__ == "__main__":
    main()
