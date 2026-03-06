# -*- mode: python ; coding: utf-8 -*-
# usage : pyinstaller pdf_bunny.spec

a = Analysis(
    ['../pdf_bunny/main.py'],
    pathex=['../pdf_bunny'],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt5.QtXml'],# required by PopplerQt5
    hookspath=[],
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
    name='pdf_bunny',
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
    icon="../data/pdf-bunny.ico",
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pdf_bunny',
)
