@echo off
title Build Standalone NX2navi_Trainer.exe
echo Installing PyInstaller (if not already installed)...
py -m pip install pyinstaller pymem keyboard
echo.
echo Compiling NX2navi_Trainer.py into a single standalone .exe...
py -m PyInstaller --noconfirm --onefile --windowed --name "NX2navi_Trainer" NX2navi_Trainer.py
echo.
if exist "dist\NX2navi_Trainer.exe" (
    copy /Y "dist\NX2navi_Trainer.exe" "NX2navi_Trainer.exe" >nul
    echo ====================================================
    echo   SUCCESS! NX2navi_Trainer.exe is ready!
    echo ====================================================
) else (
    echo [ERROR] Build failed. Check the messages above.
)
pause
