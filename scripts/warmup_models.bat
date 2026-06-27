@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

call scripts\env.bat require
if errorlevel 1 (
    echo 请先运行 install.bat
    pause
    exit /b 1
)

echo 正在预下载 ASR 模型（Qwen/Qwen3-ASR-0.6B）...
"%PY%" -c "from qwen_asr import Qwen3ASRModel; Qwen3ASRModel.from_pretrained('Qwen/Qwen3-ASR-0.6B')"
if errorlevel 1 (
    echo ASR 模型预下载失败，请检查网络连接
    pause
    exit /b 1
)

echo 正在预下载 MT 模型（tencent/Hy-MT2-7B）...
"%PY%" -c "from huggingface_hub import snapshot_download; from transformers import AutoTokenizer; m='tencent/Hy-MT2-7B'; snapshot_download(m); AutoTokenizer.from_pretrained(m, trust_remote_code=True)"
if errorlevel 1 (
    echo MT 模型预下载失败，请检查网络连接
    pause
    exit /b 1
)

echo 模型预下载完成 ✓
pause
