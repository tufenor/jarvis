@echo off
cd /d C:\JARVIS
.venv\Scripts\mpremote.exe connect COM7 reset
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 15 > scripts\resultado_ip.txt 2>&1
echo.
echo Pronto. Resultado em scripts\resultado_ip.txt
pause >nul
