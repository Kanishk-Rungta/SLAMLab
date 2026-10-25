@echo off
cd /d "%~dp0"
if not exist "runs\LATEST.txt" (echo No D2SLAM run found. & pause & exit /b)
set /p RUN=<"runs\LATEST.txt"
if not exist "%RUN%\benchmark" (echo Latest run folder is missing. & pause & exit /b)
type nul > "%RUN%\STOP"
type nul > "%RUN%\benchmark\STOP"
echo Stop requested for %RUN%
pause
