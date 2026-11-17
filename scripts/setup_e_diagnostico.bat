@echo off
cd /d C:\JARVIS
echo Instalando dependencias (pode levar alguns minutos)...
echo Instalando... > scripts\resultado_setup.txt
.venv\Scripts\python.exe -m pip install pyserial requests opencv-python psutil >> scripts\resultado_setup.txt 2>&1
echo. >> scripts\resultado_setup.txt
echo ======== DIAGNOSTICO ======== >> scripts\resultado_setup.txt
.venv\Scripts\python.exe _verificar.py >> scripts\resultado_setup.txt 2>&1
echo Pronto.
pause >nul
