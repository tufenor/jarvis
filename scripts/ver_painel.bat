@echo off
cd /d C:\JARVIS
echo Reiniciando a placa e escutando...
echo ---- boot ---- > scripts\resultado_deploy.txt
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_deploy.txt 2>&1
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 22 >> scripts\resultado_deploy.txt 2>&1
echo Pronto.
pause >nul
