"""Tentativa limitada de detectar cartao e ler UID; nao escreve no cartao.

Protocolo e registradores: datasheet MFRC522 da NXP.
Referencia revisada: github.com/wendlers/micropython-mfrc522.
Implementacao local para ESP32-S3; execucao temporaria via mpremote run.
Reiniciar main.py ao terminar. Pinos: CS10, RST9, SCK12, MOSI11, MISO13.
"""
from machine import Pin, SoftSPI, SPI
from time import sleep_ms, ticks_ms, ticks_diff

select = Pin(10, Pin.OUT, value=1)
reset = Pin(9, Pin.OUT, value=1)
led = Pin(4, Pin.OUT)


class CardProbe:
    def __init__(self, wire):
        self.wire = wire

    def get(self, address):
        response = bytearray(2)
        select.value(0)
        try:
            self.wire.write_readinto(bytes((0x80 | ((address << 1) & 0x7E), 0)), response)
        finally:
            select.value(1)
        return response[1]

    def put(self, address, value):
        select.value(0)
        try:
            self.wire.write(bytes(((address << 1) & 0x7E, value & 255)))
        finally:
            select.value(1)

    def setup(self):
        reset.value(0)
        sleep_ms(20)
        reset.value(1)
        sleep_ms(100)
        self.put(0x01, 0x0F)
        sleep_ms(50)
        for address, value in ((0x2A, 0x8D), (0x2B, 0x3E), (0x2C, 0),
                               (0x2D, 30), (0x15, 0x40), (0x11, 0x3D),
                               (0x12, 0), (0x13, 0), (0x14, 0x03)):
            self.put(address, value)

    def exchange(self, frame, last_bits=0):
        self.put(0x01, 0)  # Idle antes de preparar o FIFO.
        self.put(0x04, 0x7F)
        self.put(0x0A, 0x80)
        self.put(0x0D, last_bits & 7)
        for octet in frame:
            self.put(0x09, octet)
        self.put(0x01, 0x0C)
        self.put(0x0D, 0x80 | (last_bits & 7))
        started = ticks_ms()
        irq = 0
        while ticks_diff(ticks_ms(), started) < 80:
            irq = self.get(0x04)
            if irq & 0x31:
                break
            sleep_ms(1)
        self.put(0x0D, last_bits & 7)
        if not irq & 0x30 or self.get(0x06) & 0x1B:
            return None
        length = self.get(0x0A) & 0x7F
        if not 1 <= length <= 64:
            return None
        remainder = self.get(0x0C) & 7
        bit_count = (length - 1) * 8 + remainder if remainder else length * 8
        data = bytes(self.get(0x09) for _ in range(length))
        return data, bit_count

    def crc(self, frame):
        self.put(0x01, 0)
        self.put(0x05, 0x04)
        self.put(0x0A, 0x80)
        for octet in frame:
            self.put(0x09, octet)
        self.put(0x01, 0x03)
        started = ticks_ms()
        while ticks_diff(ticks_ms(), started) < 50:
            if self.get(0x05) & 0x04:
                self.put(0x01, 0)
                return bytes((self.get(0x22), self.get(0x21)))
            sleep_ms(1)
        return None

    def uid(self):
        wake = self.exchange(b'\x52', last_bits=7)
        if wake is None or wake[1] != 16 or len(wake[0]) != 2:
            return None
        print('Cartao respondeu ATQA:', wake[0].hex())
        identity = bytearray()
        for cascade in (0x93, 0x95, 0x97):
            answer = self.exchange(bytes((cascade, 0x20)))
            if answer is None or answer[1] != 40 or len(answer[0]) != 5:
                return None
            block = answer[0]
            if block[0] ^ block[1] ^ block[2] ^ block[3] != block[4]:
                return None
            frame = bytes((cascade, 0x70)) + block
            check = self.crc(frame)
            if check is None:
                return None
            chosen = self.exchange(frame + check)
            if chosen is None or chosen[1] != 24 or len(chosen[0]) != 3:
                return None
            sak = chosen[0]
            if self.crc(sak[:1]) != sak[1:]:
                return None
            continuing = bool(sak[0] & 0x04)
            if continuing:
                if block[0] != 0x88 or cascade == 0x97:
                    return None
                identity.extend(block[1:4])
            else:
                identity.extend(block[:4])
                if len(identity) in (4, 7, 10):
                    return bytes(identity)
                return None
        return None


found = False
for mode in ('SPI(1)', 'SoftSPI'):
    wire = None
    probe = None
    try:
        options = dict(baudrate=100_000, polarity=0, phase=0,
                       sck=Pin(12), mosi=Pin(11), miso=Pin(13))
        wire = SPI(1, **options) if mode == 'SPI(1)' else SoftSPI(**options)
        probe = CardProbe(wire)
        probe.setup()
        print(mode, 'VersionReg:', hex(probe.get(0x37)))
        print('Janela de leitura:', mode, '- mantenha o cartao junto a antena.')
        started = ticks_ms()
        attempts = 0
        while ticks_diff(ticks_ms(), started) < 8000:
            led.value((ticks_ms() // 1000) & 1)
            attempts += 1
            identity = probe.uid()
            if identity is not None:
                print('CARTAO LIDO - UID:', ':'.join('%02X' % octet for octet in identity))
                found = True
                break
            sleep_ms(150)
        print(mode, 'tentativas:', attempts, 'UID validado:', found)
    finally:
        select.value(1)
        if wire is not None:
            if probe is not None:
                probe.put(0x14, 0)  # Desligar campo do leitor no fim do modo.
            wire.deinit()
    if found:
        break

if not found:
    print('NENHUM UID VALIDADO nesta tentativa. Isso nao prova defeito do cartao.')
