@echo off
setlocal

:: Pede elevacao UAC se nao for admin.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Pedindo elevacao...
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
    exit /b
)

echo.
echo =========================================================
echo  JARVIS - Configurando o Windows para Wake-on-LAN
echo =========================================================
echo.

echo [1/3] Desligando hibernacao (powercfg -h off)...
powercfg -h off
if %errorlevel% equ 0 (echo     OK - hibernacao desligada) else (echo     FALHOU)

echo.
echo [2/3] Desligando Inicializacao Rapida...
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power" ^
    /v HiberbootEnabled /t REG_DWORD /d 0 /f >nul 2>&1
if %errorlevel% equ 0 (echo     OK - inicializacao rapida desligada) else (echo     FALHOU)

echo.
echo [3/3] Permitindo que o Wi-Fi acorde o PC...
powershell -NoProfile -Command ^
    "$ad = Get-NetAdapter -Name 'Wi-Fi'; " ^
    "if ($ad) { " ^
    "    Enable-NetAdapterPowerManagement -Name 'Wi-Fi' -WakeOnMagicPacket -WakeOnPattern -ErrorAction SilentlyContinue; " ^
    "    Set-NetAdapterPowerManagement -Name 'Wi-Fi' -WakeOnMagicPacket Enabled -WakeOnPattern Enabled -AllowComputerToTurnOffDevice Disabled -ErrorAction SilentlyContinue; " ^
    "    powercfg -deviceenablewake $ad.InterfaceDescription; " ^
    "    Write-Host '    OK - Wi-Fi configurado para acordar' " ^
    "} else { Write-Host '    FALHOU - adaptador Wi-Fi nao encontrado' }"

echo.
echo =========================================================
echo  O que AINDA precisa ser feito manualmente na BIOS:
echo =========================================================
echo.
echo  1. Reiniciar o PC
echo  2. Entrar no setup da BIOS/UEFI (geralmente DEL ou F2 na POST)
echo  3. Procurar e ATIVAR:
echo        - "Wake on LAN"
echo        - "Wake on PCI-E"
echo        - "Power On By PCI-E Devices"
echo  4. Procurar e DESATIVAR:
echo        - "ErP Ready"
echo        - "Deep Sleep"
echo        - "EuP"
echo  5. Salvar e sair (geralmente F10)
echo.
echo Depois de tudo, mande o PC dormir (Start -^> Suspender) e teste
echo o botao LIGAR PC do app JARVIS do celular.
echo.
pause
