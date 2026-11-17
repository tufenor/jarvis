@echo off
cd /d C:\JARVIS
echo Gravando firmware completo na placa...
echo ---- porta ---- > scripts\resultado_deploy.txt
.venv\Scripts\python.exe -m serial.tools.list_ports >> scripts\resultado_deploy.txt 2>&1
echo ---- envio ---- >> scripts\resultado_deploy.txt
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\lcd_display.py :lcd_display.py >> scripts\resultado_deploy.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\main_network.py :main.py >> scripts\resultado_deploy.txt 2>&1
timeout /t 2 >nul
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_deploy.txt 2>&1
echo ---- boot ---- >> scripts\resultado_deploy.txt
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 25 >> scripts\resultado_deploy.txt 2>&1
echo Pronto.
pause >nul
