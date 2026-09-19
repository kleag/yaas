# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT, BUNDLE

# block_cipher = None

# The `uv` binary powers the on-demand GPU-acceleration environment (see
# src/yaas/gpu_env.py): release.yml downloads the platform-matching release
# of https://github.com/astral-sh/uv into ./bundled_uv/ before running
# PyInstaller. Bundling is optional -- a local/dev build without that
# directory just skips the GPU-acceleration menu entry at runtime (see
# gpu_env.find_uv_binary()'s "uv on PATH" fallback for dev-mode testing).
_uv_binary_name = 'uv.exe' if sys.platform == 'win32' else 'uv'
_uv_binary_path = os.path.join('bundled_uv', _uv_binary_name)
_bundled_binaries = [(_uv_binary_path, '.')] if os.path.exists(_uv_binary_path) else []

a = Analysis(
    ['src/pyinstmain.py'],
    pathex=['.'],
    binaries=_bundled_binaries,
    datas=[('src/yaas/separate_worker.py', '.')],
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
