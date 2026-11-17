@echo off
setlocal
cd /d C:\JARVIS
echo Configuracao local da ponte Alexa - JARVIS
echo.
echo Os valores sensiveis serao digitados somente neste terminal.
echo Nao cole senhas, chaves ou o conteudo dos arquivos no chat.
echo.
.venv\Scripts\python.exe -m integracoes.alexa.preparar --preparar
if errorlevel 1 goto :fim
.venv\Scripts\python.exe -m integracoes.alexa.preparar --empacotar-hosted
echo.
echo Agora envie integracoes\alexa\alexa-hosted-code-configurado.zip na aba Code da skill e clique Deploy.
:fim
echo.
pause
endlocal
