"""Leitura não destrutiva do VersionReg do RC522 via ESP32-S3."""
from machine import Pin, SoftSPI, SPI
from time import sleep_ms

spi = SoftSPI(
    baudrate=100_000,
    polarity=0,
    phase=0,
    sck=Pin(12),
    mosi=Pin(11),
    miso=Pin(13),
)
cs = Pin(10, Pin.OUT, value=1)
rst = Pin(9, Pin.OUT, value=1)

rst.value(0)
sleep_ms(20)
rst.value(1)
sleep_ms(50)

def read_register(bus, address):
    tx = bytes((((address << 1) & 0x7E) | 0x80, 0))
    rx = bytearray(2)
    cs.value(0)
    bus.write_readinto(tx, rx)
    cs.value(1)
    return rx[1]

def read_versions(bus):
    values = []
    for _ in range(5):
        values.append(read_register(bus, 0x37))
        sleep_ms(20)
    return values


try:
    soft_versions = read_versions(spi)
    print("RC522 VersionReg SoftSPI (5 leituras):", [hex(v) for v in soft_versions])
finally:
    spi.deinit()

hardware_versions = []
hardware_spi = None
try:
    hardware_spi = SPI(1, baudrate=100_000, polarity=0, phase=0,
                       sck=Pin(12), mosi=Pin(11), miso=Pin(13))
    rst.value(0)
    sleep_ms(20)
    rst.value(1)
    sleep_ms(50)
    hardware_versions = read_versions(hardware_spi)
    print("RC522 VersionReg SPI(1) (5 leituras):", [hex(v) for v in hardware_versions])
except Exception as error:
    print("SPI(1) indisponivel:", repr(error))
finally:
    if hardware_spi is not None:
        hardware_spi.deinit()

valid_versions = (0x91, 0x92, 0x88)
def stable_version(values):
    return (len(values) == 5 and values[0] in valid_versions
            and all(value == values[0] for value in values))

if stable_version(soft_versions) or stable_version(hardware_versions):
    print("RC522 respondeu de forma estavel ao SPI; proximo teste: ler o cartao.")
else:
    print("Sem resposta SPI valida e estavel; leitura do cartao ainda nao validada.")
