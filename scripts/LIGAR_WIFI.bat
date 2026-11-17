@echo off
cd /d C:\JARVIS
echo Enviando a rede para a placa e reiniciando...
echo ---- envio ---- > scripts\resultado_wifi.txt
.venv\Scripts\mpremote.exe connect COM7 fs cp scripts\_wifi_temp.json :wifi.json >> scripts\resultado_wifi.txt 2>&1
del /q scripts\_wifi_temp.json
timeout /t 2 >nul
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_wifi.txt 2>&1
echo. >> scripts\resultado_wifi.txt
echo ---- conectando ---- >> scripts\resultado_wifi.txt
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 30 >> scripts\resultado_wifi.txt 2>&1
echo Pronto.
pause >nul
