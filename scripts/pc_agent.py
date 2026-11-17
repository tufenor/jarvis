"""Authenticated, LAN-only Windows power endpoint for the JARVIS ESP32."""
import argparse
import getpass
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULT_NETWORK = "192.168.50.0/24"
DEFAULT_PORT = 8765
SHUTDOWN_COMMAND = [
    os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "shutdown.exe"),
    "/s", "/t", "30", "/c", "JARVIS: desligamento solicitado pelo usuario",
]


def default_config_path():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / "JARVIS" / "pc_agent.json"


def _run_command(arguments):
    return subprocess.run(arguments, shell=False, check=False,
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL).returncode


def _suspend():
    """Suspende o Windows sem hibernar.

    O primeiro argumento 0 pede suspensao, nao hibernacao. Para valer, a
    hibernacao precisa estar desligada antes ("powercfg -h off"), senao o
    Windows hiberna assim mesmo - e de hibernacao a placa Wi-Fi fica sem
    energia e o Wake-on-LAN nunca chega.
    """
    import ctypes
    if not ctypes.windll.powrprof.SetSuspendState(0, 1, 0):
        raise OSError("O Windows recusou a suspensao")


def _jarvis_rodando(porta=8080):
    """O servidor do JARVIS esta no ar? Checa pelo /api/saude em localhost."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/saude", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def _parar_jarvis():
    """Mata qualquer processo `-m jarvis` do venv local."""
    if os.name != "nt":
        return False, "so suportado no Windows"
    raiz = Path(__file__).resolve().parents[1]
    venv = str((raiz / ".venv" / "Scripts").resolve()).lower()
    try:
        import ctypes
    except ImportError:
        pass
    try:
        # Lista processos usando WMI pelo CommandLine; mata quem casar.
        resultado = subprocess.run(
            ["wmic", "process", "where",
             "name='python.exe' or name='pythonw.exe'",
             "get", "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, check=False,
        )
        mortos = 0
        for linha in resultado.stdout.splitlines():
            if "-m" not in linha or "jarvis" not in linha.lower():
                continue
            if venv not in linha.lower():
                continue
            pid = linha.strip().split(",")[-1]
            if pid.isdigit():
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False)
                mortos += 1
        return (mortos > 0, None if mortos > 0 else "nenhum processo")
    except OSError as exc:
        return False, str(exc)


def _iniciar_jarvis():
    """Inicia `python -m jarvis --servidor` oculto; nao espera o processo."""
    raiz = Path(__file__).resolve().parents[1]
    venv_python = raiz / ".venv" / "Scripts" / "pythonw.exe"
    python = venv_python if venv_python.exists() else (
        raiz / ".venv" / "Scripts" / "python.exe"
    )
    if not python.exists():
        return False, "python do venv nao encontrado"
    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [str(python), "-m", "jarvis", "--servidor"],
            cwd=str(raiz),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=creationflags,
        )
        return True, None
    except OSError as exc:
        return False, str(exc)


def _rede_aceita(rede):
    return rede.is_private or rede.subnet_of(ipaddress.ip_network("100.64.0.0/10"))


def _normalizar_redes(valor):
    """Aceita string unica, lista, ou o alias antigo `allowed_network`."""
    if isinstance(valor, (list, tuple)):
        itens = [str(v) for v in valor]
    else:
        itens = [str(valor)]
    redes = []
    for item in itens:
        rede = ipaddress.ip_network(item, strict=False)
        if rede.version != 4 or not _rede_aceita(rede) or rede.prefixlen < 10:
            raise ValueError(
                "allowed_networks exige IPv4 privado ou Tailscale (100.64/10) /10 ou menor"
            )
        redes.append(rede)
    if not redes:
        raise ValueError("allowed_networks vazio")
    return redes


def process_action(action, authorization, expected_digest, allowed_network,
                   client_ip, confirmation, pending, run_command=_run_command,
                   suspend=_suspend, jarvis_rodando=_jarvis_rodando,
                   iniciar_jarvis=_iniciar_jarvis, parar_jarvis=_parar_jarvis):
    """Validate a fixed power action and return (HTTP status, JSON, pending).

    `allowed_network` aceita string (CIDR), lista de CIDRs ou uma rede ja
    construida. Tailscale (100.64.0.0/10) e tratada como privada aqui.
    """
    if action not in ("shutdown", "cancel", "sleep", "start_jarvis", "stop_jarvis"):
        return 404, {"error": "Rota inexistente"}, pending
    if not isinstance(expected_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
        return 503, {"error": "Agente nao configurado"}, pending
    scheme, separator, supplied = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not separator or not re.fullmatch(r"[0-9a-fA-F]{32}", supplied):
        return 401, {"error": "Token invalido"}, pending
    supplied_digest = hashlib.sha256(supplied.encode("ascii")).hexdigest()
    if not hmac.compare_digest(supplied_digest, expected_digest):
        return 401, {"error": "Token invalido"}, pending
    try:
        if isinstance(allowed_network, (list, tuple)):
            redes = [ipaddress.ip_network(str(r), strict=False) for r in allowed_network]
        elif hasattr(allowed_network, "network_address"):
            redes = [allowed_network]
        else:
            redes = [ipaddress.ip_network(str(allowed_network), strict=False)]
        address = ipaddress.ip_address(client_ip)
    except (TypeError, ValueError):
        return 503, {"error": "Rede permitida invalida"}, pending
    if address.version != 4 or not any(address in r and _rede_aceita(r) for r in redes):
        return 403, {"error": "Origem fora da rede permitida"}, pending

    if action == "shutdown":
        if confirmation != "SHUTDOWN":
            return 400, {"error": "Confirmacao necessaria"}, pending
        if pending:
            return 409, {"error": "Desligamento ja agendado"}, pending
        arguments = SHUTDOWN_COMMAND[:]
        try:
            result = run_command(arguments)
        except OSError:
            return 503, {"error": "Nao foi possivel iniciar o desligamento"}, pending
        if result != 0:
            return 503, {"error": "Windows recusou o desligamento"}, pending
        return 202, {"status": "scheduled", "delay_seconds": 30}, True

    if action == "start_jarvis":
        # Confirmacao exigida para evitar start acidental, igual as outras acoes.
        if confirmation != "START":
            return 400, {"error": "Confirmacao necessaria"}, pending
        if jarvis_rodando():
            return 200, {"status": "already_running"}, pending
        ok, motivo = iniciar_jarvis()
        if not ok:
            return 503, {"error": f"Falhou ao iniciar: {motivo}"}, pending
        return 202, {"status": "starting"}, pending

    if action == "stop_jarvis":
        if confirmation != "STOP":
            return 400, {"error": "Confirmacao necessaria"}, pending
        ok, motivo = parar_jarvis()
        if not ok:
            return 200, {"status": "already_stopped", "detail": motivo}, pending
        return 202, {"status": "stopping"}, pending

    if action == "sleep":
        if confirmation != "SLEEP":
            return 400, {"error": "Confirmacao necessaria"}, pending
        # Suspender nao agenda nada, entao nao mexe em 'pending': o que o
        # /cancel cancela continua sendo apenas o desligamento com atraso.
        try:
            suspend()
        except OSError:
            return 503, {"error": "Nao foi possivel suspender"}, pending
        return 202, {"status": "suspending"}, pending

    if confirmation != "CANCEL":
        return 400, {"error": "Confirmacao necessaria"}, pending
    try:
        result = run_command([SHUTDOWN_COMMAND[0], "/a"])
    except OSError:
        return 503, {"error": "Nao foi possivel cancelar"}, pending
    if result != 0:
        if not pending:
            return 409, {"error": "Nenhum desligamento pendente no Windows"}, pending
        return 503, {"error": "Windows nao cancelou o desligamento"}, pending
    return 200, {"status": "cancelled"}, False


def load_config(path):
    with open(path, "r", encoding="utf-8") as source:
        config = json.load(source)
    # Aceita tanto allowed_networks (lista) quanto allowed_network (string, legado).
    bruto = config.get("allowed_networks")
    if bruto is None:
        bruto = config.get("allowed_network", "")
    redes = _normalizar_redes(bruto)
    digest = config.get("token_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("token_sha256 invalido")
    port = config.get("port", DEFAULT_PORT)
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("porta invalida")
    return {"allowed_networks": [str(r) for r in redes],
            "token_sha256": digest, "port": port}


def configure(path):
    print("Configuração local do agente JARVIS (o token não será exibido nem salvo em texto simples).")
    token = getpass.getpass("Token de 32 caracteres hex usado no painel ESP32: ").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", token):
        raise ValueError("O token precisa ter exatamente 32 caracteres hexadecimais.")
    confirmation = getpass.getpass("Repita o token: ").strip()
    if not hmac.compare_digest(token.lower(), confirmation.lower()):
        raise ValueError("Os tokens não coincidem.")
    cidr = input("Rede local da ESP32 [192.168.50.0/24]: ").strip() or DEFAULT_NETWORK
    network = ipaddress.ip_network(cidr, strict=False)
    if network.version != 4 or not network.is_private or network.prefixlen < 16:
        raise ValueError("Use a rede IPv4 privada exata (por exemplo 192.168.50.0/24).")
    config = {
        "token_sha256": hashlib.sha256(token.lower().encode("ascii")).hexdigest(),
        "allowed_network": str(network),
        "port": DEFAULT_PORT,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as destination:
        json.dump(config, destination, indent=2)
    if os.name != "nt":
        path.chmod(0o600)
    print("Configuração salva em:", path)
    print("Foi salvo somente o hash SHA-256 do token.")


class AgentHandler(BaseHTTPRequestHandler):
    server_version = "JARVIS-PC/1.0"
    sys_version = ""

    def log_message(self, _format, *_args):
        return

    def _reply(self, status, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _redes(self):
        bruto = (self.server.config.get("allowed_networks")
                 or self.server.config.get("allowed_network", ""))
        if isinstance(bruto, (list, tuple)):
            return [ipaddress.ip_network(str(r)) for r in bruto]
        return [ipaddress.ip_network(str(bruto))]

    def do_GET(self):
        if self.path != "/health":
            self._reply(404, {"error": "Rota inexistente"})
            return
        try:
            address = ipaddress.ip_address(self.client_address[0])
            redes = self._redes()
        except ValueError:
            self._reply(403, {"error": "Origem nao permitida"})
            return
        if not any(address in r for r in redes):
            self._reply(403, {"error": "Origem fora da rede permitida"})
            return
        self._reply(200, {"name": "JARVIS PC agent", "status": "ready",
                          "shutdown_pending": self.server.pending})

    def do_POST(self):
        actions = {"/shutdown": ("shutdown", "SHUTDOWN"),
                   "/cancel": ("cancel", "CANCEL"),
                   "/sleep": ("sleep", "SLEEP"),
                   "/start_jarvis": ("start_jarvis", "START"),
                   "/stop_jarvis": ("stop_jarvis", "STOP")}
        if self.path not in actions:
            self._reply(404, {"error": "Rota inexistente"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, {"error": "Corpo invalido"})
            return
        if length > 32 or length < 0:
            self._reply(413, {"error": "Corpo excede o limite"})
            return
        body = self.rfile.read(length).decode("ascii", "ignore")
        action, expected_confirmation = actions[self.path]
        with self.server.action_lock:
            status, payload, pending = process_action(
                action=action,
                authorization=self.headers.get("Authorization", ""),
                expected_digest=self.server.config["token_sha256"],
                allowed_network=(self.server.config.get("allowed_networks")
                                 or self.server.config.get("allowed_network")),
                client_ip=self.client_address[0],
                confirmation=body[8:] if body.startswith("confirm=") else "",
                pending=self.server.pending,
                run_command=self.server.run_command,
            )
            self.server.pending = pending
        self._reply(status, payload)


def _heartbeat_rele(config, parar):
    """Posta a cada 15 s no rele Hostinger: 'estou vivo'.

    O relay_url e o relay_token vem do config. Sem eles a thread sai na calada.
    Serve pro app no celular perguntar ao rele (sem Tailscale, sem LAN) se o PC
    ja subiu, depois do WoL.
    """
    url = config.get("relay_url")
    token = config.get("relay_token")
    if not url or not token:
        return
    try:
        import urllib.request
    except ImportError:
        return
    while not parar.is_set():
        try:
            pedido = urllib.request.Request(
                url, method="POST",
                headers={"X-Jarvis-Token": token, "Content-Length": "0"},
                data=b"",
            )
            urllib.request.urlopen(pedido, timeout=10).close()
        except Exception as exc:
            # Rele fora do ar nao pode derrubar o pc_agent; segue a vida.
            print("Heartbeat rele falhou:", exc)
        parar.wait(15)


def serve(config):
    server = ThreadingHTTPServer(("0.0.0.0", config["port"]), AgentHandler)
    server.daemon_threads = True
    server.config = config
    server.pending = False
    server.action_lock = threading.Lock()
    server.run_command = _run_command
    redes = (config.get("allowed_networks") or [config.get("allowed_network", "")])
    print("Agente JARVIS disponível apenas para as redes configuradas:",
          ", ".join(map(str, redes)), "porta", config["port"])
    print("Health check: http://<IP-do-PC>:%d/health" % config["port"])
    parar_heartbeat = threading.Event()
    threading.Thread(
        target=_heartbeat_rele, args=(config, parar_heartbeat),
        name="heartbeat-rele", daemon=True,
    ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAgente encerrado.")
    finally:
        parar_heartbeat.set()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true", help="cadastrar o token localmente")
    parser.add_argument("--config", type=Path, default=default_config_path())
    args = parser.parse_args()
    try:
        if args.setup:
            configure(args.config)
        else:
            serve(load_config(args.config))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("Agente JARVIS não iniciado: %s. Execute --setup primeiro." % exc)


if __name__ == "__main__":
    main()
