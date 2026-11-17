"""LCD1602/PCF8574: fixed wiring, bounded refresh and recoverable I2C errors.

JARVIS: SDA=GPIO15, SCL=GPIO16, address=0x27, 10 kHz.
PCF8574: RS=P0, RW=P1, E=P2, backlight=P3, D4-D7=P4-P7.
The LCD and ESP32 retain their existing 3.3 V wiring.
"""
import time


def _row(text):
    # MicroPython's str has no ljust(); slicing/padding works on both runtimes.
    return (text + " " * 16)[:16]


def format_lines(temperature, humidity, motion):
    if (temperature is None or humidity is None
            or (temperature == 0 and humidity == 0)):
        first = "Sem leitura"
    else:
        first = "T:%dC U:%02d%%" % (temperature, humidity)
    second = "Movimento: " + ("SIM" if motion else "NAO")
    return (_row(first), _row(second))


class LCD1602:
    def __init__(self, bus, address=0x27, clock=None):
        self.bus = bus
        self.address = address
        self.clock = time if clock is None else clock
        self._lines = None
        try:
            self._port(8)
            self.clock.sleep_ms(50)
            self._nibble(0x30)
            self.clock.sleep_ms(5)
            self._nibble(0x30)
            self.clock.sleep_ms(1)
            self._nibble(0x30)
            self.clock.sleep_ms(1)
            self._nibble(0x20)
            self.clock.sleep_ms(1)
            for command in (0x28, 0x08, 0x01, 0x02, 0x06, 0x0C):
                self._send(command)
        except Exception:
            self.close()
            raise

    def _port(self, value):
        if self.bus.writeto(self.address, bytes([value])) != 1:
            raise OSError("LCD: ACK incompleto")

    def _nibble(self, value, rs=0):
        value = (value & 0xF0) | 8 | rs
        self._port(value | 4)
        self.clock.sleep_us(100)
        self._port(value)
        self.clock.sleep_us(100)

    def _send(self, value, rs=0):
        self._nibble(value, rs)
        self._nibble(value << 4, rs)
        self.clock.sleep_us(100)
        if not rs and value in (1, 2):
            self.clock.sleep_ms(5)

    def show(self, lines):
        lines = tuple(_row(line) for line in lines)
        changed = False
        for row in (0, 1):
            if self._lines is not None and self._lines[row] == lines[row]:
                continue
            self._send(0x80 if row == 0 else 0xC0)
            for character in lines[row]:
                self._send(ord(character), 1)
            changed = True
        # Commit only after both writes finish, not after a partial frame.
        self._lines = lines
        return changed

    def close(self):
        try:
            self.bus.deinit()
        except Exception:
            pass


def _connect_lcd():
    # Mesmo motivo de _conectar_plus: SoftI2C a 100 kHz funciona, o
    # periferico de hardware a 10 kHz devolve ENODEV nesta placa.
    from machine import Pin
    try:
        from machine import SoftI2C
        return LCD1602(SoftI2C(sda=Pin(15), scl=Pin(16), freq=100000))
    except ImportError:
        from machine import I2C
        return LCD1602(I2C(0, sda=Pin(15), scl=Pin(16), freq=100000))


class SensorDisplay:
    def __init__(self, lcd_factory=None, clock=None, report=None):
        self._factory = _connect_lcd if lcd_factory is None else lcd_factory
        self._clock = time if clock is None else clock
        self._report = print if report is None else report
        self._lcd = None
        self._last_refresh = None
        self._last_attempt = None

    def update(self, temperature, humidity, motion, now_ms=None):
        now = self._clock.ticks_ms() if now_ms is None else now_ms
        if self._lcd is None:
            if (self._last_attempt is not None
                    and self._clock.ticks_diff(now, self._last_attempt) < 5000):
                return False
        elif (self._last_refresh is not None
              and self._clock.ticks_diff(now, self._last_refresh) < 1000):
            return False
        self._last_refresh = now
        try:
            if self._lcd is None:
                self._last_attempt = now
                self._lcd = self._factory()
            lines = format_lines(temperature, humidity, motion)
            changed = self._lcd.show(lines)
            if changed:
                self._report("LCD: %s | %s" % (lines[0].rstrip(), lines[1].rstrip()))
            return changed
        except Exception as exc:
            if self._lcd is not None:
                self._lcd.close()
            self._lcd = None
            self._last_attempt = now
            self._report("LCD: indisponivel; nova tentativa em 5s: %s" % exc)
            return False


