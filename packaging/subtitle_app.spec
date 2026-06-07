# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(project_root / "src" / "japanese_subtitle" / "app" / "gui.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "assets" / "app.ico"), "assets"),
        (str(project_root / "assets" / "app.svg"), "assets"),
    ],
    hiddenimports=[
        "japanese_subtitle",
        "japanese_subtitle.app.gui",
        "japanese_subtitle.services.subtitle_service",
        "japanese_subtitle.pipeline.orchestrator",
        "japanese_subtitle.asr.engine",
        "japanese_subtitle.translation.engine",
    ],
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
