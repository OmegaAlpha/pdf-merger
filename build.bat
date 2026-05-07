@echo off
setlocal enabledelayedexpansion

echo ===================================
echo   PDF Merger Executable Builder
echo ===================================
echo.

REM Define paths
set "VENV_DIR=.venv"
set "SPEC_FILE=pdf_merger.spec"
set "VENV_PYINSTALLER=%VENV_DIR%\Scripts\pyinstaller.exe"

REM Check if the virtual environment exists
if not exist "%VENV_DIR%" (
    echo ERROR: Virtual environment folder "%VENV_DIR%" not found.
    echo Please create it by running:
    echo   python -m venv %VENV_DIR%
    echo Then activate it and install requirements:
    echo   %VENV_DIR%\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if pyinstaller exists in the virtual environment
if not exist "%VENV_PYINSTALLER%" (
    echo ERROR: PyInstaller not found at %VENV_PYINSTALLER%
    echo Please activate the virtual environment and install dependencies:
    echo   %VENV_DIR%\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

REM Check if the spec file exists
if not exist "%SPEC_FILE%" (
    echo ERROR: Spec file "%SPEC_FILE%" not found.
    echo This file is required to build the project correctly with all assets.
    pause
    exit /b 1
)

echo Using PyInstaller from: %VENV_PYINSTALLER%
echo Building using spec: %SPEC_FILE%
echo.

echo Cleaning previous build directories (dist\, build\)...
if exist "dist" rd /s /q "dist"
if exist "build" rd /s /q "build"
echo Done cleaning.
echo.

echo Starting PyInstaller... Please wait, this might take a while.
echo Command: "%VENV_PYINSTALLER%" --clean --noconfirm "%SPEC_FILE%"
echo ------------------------------------------------------------

REM Run PyInstaller using the full path from the venv
call "%VENV_PYINSTALLER%" --clean --noconfirm "%SPEC_FILE%"

REM Check the result
if %errorlevel% neq 0 (
    echo ------------------------------------------------------------
    echo ERROR: PyInstaller failed with error code %errorlevel%!
    echo Please check the output above for specific errors.
    echo ------------------------------------------------------------
    pause
    exit /b %errorlevel%
)

echo ------------------------------------------------------------
echo Build successful!
echo Executable created in the dist\ directory.
echo ------------------------------------------------------------
echo.
pause