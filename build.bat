@echo off
if not exist vendor\ffmpeg\ffmpeg.exe (
    echo ffmpeg not found in vendor\ffmpeg, downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -File setup_ffmpeg.ps1
    if errorlevel 1 (
        echo Could not download ffmpeg. Put ffmpeg.exe in vendor\ffmpeg manually.
        pause
        exit /b 1
    )
)
echo Building DownYT...
pyinstaller downyt.spec --clean --noconfirm
echo.
if %errorlevel% neq 0 (
    echo Build failed. Check output above for errors.
) else (
    echo Build successful! Executable is at dist\DownYT.exe
)
pause
