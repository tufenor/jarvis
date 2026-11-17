$ErrorActionPreference = 'Stop'
$raiz = 'C:\JARVIS'
$pasta = Join-Path $raiz 'modelos\rosto'
New-Item -ItemType Directory -Force -Path $pasta | Out-Null

$arquivos = @(
    @{
        Nome = 'face_detection_yunet_2023mar.onnx'
        Url = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
    },
    @{
        Nome = 'face_recognition_sface_2021dec.onnx'
        Url = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx'
    }
)

foreach ($item in $arquivos) {
    $destino = Join-Path $pasta $item.Nome
    if (-not (Test-Path -LiteralPath $destino) -or (Get-Item -LiteralPath $destino).Length -lt 100000) {
        Write-Host "Baixando $($item.Nome)..."
        $temporario = "$destino.download"
        Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue
        Invoke-WebRequest -Uri $item.Url -OutFile $temporario
        if ((Get-Item -LiteralPath $temporario).Length -lt 100000) {
            throw "download incompleto: $($item.Nome)"
        }
        Move-Item -LiteralPath $temporario -Destination $destino -Force
    } else {
        Write-Host "Já existe: $($item.Nome)"
    }
}

Write-Host ''
Write-Host 'Modelos prontos. Para cadastrar o rosto:'
Write-Host '  C:\JARVIS\.venv\Scripts\python.exe -m jarvis --cadastrar-rosto'
