@echo off
cd /d C:\JARVIS
echo Autorizacao do upload de videos do JARVIS no Google Drive.
echo Nao cole credenciais neste terminal.
echo.
.venv\Scripts\python.exe seguranca\autorizar_google_drive.py
echo.
pause
