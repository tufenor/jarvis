param(
    [switch]$SemChatGPT
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $raiz ".venv\Scripts\pythonw.exe"
$executavel = Join-Path $raiz "dist\JARVIS\JARVIS.exe"
$icone = Join-Path $raiz "assets\jarvis.ico"
$startup = [Environment]::GetFolderPath("Startup")
$atalhoJarvis = Join-Path $startup "JARVIS.lnk"
$atalhoChatGPT = Join-Path $startup "ChatGPT.lnk"
$vbsAntigo = Join-Path $startup "JARVIS.vbs"

if (-not (Test-Path -LiteralPath $pythonw) -and -not (Test-Path -LiteralPath $executavel)) {
    throw "JARVIS pythonw.exe not found: $pythonw"
}
if (-not (Test-Path -LiteralPath $icone)) {
    throw "JARVIS icon not found: $icone"
}

$shell = New-Object -ComObject WScript.Shell

$jarvis = $shell.CreateShortcut($atalhoJarvis)
$jarvis.TargetPath = if (Test-Path -LiteralPath $executavel) { $executavel } else { $pythonw }
$jarvis.Arguments = if (Test-Path -LiteralPath $executavel) { "" } else { "-m jarvis" }
$jarvis.WorkingDirectory = if (Test-Path -LiteralPath $executavel) { Split-Path $executavel } else { $raiz }
$jarvis.IconLocation = "$icone,0"
$jarvis.Description = "JARVIS post-login lock"
$jarvis.Save()

# Do not launch both the old delayed script and the new shortcut.
if (Test-Path -LiteralPath $vbsAntigo) {
    Remove-Item -LiteralPath $vbsAntigo -Force
}

if (-not $SemChatGPT) {
    $chatExe = $null
    $runningChat = Get-Process -Name ChatGPT -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($runningChat) {
        try { $chatExe = $runningChat.Path } catch { $chatExe = $null }
    }
    if (-not $chatExe) {
        $pacotes = @(Get-ChildItem "$env:ProgramFiles\WindowsApps" -Directory -Filter "OpenAI.Codex_*__2p2nqsd0c76g0" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending)
        if ($pacotes.Count -gt 0) {
            $chatExe = Join-Path $pacotes[0].FullName "app\ChatGPT.exe"
        }
    }

    if ($chatExe -and (Test-Path -LiteralPath $chatExe)) {
        $packageDir = Split-Path (Split-Path $chatExe -Parent) -Parent
        $packageName = Split-Path $packageDir -Leaf
        $match = [regex]::Match($packageName, '^(.+?)_[0-9.]+_x64__([a-z0-9]+)$')
        if ($match.Success) {
            $family = $match.Groups[1].Value + "_" + $match.Groups[2].Value
            $chat = $shell.CreateShortcut($atalhoChatGPT)
            $chat.TargetPath = Join-Path $env:WINDIR "explorer.exe"
            $chat.Arguments = "shell:AppsFolder\$family!App"
            $chat.WorkingDirectory = $env:WINDIR
            $chat.IconLocation = "$chatExe,0"
            $chat.Description = "Start ChatGPT with Windows"
            $chat.Save()
            Write-Output "ChatGPT startup shortcut: $atalhoChatGPT"
        }
    }
}

Write-Output "JARVIS startup shortcut: $atalhoJarvis"
Write-Output "Ctrl+Alt+Del remains available as Windows recovery."
