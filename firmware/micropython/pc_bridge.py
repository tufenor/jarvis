"""Authenticated bridge from ESP32 panel to the fixed local Windows agent."""


def _http_response(status, reason, message):
    body = message.encode("utf-8")
    return ("HTTP/1.1 %s %s\r\nContent-Type: text/plain; charset=utf-8\r\n"
            "Content-Length: %d\r\nConnection: close\r\n\r\n" %
            (status, reason, len(body))) + message


def _authorized(request, token):
    if len(token) != 32:
        return False
    for line in request.split("\r\n")[1:]:
        if not line:
            break
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == "authorization":
            return value.strip() == "Bearer " + token
    return False


def _send_all(client, data):
    remaining = data
    while remaining:
        sent = client.send(remaining)
        if sent is None or sent <= 0:
            raise OSError("Windows agent disconnected")
        remaining = remaining[sent:]


def valid_private_ipv4(value):
    """Accept only a private unicast IPv4 address for the PC agent target."""
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        address = [int(part) for part in parts]
    except Exception:
        return False
    if any(not 0 <= part <= 255 or str(part) != raw
           for part, raw in zip(address, parts)):
        return False
    return (address[0] == 10 or
            (address[0] == 172 and 16 <= address[1] <= 31) or
            (address[0] == 192 and address[1] == 168))


def _read_http_response(client):
    response = bytearray()
    while len(response) < 1024:
        chunk = client.recv(256)
        if not chunk:
            break
        response.extend(chunk)
        boundary = response.find(b"\r\n\r\n")
        if boundary >= 0:
            header = bytes(response[:boundary]).decode("ascii", "ignore")
            body_length = 0
            for line in header.split("\r\n")[1:]:
                name, separator, value = line.partition(":")
                if separator and name.strip().lower() == "content-length":
                    try:
                        body_length = int(value.strip())
                    except ValueError:
                        body_length = 0
            if len(response) >= boundary + 4 + body_length:
                break
    return bytes(response).decode("utf-8", "ignore")


def pc_action_response(request, token, sta_connected, pc_host, socket_module,
                       port=8765):
    first_line = request.split("\r\n", 1)[0].split(" ")
    if len(first_line) < 2 or first_line[0] != "POST":
        return _http_response("405", "Method Not Allowed", "Use POST /pc/shutdown or /pc/cancel")
    routes = {"/pc/shutdown": ("/shutdown", "SHUTDOWN"),
              "/pc/cancel": ("/cancel", "CANCEL")}
    route = routes.get(first_line[1])
    if route is None:
        return _http_response("404", "Not Found", "Unknown PC action")
    if not sta_connected:
        return _http_response("503", "Service Unavailable", "Wi-Fi station is offline")
    if not _authorized(request, token):
        return _http_response("401", "Unauthorized", "Invalid bearer token")
    target_path, confirmation = route
    body = "confirm=" + confirmation
    data = ("POST %s HTTP/1.1\r\nHost: %s\r\nAuthorization: Bearer %s\r\n"
            "Content-Type: application/x-www-form-urlencoded\r\n"
            "Content-Length: %d\r\nConnection: close\r\n\r\n%s" %
            (target_path, pc_host, token, len(body), body)).encode("ascii")
    client = None
    try:
        client = socket_module.socket(socket_module.AF_INET,
                                      socket_module.SOCK_STREAM)
        client.settimeout(3)
        client.connect((pc_host, port))
        _send_all(client, data)
        response = _read_http_response(client)
    except Exception:
        return _http_response("502", "Bad Gateway", "PC agent unavailable on the local network")
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    status_line = response.split("\r\n", 1)[0].split(" ")
    if len(status_line) < 2 or not status_line[1].isdigit():
        return _http_response("502", "Bad Gateway", "Invalid response from PC agent")
    status = int(status_line[1])
    if status == 202:
        return _http_response("202", "Accepted", "Desligamento agendado para 30 segundos; nao fecha aplicativos a forca")
    if status == 200:
        return _http_response("200", "OK", "Desligamento cancelado")
    if status == 401:
        return _http_response("401", "Unauthorized", "Token recusado pelo agente do PC")
    if status == 403:
        return _http_response("403", "Forbidden", "O PC recusou a origem fora da rede local configurada")
    if status == 409:
        return _http_response("409", "Conflict", "O pedido nao pode ser aplicado no estado atual")
    return _http_response("503", "Service Unavailable", "O agente do PC recusou a acao (HTTP %d)" % status)
