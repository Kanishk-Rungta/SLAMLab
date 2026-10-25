@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_door_slam_original.ps1" -BuildOnly %*
set RESULT=%ERRORLEVEL%
echo.
pause
exit /b %RESULT%
