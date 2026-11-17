@echo off
cd /d C:\JARVIS
echo Varrendo o barramento I2C...
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\diagnostico_i2c.py > scripts\resultado_i2c.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_i2c.txt 2>&1
echo Pronto.
pause >nul
