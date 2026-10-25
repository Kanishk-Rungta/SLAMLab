@echo off
cd /d "%~dp0"
if not exist "runs\LATEST.txt" (echo No D2SLAM run found. & pause & exit /b)
set /p RUN=<"runs\LATEST.txt"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_d2slam.ps1" -EvaluateRun "%RUN%"
pause