# =====================================================================
#  JARVIS - camada visual criativa
#  Tudo abaixo e adicao. Nada acima foi alterado, os testes seguem valendo.
# =====================================================================

# Simbolos proprios do LCD: 8 desenhos de 5x8 pixels guardados na memoria
# do display. Cada numero e uma linha; cada bit aceso e um pixel.
SIMBOLOS = {
    "termometro": (0b00100, 0b01010, 0b01010, 0b01110,
                   0b01110, 0b11111, 0b11111, 0b01110),
    "gota":       (0b00100, 0b00100, 0b01110, 0b01110,
                   0b11111, 0b11111, 0b11111, 0b01110),
    "parado":     (0b00100, 0b00100, 0b01110, 0b10101,
                   0b00100, 0b00100, 0b01010, 0b10001),
    "andando":    (0b00100, 0b00100, 0b01110, 0b00101,
                   0b01100, 0b00100, 0b01010, 0b10010),
    "antena":     (0b11111, 0b00000, 0b01110, 0b00000,
                   0b00100, 0b00000, 0b00000, 0b00000),
    "pulso_fraco": (0b00000, 0b00000, 0b01010, 0b11111,
                    0b11111, 0b01110, 0b00100, 0b00000),
    "pulso_forte": (0b00000, 0b01010, 0b11111, 0b11111,
                    0b11111, 0b01110, 0b00100, 0b00000),
    "bloco":      (0b11111, 0b11111, 0b11111, 0b11111,
                   0b11111, 0b11111, 0b11111, 0b11111),
}

# Posicao de cada simbolo na memoria do display (so cabem 8).
TERMOMETRO, GOTA, PARADO, ANDANDO, ANTENA, PULSO_FRACO, PULSO_FORTE, BLOCO = range(8)

_ORDEM = ("termometro", "gota", "parado", "andando",
          "antena", "pulso_fraco", "pulso_forte", "bloco")


class LCD1602Plus(LCD1602):
    """O mesmo driver, com simbolos proprios e escrita em um ponto so.

    Redesenhar a linha inteira a cada animacao deixaria tudo lento, entao
    existe write_at para trocar um unico caractere.
    """

    def carregar_simbolos(self):
        for indice, nome in enumerate(_ORDEM):
            self._send(0x40 | ((indice & 7) << 3))
            for linha in SIMBOLOS[nome]:
                self._send(linha & 0x1F, 1)
        self._send(0x80)
        self._lines = None  # a memoria mudou; forcar redesenho

    def write_at(self, row, col, texto):
        """Escreve a partir de uma posicao, sem mexer no resto da tela."""
        base = 0x80 if row == 0 else 0xC0
        self._send(base + col)
        escritos = []
        for ch in texto:
            codigo = ch if isinstance(ch, int) else ord(ch)
            self._send(codigo, 1)
            escritos.append(chr(codigo))

        # Antes isto zerava o cache inteiro, e o batimento de cada segundo
        # obrigava a redesenhar os 32 caracteres da tela. Num display com
        # alimentacao apertada isso aparece como piscada. Agora so o trecho
        # que mudou e anotado, e show() continua pulando o que esta igual.
        if self._lines is not None:
            linha = self._lines[row]
            trecho = "".join(escritos)
            atualizada = (linha[:col] + trecho + linha[col + len(trecho):])[:16]
            linhas = list(self._lines)
            linhas[row] = atualizada
            self._lines = tuple(linhas)


def _conectar_plus():
    """Abre o barramento do LCD preferindo SoftI2C.

    Medido na placa em 20/10/2026: o periferico I2C de hardware a 10 kHz
    devolve ENODEV, enquanto o SoftI2C enxerga o 0x27 normalmente. O
    divisor de clock do hardware nao desce bem ate 10 kHz; 100 kHz com
    SoftI2C e estavel. O hardware fica como segunda opcao, caso alguma
    build nao traga SoftI2C.
    """
    from machine import Pin
    try:
        from machine import SoftI2C
        barramento = SoftI2C(sda=Pin(15), scl=Pin(16), freq=100000)
    except ImportError:
        from machine import I2C
        barramento = I2C(0, sda=Pin(15), scl=Pin(16), freq=100000)
    lcd = LCD1602Plus(barramento)
    lcd.carregar_simbolos()
    return lcd


