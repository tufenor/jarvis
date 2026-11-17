@echo off
cd /d C:\JARVIS
echo Instalando o que a vigilancia precisa (webcam + Telegram)...
.venv\Scripts\python.exe -m pip install -r seguranca\requirements.txt
echo.
echo ============================================
echo Instalacao concluida.
pause >nul
