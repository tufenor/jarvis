@echo off
setlocal
cd /d C:\JARVIS
echo Configuracao local do codigo de desbloqueio do JARVIS.
echo O codigo nao sera exibido nem salvo em texto puro.
echo.
.venv\Scripts\python.exe -m jarvis --codigo-bloqueio
echo.
pause
endlocal
