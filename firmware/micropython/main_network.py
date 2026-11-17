"""JARVIS ESP32-S3 - Wi-Fi, Bluetooth, sensores, controle HTTP e Wake-on-LAN.

Novidades desta versao:
  - /acordar-pc  : manda o "pacote magico" que tira o PC da suspensao
  - diagnostico de Wi-Fi detalhado no serial (diz POR QUE nao conectou)
  - reconexao automatica se o Wi-Fi cair

Primeira configuracao do Wi-Fi: use scripts/configurar_wifi.bat pelo cabo USB
(mais facil), ou conecte na rede JARVIS-SETUP e abra http://192.168.4.1
"""
import time
import socket
import network
import machine
import dht

try:
    from lcd_display import JarvisDisplay
except ImportError as exc:
    JarvisDisplay = None
    print("LCD: driver indisponivel", exc)

try:
    import ujson as json
except ImportError:
    import json

try:
    import bluetooth
except ImportError:
    bluetooth = None

SETUP_SSID = "JARVIS-SETUP"
SETUP_PASSWORD = "DEFINA_A_SENHA_DE_SETUP"  # troque no primeiro boot; senha padrao no repositorio e falha de seguranca
CONFIG_FILE = "wifi.json"

# MAC da placa de rede do PC (Intel Wireless-AC 9260), para o Wake-on-LAN.
MAC_DO_PC = "00-00-00-00-00-00"  # preencha com o MAC da sua placa; o real nao vai para o repositorio
REDE_BROADCAST = "192.168.50.255"

# Agente de energia rodando no PC (scripts/pc_agent.py).
IP_DO_PC = "192.168.50.10"
PORTA_DO_AGENTE = 8765
TOKEN_DO_AGENTE = "DEFINA_SEU_TOKEN"

# GPIO20/19 pertencem a USB nativa desta ESP32-S3; use GPIO4 para o LED externo.
external_led = machine.Pin(4, machine.Pin.OUT, value=0)
dht_sensor = dht.DHT11(machine.Pin(6))
pir_sensor = machine.Pin(7, machine.Pin.IN)
display = JarvisDisplay() if JarvisDisplay is not None else None

led_manual = False
temperature = None
humidity = None


# ------------------------------------------------------------------ wi-fi
def load_wifi():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_wifi(ssid, password):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"ssid": ssid, "password": password}, f)


def explicar_status(sta):
    """Traduz o codigo de status do Wi-Fi para algo legivel no serial."""
    try:
        codigo = sta.status()
    except Exception:
        return "status indisponivel"
    mapa = {
        network.STAT_IDLE: "parado (nao tentou ainda)",
        network.STAT_CONNECTING: "tentando conectar",
        network.STAT_GOT_IP: "conectado, com IP",
    }
    # Os codigos de erro variam entre builds; tratados um a um quando existirem.
    for nome, texto in (("STAT_WRONG_PASSWORD", "SENHA INCORRETA"),
                        ("STAT_NO_AP_FOUND", "REDE NAO ENCONTRADA (nome errado ou fora de alcance)"),
                        ("STAT_ASSOC_FAIL", "o roteador recusou a associacao"),
                        ("STAT_HANDSHAKE_TIMEOUT", "tempo esgotado na negociacao de senha")):
        valor = getattr(network, nome, None)
        if valor is not None:
            mapa[valor] = texto
    return mapa.get(codigo, "codigo desconhecido: %s" % codigo)


def listar_redes(sta):
    """Mostra as redes visiveis - ajuda a ver se a rede de casa aparece."""
    try:
        print("WIFI: redes visiveis daqui:")
        for rede in sta.scan():
            nome = rede[0].decode("utf-8", "replace")
            forca = rede[3]
            if nome:
                print("   - %-28s sinal %s dBm" % (nome, forca))
    except Exception as exc:
        print("WIFI: nao consegui escanear:", exc)


def start_wifi():
    cfg = load_wifi()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)

    if not cfg.get("ssid"):
        print("WIFI: nenhuma rede salva em", CONFIG_FILE)
        listar_redes(sta)
    else:
        print("WIFI: tentando conectar em", cfg["ssid"])
        sta.connect(cfg["ssid"], cfg.get("password", ""))
        for _ in range(30):
            if sta.isconnected():
                print("WIFI: CONECTADO - IP", sta.ifconfig()[0])
                return sta, True
            time.sleep(0.4)
        print("WIFI: NAO conectou. Motivo:", explicar_status(sta))
        listar_redes(sta)

    # Sem conexao: sobe a rede de configuracao.
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(ssid=SETUP_SSID, password=SETUP_PASSWORD,
                  authmode=network.AUTH_WPA2_PSK)
    except Exception as exc:
        print("WIFI SETUP: configuracao protegida falhou", exc)
        ap.config(ssid=SETUP_SSID, password=SETUP_PASSWORD)
    print("WIFI SETUP: conecte na rede", SETUP_SSID, "senha", SETUP_PASSWORD)
    print("WIFI SETUP: depois abra http://192.168.4.1")
    return ap, False


