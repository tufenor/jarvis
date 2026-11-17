@echo off
cd /d C:\JARVIS
echo Gravando o LCD otimizado...
echo ---- envio ---- > scripts\resultado_lcd.txt
.venv\Scripts\mpremote.exe connect COM7 fs cp firmware\micropython\lcd_display.py :lcd_display.py >> scripts\resultado_lcd.txt 2>&1
timeout /t 2 >nul
.venv\Scripts\mpremote.exe connect COM7 reset >> scripts\resultado_lcd.txt 2>&1
echo. >> scripts\resultado_lcd.txt
.venv\Scripts\python.exe scripts\escutar_boot.py COM7 18 >> scripts\resultado_lcd.txt 2>&1
echo Pronto.
pause >nul
