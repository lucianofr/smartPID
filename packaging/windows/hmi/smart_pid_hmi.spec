# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Smart PID HMI desktop client (onedir)."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules("smart_pid_hmi")
    + collect_submodules("smart_pid_domain")
    + [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtCharts",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
    ]
)

# Bundle the packaged hmi.env + any theme/resource files shipped with the
# HMI package (themes/, dialogs/, pages/, widgets/).
datas = collect_data_files(
    "smart_pid_hmi",
    includes=["*.env", "themes/*", "pages/*", "widgets/*", "dialogs/*"],
)

block_cipher = None

a = Analysis(
    ["run_hmi.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="smart-pid-hmi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app: no black console window
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="smart-pid-hmi",
)
