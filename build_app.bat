@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo 日语字幕生成器 - Windows App Build
echo ==================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 Python。请先安装 Python 3.9+。
    pause
    exit /b 1
)

echo 正在生成应用图标...
python scripts\generate_icon.py
if errorlevel 1 (
    echo 图标生成失败。
    pause
    exit /b 1
)

echo.
echo 正在安装 PyInstaller...
pip install pyinstaller
if errorlevel 1 (
    echo PyInstaller 安装失败。
    pause
    exit /b 1
)

echo.
echo 正在构建 standalone onedir 应用...
pyinstaller packaging\subtitle_app.spec --noconfirm
if errorlevel 1 (
    echo 构建失败，请查看上方错误信息。
    pause
    exit /b 1
)

echo.
echo Build complete:
echo dist\JapaneseSubtitleGenerator\JapaneseSubtitleGenerator.exe
echo.
echo 你可以双击上面的 exe 启动应用，或右键固定到桌面/任务栏。
pause
