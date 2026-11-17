$ErrorActionPreference = 'Stop'
Set-Location 'C:\JARVIS'

if (-not (Test-Path '.venv\Scripts\pyinstaller.exe')) {
    Write-Host 'Instalando PyInstaller no ambiente local...'
    .venv\Scripts\python.exe -m pip install 'pyinstaller>=6.10'
}

Write-Host 'Gerando JARVIS em modo onedir...'
.venv\Scripts\pyinstaller.exe --noconfirm --clean JARVIS.spec

# Configuração e dados do operador ficam fora do bundle para sobreviver a
# atualizações e não serem substituídos por uma nova compilação.
Copy-Item 'jarvis\config.json' 'dist\JARVIS\config.json' -Force
New-Item -ItemType Directory -Force 'dist\JARVIS\dados' | Out-Null
if (Test-Path 'dados\bloqueio.json') { Copy-Item 'dados\bloqueio.json' 'dist\JARVIS\dados\' -Force }
if (Test-Path 'dados\rosto.json') { Copy-Item 'dados\rosto.json' 'dist\JARVIS\dados\' -Force }
if (Test-Path 'dados\vozes.json') { Copy-Item 'dados\vozes.json' 'dist\JARVIS\dados\' -Force }

Write-Host ''
Write-Host 'Executável criado em C:\JARVIS\dist\JARVIS\JARVIS.exe'
