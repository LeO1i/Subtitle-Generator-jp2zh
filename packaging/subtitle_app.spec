# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).resolve().parent

datas = [
    (str(project_root / "assets" / "app.ico"), "assets"),
    (str(project_root / "assets" / "app.svg"), "assets"),
]
binaries = []
hiddenimports = [
    "japanese_subtitle",
    "japanese_subtitle.app.gui",
    "japanese_subtitle.services.subtitle_service",
    "japanese_subtitle.pipeline.orchestrator",
    "japanese_subtitle.asr.engine",
    "japanese_subtitle.translation.engine",
    "qwen_asr",
    "transformers",
    "tokenizers",
    "safetensors",
    "accelerate",
]

for package in ("torch", "transformers", "tokenizers"):
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    [str(project_root / "src" / "japanese_subtitle" / "app" / "gui.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "pyi_rth_pytorch.py")],
    excludes=[
        "torchvision",
        "torchvision.transforms",
        "pytest",
        "gradio",
    ],
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
    icon=str(project_root / "assets" / "app.ico"),
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
