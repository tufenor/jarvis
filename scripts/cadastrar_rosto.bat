@echo off
setlocal
cd /d C:\JARVIS
echo Cadastro facial local do JARVIS.
echo Fique diante da webcam, com o rosto iluminado, e mova a cabeca para os lados quando solicitado.
echo Nenhuma fotografia sera guardada; somente um vetor facial sera salvo.
echo.
.venv\Scripts\python.exe -m jarvis --cadastrar-rosto
if errorlevel 1 exit /b %errorlevel%
if not exist dist\JARVIS\dados mkdir dist\JARVIS\dados
copy /Y dados\rosto.json dist\JARVIS\dados\rosto.json >nul
echo.
echo Perfil copiado para o executavel em dist\JARVIS\dados\rosto.json
pause
endlocal
