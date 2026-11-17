"""Small authenticated Wake-on-LAN helper for the JARVIS ESP32."""


def decode_form_value(value):
    """Decode one application/x-www-form-urlencoded UTF-8 field."""
    value = value.replace("+", " ")
    decoded = bytearray()
    index = 0
    while index < len(value):
        if value[index] == "%" and index + 2 < len(value):
            try:
                decoded.append(int(value[index + 1:index + 3], 16))
                index += 3
                continue
            except ValueError:
                pass
        decoded.extend(value[index].encode("utf-8"))
        index += 1
    return bytes(decoded).decode("utf-8")


def build_magic_packet(mac):
    normalized = mac.replace(":", "").replace("-", "").replace(".", "")
    if len(normalized) != 12:
        raise ValueError("MAC must contain 12 hexadecimal digits")
    try:
        address = bytearray()
        for offset in range(0, 12, 2):
            address.append(int(normalized[offset:offset + 2], 16))
    except ValueError:
        raise ValueError("MAC must contain 12 hexadecimal digits")
    packet = bytearray(b"\xff" * 6)
    for _ in range(16):
        packet.extend(address)
    return bytes(packet)


def directed_broadcast(ip, netmask):
    try:
        address = [int(part) for part in ip.split(".")]
        mask = [int(part) for part in netmask.split(".")]
        if len(address) != 4 or len(mask) != 4:
            raise ValueError()
        if any(value < 0 or value > 255 for value in address + mask):
            raise ValueError()
    except Exception:
        raise ValueError("Invalid IPv4 address or netmask")
    return ".".join(str((address[i] & mask[i]) | (255 ^ mask[i]))
                     for i in range(4))


def _http_response(status, reason, message):
    body = message.encode("utf-8")
    return ("HTTP/1.1 %s %s\r\nContent-Type: text/plain; charset=utf-8\r\n"
            "Content-Length: %d\r\nConnection: close\r\n\r\n" %
            (status, reason, len(body))) + message


def _authorized(request, token):
    if not token or len(token) < 24:
        return False, False
    for line in request.split("\r\n")[1:]:
        if not line:
            break
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == "authorization":
            return True, value.strip() == "Bearer " + token
    return True, False


def wake_response(request, token, sta_connected, ip, netmask, mac, socket_module):
    first_line = request.split("\r\n", 1)[0].split(" ")
    if len(first_line) < 2 or first_line[0] != "POST" or first_line[1] != "/wake":
        return _http_response("405", "Method Not Allowed", "Use POST /wake")
    if not sta_connected:
        return _http_response("503", "Service Unavailable", "Wi-Fi station is offline")
    token_configured, authorized = _authorized(request, token)
    if not token_configured:
        return _http_response("503", "Service Unavailable", "Wake endpoint is not configured")
    if not authorized:
        return _http_response("401", "Unauthorized", "Invalid bearer token")
    try:
        packet = build_magic_packet(mac)
        broadcast = directed_broadcast(ip, netmask)
        udp = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        try:
            udp.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_BROADCAST, 1)
            udp.sendto(packet, (broadcast, 9))
        finally:
            udp.close()
    except ValueError:
        return _http_response("400", "Bad Request", "Invalid target MAC or Wi-Fi subnet")
    except Exception:
        return _http_response("502", "Bad Gateway", "Could not send Wake-on-LAN packet")
    return _http_response("200", "OK", "Wake-on-LAN packet sent")
