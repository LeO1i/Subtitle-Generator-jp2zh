@echo off
chcp 65001 >nul

echo 日语字幕生成器 - 安装脚本

echo ==========================

echo.



cd /d "%~dp0"

call scripts\env.bat



REM Check if Python is available

echo 正在检查 Python 安装情况...

set "BOOTSTRAP_PY=python"

py -3.11 --version >nul 2>&1

if not errorlevel 1 (

    set "BOOTSTRAP_PY=py -3.11"

)



%BOOTSTRAP_PY% --version >nul 2>&1

if errorlevel 1 (

    echo 错误：未找到 Python

    echo.

    echo 请安装 Python 3.9 或更高版本：

    echo 1. 访问 https://python.org

    echo 2. 下载并安装 Python 3.9+

    echo 3. 安装时勾选 "Add Python to PATH"

    echo 4. 安装完成后重新运行本脚本

    echo.

    pause

    exit /b 1

)



%BOOTSTRAP_PY% -c "import sys; raise SystemExit(0 if (3, 9) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1

if errorlevel 1 (

    echo 错误：当前 Python 版本不适合本项目依赖

    echo 建议安装 Python 3.11，并确保 py -3.11 可用

    pause

    exit /b 1

)



echo 已找到 Python ✓



if not exist "%PY%" (

    echo.

    echo 正在创建虚拟环境 .venv ...

    %BOOTSTRAP_PY% -m venv "%VENV_DIR%"

    if errorlevel 1 (

        echo 错误：虚拟环境创建失败

        pause

        exit /b 1

    )

    echo 虚拟环境创建完成 ✓

)



call scripts\env.bat require

if errorlevel 1 (

    pause

    exit /b 1

)

echo 使用 Python：%PY%



"%PY%" -c "import sys; print('Python:', sys.executable); print('In venv:', sys.prefix != sys.base_prefix)"

if errorlevel 1 (

    echo 错误：虚拟环境 Python 无法运行

    pause

    exit /b 1

)



REM Install PyTorch (prefer CUDA build; fallback to CPU if needed)

echo.

echo 正在升级 pip...

"%PY%" -m pip install -U pip setuptools wheel

if errorlevel 1 (

    echo pip 升级失败

    pause

    exit /b 1

)



echo.

echo 正在安装 PyTorch CUDA 版本（cu128）...

"%PY%" -m pip uninstall -y torch torchvision torchaudio >nul 2>&1

"%PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

if errorlevel 1 (

    echo CUDA 版 PyTorch 安装失败，正在回退到默认 PyTorch...

    "%PY%" -m pip install torch

    if errorlevel 1 (

        echo PyTorch 安装失败

        pause

        exit /b 1

    )

    echo 警告：已安装回退版 PyTorch（可能为 CPU-only）。

)



echo PyTorch 安装完成 ✓



REM Install other dependencies

echo.

echo 正在安装项目依赖...

"%PY%" -m pip install -e ".[dev]"

if errorlevel 1 (

    echo 项目安装失败，正在回退到 requirements.txt...

    "%PY%" -m pip install -r requirements.txt

    if errorlevel 1 (

        echo 依赖安装失败

        pause

        exit /b 1

    )

)



echo 依赖安装完成 ✓



echo.

echo 正在移除过时的 typing 包（Python 3.9+ 不需要，且会导致 PyInstaller 失败）...

"%PY%" -m pip uninstall -y typing >nul 2>&1

where conda >nul 2>&1

if %errorlevel%==0 (

    call conda remove -y typing >nul 2>&1

)



echo.

echo 正在验证关键依赖导入...

"%PY%" -c "import japanese_subtitle, torch, transformers, accelerate, tokenizers, safetensors, sentencepiece, qwen_asr, PySide6, opencc, numpy, sklearn, resemblyzer" >nul 2>&1

if errorlevel 1 (

    echo 导入检查失败。请重新运行 install.bat

    pause

    exit /b 1

)

echo 导入检查通过 ✓

"%PY%" -c "import torch; print('Torch 版本：', torch.__version__); print('CUDA 是否可用：', torch.cuda.is_available()); print('Torch CUDA：', torch.version.cuda)"



REM Check FFmpeg (hard gate)

echo.

echo 正在检查 FFmpeg...

ffmpeg -version >nul 2>&1

if errorlevel 1 (

    echo 错误：未找到 FFmpeg

    echo.

    echo 请先安装 FFmpeg：

    echo 1. 访问 https://ffmpeg.org/download.html

    echo 2. 下载 Windows 版本

    echo 3. 解压并将 ffmpeg\bin 加入系统 PATH

    echo 4. 安装完成后重新运行本脚本

    pause

    exit /b 1

)

echo 已找到 FFmpeg ✓



echo.

echo 安装完成！

echo.

echo 依赖已安装到项目虚拟环境：.venv

echo 启动程序请运行 run.bat

echo.

pause

