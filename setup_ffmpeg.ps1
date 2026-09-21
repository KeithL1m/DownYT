# Downloads an ffmpeg "essentials" build (gyan.dev) into vendor/ffmpeg/ so
# downyt.spec can bundle it. Skips the download if ffmpeg.exe is already there.
#
# Sources are tried in order, two attempts each. The pinned GitHub release comes
# first (the exact version DownYT is tested with, and more reliable than
# gyan.dev, which has been seen returning 503 / refusing connections).
param(
    [string]$Dest = (Join-Path $PSScriptRoot 'vendor\ffmpeg')
)

$ErrorActionPreference = 'Stop'
$exe = Join-Path $Dest 'ffmpeg.exe'
if (Test-Path $exe) {
    Write-Host "ffmpeg already present: $exe"
    exit 0
}

$urls = @(
    'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip',
    'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
)
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('downyt_ffmpeg_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'ffmpeg.zip'
    $ok = $false
    foreach ($url in $urls) {
        foreach ($attempt in 1..2) {
            try {
                Write-Host "Downloading ffmpeg (about 100 MB) from $url (attempt $attempt)..."
                Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
                if ((Get-Item $zip).Length -lt 50MB) { throw 'Downloaded file looks truncated.' }
                $ok = $true
                break
            } catch {
                Write-Host "  failed: $($_.Exception.Message)"
                Start-Sleep -Seconds 2
            }
        }
        if ($ok) { break }
    }
    if (-not $ok) { throw 'All ffmpeg download sources failed.' }

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
