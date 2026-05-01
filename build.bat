@echo off
echo Building DownYT...
pyinstaller downyt.spec --clean
echo.
if exist dist\DownYT.exe (
    echo Build successful! Executable is at dist\DownYT.exe
) else (
    echo Build failed. Check output above for errors.
)
pause
