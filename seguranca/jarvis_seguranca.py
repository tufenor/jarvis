"""JARVIS - vigilancia: movimento no PIR -> grava webcam -> envia no Telegram.

Dois modos de ouvir o sensor (definidos em config.json):
  "serial" -> le a porta COM da ESP32 (funciona sempre, mas prende a porta)
  "http"   -> consulta http://<ip-da-placa>/status (sem cabo USB)

O cooldown evita enxurrada de mensagens quando ha movimento continuo.
"""
import json
import os
import subprocess
import sys
import time
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
GRAVACOES = os.path.join(BASE, "gravacoes")
LOG_PATH = os.path.join(BASE, "jarvis_seguranca.log")


def log(msg):
    stamp = datetime.datetime.now().strftime("%d/%m %H:%M:%S")
    linha = f"[{stamp}] {msg}"
    print(linha, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def carregar_config():
    if not os.path.exists(CONFIG_PATH):
        log("ERRO: config.json nao encontrado em " + CONFIG_PATH)
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    token = cfg.get("telegram_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    telegram_ok = bool(token and chat_id and "COLOQUE" not in str(token)
                       and "COLOQUE" not in str(chat_id))
    drive_ok = bool(cfg.get("google_drive", {}).get("ativado", False))
    if not telegram_ok and not drive_ok:
        log("ERRO: configure Telegram ou ative Google Drive no config.json")
        sys.exit(1)
    cfg["_telegram_configurado"] = telegram_ok
    return cfg


# ----------------------------------------------------------------- webcam
def _detector_de_rostos():
    """Carrega o detector local opcional usado para contar rostos no clipe."""
    try:
        import cv2
        modelo = os.path.join(
            os.path.dirname(BASE), "modelos", "rosto",
            "face_detection_yunet_2023mar.onnx",
        )
        if not os.path.isfile(modelo) or not hasattr(cv2, "FaceDetectorYN_create"):
            return None
        return cv2.FaceDetectorYN_create(modelo, "", (320, 320), 0.7, 0.3, 500)
    except Exception as exc:
        log(f"Detecção facial indisponível ({type(exc).__name__})")
        return None


def _perfil_facial_local():
    """Carrega o vetor local cadastrado sem ler ou guardar imagens."""
    try:
        import numpy as np
        caminho = os.path.join(os.path.dirname(BASE), "dados", "rosto.json")
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        vetor = np.asarray(dados["embedding"], dtype=np.float32).reshape(-1)
        norma = float(np.linalg.norm(vetor))
        if norma <= 1e-8:
            return None, ""
        return vetor / norma, str(dados.get("nome", "usuario"))
    except (OSError, ValueError, KeyError, TypeError):
        return None, ""


def gravar_webcam(segundos, indice_camera, analisar_rostos=False,
                  reconhecer_usuario=False, limiar_rosto=0.363):
    """Grava N segundos e analisa rostos localmente, quando configurado.

    O retorno normal continua sendo o caminho do vídeo. Com análise ativada,
    retorna ``(caminho, maior_numero_rostos, usuario_confirmado)``.
    """
    try:
        import cv2
    except ImportError:
        log("AVISO: opencv nao instalado; rode setup_seguranca.bat")
        return None

    os.makedirs(GRAVACOES, exist_ok=True)
    nome = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".mp4"
    caminho = os.path.join(GRAVACOES, nome)

    # CAP_DSHOW e bem mais confiavel que o backend padrao no Windows.
    cap = cv2.VideoCapture(indice_camera, cv2.CAP_DSHOW)
    if not cap.isOpened():
        log(f"AVISO: webcam (indice {indice_camera}) nao abriu")
        cap.release()
        return None

    largura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    altura = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

    # Descarta os primeiros quadros: webcam leva um instante para expor direito.
    for _ in range(5):
        cap.read()

    quadros = []
    detector = _detector_de_rostos() if analisar_rostos else None
    reconhecedor = None
    perfil, _ = _perfil_facial_local() if reconhecer_usuario else (None, "")
    if detector is not None and perfil is not None:
        try:
            import cv2
            modelo = os.path.join(
                os.path.dirname(BASE), "modelos", "rosto",
                "face_recognition_sface_2021dec.onnx",
            )
            if os.path.isfile(modelo) and hasattr(cv2, "FaceRecognizerSF_create"):
                reconhecedor = cv2.FaceRecognizerSF_create(modelo, "")
        except Exception as exc:
            log(f"Reconhecimento facial indisponível ({type(exc).__name__})")
    maior_numero_rostos = 0
    acertos_usuario = 0
    usuario_confirmado = False
    inicio = time.time()
    while time.time() - inicio < segundos:
        ok, frame = cap.read()
        if not ok:
            break
        quadros.append(frame)
        if detector is not None:
            try:
                altura, largura = frame.shape[:2]
                detector.setInputSize((largura, altura))
                _, rostos = detector.detect(frame)
                quantidade = 0 if rostos is None else len(rostos)
                maior_numero_rostos = max(maior_numero_rostos, quantidade)
                if reconhecedor is not None and rostos is not None and len(rostos):
                    principal = max(rostos, key=lambda rosto: float(rosto[2] * rosto[3]))
                    alinhado = reconhecedor.alignCrop(frame, principal)
                    caracteristica = reconhecedor.feature(alinhado).reshape(-1)
                    import numpy as np
                    norma = float(np.linalg.norm(caracteristica))
                    if norma > 1e-8:
                        score = float(np.dot(caracteristica / norma, perfil))
                        if score >= float(limiar_rosto):
                            acertos_usuario += 1
                            if acertos_usuario >= 3:
                                usuario_confirmado = True
            except Exception:
                # A gravação não deve falhar só porque o modelo facial falhou.
                detector = None
    duracao = time.time() - inicio
    cap.release()

    if not quadros:
        log("AVISO: webcam abriu mas nao entregou nenhum quadro")
        return None

    # FPS real medido, para o video nao sair acelerado nem lento.
    fps = max(1.0, len(quadros) / duracao if duracao > 0 else 15.0)
    escritor = cv2.VideoWriter(caminho, cv2.VideoWriter_fourcc(*"mp4v"),
                               fps, (largura, altura))
    for frame in quadros:
        escritor.write(frame)
    escritor.release()
    log(f"Gravado: {nome} ({len(quadros)} quadros, {duracao:.1f}s, {fps:.1f} fps)")
    if analisar_rostos:
        log(f"Maior número de rostos no clipe: {maior_numero_rostos}")
        if reconhecer_usuario and perfil is not None:
            log("Rosto do operador confirmado" if usuario_confirmado
                else "Rosto do operador não confirmado")
        return caminho, maior_numero_rostos, usuario_confirmado
    return caminho


# --------------------------------------------------------------- telegram
def enviar_telegram(cfg, texto, caminho_video=None):
    import requests
    token = cfg["telegram_token"]
    chat_id = cfg["telegram_chat_id"]
    try:
        if caminho_video and os.path.exists(caminho_video):
            url = f"https://api.telegram.org/bot{token}/sendVideo"
            with open(caminho_video, "rb") as video:
                resp = requests.post(url, data={"chat_id": chat_id, "caption": texto},
                                     files={"video": video}, timeout=180)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            resp = requests.post(url, data={"chat_id": chat_id, "text": texto}, timeout=60)
        if resp.status_code == 200:
            log("Telegram: enviado")
            return True
        log(f"Telegram: falhou (HTTP {resp.status_code})")
    except Exception:
        # Não registrar exceções de requests: elas podem incluir o token na URL.
        log("Telegram: falha de conexão")
    return False


def enviar_drive(cfg, caminho_video):
    """Envia o vídeo ao Drive sem impedir o alerta do Telegram."""
    if not caminho_video or not cfg.get("google_drive", {}).get("ativado", True):
        return False
    try:
        from google_drive_upload import upload_video

        pasta = cfg.get("google_drive", {}).get("pasta", "JARVIS - Segurança")
        arquivo = upload_video(caminho_video, pasta=pasta)
        log(f"Google Drive: enviado {arquivo.get('name', 'vídeo')}")
        if cfg.get("google_drive", {}).get("apagar_local_apos_upload", False):
            try:
                os.remove(caminho_video)
                log("Cópia local apagada após confirmação do upload")
            except OSError as exc:
                log(f"Drive enviado, mas não consegui apagar a cópia local ({type(exc).__name__})")
        return True
    except Exception as exc:
        # Não registrar a exceção completa: ela pode conter dados de autenticação.
        log(f"Google Drive: não enviado ({type(exc).__name__})")
        return False


# ----------------------------------------------------------------- alerta
def disparar_alerta(cfg):
    """Abre a tela vermelha e fala o aviso, sem travar a gravacao."""
    if not cfg.get("alerta_na_tela", True):
        return
    texto = cfg.get("texto_do_alerta",
                    "O responsável foi comunicado da invasão, "
                    "e voce esta sendo gravado.")
    segundos = cfg.get("segundos_do_alerta", 20)
    script = os.path.join(BASE, "alerta_invasor.py")
    try:
        subprocess.Popen([sys.executable, script, texto, str(segundos)])
        log("Alerta na tela + aviso falado disparados")
    except Exception as exc:
        log(f"Falha ao disparar o alerta: {exc}")


# ---------------------------------------------------------------- sensor
def eventos_serial(cfg):
    """Gera uma vez por transicao do PIR lida pela porta serial."""
    import serial
    porta = cfg.get("porta_serial", "COM7")
    log(f"Ouvindo o PIR pela serial {porta}...")
    anterior = None
    with serial.Serial(porta, 115200, timeout=1) as ser:
        while True:
            linha = ser.readline()
            if not linha:
                continue
            texto = linha.decode("utf-8", errors="replace").strip()
            if "PIR" not in texto:
                continue
            atual = "MOVIMENTO" in texto and "SEM MOVIMENTO" not in texto
            if anterior is not None and atual != anterior:
                yield atual
            anterior = atual


def eventos_http(cfg):
    """Gera uma vez por transicao de ``motion`` lido de ``/status``.

    A primeira leitura apenas estabelece a referencia. Isso evita um alerta
    falso logo apos ligar a placa enquanto o PIR ainda esta estabilizando.
    """
    import requests
    ip = cfg.get("ip_da_placa", "")
    if not ip:
        log("ERRO: modo http exige 'ip_da_placa' no config.json")
        sys.exit(1)
    url = f"http://{ip}/status"
    log(f"Ouvindo o PIR por {url} ...")
    anterior = None
    while True:
        try:
            dados = requests.get(url, timeout=4).json()
            atual = bool(dados.get("motion"))
            if anterior is not None and atual != anterior:
                yield atual
            anterior = atual
        except Exception as exc:
            log(f"Falha ao consultar a placa: {exc}")
            time.sleep(5)
        time.sleep(1)


# ------------------------------------------------------------------ main
def main():
    cfg = carregar_config()
    import threading
    parar = threading.Event()
    if cfg.get("_telegram_configurado"):
        from telegram_control import ouvir_comandos
        threading.Thread(target=ouvir_comandos, args=(cfg, parar),
                         name="telegram-comandos", daemon=True).start()
        log("Comandos Telegram ativos (somente chat privado autorizado)")
    else:
        log("Telegram desativado; vigilância seguirá com tela, gravação e Drive")
    modo = cfg.get("modo", "serial")
    cooldown = int(cfg.get("cooldown_segundos", 60))
    duracao = int(cfg.get("segundos_gravacao", 10))
    camera = int(cfg.get("indice_camera", 0))
    analisar_rostos = bool(cfg.get("detectar_outra_pessoa", True))
    reconhecer_usuario = bool(cfg.get("reconhecer_usuario", True))
    limiar_rosto = float(cfg.get("limiar_rosto", 0.363))

    log("=" * 50)
    log(f"JARVIS vigilancia iniciada (modo={modo}, gravacao={duracao}s, "
        f"cooldown={cooldown}s)")
    if cfg.get("_telegram_configurado"):
        enviar_telegram(cfg, "JARVIS: vigilancia ligada e monitorando.")

    fonte = eventos_serial(cfg) if modo == "serial" else eventos_http(cfg)
    ultimo_alerta = 0.0

    for movimento in fonte:
        agora = time.time()
        hora = datetime.datetime.now().strftime("%H:%M:%S")
        if not movimento:
            log(f"PIR voltou ao repouso as {hora}")
            if cfg.get("_telegram_configurado"):
                enviar_telegram(cfg, f"JARVIS: sensor voltou ao repouso as {hora}.")
            continue
        if agora - ultimo_alerta < cooldown:
            continue  # evita varias gravacoes durante o mesmo episodio
        ultimo_alerta = agora
        log(f"MOVIMENTO detectado as {hora}")
        gravacao = gravar_webcam(
            duracao, camera, analisar_rostos=analisar_rostos,
            reconhecer_usuario=reconhecer_usuario, limiar_rosto=limiar_rosto,
        )
        if isinstance(gravacao, tuple):
            video, quantidade_rostos, usuario_confirmado = gravacao
        else:
            video, quantidade_rostos, usuario_confirmado = gravacao, 0, False
        if video:
            outra_pessoa = quantidade_rostos >= 2
            presenca_confirmada = usuario_confirmado and not outra_pessoa
            if not presenca_confirmada:
                disparar_alerta(cfg)
            else:
                log("Presença do operador confirmada; alerta visual não disparado")
            if outra_pessoa:
                log("Duas ou mais pessoas detectadas no clipe")
            legenda = f"JARVIS: movimento detectado as {hora}"
            if outra_pessoa:
                legenda += "; outra pessoa detectada no quarto"
            elif usuario_confirmado:
                legenda += "; usuário autorizado confirmado pela câmera"
            else:
                legenda += "; rosto não confirmado"
            if cfg.get("_telegram_configurado"):
                enviar_telegram(cfg, legenda, video)
            enviar_drive(cfg, video)
        else:
            disparar_alerta(cfg)
            if cfg.get("_telegram_configurado"):
                enviar_telegram(cfg, f"JARVIS: movimento detectado as {hora} "
                                 "(webcam indisponivel, sem video)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Encerrado pelo usuario.")
    except Exception as exc:
        log(f"ERRO FATAL: {exc}")
        raise
