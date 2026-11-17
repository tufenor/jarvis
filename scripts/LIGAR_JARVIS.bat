@echo off
cd /d C:\JARVIS
echo [1/4] Escaneando o barramento I2C (procurando LCD e PCA9685)...
echo ======== SCAN I2C ======== > scripts\resultado_jarvis.txt
.venv\Scripts\mpremote.exe connect COM7 exec "from machine import Pin,I2C; i=I2C(0,sda=Pin(15),scl=Pin(16),freq=10000); a=i.scan(); print('enderecos:',[hex(x) for x in a]); print('LCD 0x27:', 0x27 in a); print('PCA9685 0x40:', 0x40 in a)" >> scripts\resultado_jarvis.txt 2>&1
echo. >> scripts\resultado_jarvis.txt
echo [2/4] Enviando a tela nova...
echo ======== ENVIO ======== >> scripts\resultado_jarvis.txt
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\lcd_display.py :lcd_display.py >> scripts\resultado_jarvis.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\main_network.py :main.py >> scripts\resultado_jarvis.txt 2>&1
echo [3/4] Reiniciando a placa...
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_jarvis.txt 2>&1
echo [4/4] Olhe para o LCD agora - a abertura esta rodando!
echo ======== BOOT ======== >> scripts\resultado_jarvis.txt
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 22 >> scripts\resultado_jarvis.txt 2>&1
echo.
echo Pronto. Resultado em scripts\resultado_jarvis.txt
pause >nul
