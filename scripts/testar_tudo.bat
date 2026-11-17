@echo off
cd /d C:\JARVIS
echo ---- PORTAS ---- > scripts\resultado_geral.txt
.venv\Scripts\python.exe -m serial.tools.list_ports -v >> scripts\resultado_geral.txt 2>&1
echo. >> scripts\resultado_geral.txt
echo ---- TESTE ELETRICO I2C ---- >> scripts\resultado_geral.txt
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\diagnostico_i2c.py >> scripts\resultado_geral.txt 2>&1
echo. >> scripts\resultado_geral.txt
echo ---- RC522 ---- >> scripts\resultado_geral.txt
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\teste_rc522_cartao.py >> scripts\resultado_geral.txt 2>&1
echo. >> scripts\resultado_geral.txt
echo ---- SENSORES (serial) ---- >> scripts\resultado_geral.txt
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_geral.txt 2>&1
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 20 >> scripts\resultado_geral.txt 2>&1
echo Pronto.
pause >nul
