@echo off
cd /d C:\JARVIS
echo JARVIS - vigilancia ativa. Feche esta janela para parar.
echo.
.venv\Scripts\python.exe seguranca\jarvis_seguranca.py
echo.
pause >nul
