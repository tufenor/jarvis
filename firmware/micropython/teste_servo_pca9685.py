"""Teste isolado e limitado do PCA9685 + servo, canal 0.

ATENCAO: so rodar depois de confirmar V+ da PCA9685 perto de 5V
(boost conversor ajustado), senao o servo pode nao se mover ou a
leitura de tensao ficar instavel. Nao grava firmware; roda em RAM
via `mpremote run` e desliga o canal ao final.

I2C: SDA=GPIO15, SCL=GPIO16 (mesmo barramento do LCD).
"""
from machine import Pin, I2C
from time import sleep_ms

i2c = I2C(0, sda=Pin(15), scl=Pin(16), freq=100_000)

print("Escaneando I2C...")
found = i2c.scan()
print("Enderecos encontrados:", [hex(a) for a in found])

PCA_ADDR = 0x40
if PCA_ADDR not in found:
    print("PCA9685 (0x40) NAO respondeu no barramento. Parando aqui.")
else:
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def write8(reg, value):
        i2c.writeto_mem(PCA_ADDR, reg, bytes([value & 0xFF]))

    def read8(reg):
        return i2c.readfrom_mem(PCA_ADDR, reg, 1)[0]

    def set_pwm_freq(hz):
        prescale_val = int(25_000_000.0 / (4096 * hz) - 1 + 0.5)
        old_mode = read8(MODE1)
        write8(MODE1, (old_mode & 0x7F) | 0x10)  # sleep
        write8(PRESCALE, prescale_val)
        write8(MODE1, old_mode)
        sleep_ms(5)
        write8(MODE1, old_mode | 0xA1)  # auto-increment, restart

    def set_pwm(channel, on, off):
        base = LED0_ON_L + 4 * channel
        i2c.writeto_mem(PCA_ADDR, base, bytes([on & 0xFF, (on >> 8) & 0xFF,
                                                off & 0xFF, (off >> 8) & 0xFF]))

    def pulse_ms(channel, ms):
        # 50Hz -> periodo 20ms -> 4096 ticks. ticks = ms/20*4096
        ticks = int(ms / 20.0 * 4096)
        set_pwm(channel, 0, ticks)

    print("PCA9685 encontrado. Configurando 50Hz...")
    write8(MODE1, 0x00)
    set_pwm_freq(50)
    sleep_ms(10)

    CHANNEL = 0
    print("Movendo canal", CHANNEL, ": 1.3ms -> 1.7ms -> 1.3ms")
    for ms in (1.3, 1.7, 1.3):
        pulse_ms(CHANNEL, ms)
        sleep_ms(700)

    set_pwm(CHANNEL, 0, 0)
    print("Canal", CHANNEL, "desligado. Teste encerrado.")
    print("Se o servo NAO se moveu: confira V+ (precisa ~5V) e o canal fisico certo.")
