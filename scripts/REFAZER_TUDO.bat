@echo off
cd /d C:\JARVIS
echo Refazendo todos os testes. Aguarde ~90 segundos.
echo ======== 1. PORTA ======== > scripts\resultado_tudo.txt
.venv\Scripts\python.exe -m serial.tools.list_ports -v >> scripts\resultado_tudo.txt 2>&1
timeout /t 2 >nul
echo. >> scripts\resultado_tudo.txt
echo ======== 2. TESTE ELETRICO DO I2C ======== >> scripts\resultado_tudo.txt
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\diagnostico_i2c.py >> scripts\resultado_tudo.txt 2>&1
timeout /t 4 >nul
echo. >> scripts\resultado_tudo.txt
echo ======== 3. RC522 ======== >> scripts\resultado_tudo.txt
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\teste_rc522_cartao.py >> scripts\resultado_tudo.txt 2>&1
timeout /t 4 >nul
echo. >> scripts\resultado_tudo.txt
echo ======== 4. SENSORES (LED/DHT/PIR/LCD) ======== >> scripts\resultado_tudo.txt
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_tudo.txt 2>&1
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 20 >> scripts\resultado_tudo.txt 2>&1
echo Pronto.
pause >nul