def _centralizar(texto):
    sobra = 16 - len(texto)
    if sobra <= 0:
        return texto[:16]
    return " " * (sobra // 2) + texto + " " * (sobra - sobra // 2)


def _clima_em_palavras(temperatura, umidade):
    """Numero vira leitura humana: e o JARVIS opinando, nao so medindo.

    Cabe em 15 colunas para nao colidir com o batimento no canto.
    """
    if temperatura is None or umidade is None:
        return "lendo sensor"
    if umidade < 25:
        return "ar muito seco"
    if umidade > 75:
        return "ar muito umido"
    if temperatura >= 30:
        return "esta quente"
    if temperatura >= 25:
        return "agradavel"
    if temperatura >= 17:
        return "clima ameno"
    return "esta frio"


def _tempo_ligado(segundos):
    segundos = int(segundos)
    if segundos < 3600:
        return "%dmin" % (segundos // 60)
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    if horas < 24:
        return "%dh %02dmin" % (horas, minutos)
    return "%dd %dh" % (horas // 24, horas % 24)


class JarvisDisplay:
    """Tela do JARVIS: abertura animada, telas que giram e alertas.

    Nao trava o programa: cada chamada de update faz no maximo um
    pedacinho de desenho e volta na hora.
    """

    def __init__(self, lcd_factory=None, clock=None, report=None,
                 segundos_por_tela=4):
        self._factory = _conectar_plus if lcd_factory is None else lcd_factory
        self._clock = time if clock is None else clock
        self._report = print if report is None else report
        self._lcd = None
        self._ultima_tentativa = None

        self._tela = 0
        self._trocou_em = None
        self._bateu_em = None
        self._coracao = False
        self._passo = False
        self._linhas = [None, None]
        self._alerta_ate = None
        self._nascimento = None
        self._ja_abriu = False
        self._segundos_por_tela = segundos_por_tela
        self._ultimo_relato = None
        self._ja_teve_leitura = False
        self._visto_movimento_em = None

    # ------------------------------------------------------------ interno
    def _garantir(self, agora):
        if self._lcd is not None:
            return True
        if (self._ultima_tentativa is not None
                and self._clock.ticks_diff(agora, self._ultima_tentativa) < 5000):
            return False
        self._ultima_tentativa = agora
        try:
            self._lcd = self._factory()
            self._linhas = [None, None]
            return True
        except Exception as exc:
            self._report("LCD: indisponivel, nova tentativa em 5s: %s" % exc)
            self._lcd = None
            return False

    def _perdeu_contato(self, exc):
        self._report("LCD: perdi contato (%s)" % exc)
        try:
            self._lcd.close()
        except Exception:
            pass
        self._lcd = None
        self._ultima_tentativa = self._clock.ticks_ms()

    def _escrever(self, linha0, linha1):
        """So manda para o display o que realmente mudou."""
        novas = [_centralizar(linha0) if len(linha0) < 16 else linha0[:16],
                 (linha1 + " " * 16)[:16]]
        try:
            for i in (0, 1):
                if self._linhas[i] != novas[i]:
                    self._lcd.write_at(i, 0, novas[i])
                    self._linhas[i] = novas[i]
        except Exception as exc:
            self._perdeu_contato(exc)

    def _simbolo(self, linha, coluna, indice):
        try:
            self._lcd.write_at(linha, coluna, chr(indice))
        except Exception as exc:
            self._perdeu_contato(exc)

    # ---------------------------------------------------------- abertura
    def abertura(self):
        """Animacao de boas-vindas. So roda uma vez, na ligada."""
        agora = self._clock.ticks_ms()
        if self._ja_abriu or not self._garantir(agora):
            self._ja_abriu = True
            return
        self._ja_abriu = True
        self._nascimento = agora
        try:
            nome = "J.A.R.V.I.S."
            inicio = (16 - len(nome)) // 2
            self._lcd.show(("                ", "                "))
            for i in range(len(nome)):
                self._lcd.write_at(0, inicio + i, nome[i])
                self._clock.sleep_ms(55)
            # barra de carregamento com o bloco cheio
            for coluna in range(16):
                self._lcd.write_at(1, coluna, chr(BLOCO))
                self._clock.sleep_ms(22)
            self._clock.sleep_ms(150)
            self._lcd.write_at(1, 0, _centralizar("SISTEMAS ONLINE"))
            self._clock.sleep_ms(500)
            self._linhas = [None, None]
        except Exception as exc:
            self._perdeu_contato(exc)

    # ------------------------------------------------------------ alerta
    def alerta(self, titulo="! INTRUSO !", segundos=8):
        """Toma a tela por alguns segundos, por cima do rodizio."""
        agora = self._clock.ticks_ms()
        if not self._garantir(agora):
            return
        self._alerta_ate = agora + segundos * 1000
        self._escrever(titulo, "")
        self._report("LCD: alerta -> %s" % titulo)

    # ---------------------------------------------------------- rodizio
    def update(self, temperature, humidity, motion, ip=None, now_ms=None):
        agora = self._clock.ticks_ms() if now_ms is None else now_ms
        if not self._garantir(agora):
            return False
        if self._nascimento is None:
            self._nascimento = agora

        # Assim que a primeira leitura valida chega, pular para a tela de
        # ambiente: sem isso o display fica exibindo "sem leitura" ate o
        # rodizio dar a volta, mesmo com o sensor ja respondendo.
        # So consumir a chance quando o salto realmente acontecer: se um
        # alerta estiver na tela, espera ele acabar e salta depois.
        if motion:
            self._visto_movimento_em = agora

        tem_leitura = temperature is not None and humidity is not None
        if tem_leitura and not self._ja_teve_leitura and self._alerta_ate is None:
            self._ja_teve_leitura = True
            self._tela = 0
            self._trocou_em = agora
            self._linhas = [None, None]

        # Prova no serial de que os valores chegaram ao display.
        classicas = format_lines(temperature, humidity, motion)
        relato = "%s | %s" % (classicas[0].rstrip(), classicas[1].rstrip())
        if relato != self._ultimo_relato:
            self._report("LCD: %s" % relato)
            self._ultimo_relato = relato
        if self._trocou_em is None:
            self._trocou_em = agora
        if self._bateu_em is None:
            self._bateu_em = agora

        # ----- alerta tem prioridade sobre tudo
        if self._alerta_ate is not None:
            if self._clock.ticks_diff(self._alerta_ate, agora) > 0:
                if self._clock.ticks_diff(agora, self._bateu_em) >= 400:
                    self._passo = not self._passo
                    self._simbolo(1, 7, ANDANDO if self._passo else PARADO)
                    self._bateu_em = agora
                return True
            self._alerta_ate = None
            self._linhas = [None, None]

        # ----- troca de tela a cada N segundos
        if self._clock.ticks_diff(agora, self._trocou_em) >= self._segundos_por_tela * 1000:
            self._tela = (self._tela + 1) % 4
            self._trocou_em = agora

        # Pula a tela de rede quando ainda nao ha IP para mostrar.
        if self._tela == 2 and not ip:
            self._tela = 3

        if self._tela == 0:
            titulo = " " + _clima_em_palavras(temperature, humidity)
            if temperature is None or humidity is None:
                self._escrever(titulo, "  sem leitura")
            else:
                self._escrever(titulo,
                               "  %2dC      %02d%%" % (temperature, humidity))
                self._simbolo(1, 1, TERMOMETRO)
                self._simbolo(1, 9, GOTA)
        elif self._tela == 1:
            if motion:
                self._escrever(" PRESENCA", "   MOVIMENTO")
            else:
                parado = None if self._visto_movimento_em is None else \
                    self._clock.ticks_diff(agora, self._visto_movimento_em) / 1000.0
                # Abaixo de um minuto o contador em minutos daria "0min".
                if parado is None or parado < 60:
                    self._escrever(" PRESENCA", "   tudo calmo")
                else:
                    self._escrever(" PRESENCA",
                                   "   calmo ha " + _tempo_ligado(parado))
            self._simbolo(1, 1, ANDANDO if motion else PARADO)
        elif self._tela == 2:
            self._escrever(" REDE", "  " + str(ip))
            self._simbolo(1, 0, ANTENA)
        else:
            segundos = self._clock.ticks_diff(agora, self._nascimento) / 1000.0
            self._escrever("J.A.R.V.I.S.",
                           "  ativo ha " + _tempo_ligado(segundos))

        # ----- batimento: mostra que esta vivo, custa 1 caractere
        if self._clock.ticks_diff(agora, self._bateu_em) >= 1000:
            self._coracao = not self._coracao
            self._simbolo(0, 15, PULSO_FORTE if self._coracao else PULSO_FRACO)
            self._bateu_em = agora
        return True
