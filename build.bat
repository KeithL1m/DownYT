@echo off
echo Building DownYT...
pyinstaller downyt.spec --clean --noconfirm
echo.
if %errorlevel% neq 0 (
    echo Build failed. Check output above for errors.
) else (
    echo Build successful! Executable is at dist\DownYT.exe
)
pause
