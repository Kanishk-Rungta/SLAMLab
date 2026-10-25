@echo off
cd /d "%~dp0"
if not exist "runs\LATEST.txt" (echo No original DOOR-SLAM run found. & pause & exit /b)
set /p RUN=<"runs\LATEST.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_door_slam_original.ps1" -EvaluateRun "%RUN%"
pause
