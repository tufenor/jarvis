@echo off
rem Remove o launcher do JARVIS da inicializacao do Windows.
title JARVIS - remover da inicializacao
set ARQ=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.lnk
if exist "%ARQ%" del /Q "%ARQ%"
set ARQVBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\JARVIS.vbs
if exist "%ARQVBS%" del /Q "%ARQVBS%"
echo Pronto. O JARVIS nao abrira mais automaticamente.
echo O atalho do ChatGPT nao foi alterado.
pause
