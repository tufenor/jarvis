$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$vsRoot = (& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($vsRoot)) {
    throw 'Build Tools do Visual Studio com C++ nao foram encontrados.'
}

$vcvars = Join-Path $vsRoot 'VC\Auxiliary\Build\vcvars64.bat'
$msbuild = Join-Path $vsRoot 'MSBuild\Current\Bin\MSBuild.exe'
$project = Join-Path $root 'JARVISCredentialProvider.vcxproj'
$command = '"{0}" && "{1}" "{2}" /m /p:Configuration=Release /p:Platform=x64 /v:minimal' -f $vcvars, $msbuild, $project
cmd.exe /d /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw "Compilacao falhou com codigo $LASTEXITCODE."
}
