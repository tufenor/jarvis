@echo off
cd /d C:\JARVIS
echo Coletando dados de rede...
echo ======== GETMAC ======== > scripts\resultado_rede.txt
getmac /v /fo list >> scripts\resultado_rede.txt 2>&1
echo. >> scripts\resultado_rede.txt
echo ======== IPCONFIG ======== >> scripts\resultado_rede.txt
ipconfig /all >> scripts\resultado_rede.txt 2>&1
echo. >> scripts\resultado_rede.txt
echo ======== ARP ======== >> scripts\resultado_rede.txt
arp -a >> scripts\resultado_rede.txt 2>&1
echo Pronto.
pause >nul
