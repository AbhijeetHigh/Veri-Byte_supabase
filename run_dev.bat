@echo off
title Veri-Byte Development Mode (Hot Reload)
echo =====================================================================
echo   Starting Veri-Byte in Full Development Mode
echo   - Backend: http://127.0.0.1:8000
echo   - React Dev Server: http://127.0.0.1:5173
echo =====================================================================

set "PATH=C:\Users\ASHMIT\nodejs;%PATH%"

if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

start "Veri-Byte Backend API" cmd /k "cd /d ""%~dp0backend"" && ""%PYTHON_EXE%"" server.py"
timeout /t 2 /nobreak >nul
start "Veri-Byte React Dev Server" cmd /k "cd /d ""%~dp0frontend"" && node node_modules\vite\bin\vite.js"

echo Both services launched!
