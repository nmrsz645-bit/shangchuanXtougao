# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules


ROOT = Path(SPECPATH)
playwright_datas, playwright_binaries, playwright_hiddenimports = collect_all("playwright")

a = Analysis(
    [str(ROOT / "投稿中心.py")],
    pathex=[str(ROOT / "API投稿2.0" / "app"), str(ROOT / "自动上传" / "src")],
    binaries=playwright_binaries,
    datas=[*playwright_datas, (str(ROOT / "发布版使用说明.txt"), ".")],
    hiddenimports=["keyring.backends.Windows", *collect_submodules("desktop_posting"), *playwright_hiddenimports],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="上传投稿中心",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="上传投稿中心",
)
