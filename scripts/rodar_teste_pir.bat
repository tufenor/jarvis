@echo off
cd /d C:\JARVIS
.venv\Scripts\python.exe scripts\teste_pir_serial.py COM7 > scripts\resultado_pir.txt 2>&1
echo.
echo Teste terminado. Resultado salvo em scripts\resultado_pir.txt
echo Pressione qualquer tecla para fechar.
pause >nul
