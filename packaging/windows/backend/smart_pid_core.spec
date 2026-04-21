# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Smart PID backend daemon (onedir)."""

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("smart_pid_core")
    + collect_submodules("smart_pid_domain")
    + [
        # uvicorn loads these dynamically via strings
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # structlog reads its config dynamically
        "structlog",
        # asyncua uses aiosqlite-style late imports
        "asyncua",
        "aiosqlite",
        # FastAPI imports multipart only when a route uses File/Form/UploadFile
        # (see ensure_multipart_is_installed); PyInstaller needs both names
        # because older python-multipart ships as "multipart" and newer
        # versions ship as "python_multipart".
        "multipart",
        "python_multipart",
    ]
)

block_cipher = None

a = Analysis(
    ["run_backend.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Backend must never bundle the HMI GUI toolkit
        "PySide6",
        "shiboken6",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="smart-pid-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # service uses stdout/stderr, NSSM redirects to log files
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
    name="smart-pid-core",
)
