@echo off
chcp 65001 >nul
echo 日语字幕生成器
echo ==============
echo.

cd /d "%~dp0"
call scripts\env.bat require
if errorlevel 1 (
    pause
    exit /b 1
)

"%PY%" -c "import japanese_subtitle, PySide6" >nul 2>&1
if errorlevel 1 (
    echo 缺少必要依赖。
    echo 请运行 install.bat 安装依赖到虚拟环境。
    pause
    exit /b 1
)

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo 错误：未找到 FFmpeg
    echo 请先安装 FFmpeg 并将 ffmpeg 加入 PATH，然后重新运行 run.bat
    pause
    exit /b 1
)

echo 正在启动程序...

if exist "%PYW%" (
    start "" "%PYW%" -m japanese_subtitle.app.gui
) else (
    start "" "%PY%" -m japanese_subtitle.app.gui
)

exit /b 0
