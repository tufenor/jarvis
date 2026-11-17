@echo off
rem Configura o launcher rapido do JARVIS e o inicio do ChatGPT.
rem O launcher usa um atalho com icone e nao espera 25 segundos.
cd /d C:\JARVIS
title JARVIS - instalar na inicializacao
if not exist .venv\Scripts\pythonw.exe goto sem_venv
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\JARVIS\scripts\configurar_inicio_rapido.ps1"
if errorlevel 1 goto falhou
echo.
echo PRONTO. O JARVIS vai abrir rapidamente no proximo login do Windows.
echo O Ctrl+Alt+Del continua disponivel para recuperacao.
echo.
goto fim
:sem_venv
echo ERRO: nao achei C:\JARVIS\.venv\Scripts\pythonw.exe
goto fim
:falhou
echo ERRO: nao consegui configurar os atalhos de inicializacao.
:fim
pause
