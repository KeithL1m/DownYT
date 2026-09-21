# Downloads the background-removal model (rembg's u2net, ~176 MB) into
# vendor/models/ so downyt.spec can bundle it. Skips it if already present.
param(
    [string]$Dest = (Join-Path $PSScriptRoot 'vendor\models')
)

$ErrorActionPreference = 'Stop'
$model = Join-Path $Dest 'u2net.onnx'
if (Test-Path $model) {
    Write-Host "Model already present: $model"
    exit 0
}

$url = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx'
New-Item -ItemType Directory -Force $Dest | Out-Null
$tmp = "$model.download"
try {
    Write-Host 'Downloading background removal model (about 176 MB)...'
    Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
    if ((Get-Item $tmp).Length -lt 100MB) { throw 'Downloaded model looks truncated.' }
    Move-Item $tmp $model
    Write-Host "Installed: $model"
} finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
}
