#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dll = Join-Path $root 'build\x64\Release\JARVISCredentialProvider.dll'
if (-not (Test-Path -LiteralPath $dll)) {
    throw 'Compile primeiro com build_x64.ps1.'
}

$installDir = Join-Path ${env:ProgramFiles} 'JARVIS\CredentialProvider'
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
$installedDll = Join-Path $installDir 'JARVISCredentialProvider.dll'
Copy-Item -LiteralPath $dll -Destination $installedDll -Force

$regsvr32 = Join-Path ${env:windir} 'System32\regsvr32.exe'
$registration = Start-Process -FilePath $regsvr32 -ArgumentList "/s `"$installedDll`"" -Wait -PassThru
if ($registration.ExitCode -ne 0) {
    throw "Registro do Credential Provider falhou com codigo $($registration.ExitCode)."
}
Write-Output "JARVIS Credential Provider instalado em $installedDll"
Write-Output 'O bloco visual nao autentica e nao injeta senha; use Windows Hello/PIN.'
