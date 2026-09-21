# Downloads the latest ffmpeg "essentials" build (gyan.dev) into vendor/ffmpeg/
# so downyt.spec can bundle it. Skips the download if ffmpeg.exe is already there.
param(
    [string]$Dest = (Join-Path $PSScriptRoot 'vendor\ffmpeg')
)

$ErrorActionPreference = 'Stop'
$exe = Join-Path $Dest 'ffmpeg.exe'
if (Test-Path $exe) {
    Write-Host "ffmpeg already present: $exe"
    exit 0
}

$url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('downyt_ffmpeg_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    Write-Host 'Downloading ffmpeg (about 100 MB)...'
    $zip = Join-Path $tmp 'ffmpeg.zip'
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $bin = Get-ChildItem $tmp -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if (-not $bin) { throw 'ffmpeg.exe not found in the downloaded archive.' }
    New-Item -ItemType Directory -Force $Dest | Out-Null
    Copy-Item $bin.FullName $exe
    $license = Get-ChildItem $tmp -Recurse -Filter LICENSE | Select-Object -First 1
    if ($license) { Copy-Item $license.FullName (Join-Path $Dest 'LICENSE') -Force }
    Write-Host "Installed: $exe"
    & $exe -version | Select-Object -First 1
} finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
