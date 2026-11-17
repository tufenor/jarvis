"""JARVIS - suspensao inteligente do PC.

Diferente do timer do Windows, que so olha se voce mexeu no mouse, este
guardiao so deixa o PC dormir quando NADA importante esta acontecendo:

  1. voce nao mexe no PC ha X minutos          E
  2. a CPU esta abaixo do limite               E
  3. nenhum programa da lista protegida roda   E
  4. nao ha download/upload acontecendo        E
  5. nada no Windows esta pedindo para ficar acordado (players, jogos)
                                                E
  6. o arquivo NAO_SUSPENDER.txt nao existe

Basta UMA dessas condicoes falhar para ele nao suspender.

Uso:  .venv\\Scripts\\python.exe dormir_inteligente.py
"""
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config_sono.json")
TRAVA_PATH = os.path.join(BASE, "NAO_SUSPENDER.txt")
LOG_PATH = os.path.join(BASE, "dormir_inteligente.log")

PADRAO = {
    "minutos_sem_mexer": 20,
    "limite_cpu_porcento": 20,
    "limite_rede_kbps": 150,
    "minutos_de_calmaria": 5,
    "processos_protegidos": [
        "ffmpeg.exe", "handbrake.exe", "blender.exe", "obs64.exe",
        "7zg.exe", "winrar.exe", "qbittorrent.exe",
        "python.exe", "node.exe", "java.exe",
        "vlc.exe", "mpc-hc64.exe", "steam.exe"
    ],
    "respeitar_pedidos_do_windows": True,
    "intervalo_checagem_segundos": 30
}


def log(msg):
    linha = f"[{datetime.datetime.now():%d/%m %H:%M:%S}] {msg}"
    print(linha, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception:
        pass


def carregar_config():
    cfg = dict(PADRAO)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items()
                            if not k.startswith("_")})
        except Exception as exc:
            log(f"config_sono.json com problema, usando padrao: {exc}")
    else:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(PADRAO, f, indent=2, ensure_ascii=False)
            log("config_sono.json criado com os valores padrao")
        except Exception:
            pass
    return cfg


# ------------------------------------------------------------ verificacoes
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def minutos_sem_mexer():
    """Ha quanto tempo ninguem toca no mouse ou no teclado."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    agora = ctypes.windll.kernel32.GetTickCount()
    return max(0.0, (agora - info.dwTime) / 1000.0 / 60.0)


def processos_rodando(lista):
    """Devolve os programas protegidos que estao abertos agora."""
    import psutil
    alvos = {n.lower() for n in lista}
    encontrados = set()
    for proc in psutil.process_iter(["name"]):
        try:
            nome = (proc.info.get("name") or "").lower()
            if nome in alvos:
                encontrados.add(nome)
        except Exception:
            continue
    return sorted(encontrados)


def pedidos_do_windows():
    """Le 'powercfg /requests': o proprio Windows sabe quem pede para ficar acordado.

    Players de video, jogos e downloads registram esse pedido. Precisa de
    permissao de administrador; sem ela, a checagem e simplesmente ignorada.
    """
    try:
        r = subprocess.run(["powercfg", "/requests"], capture_output=True,
                           text=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        return None
    if r.returncode != 0:
        return None
    saida = (r.stdout or "")
    if "privil" in saida.lower() or "administrator" in saida.lower():
        return None  # rodando sem admin

    pedidos = []
    categoria = None
    for linha in saida.splitlines():
        crua = linha.strip()
        if not crua:
            continue
        if crua.endswith(":") and crua.upper() == crua:
            categoria = crua.rstrip(":")
            continue
        if crua.lower().startswith("nenhum") or crua.lower() == "none.":
            continue
        if categoria in ("DISPLAY", "SYSTEM", "AWAYMODE", "EXECUTION"):
            pedidos.append(f"{categoria}: {crua[:60]}")
    return pedidos


def suspender():
    """Suspende de verdade (nao hiberna). Exige 'powercfg -h off' feito antes."""
    ctypes.windll.powrprof.SetSuspendState(0, 1, 0)


# ------------------------------------------------------------------- main
def main():
    cfg = carregar_config()
    import psutil

    log("=" * 56)
    log("Guardiao do sono iniciado")
    log(f"  suspende apos {cfg['minutos_sem_mexer']} min sem mexer,")
    log(f"  com CPU abaixo de {cfg['limite_cpu_porcento']}% e rede abaixo de "
        f"{cfg['limite_rede_kbps']} kbps")
    log(f"  por {cfg['minutos_de_calmaria']} minutos seguidos")
    log("  Para travar a suspensao: crie o arquivo NAO_SUSPENDER.txt nesta pasta")
    log("=" * 56)

    intervalo = cfg["intervalo_checagem_segundos"]
    preciso_de = max(1, int(cfg["minutos_de_calmaria"] * 60 / intervalo))
    calmaria = 0
    ultimo_motivo = ""
    rede_antes = psutil.net_io_counters()
    marco = time.time()

    while True:
        time.sleep(intervalo)

        # --- rede: quanto passou desde a ultima volta
        rede_agora = psutil.net_io_counters()
        decorrido = max(0.001, time.time() - marco)
        bytes_passados = ((rede_agora.bytes_sent - rede_antes.bytes_sent) +
                          (rede_agora.bytes_recv - rede_antes.bytes_recv))
        kbps = (bytes_passados * 8 / 1000.0) / decorrido
        rede_antes, marco = rede_agora, time.time()

        cpu = psutil.cpu_percent(interval=1)
        parado = minutos_sem_mexer()

        motivo = None
        if os.path.exists(TRAVA_PATH):
            motivo = "NAO_SUSPENDER.txt existe (travado por voce)"
        elif parado < cfg["minutos_sem_mexer"]:
            motivo = f"voce mexeu ha {parado:.1f} min"
        elif cpu > cfg["limite_cpu_porcento"]:
            motivo = f"CPU em {cpu:.0f}% (limite {cfg['limite_cpu_porcento']}%)"
        elif kbps > cfg["limite_rede_kbps"]:
            motivo = f"rede em {kbps:.0f} kbps (limite {cfg['limite_rede_kbps']})"
        else:
            abertos = processos_rodando(cfg["processos_protegidos"])
            if abertos:
                motivo = "programa protegido aberto: " + ", ".join(abertos)
            elif cfg.get("respeitar_pedidos_do_windows", True):
                pedidos = pedidos_do_windows()
                if pedidos:
                    motivo = "o Windows pede para ficar acordado -> " + pedidos[0]

        if motivo:
            if motivo != ultimo_motivo:
                log(f"Nao vou suspender: {motivo}")
                ultimo_motivo = motivo
            calmaria = 0
            continue

        calmaria += 1
        ultimo_motivo = ""
        restante = (preciso_de - calmaria) * intervalo / 60.0
        if calmaria < preciso_de:
            log(f"Tudo calmo. Suspendo em {restante:.1f} min se continuar assim.")
            continue

        log("Tudo calmo pelo tempo necessario. SUSPENDENDO AGORA.")
        try:
            suspender()
        except Exception as exc:
            log(f"Falha ao suspender: {exc}")
        # Ao acordar, o loop continua daqui. Zera para nao dormir de novo na hora.
        time.sleep(60)
        calmaria = 0
        rede_antes = psutil.net_io_counters()
        marco = time.time()
        log("PC acordou. Guardiao continua vigiando.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Guardiao encerrado por voce.")
    except Exception as exc:
        log(f"ERRO FATAL: {exc}")
        raise
