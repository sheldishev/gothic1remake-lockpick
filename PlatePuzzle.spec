# -*- mode: python ; coding: utf-8 -*-
# Один файл: pyinstaller PlatePuzzle.spec
# macOS: dist/PlatePuzzle
# Windows: dist/PlatePuzzle.exe

block_cipher = None

a = Analysis(
    ['plate_puzzle_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['plate_puzzle_solver', 'i18n'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PlatePuzzle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
