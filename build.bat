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
if not exist vendor\models\u2net.onnx (
    echo Background removal model not found, downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -File setup_models.ps1
    if errorlevel 1 (
        echo Could not download the model. Put u2net.onnx in vendor\models manually.
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
    echo Build successful! Run dist\DownYT\DownYT.exe - copy the whole dist\DownYT folder to install elsewhere.
)
pause
