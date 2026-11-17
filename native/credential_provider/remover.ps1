#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$installDir = Join-Path ${env:ProgramFiles} 'JARVIS\CredentialProvider'
$installedDll = Join-Path $installDir 'JARVISCredentialProvider.dll'
$regsvr32 = Join-Path ${env:windir} 'System32\regsvr32.exe'
if (Test-Path -LiteralPath $installedDll) {
    $unregistration = Start-Process -FilePath $regsvr32 -ArgumentList "/s /u `"$installedDll`"" -Wait -PassThru
    if ($unregistration.ExitCode -ne 0) {
        throw "Desregistro do Credential Provider falhou com codigo $($unregistration.ExitCode)."
    }
}
if (Test-Path -LiteralPath $installDir) {
    Remove-Item -LiteralPath $installDir -Recurse -Force
}
Write-Output 'JARVIS Credential Provider removido; o login padrao do Windows permanece.'
