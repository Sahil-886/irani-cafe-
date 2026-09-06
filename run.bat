@echo off
echo Starting Irani Cafe Management System...

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using Python launcher (py -3)...
    py -3 app.py
    goto end
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using Python (python)...
    python app.py
    goto end
)

echo.
echo [ERROR] Python 3 could not be found on this system.
echo Please install Python 3.8 or newer from https://www.python.org/
echo Ensure "Add Python to PATH" is checked during installation.
echo.
pause

:end