def start_bluetooth():
    if bluetooth is None:
        print("BLUETOOTH: modulo indisponivel")
        return False
    try:
        ble = bluetooth.BLE()
        ble.active(True)
        nome = b"JARVIS-ESP32"
        adv = bytearray(b"\x02\x01\x06") + bytearray((len(nome) + 1, 0x09)) + nome
        ble.gap_advertise(100000, adv_data=adv)
        print("BLUETOOTH: anunciando JARVIS-ESP32")
        return True
    except Exception as exc:
        print("BLUETOOTH: erro", exc)
        return False


# ----------------------------------------------------------- wake-on-lan
def montar_pacote_magico(mac_texto):
    """6 bytes 0xFF seguidos do MAC repetido 16 vezes - padrao Wake-on-LAN."""
    limpo = mac_texto.replace("-", "").replace(":", "").replace(" ", "")
    if len(limpo) != 12:
        raise ValueError("MAC invalido: " + mac_texto)
    mac = bytes(int(limpo[i:i + 2], 16) for i in range(0, 12, 2))
    return b"\xff" * 6 + mac * 16


def acordar_pc():
    """Envia o pacote magico. Retorna (sucesso, mensagem)."""
    try:
        pacote = montar_pacote_magico(MAC_DO_PC)
    except Exception as exc:
        return False, "MAC mal configurado: %s" % exc

    enviados = 0
    erros = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # SO_BROADCAST: a constante nem sempre existe no MicroPython; 32 e o valor.
        try:
            sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_BROADCAST", 32), 1)
        except Exception:
            pass
        # Manda nas portas e enderecos usuais - placas diferentes escutam em lugares diferentes.
        for destino in (REDE_BROADCAST, "255.255.255.255"):
            for porta in (9, 7):
                try:
                    sock.sendto(pacote, (destino, porta))
                    enviados += 1
                except Exception as exc:
                    erros.append("%s:%s %s" % (destino, porta, exc))
    finally:
        try:
            sock.close()
        except Exception:
            pass

    if enviados:
        print("WOL: pacote magico enviado %dx para %s" % (enviados, MAC_DO_PC))
        return True, "pacote enviado %d vezes" % enviados
    return False, "nenhum envio deu certo: %s" % "; ".join(erros)


def suspender_pc():
    """Pede ao agente do PC que suspenda a maquina.

    Suspensao, nao desligamento: com o PC desligado a placa Wi-Fi fica sem
    energia e o Wake-on-LAN nunca mais consegue acorda-lo. Feito com socket
    cru porque urequests nem sempre esta presente nesta build.
    """
    corpo = "confirm=SLEEP"
    pedido = (
        "POST /sleep HTTP/1.0\r\n"
        "Host: %s:%d\r\n"
        "Authorization: Bearer %s\r\n"
        "Content-Type: application/x-www-form-urlencoded\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n\r\n%s"
    ) % (IP_DO_PC, PORTA_DO_AGENTE, TOKEN_DO_AGENTE, len(corpo), corpo)

    sock = socket.socket()
    try:
        sock.settimeout(6)
        sock.connect((IP_DO_PC, PORTA_DO_AGENTE))
        sock.send(pedido.encode())
        resposta = sock.recv(512).decode()
    except Exception as exc:
        return False, "nao alcancei o agente no PC (%s)" % exc
    finally:
        try:
            sock.close()
        except Exception:
            pass

    primeira = resposta.split("\r\n", 1)[0]
    if " 202" in primeira:
        return True, "PC suspendendo"
    if " 401" in primeira:
        return False, "o agente recusou o token"
    if " 403" in primeira:
        return False, "o agente nao aceita esta origem"
    return False, "resposta inesperada: %s" % primeira


# -------------------------------------------------------------- paginas
def pagina_setup(ip):
    return ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
            "<!doctype html><meta charset=utf-8><title>JARVIS Wi-Fi</title>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<body style='font:18px system-ui;max-width:520px;margin:40px auto;background:#071426;color:#eef'>"
            "<h1>J.A.R.V.I.S.</h1><p>Configure a rede Wi-Fi da placa.</p>"
            "<form method=POST action=/wifi><label>Nome da rede</label><br>"
            "<input name=ssid required style='width:100%;padding:12px'><br><br>"
            "<label>Senha</label><br><input name=password type=password style='width:100%;padding:12px'><br><br>"
            "<button style='padding:12px'>Salvar e reiniciar</button></form>"
            "<p>IP atual: %s</p></body>" % ip)


