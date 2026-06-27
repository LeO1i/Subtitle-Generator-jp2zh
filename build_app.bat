@echo off

chcp 65001 >nul

setlocal EnableDelayedExpansion



cd /d "%~dp0"

set "LOG=%~dp0packaging\build.log"

if not exist "%~dp0packaging" mkdir "%~dp0packaging"



if /i not "%~1"=="__run__" (

    echo 日志将写入：%LOG%

    echo 若窗口闪退，请打开 packaging\build.log 查看详情。

    echo.

    cmd /c "%~f0" __run__ > "%LOG%" 2>&1

    set "RC=!ERRORLEVEL!"

    type "%LOG%"

    echo.

    if !RC! neq 0 (

        echo 构建失败，退出代码：!RC!

    ) else (

        echo 构建成功。

        echo 可执行文件：dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe

    )

    pause

    exit /b !RC!

)



echo 日语字幕生成器 - Windows App Build

echo ==================================

echo.



call scripts\env.bat require

if errorlevel 1 (

    echo 错误：未找到虚拟环境。请先运行 install.bat。

    exit /b 1

)



echo 使用 Python：%PY%



echo 正在安装 PyTorch CUDA 版本（cu128，与 install.bat 一致）...

"%PY%" -m pip uninstall -y torch torchvision torchaudio >nul 2>&1

"%PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128

if errorlevel 1 (

    echo CUDA 版 PyTorch 安装失败，正在回退到默认 PyTorch...

    "%PY%" -m pip install torch torchaudio

    if errorlevel 1 (

        echo PyTorch 安装失败。

        exit /b 1

    )

    echo 警告：已安装回退版 PyTorch（可能为 CPU-only）。打包后的 exe 也会是 CPU 模式。

)



echo 正在安装项目依赖...

"%PY%" -m pip install -e .

if errorlevel 1 (

    echo 项目安装失败，正在回退到 requirements.txt...

    "%PY%" -m pip install -r requirements.txt

    if errorlevel 1 (

        echo 依赖安装失败。

        exit /b 1

    )

)



echo 正在验证 CUDA 是否可用...

"%PY%" -c "import torch; ok=torch.cuda.is_available(); print('Torch:', torch.__version__, '| CUDA:', getattr(torch.version,'cuda',None), '| GPU:', torch.cuda.is_available()); import sys; sys.exit(0 if ok else 1)"

if errorlevel 1 (

    echo.

    echo 警告：当前环境未检测到可用 CUDA。exe 将只能以 CPU 运行，长视频会非常慢。

    echo 建议先运行 install.bat 或确认 NVIDIA 驱动 / CUDA 12.8 环境正常后再打包。

    echo.

)



call :remove_obsolete_typing

if errorlevel 1 exit /b 1



echo 正在移除 torchvision（ASR 不需要，且会导致打包后启动失败）...

"%PY%" -m pip uninstall -y torchvision >nul 2>&1

"%PY%" -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('torchvision') is None else 1)"

if errorlevel 1 (

    echo 错误：仍检测到 torchvision，请手动执行："%PY%" -m pip uninstall torchvision

    exit /b 1

)

echo torchvision 已移除



echo 正在验证关键导入...

"%PY%" -c "from qwen_asr import Qwen3ASRModel; from japanese_subtitle.services.subtitle_service import SubtitleService"

if errorlevel 1 (

    echo 导入检查失败，请确认依赖已正确安装。

    exit /b 1

)

echo 导入检查通过



echo 正在生成应用图标...

"%PY%" scripts\generate_icon.py

if errorlevel 1 (

    echo 图标生成失败。

    exit /b 1

)



echo.

echo 正在安装 PyInstaller...

"%PY%" -m pip install pyinstaller

if errorlevel 1 (

    echo PyInstaller 安装失败。

    exit /b 1

)



call :remove_obsolete_typing

if errorlevel 1 exit /b 1



echo.

echo 正在构建 standalone onedir 应用...

"%PY%" -m PyInstaller packaging\subtitle_app.spec --noconfirm

if errorlevel 1 (

    echo 构建失败，请查看 packaging\build.log

    exit /b 1

)



echo.

echo Build complete:

echo dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe

exit /b 0



:remove_obsolete_typing

echo 正在移除过时的 typing 包（PyInstaller 不兼容）...

"%PY%" -m pip uninstall -y typing >nul 2>&1

where conda >nul 2>&1

if not errorlevel 1 (

    call conda remove -y typing >nul 2>&1

)

"%PY%" -c "import shutil,sys; from pathlib import Path; site=Path(sys.prefix)/'Lib'/'site-packages'; targets=[site/'typing.py', *site.glob('typing-*.dist-info')]; [shutil.rmtree(p) if p.is_dir() else p.unlink() for p in targets if p.exists()]; sys.exit(1 if (site/'typing.py').exists() or any(site.glob('typing-*.dist-info')) else 0)"

if errorlevel 1 (

    echo 错误：site-packages 中仍有 typing 残留，请手动删除后重试：

    echo   "%PY%" -m pip uninstall typing

    echo   删除 %%CONDA_PREFIX%%\Lib\site-packages\typing.py

    echo   删除 %%CONDA_PREFIX%%\Lib\site-packages\typing-*.dist-info

    exit /b 1

)

echo typing 检查通过

exit /b 0

