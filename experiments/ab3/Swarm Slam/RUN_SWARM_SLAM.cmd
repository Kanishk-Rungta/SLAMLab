@echo off
rem run for Swarm Slam, with the benchmark Python environment (.venv).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\Standard Environment\tools\run_with_bench_python.ps1" "%~dp0run_swarm_slam.py" %*
set RESULT=%ERRORLEVEL%
echo.
pause
exit /b %RESULT%
