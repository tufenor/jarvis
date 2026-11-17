@echo off
cd /d C:\JARVIS
echo Rodando teste do RC522 (ate 16s, duas tentativas de SPI)...
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\teste_rc522_cartao.py > scripts\resultado_rc522.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 reset
echo.
echo Teste terminado. Resultado em scripts\resultado_rc522.txt
pause >nul
