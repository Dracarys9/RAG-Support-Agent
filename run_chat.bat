@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The project environment is missing.
    echo Run this once first: py -m venv .venv
    pause
    exit /b 1
)

if not exist "web\static\app.js" (
    echo The browser file web\static\app.js is missing.
    echo Copy the enhanced UI files into the web\static folder, then run this command again.
    pause
    exit /b 1
)

echo Preparing Aster ^& Row support chat...
".venv\Scripts\python.exe" -m pip install -e . --disable-pip-version-check --quiet
if errorlevel 1 (
    echo Dependency installation failed. Check the message above.
    pause
    exit /b 1
)

 echo Opening http://127.0.0.1:5000
start "" "http://127.0.0.1:5000"
echo The chat is running. Close this window or press Ctrl+C to stop it.
".venv\Scripts\python.exe" -m rag_support_agent.web_app
