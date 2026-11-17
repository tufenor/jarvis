@echo off
cd /d C:\JARVIS
echo Gravando painel e firmware na placa...
echo ---- envio ---- > scripts\resultado_deploy.txt
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\lcd_display.py :lcd_display.py >> scripts\resultado_deploy.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\main_network.py :main.py >> scripts\resultado_deploy.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_deploy.txt 2>&1
echo. >> scripts\resultado_deploy.txt
echo ---- o que a placa diz ---- >> scripts\resultado_deploy.txt
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 20 >> scripts\resultado_deploy.txt 2>&1
echo Pronto.
pause >nul
