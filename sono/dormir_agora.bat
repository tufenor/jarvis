@echo off
cd /d C:\JARVIS\sono
echo Suspendendo agora...
C:\JARVIS\.venv\Scripts\python.exe -c "import ctypes;ctypes.windll.powrprof.SetSuspendState(0,1,0)"
