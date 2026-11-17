@echo off
cd /d C:\JARVIS
.venv\Scripts\python.exe scripts\teste_completo_serial.py COM7 > scripts\resultado_teste.txt 2>&1
echo.
echo Teste terminado. Resultado salvo em scripts\resultado_teste.txt
echo Pressione qualquer tecla para fechar.
pause >nul
