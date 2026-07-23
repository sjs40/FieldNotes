@echo off
setlocal
cd /d "%~dp0"

echo Starting Fieldnotes at http://127.0.0.1:8000 ...
where py >nul 2>nul
if %errorlevel% equ 0 (
  set "PYTHON_CMD=py -3"
) else (
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% -c "import fastapi, sqlalchemy, yfinance" >nul 2>nul
if errorlevel 1 (
  echo Installing Fieldnotes dependencies. This only happens when they are missing.
  %PYTHON_CMD% -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo.
    echo Dependency installation failed. Please install Python with pip and try again.
    pause
    exit /b 1
  )
)

start "Fieldnotes server" /min cmd /c "%PYTHON_CMD% -m uvicorn backend.app.main:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000"
endlocal
