@echo off
setlocal
cd /d "%~dp0"

echo Starting Fieldnotes at http://127.0.0.1:8000 ...
where py >nul 2>nul
if %errorlevel% equ 0 (
  start "Fieldnotes server" /min cmd /c "py -3 -m uvicorn backend.app.main:app --reload --port 8000"
) else (
  start "Fieldnotes server" /min cmd /c "python -m uvicorn backend.app.main:app --reload --port 8000"
)
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000"
endlocal
