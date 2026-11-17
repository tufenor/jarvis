@echo off
cd /d C:\JARVIS
echo O token sera digitado sem aparecer e salvo apenas como hash no perfil local.
.venv\Scripts\python.exe scripts\pc_agent.py --setup
if errorlevel 1 echo Falha ao configurar. Nenhum comando de energia foi executado.
pause
