@echo off
cd /d C:\JARVIS
.venv\Scripts\python.exe -m serial.tools.list_ports -v > scripts\portas_detectadas.txt 2>&1
echo Pronto. Resultado em scripts\portas_detectadas.txt
pause >nul