def pagina_controle(estado, aviso=""):
    led = "LIGADO" if estado["led"] else "DESLIGADO"
    mov = "SIM" if estado["motion"] else "NAO"
    temp = ("%s C" % estado["temperature"]) if estado["temperature"] is not None else "sem leitura"
    umid = ("%s%%" % estado["humidity"]) if estado["humidity"] is not None else "sem leitura"
    bloco_aviso = ("<p style='background:#143d2a;padding:10px;border-radius:8px'>%s</p>" % aviso) if aviso else ""
    return ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n"
            "<!doctype html><meta charset=utf-8><title>JARVIS</title>"
            "<meta name=viewport content='width=device-width,initial-scale=1'>"
            "<body style='font:20px system-ui;max-width:420px;margin:30px auto;background:#071426;color:#eef;text-align:center'>"
            "<h1>J.A.R.V.I.S.</h1>%s"
            "<p>Temperatura: %s &nbsp;|&nbsp; Umidade: %s</p>"
            "<p>Movimento: %s</p><p>LED: <b>%s</b></p>"
            "<p><a href='/led/on' style='display:inline-block;padding:14px 22px;margin:6px;background:#1b7a3d;color:#fff;border-radius:8px;text-decoration:none'>Ligar LED</a>"
            "<a href='/led/off' style='display:inline-block;padding:14px 22px;margin:6px;background:#7a1b1b;color:#fff;border-radius:8px;text-decoration:none'>Desligar LED</a></p>"
            "<p><a href='/acordar-pc' style='display:inline-block;padding:14px 22px;margin:6px;background:#1b4f7a;color:#fff;border-radius:8px;text-decoration:none'>Acordar o PC</a><a href='/dormir-pc' style='display:inline-block;padding:14px 22px;margin:6px;background:#4a3b7a;color:#fff;border-radius:8px;text-decoration:none'>Suspender o PC</a></p>"
            "<p><a href='/status' style='color:#9db4d8;font-size:16px'>status em JSON</a></p>"
            "</body>" % (bloco_aviso, temp, umid, mov, led))


def resposta_texto(texto):
    return "HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nConnection: close\r\n\r\n" + texto


def estado_atual():
    return {
        "led": bool(external_led.value()),
        "motion": bool(pir_sensor.value()),
        "temperature": temperature,
        "humidity": humidity,
        "manual_led": led_manual,
    }


def parse_form(body):
    resultado = {}
    for item in body.split("&"):
        par = item.split("=", 1)
        if len(par) == 2:
            resultado[par[0].replace("+", " ")] = par[1].replace("+", " ")
    return resultado


def atender(server, ip, conectado):
    global led_manual
    try:
        client, _ = server.accept()
    except Exception:
        return
    client.settimeout(1)
    try:
        pedido = client.recv(2048).decode()
        primeira = pedido.split("\r\n", 1)[0]
        partes = primeira.split(" ")
        metodo = partes[0] if partes else ""
        caminho = partes[1] if len(partes) > 1 else "/"

        if metodo == "POST" and caminho == "/wifi":
            corpo = pedido.split("\r\n\r\n", 1)[-1]
            form = parse_form(corpo)
            if form.get("ssid"):
                save_wifi(form["ssid"], form.get("password", ""))
                client.send(resposta_texto("Salvo. Reiniciando JARVIS...").encode())
                client.close()
                time.sleep(1)
                machine.reset()
        elif metodo == "GET" and caminho == "/status":
            client.send(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                         "Connection: close\r\n\r\n" + json.dumps(estado_atual())).encode())
        elif metodo == "GET" and caminho == "/acordar-pc":
            ok, msg = acordar_pc()
            texto = ("PC acordando: " + msg) if ok else ("Falhou: " + msg)
            # Chamado pelo atalho do iPhone: resposta curta em texto e suficiente.
            if "curl" in pedido.lower() or "shortcuts" in pedido.lower():
                client.send(resposta_texto(texto).encode())
            elif conectado:
                client.send(pagina_controle(estado_atual(), texto).encode())
            else:
                client.send(resposta_texto(texto).encode())
        elif metodo == "GET" and caminho == "/dormir-pc":
            ok, msg = suspender_pc()
            texto = ("OK: " + msg) if ok else ("Falhou: " + msg)
            if conectado:
                client.send(pagina_controle(estado_atual(), texto).encode())
            else:
                client.send(resposta_texto(texto).encode())
        elif metodo == "GET" and caminho == "/led/on":
            led_manual = True
            external_led.value(1)
            client.send((pagina_controle(estado_atual()) if conectado
                         else resposta_texto("LED LIGADO")).encode())
        elif metodo == "GET" and caminho == "/led/off":
            led_manual = True
            external_led.value(0)
            client.send((pagina_controle(estado_atual()) if conectado
                         else resposta_texto("LED DESLIGADO")).encode())
        elif metodo == "GET" and caminho == "/led/auto":
            led_manual = False
            client.send(resposta_texto("LED voltou ao modo automatico").encode())
        elif conectado:
            client.send(pagina_controle(estado_atual()).encode())
        else:
            client.send(pagina_setup(ip).encode())
    except Exception as exc:
        print("HTTP erro", exc)
    finally:
        try:
            client.close()
        except Exception:
            pass


