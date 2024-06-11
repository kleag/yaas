# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/yaas.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6', 'pytube', 'pydub', 'torch', 'torchaudio', 'openunmix', 'moviepy', 'ffmpeg'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=True,
    name='yaas',
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


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='yaas',
)

app = BUNDLE(
    coll,
    name='yaas',
    icon=None,
    bundle_identifier=None,
    version=None,
)
