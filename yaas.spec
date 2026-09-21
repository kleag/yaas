# -*- mode: python ; coding: utf-8 -*-

import os
import sys

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata
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

# pytubefix (>=recent versions, see JuanBindez/pytubefix#209) shells out to a
# Node.js binary to run YouTube's signature/PoToken-deciphering JS, via the
# nodejs_wheel package. PyInstaller's static import scanner only bundles
# nodejs_wheel's *.py files, never the actual node executable it ships as
# package data, nor pytubefix's own runner.js/botGuard.js data files --
# leaving all of them missing from the frozen app and pytubefix unable to
# download anything. Locate them the same way pytubefix itself does, so the
# bundled path always matches exactly what it looks for at runtime.
try:
    from pytubefix.sig_nsig.node_runner import NodeRunner as _NodeRunner
    _node_source_path = _NodeRunner._node_path()
    _node_dest_dir = 'nodejs_wheel' if sys.platform == 'win32' else 'nodejs_wheel/bin'
    _bundled_binaries.append((_node_source_path, _node_dest_dir))
except Exception as _ex:
    print(f"WARNING: could not locate the nodejs_wheel node binary to bundle "
          f"it ({_ex}); pytubefix downloads will likely fail in the frozen app.")

a = Analysis(
    ['src/pyinstmain.py'],
    pathex=['.'],
    binaries=_bundled_binaries,
    # audio_separator's own __init__ unconditionally does
    # metadata.distribution("audio-separator").version to log its version;
    # frozen bundles don't include .dist-info metadata by default, so that
    # lookup raises PackageNotFoundError, audio_separator's own helper
    # swallows it and returns None, and `.version` on that None crashes
    # every extraction attempt ('NoneType' object has no attribute
    # 'version'). copy_metadata makes the .dist-info available again.
    # audio_separator also ships its own top-level data files (models.json,
    # models-scores.json, model-data.json, ensemble_presets.json) that it
    # reads relative to its own package directory at runtime; same story as
    # pytubefix's JS files above -- collect_data_files() sweeps up all of
    # them so they don't need discovering one crash at a time.
    datas=([('src/yaas/separate_worker.py', '.'), ('src/yaas/resources', 'yaas/resources')]
           + collect_data_files('pytubefix')
           + collect_data_files('audio_separator') + copy_metadata('audio-separator')),
    # audio_separator picks its architecture implementation (MDX/MDXC/VR/
    # Demucs) via importlib.import_module(f"...architectures.{module_name}")
    # with a name built at runtime -- invisible to PyInstaller's static
    # scanner, so none of those submodules get bundled at all and loading
    # any model fails with "No module named
    # 'audio_separator.separator.architectures'". Given how many separate
    # audio_separator packaging gaps have turned up already (missing data
    # files, missing metadata, this dynamic-import one), collect *all* of
    # its submodules rather than chasing individual subpackages one crash
    # at a time.
    hiddenimports=(['PySide6', 'pytubefix', 'pydub', 'torch', 'torchaudio', 'torchcodec',
                    'openunmix', 'audioop', 'ffmpeg', 'soundfile', 'audioread']
                   + collect_submodules('audio_separator')),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)
#     cipher=block_cipher,

if sys.platform.startswith('linux'):
    # PyInstaller's static dependency scanner finds libxkbcommon.so.0 as a
    # normal linked dependency of a bundled Qt library and bundles that
    # build's copy, but Qt's XCB platform plugin also dlopen()s
    # libxkbcommon-x11.so.0 at runtime -- invisible to the static scanner,
    # so it's never bundled and always resolves from the system instead.
    # libxkbcommon-x11 must match its base library's ABI exactly; mixing a
    # bundled base with a system extension corrupts state and segfaults in
    # libxkbcommon on the first real key event (confirmed via a crash
    # report's core dump: SIGSEGV in the bundled libxkbcommon.so.0, called
    # from libQt6XcbQpa.so.6, with libxkbcommon-x11.so.0 loaded from
    # /usr/lib/x86_64-linux-gnu/). Excluding the bundled copy makes both
    # consistently resolve from the system, which -- as a core dependency
    # of any X11/Wayland desktop -- is always present anyway.
    a.binaries = [b for b in a.binaries if not b[0].startswith('libxkbcommon')]

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
    icon='src/yaas/resources/icon.ico' if sys.platform == 'win32' else None,
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
        icon='src/yaas/resources/icon.icns',
        bundle_identifier='com.kleag.yaas',
    )
