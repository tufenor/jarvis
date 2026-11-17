@echo off
cd /d C:\JARVIS
set PORT=%~1
if "%PORT%"=="" set PORT=COM7
echo Enviando firmware JARVIS para %PORT%...
.venv\Scripts\mpremote.exe connect %PORT% fs cp firmware\micropython\wake_on_lan.py :wake_on_lan.py > scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
.venv\Scripts\mpremote.exe connect %PORT% fs cp firmware\micropython\lcd_display.py :lcd_display.py >> scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
.venv\Scripts\mpremote.exe connect %PORT% fs cp firmware\micropython\mobile_panel.py :mobile_panel.py >> scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
.venv\Scripts\mpremote.exe connect %PORT% fs cp firmware\micropython\pc_bridge.py :pc_bridge.py >> scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
.venv\Scripts\mpremote.exe connect %PORT% fs cp firmware\micropython\main_network.py :main.py >> scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
.venv\Scripts\mpremote.exe connect %PORT% reset >> scripts\resultado_flash.txt 2>&1
if errorlevel 1 goto failed
echo.
echo Envio concluido. Resultado em scripts\resultado_flash.txt
goto end
:failed
echo Falha no envio ou reinicio. Consulte scripts\resultado_flash.txt antes de tentar novamente.
:end
pause >nul
