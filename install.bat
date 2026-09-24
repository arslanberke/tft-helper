@echo off
REM One-time setup: runs start.bat's install steps, then drops a
REM "TFT Advisor" shortcut on the Desktop. Double-click that shortcut
REM from then on — it starts the decision service; launch TFT + the
REM Overwolf app as usual.
cd /d "%~dp0"

call "%~dp0start.bat" --install-only

powershell -NoProfile -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([IO.Path]::Combine($env:USERPROFILE,'Desktop','TFT Advisor.lnk')); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='shell32.dll,44'; $s.Description='Start the TFT comp advisor service'; $s.Save()"

echo.
echo Shortcut created: Desktop\TFT Advisor.lnk
echo.
echo Remaining one-time steps (can't be automated):
echo   1. Overwolf: enable dev mode, "Load unpacked extension" -^> %~dp0overwolf-app
echo   2. Optional: set TYPESAFE_API_KEY (Jev) or KEV_URL (local Kev)
pause
