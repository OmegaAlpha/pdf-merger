@echo off
echo ===================================
echo   PDF Merger Executable Builder
echo ===================================
echo.

REM Define relative paths (assuming this .bat file is in the project root)
set VENV_DIR=.venv
set SCRIPT_FILE=source\pdf_merger.py
set OUTPUT_NAME=PDFMerger
set VENV_PYINSTALLER=%VENV_DIR%\Scripts\pyinstaller.exe

REM Check if the virtual environment exists
if not exist "%VENV_DIR%" (
    echo ERROR: Virtual environment folder "%VENV_DIR%" not found.
    echo Please ensure the virtual environment exists in the project root.
    pause
    exit /b 1
)

REM Check if pyinstaller exists in the virtual environment
if not exist "%VENV_PYINSTALLER%" (
    echo   "ERROR: PyInstaller not found at %VENV_PYINSTALLER%"
    echo   Please activate the virtual environment:
    echo   "%VENV_DIR%\Scripts\activate.bat (CMD)"
    echo   or
    echo   "%VENV_DIR%\Scripts\Activate.ps1 (PowerShell - might require execution policy change)"
    echo.
    echo   #Then run: pip install pyinstaller
    pause
    exit /b 1
)

REM Check if the source script exists
if not exist "%SCRIPT_FILE%" (
    echo ERROR: Source script "%SCRIPT_FILE%" not found.
    pause
    exit /b 1
)

echo Using PyInstaller from: %VENV_PYINSTALLER%
echo Building script: %SCRIPT_FILE%
echo Output name: %OUTPUT_NAME%.exe
echo.

echo Cleaning previous build directories (dist/, build/, *.spec)...
if exist dist rd /s /q dist
if exist build rd /s /q build
del /q "%OUTPUT_NAME%.spec" > nul 2>&1
echo Done cleaning.
echo.

echo Starting PyInstaller... Please wait, this might take a while.
echo Command: "%VENV_PYINSTALLER%" --onedir --windowed --clean --name "%OUTPUT_NAME%" "%SCRIPT_FILE%"
echo ------------------------------------------------------------

REM Run PyInstaller using the full path from the venv
call "%VENV_PYINSTALLER%" --onedir --windowed --clean --name "%OUTPUT_NAME%" "%SCRIPT_FILE%"

REM Check the result
if %errorlevel% neq 0 (
    echo ------------------------------------------------------------
    echo ERROR: PyInstaller failed with error code "%errorlevel%"!
    echo Please check the output above for specific errors.
    echo Common issues include missing packages or hidden imports.
    echo ------------------------------------------------------------
    pause
    exit /b %errorlevel%
)

echo ------------------------------------------------------------
echo Build successful!
echo Executable created: dist\%OUTPUT_NAME%.exe
echo ------------------------------------------------------------
echo.
pause