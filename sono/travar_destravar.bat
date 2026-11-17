@echo off
cd /d C:\JARVIS\sono
if exist NAO_SUSPENDER.txt (
 del NAO_SUSPENDER.txt
 echo TRAVA REMOVIDA - o PC voltou a poder suspender sozinho.
) else (
 echo trava > NAO_SUSPENDER.txt
 echo TRAVA ATIVA - o PC nao vai suspender ate voce rodar isto de novo.
)
echo.
pause
