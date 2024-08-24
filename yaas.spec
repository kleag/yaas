# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

# block_cipher = None

a = Analysis(
    ['src/yaas/yaas.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['PySide6', 'pytubefix', 'pydub', 'torch', 'torchaudio', 'openunmix', 'moviepy', 'ffmpeg', 'PySoundFile'],
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

# app = BUNDLE(
#     coll,
#     name='yaas',
#     format='onefile'
# )
#     icon=None,
#     bundle_identifier=None,
#     version=None,
