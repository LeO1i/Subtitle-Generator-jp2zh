# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project_root = Path(SPECPATH).resolve().parent.parent
icon_path = project_root / "assets" / "app.ico"


def safe_collect_submodules(package_name):
    try:
        return collect_submodules(package_name)
    except Exception:
        return []


def safe_collect_data_files(package_name):
    try:
        return collect_data_files(package_name)
    except Exception:
        return []


def safe_collect_dynamic_libs(package_name):
    try:
        return collect_dynamic_libs(package_name)
    except Exception:
        return []


datas = [
    (str(project_root / "assets" / "app.ico"), "assets"),
    (str(project_root / "assets" / "app.svg"), "assets"),
]

ffmpeg_dir = project_root / "ffmpeg"
if ffmpeg_dir.exists():
    datas.append((str(ffmpeg_dir), "ffmpeg"))

for package in ("qwen_asr", "opencc", "transformers", "sentencepiece", "sklearn", "resemblyzer"):
    datas.extend(safe_collect_data_files(package))

hiddenimports = []
for package in (
    "PySide6",
    "torch",
    "transformers",
    "accelerate",
    "tokenizers",
    "safetensors",
    "sentencepiece",
    "qwen_asr",
    "opencc",
    "sklearn",
    "resemblyzer",
):
    hiddenimports.extend(safe_collect_submodules(package))

binaries = []
for package in ("torch", "PySide6"):
    binaries.extend(safe_collect_dynamic_libs(package))

a = Analysis(
    [str(project_root / "gui.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JapaneseSubtitleGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="JapaneseSubtitleGenerator",
)
