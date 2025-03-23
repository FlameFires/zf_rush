@echo off
setlocal enabledelayedexpansion

:: ===================================
:: ZF_RUSH Build & Publish Script v3.0
:: ===================================

echo ===================================
echo ZF_RUSH Package Build and Publish
echo ===================================

:: Basic Setup
set "VERSION="
set "ESC="
set "PYPI_TOKEN="

:: Windows Version Check
ver | find "10.0" >nul 2>&1
if %errorlevel% equ 0 (
    for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
)

:: Color Definitions
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "RESET=%ESC%[0m"

:: Read API Token
if not exist pypi.key (
    echo %RED%Error: pypi.key not found%RESET%
    exit /b 1
)
set /p PYPI_TOKEN=<pypi.key
set "PYPI_TOKEN=!PYPI_TOKEN: =!"

:: Tool Checks
echo %GREEN%Checking requirements...%RESET%
where uv >nul 2>&1 || (
    echo %RED%Error: uv not found%RESET%
    exit /b 1
)
where twine >nul 2>&1 || (
    echo %YELLOW%Installing twine...%RESET%
    pip install -q twine
)

:: Cleanup
echo %GREEN%Cleaning build environment...%RESET%
for %%d in (dist build zf_rush.egg-info) do (
    if exist %%d rmdir /s /q %%d
)

:: Version Extraction
echo %GREEN%Detecting version...%RESET%
for /f "tokens=2 delims==" %%v in ('findstr "version" pyproject.toml') do (
    set "VER=%%v"
    set "VER=!VER:"=!"
    set "VER=!VER: =!"
    set "VERSION=!VER!"
)
if not defined VERSION (
    echo %RED%Version detection failed%RESET%
    exit /b 1
)
echo Current version: %YELLOW%!VERSION!%RESET%

:: Build Process
echo %GREEN%Starting build...%RESET%
uv build --quiet
if !errorlevel! neq 0 (
    echo %RED%Build failed%RESET%
    exit /b 1
)

:: Build Verification
if not exist dist (
    echo %RED%Build artifacts not found%RESET%
    exit /b 1
)
echo %GREEN%Build success!%RESET%

:: Upload to PyPI
echo %GREEN%Uploading to PyPI...%RESET%
twine upload --non-interactive --disable-progress-bar --username __token__ --password "!PYPI_TOKEN!" dist/*
if !errorlevel! neq 0 (
    echo %RED%PyPI upload failed%RESET%
    exit /b 1
)

echo %GREEN%All operations completed successfully!%RESET%
echo Package available at: https://pypi.org/project/zf_rush/
endlocal