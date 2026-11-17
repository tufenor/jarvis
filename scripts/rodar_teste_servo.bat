@echo off
cd /d C:\JARVIS
echo Rodando teste do servo/PCA9685 canal 0 (seguro, movimento curto, desliga sozinho)...
.venv\Scripts\mpremote.exe connect COM7 run firmware\micropython\teste_servo_pca9685.py > scripts\resultado_servo.txt 2>&1
.venv\Scripts\mpremote.exe connect COM7 reset
echo.
echo Teste terminado. Resultado em scripts\resultado_servo.txt
pause >nul