# ----------------------------------------------------------------- main
print("=" * 46)
print("JARVIS ESP32-S3 ONLINE")
if display is not None:
    display.abertura()
start_bluetooth()
iface, conectado = start_wifi()
ip = iface.ifconfig()[0]

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 80))
server.listen(1)
server.settimeout(0.15)
print("HTTP: http://" + ip)
if conectado:
    print("CONTROLE: abra http://" + ip + " no celular (mesma rede)")
    print("ACORDAR PC: http://" + ip + "/acordar-pc")
print("=" * 46)

external_led.value(0)
led_state = 0
pir_state = pir_sensor.value()
print("PIR GPIO7 inicial:", "MOVIMENTO" if pir_state else "SEM MOVIMENTO")
if display is not None:
    display.update(temperature, humidity, pir_state, ip if conectado else None)

ultimo_sensor = time.ticks_ms()
ultimo_led = time.ticks_ms()
ultimo_pir = time.ticks_ms()
ultima_checagem_wifi = time.ticks_ms()

# Sem o arquivo local de pareamento, a ponte permanece desligada.
try:
    from alexa_wake import iniciar as iniciar_alexa
    iniciar_alexa(acordar_pc)
except ImportError:
    pass

try:
    import jarvis_relay
except Exception as exc:
    jarvis_relay = None
    print("RELE: modulo indisponivel", exc)

while True:
    atender(server, ip, conectado)
    if jarvis_relay is not None and conectado:
        try:
            jarvis_relay.tick(network.WLAN(network.STA_IF), MAC_DO_PC, REDE_BROADCAST)
        except Exception as exc:
            print("RELE: erro no tick", exc)

    if not led_manual and time.ticks_diff(time.ticks_ms(), ultimo_led) >= 1000:
        led_state = 0 if led_state else 1
        external_led.value(led_state)
        print("LED GPIO4:", "ON" if led_state else "OFF")
        ultimo_led = time.ticks_ms()

    if time.ticks_diff(time.ticks_ms(), ultimo_pir) >= 150:
        atual = pir_sensor.value()
        if atual != pir_state:
            pir_state = atual
            print("PIR GPIO7:", "MOVIMENTO" if pir_state else "SEM MOVIMENTO")
            if pir_state and display is not None:
                display.alerta("! MOVIMENTO !", 6)
        ultimo_pir = time.ticks_ms()

    if time.ticks_diff(time.ticks_ms(), ultimo_sensor) >= 2500:
        try:
            dht_sensor.measure()
            temperature = dht_sensor.temperature()
            humidity = dht_sensor.humidity()
            if temperature == 0 and humidity == 0:
                raise ValueError("retorno zerado suspeito")
            print("DHT11: temperatura=%d C umidade=%d%%" % (temperature, humidity))
        except Exception as exc:
            temperature = None
            humidity = None
            print("DHT11: leitura indisponivel", exc)
        ultimo_sensor = time.ticks_ms()

    # A cada 30s, se estava conectado e caiu, tenta voltar sozinho.
    if conectado and time.ticks_diff(time.ticks_ms(), ultima_checagem_wifi) >= 30000:
        sta = network.WLAN(network.STA_IF)
        if not sta.isconnected():
            print("WIFI: conexao caiu, tentando reconectar...")
            cfg = load_wifi()
            if cfg.get("ssid"):
                try:
                    sta.connect(cfg["ssid"], cfg.get("password", ""))
                except Exception as exc:
                    print("WIFI: erro ao reconectar", exc)
        ultima_checagem_wifi = time.ticks_ms()

    if display is not None:
        display.update(temperature, humidity, pir_state, ip if conectado else None)
    time.sleep(0.05)
