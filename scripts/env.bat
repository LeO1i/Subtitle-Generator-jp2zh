@echo off
REM Resolve project root (parent of scripts/)
cd /d "%~dp0\.."

set "ROOT=%CD%"
set "VENV_DIR=%ROOT%\.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"
set "PYW=%VENV_DIR%\Scripts\pythonw.exe"

REM Usage: call scripts\env.bat [require]
REM   require = fail if .venv is missing
if /i "%~1"=="require" (
    if not exist "%PY%" (
        echo 错误：未找到虚拟环境
        echo 请先运行 install.bat 安装依赖
        exit /b 1
    )
)
