# -*- mode: python ; coding: utf-8 -*-

import sys

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

# block_cipher = None

a = Analysis(
    ['src/pyinstmain.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6', 'pytubefix', 'pydub', 'torch', 'torchaudio', 'torchcodec', 'openunmix', 'audio_separator', 'audioop', 'ffmpeg', 'soundfile'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)
#     cipher=block_cipher,

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='yaas',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)
#     exclude_binaries=True,
#     disable_windowed_traceback=False,
#     argv_emulation=False,
#     target_arch=None,
#     codesign_identity=None,
#     entitlements_file=None,


if sys.platform == 'darwin':
    # BUNDLE wraps the onefile `exe` target above into a double-clickable
    # yaas.app. COLLECT (the onedir variant) is intentionally not used: with
    # exclude_binaries=False, `exe` above is already a self-contained
    # onefile binary, and running COLLECT against it as well would try to
    # write a `dist/yaas` directory over the `dist/yaas` onefile binary
    # (only harmless on Windows because of the `.exe` extension).
    app = BUNDLE(
        exe,
        name='yaas.app',
        icon=None,
        bundle_identifier='com.kleag.yaas',
    )
