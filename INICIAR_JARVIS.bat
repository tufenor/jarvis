@echo off
rem Abre manualmente o aplicativo JARVIS: o console permanece disponivel.
cd /d C:\JARVIS
title JARVIS
if not exist .venv\Scripts\python.exe goto sem_venv
.venv\Scripts\python.exe -m jarvis
echo.
echo O JARVIS parou. Veja a mensagem acima.
pause
goto fim
:sem_venv
echo ERRO: nao achei C:\JARVIS\.venv.
pause
:fim
