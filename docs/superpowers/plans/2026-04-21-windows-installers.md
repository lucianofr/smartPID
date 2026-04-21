# Windows Installers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship two Windows `.exe` installers — one that installs `smart_pid_core` as a Windows service (via NSSM), and one that installs the PySide6 HMI as a desktop app with a configurable backend endpoint.

**Architecture:** PyInstaller `onedir` builds bundled into Inno Setup installers. Backend service lifecycle managed by NSSM (bundled). Backend data lives in `C:\ProgramData\SmartPID\`; HMI per-user config lives in `%APPDATA%\SmartPID\hmi.env`. Build scripts are PowerShell, executed manually on a Windows 10/11 VM.

**Tech Stack:** Python 3.13, PyInstaller (onedir), Inno Setup 6, NSSM 2.24, PowerShell, pydantic-settings.

**Design spec:** [docs/superpowers/specs/2026-04-21-windows-installers-design.md](../specs/2026-04-21-windows-installers-design.md)

---

## Repository changes at a glance

Files created:

- `packaging/windows/README.md`
- `packaging/windows/common/version.ps1`
- `packaging/windows/backend/run_backend.py` — thin launcher for PyInstaller
- `packaging/windows/backend/smart_pid_core.spec`
- `packaging/windows/backend/installer.iss`
- `packaging/windows/backend/env.template`
- `packaging/windows/backend/build_backend.ps1`
- `packaging/windows/backend/assets/nssm.exe` — NSSM 2.24 x64 binary, ~300 KB
- `packaging/windows/backend/assets/icon.ico`
- `packaging/windows/hmi/run_hmi.py`
- `packaging/windows/hmi/smart_pid_hmi.spec`
- `packaging/windows/hmi/installer.iss`
- `packaging/windows/hmi/build_hmi.ps1`
- `packaging/windows/hmi/assets/icon.ico`
- `packages/smart_pid_hmi/tests/test_config.py` — new test file (if missing)

Files modified:

- `packages/smart_pid_hmi/src/smart_pid_hmi/config.py` — add user-level config file lookup
- `packages/smart_pid_core/pyproject.toml` — add `pyinstaller` to the `dev` extras
- `packages/smart_pid_hmi/pyproject.toml` — add `pyinstaller` to the `dev` extras
- `.gitignore` — ignore `dist/windows/`

---

## Task 1: Project prerequisites — dev dep + .gitignore

**Files:**
- Modify: `packages/smart_pid_core/pyproject.toml`
- Modify: `packages/smart_pid_hmi/pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Add PyInstaller to backend dev deps**

In `packages/smart_pid_core/pyproject.toml`, inside the `[project.optional-dependencies]` `dev = [...]` list, add `"pyinstaller>=6.7"`.

- [ ] **Step 2: Add PyInstaller to HMI dev deps**

In `packages/smart_pid_hmi/pyproject.toml`, inside the `[project.optional-dependencies]` `dev = [...]` list, add `"pyinstaller>=6.7"`.

- [ ] **Step 3: Add Windows dist directory to `.gitignore`**

Append to `.gitignore`:

```
# Windows installers
/dist/windows/
```

- [ ] **Step 4: Sync and verify**

Run: `uv sync --all-packages --extra dev`
Expected: `pyinstaller` appears in resolved packages. No errors.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/pyproject.toml \
        packages/smart_pid_hmi/pyproject.toml \
        .gitignore
git commit -m "chore(packaging): add pyinstaller dev dep and ignore dist/windows"
```

---

## Task 2: HMI config — learn about user-level config file

The current `config.py` reads only the packaged `hmi.env`. Installed Windows HMIs must also read `%APPDATA%\SmartPID\hmi.env` (written by the installer). Pydantic-settings supports tuples of env files where the later file overrides earlier ones — we use that.

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/config.py`
- Create or modify: `packages/smart_pid_hmi/tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `packages/smart_pid_hmi/tests/test_config.py` (or append to an existing `test_config.py`):

```python
"""Tests for HMI configuration loading."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def _reload_config(monkeypatch: pytest.MonkeyPatch, home: Path, appdata: Path | None):
    """Reload the config module with patched home/APPDATA for isolation."""
    monkeypatch.setenv("HOME", str(home))
    if appdata is not None:
        monkeypatch.setenv("APPDATA", str(appdata))
    else:
        monkeypatch.delenv("APPDATA", raising=False)
    # Force a reimport so module-level path constants pick up the new env
    sys.modules.pop("smart_pid_hmi.config", None)
    return importlib.import_module("smart_pid_hmi.config")


def test_user_config_dir_on_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    appdata = tmp_path / "AppData" / "Roaming"
    appdata.mkdir(parents=True)
    cfg = _reload_config(monkeypatch, tmp_path, appdata)
    assert cfg.USER_CONFIG_FILE == appdata / "SmartPID" / "hmi.env"


def test_user_config_dir_on_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    assert cfg.USER_CONFIG_FILE == tmp_path / ".smart-pid" / "hmi.env"


def test_user_config_overrides_packaged(monkeypatch, tmp_path):
    """User-level hmi.env must override the packaged defaults."""
    monkeypatch.setattr(sys, "platform", "linux")
    user_dir = tmp_path / ".smart-pid"
    user_dir.mkdir()
    (user_dir / "hmi.env").write_text(
        "SPID_HMI_SERVER_HOST=remote-backend\n"
        "SPID_HMI_SERVER_PORT=9000\n"
        "SPID_HMI_ZMQ_URL=tcp://remote-backend:5555\n"
    )
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    cfg.ensure_config_file()  # creates the packaged defaults
    settings = cfg.HMISettings()
    assert settings.server_host == "remote-backend"
    assert settings.server_port == 9000
    assert settings.zmq_url == "tcp://remote-backend:5555"


def test_packaged_defaults_used_when_no_user_config(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    cfg = _reload_config(monkeypatch, tmp_path, appdata=None)
    cfg.ensure_config_file()
    settings = cfg.HMISettings()
    assert settings.server_host == "localhost"
    assert settings.server_port == 8000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/smart_pid_hmi/tests/test_config.py -v`
Expected: FAIL. `USER_CONFIG_FILE` attribute does not exist on the module yet.

- [ ] **Step 3: Implement the platform-aware config loader**

Replace the body of `packages/smart_pid_hmi/src/smart_pid_hmi/config.py` with:

```python
"""HMI configuration via pydantic-settings.

Settings are loaded in this priority (highest wins):
  1. Environment variables           (SPID_HMI_SERVER_HOST, …)
  2. User-level config file          ($APPDATA\\SmartPID\\hmi.env on Windows,
                                      ~/.smart-pid/hmi.env elsewhere)
  3. Packaged config file            (hmi.env next to this module, created
                                      on first run with built-in defaults)
  4. Built-in defaults               (class attributes below)

The user-level file is where the Windows installer writes the operator's
answers ("backend host", etc.); on Linux/macOS it is a hand-editable file
that overrides the packaged defaults without requiring the user to modify
files inside the installed package.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path.home() / ".smart-pid"
_PKG_DIR = Path(__file__).resolve().parent
PACKAGE_CONFIG_FILE = _PKG_DIR / "hmi.env"
CONFIG_FILE = PACKAGE_CONFIG_FILE  # kept for backward compatibility


def _user_config_dir() -> Path:
    """Resolve the per-user config directory for SmartPID.

    Windows: ``%APPDATA%\\SmartPID`` — matches the Windows installer layout.
    Other:   ``~/.smart-pid`` — matches ``APP_DIR`` used elsewhere.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "SmartPID"
    return Path.home() / ".smart-pid"


USER_CONFIG_FILE = _user_config_dir() / "hmi.env"

_DEFAULT_CONFIG_CONTENT = """\
# Smart PID HMI — connection settings
# Edit this file to change defaults.  Environment variables (SPID_HMI_*)
# override any value set here.

SPID_HMI_SERVER_HOST=localhost
SPID_HMI_SERVER_PORT=8000
SPID_HMI_ZMQ_URL=tcp://localhost:5555
SPID_HMI_THEME=isa101
SPID_HMI_MOCK_MODE=false
SPID_HMI_REFRESH_MS=33
"""


def ensure_config_file() -> Path:
    """Create the packaged default config file if it does not exist yet."""
    if not PACKAGE_CONFIG_FILE.exists():
        PACKAGE_CONFIG_FILE.write_text(_DEFAULT_CONFIG_CONTENT)
    return PACKAGE_CONFIG_FILE


class HMISettings(BaseSettings):
    """Desktop HMI client settings.

    Loaded from env vars (``SPID_HMI_`` prefix), then the user-level
    ``hmi.env`` (if present), then the packaged ``hmi.env``.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPID_HMI_",
        # Tuple: later files override earlier ones in pydantic-settings.
        env_file=(str(PACKAGE_CONFIG_FILE), str(USER_CONFIG_FILE)),
        env_file_encoding="utf-8",
    )

    server_host: str = "localhost"
    server_port: int = 8000
    zmq_url: str = "tcp://localhost:5555"
    theme: str = "isa101"
    mock_mode: bool = False
    refresh_ms: int = 33
    app_state_path: Path = APP_DIR / "app.json"

    @property
    def server_url(self) -> str:
        """Build the full server URL from host and port."""
        return f"http://{self.server_host}:{self.server_port}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/smart_pid_hmi/tests/test_config.py -v`
Expected: PASS (4 tests green).

- [ ] **Step 5: Run existing HMI test suite to confirm no regression**

Run: `uv run pytest packages/smart_pid_hmi/tests/ -v`
Expected: All previously-passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/config.py \
        packages/smart_pid_hmi/tests/test_config.py
git commit -m "feat(hmi): load settings from user-level hmi.env (APPDATA / ~/.smart-pid)"
```

---

## Task 3: packaging/windows scaffolding — layout + version script + README stub

**Files:**
- Create: `packaging/windows/README.md`
- Create: `packaging/windows/common/version.ps1`
- Create: `packaging/windows/backend/assets/.gitkeep`
- Create: `packaging/windows/hmi/assets/.gitkeep`

- [ ] **Step 1: Create directories**

```bash
mkdir -p packaging/windows/common \
         packaging/windows/backend/assets \
         packaging/windows/hmi/assets
touch packaging/windows/backend/assets/.gitkeep \
      packaging/windows/hmi/assets/.gitkeep
```

- [ ] **Step 2: Write `common/version.ps1`**

Create `packaging/windows/common/version.ps1`:

```powershell
<#
.SYNOPSIS
    Extract the version of a uv workspace package from its pyproject.toml.

.PARAMETER PyprojectPath
    Absolute or relative path to the pyproject.toml file.

.OUTPUTS
    Prints the version string (e.g. "0.1.0") to stdout.
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $PyprojectPath
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $PyprojectPath)) {
    throw "pyproject.toml not found at: $PyprojectPath"
}

$content = Get-Content -Raw -Path $PyprojectPath
# Match the first `version = "..."` under [project]
$match = [regex]::Match($content, '(?ms)^\[project\].*?^version\s*=\s*"(?<v>[^"]+)"')
if (-not $match.Success) {
    throw "Could not parse [project].version from $PyprojectPath"
}

Write-Output $match.Groups['v'].Value
```

- [ ] **Step 3: Write `packaging/windows/README.md` (stub — finalized in Task 9)**

Create `packaging/windows/README.md`:

```markdown
# Windows installers

Two Inno Setup installers built on a Windows 10/11 VM:

- `SmartPID-Backend-Setup-X.Y.Z.exe` — installs the backend as a Windows
  service (wrapped by NSSM).
- `SmartPID-HMI-Setup-X.Y.Z.exe` — installs the PySide6 desktop HMI.

Full build prerequisites, commands, and the verification checklist are
documented later in this file (finalized once the build scripts are in
place).
```

- [ ] **Step 4: Commit**

```bash
git add packaging/windows/
git commit -m "chore(packaging): scaffold packaging/windows layout"
```

---

## Task 4: Backend — PyInstaller spec + launcher + icon placeholder

**Files:**
- Create: `packaging/windows/backend/run_backend.py`
- Create: `packaging/windows/backend/smart_pid_core.spec`
- Create: `packaging/windows/backend/assets/icon.ico` (placeholder; see Step 4)

- [ ] **Step 1: Write the launcher**

Create `packaging/windows/backend/run_backend.py`:

```python
"""PyInstaller entry point for the Smart PID backend daemon.

PyInstaller follows imports starting from this file to assemble the
frozen executable. Keeping it trivial makes the dependency graph easy
to reason about.
"""
from __future__ import annotations

from smart_pid_core.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the PyInstaller spec**

Create `packaging/windows/backend/smart_pid_core.spec`:

```python
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
```

- [ ] **Step 3: Place an icon placeholder**

The `.ico` is required by the EXE spec but cosmetic. If no final icon is available yet, commit a small placeholder generated from any existing PNG (the HMI already has branding assets under `packages/smart_pid_hmi/src/smart_pid_hmi/themes/` — pick one and convert, or commit an empty 16×16 `.ico`). The goal is a valid ICO file at `packaging/windows/backend/assets/icon.ico`.

Quick cross-platform conversion (from any repo PNG, run locally):

```bash
python -c "from PIL import Image; Image.open('packages/smart_pid_hmi/src/smart_pid_hmi/themes/logo.png').save('packaging/windows/backend/assets/icon.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])"
```

If no suitable PNG exists, commit any valid `.ico` placeholder — the installer works without branded artwork.

- [ ] **Step 4: Commit**

```bash
git add packaging/windows/backend/run_backend.py \
        packaging/windows/backend/smart_pid_core.spec \
        packaging/windows/backend/assets/icon.ico
git rm packaging/windows/backend/assets/.gitkeep
git commit -m "feat(packaging): backend pyinstaller spec + launcher"
```

---

## Task 5: Backend — env template + NSSM binary

**Files:**
- Create: `packaging/windows/backend/env.template`
- Create: `packaging/windows/backend/assets/nssm.exe` (downloaded binary, committed)

- [ ] **Step 1: Write the env template**

Create `packaging/windows/backend/env.template`. Inno Setup substitutes `{JWT_SECRET}` at install time:

```
# Smart PID — backend configuration
# This file is written once by the installer. The service reads it via
# pydantic-settings (SPID_ prefix). Uncomment and edit any line below
# to override the built-in defaults. Restart the Smart PID Backend
# service after changes.

SPID_JWT_SECRET={JWT_SECRET}

# --- Logging ---
#SPID_LOG_LEVEL=INFO

# --- REST API ---
#SPID_API_HOST=0.0.0.0
#SPID_API_PORT=8000

# --- Telemetry publisher (ZMQ) ---
#SPID_ZMQ_PUBLISH_PORT=5555

# --- OPC-UA ---
#SPID_OPCUA_ENDPOINT=opc.tcp://localhost:4840

# --- Simulator (digital twin) ---
#SPID_SIMULATOR_ENABLED=false
#SPID_SIMULATOR_PORT=4849

# --- Data directory ---
# Default is %PROGRAMDATA%\SmartPID\projects (service CWD resolves this).
#SPID_PROJECTS_DIR=C:\ProgramData\SmartPID\projects
```

- [ ] **Step 2: Add NSSM binary**

Download NSSM 2.24 from https://nssm.cc/release/nssm-2.24.zip on the build VM, extract the **x64** `nssm.exe`, and commit it to `packaging/windows/backend/assets/nssm.exe`.

Verify size is ~300 KB and that the executable runs (`.\nssm.exe --version` prints `NSSM 2.24 64-bit 2014-08-31`).

- [ ] **Step 3: Commit**

```bash
git add packaging/windows/backend/env.template \
        packaging/windows/backend/assets/nssm.exe
git commit -m "feat(packaging): backend env template + bundled nssm.exe"
```

---

## Task 6: Backend — Inno Setup installer + build script

**Files:**
- Create: `packaging/windows/backend/installer.iss`
- Create: `packaging/windows/backend/build_backend.ps1`

- [ ] **Step 1: Write the Inno Setup script**

Create `packaging/windows/backend/installer.iss`:

```iss
; Smart PID Backend — Windows service installer
; Produces: SmartPID-Backend-Setup-{AppVersion}.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\smart-pid-core"
#endif

[Setup]
AppId={{B3E4C3D2-5B9A-4A1C-9F7B-6A2C5D9E3F10}
AppName=Smart PID Backend
AppVersion={#AppVersion}
AppPublisher=Smart PID
DefaultDirName={autopf}\SmartPID\Backend
DefaultGroupName=Smart PID
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename=SmartPID-Backend-Setup-{#AppVersion}
OutputDir=..\..\..\dist\windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\smart-pid-core.exe
SetupIconFile=assets\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "assets\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "env.template"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\SmartPID"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\logs"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\projects"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\exports"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\models"; Permissions: everyone-full

[Run]
Filename: "{app}\nssm.exe"; Parameters: "install SmartPIDBackend ""{app}\smart-pid-core.exe"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend DisplayName ""Smart PID Backend"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend Description ""Smart PID Edge Platform - Core Engine"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppDirectory ""{commonappdata}\SmartPID"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend Start SERVICE_DELAYED_AUTO_START"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppStdout ""{commonappdata}\SmartPID\logs\backend.out.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppStderr ""{commonappdata}\SmartPID\logs\backend.err.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppRotateFiles 1"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppRotateBytes 10485760"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppExit Default Restart"; Flags: runhidden waituntilterminated
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Smart PID Backend API"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden waituntilterminated
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Smart PID Backend ZMQ"" dir=in action=allow protocol=TCP localport=5555"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "start SmartPIDBackend"; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop SmartPIDBackend"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{app}\nssm.exe"; Parameters: "remove SmartPIDBackend confirm"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveSvc"
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Smart PID Backend API"""; Flags: runhidden waituntilterminated; RunOnceId: "RmFwApi"
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Smart PID Backend ZMQ"""; Flags: runhidden waituntilterminated; RunOnceId: "RmFwZmq"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  PurgeDataPage: TInputOptionWizardPage;

function GenerateRandomJwtSecret(): String;
var
  TmpFile, Cmd: String;
  ResultCode: Integer;
  Lines: TArrayOfString;
begin
  // Call PowerShell to produce a 64-char hex string from RNGCryptoServiceProvider.
  TmpFile := ExpandConstant('{tmp}\jwt_secret.txt');
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command ' +
    '"$b = New-Object byte[] 32; ' +
    '[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ' +
    '[BitConverter]::ToString($b).Replace(''-'','''').ToLower() | Set-Content -NoNewline ''' + TmpFile + '''"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    RaiseException('Failed to launch PowerShell for JWT secret generation.');
  if ResultCode <> 0 then
    RaiseException('PowerShell returned non-zero exit code generating JWT secret.');
  if not LoadStringsFromFile(TmpFile, Lines) then
    RaiseException('Could not read generated JWT secret file.');
  if GetArrayLength(Lines) = 0 then
    RaiseException('Generated JWT secret file is empty.');
  Result := Lines[0];
  DeleteFile(TmpFile);
end;

procedure WriteEnvFileIfMissing();
var
  Target, Template, Content: String;
  Lines: TArrayOfString;
  i: Integer;
  Secret: String;
begin
  Target := ExpandConstant('{commonappdata}\SmartPID\.env');
  if FileExists(Target) then
    Exit;

  Template := ExpandConstant('{app}\env.template');
  if not LoadStringsFromFile(Template, Lines) then
    RaiseException('env.template not found at ' + Template);

  Secret := GenerateRandomJwtSecret();
  Content := '';
  for i := 0 to GetArrayLength(Lines) - 1 do
    Content := Content + StringChange(Lines[i], '{JWT_SECRET}', Secret) + #13#10;

  if not SaveStringToFile(Target, Content, False) then
    RaiseException('Failed to write ' + Target);
end;

procedure InitializeUninstallPage();
begin
  PurgeDataPage := CreateInputOptionPage(wpSelectDir,
    'Remove data?',
    'Smart PID stores projects and user accounts under ProgramData\SmartPID.',
    'By default this data is preserved so you can reinstall without losing anything. ' +
    'Tick the box below only if you really want to delete it — this cannot be undone.',
    False, False);
  PurgeDataPage.Add('Also remove data and configuration (not reversible)');
  PurgeDataPage.Values[0] := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteEnvFileIfMissing();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    if (PurgeDataPage <> nil) and PurgeDataPage.Values[0] then begin
      DataDir := ExpandConstant('{commonappdata}\SmartPID');
      DelTree(DataDir, True, True, True);
    end;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  // No custom install-time wizard pages for the backend.
end;
```

- [ ] **Step 2: Write the backend build script**

Create `packaging/windows/backend/build_backend.ps1`:

```powershell
<#
.SYNOPSIS
    Build the Smart PID backend Windows installer.

.DESCRIPTION
    Syncs dependencies, runs PyInstaller in onedir mode, then invokes
    Inno Setup to wrap everything (plus NSSM) into a single .exe.

    Run from the Windows VM at the repo root. Requires:
      - Python 3.13 in PATH
      - uv in PATH
      - Inno Setup 6 (iscc.exe in PATH or at the default location)
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# Resolve repo root (two levels up from this script)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..\..\..')
$DistDir   = Join-Path $RepoRoot 'dist\windows'

Write-Host "== Smart PID Backend installer build =="
Write-Host "Repo root: $RepoRoot"

Push-Location $RepoRoot
try {
    # 1. Extract version
    $Version = & (Join-Path $ScriptDir '..\common\version.ps1') `
        -PyprojectPath (Join-Path $RepoRoot 'packages\smart_pid_core\pyproject.toml')
    Write-Host "Version: $Version"

    # 2. Sync dependencies (includes pyinstaller via dev extras)
    Write-Host "-> uv sync --all-packages --extra dev"
    uv sync --all-packages --extra dev
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    # 3. Run PyInstaller
    Push-Location $ScriptDir
    try {
        if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
        if (Test-Path 'dist')  { Remove-Item -Recurse -Force 'dist' }

        Write-Host "-> uv run pyinstaller smart_pid_core.spec --clean --noconfirm"
        uv run --project $RepoRoot pyinstaller smart_pid_core.spec --clean --noconfirm
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    }
    finally {
        Pop-Location
    }

    $PyInstallerOut = Join-Path $ScriptDir 'dist\smart-pid-core'
    if (-not (Test-Path (Join-Path $PyInstallerOut 'smart-pid-core.exe'))) {
        throw "PyInstaller did not produce smart-pid-core.exe at $PyInstallerOut"
    }

    # 4. Run Inno Setup
    $Iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $CandidateIscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        if (Test-Path $CandidateIscc) {
            $IsccPath = $CandidateIscc
        } else {
            throw "iscc.exe not found. Install Inno Setup 6 or add it to PATH."
        }
    } else {
        $IsccPath = $Iscc.Source
    }

    New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

    Write-Host "-> iscc installer.iss (version=$Version)"
    & $IsccPath "/DAppVersion=$Version" "/DDistDir=$PyInstallerOut" `
        (Join-Path $ScriptDir 'installer.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

    # 5. Summary
    $Artifact = Join-Path $DistDir "SmartPID-Backend-Setup-$Version.exe"
    if (-not (Test-Path $Artifact)) { throw "Expected artifact not found: $Artifact" }
    $SizeMb  = [math]::Round((Get-Item $Artifact).Length / 1MB, 2)
    $Sha256  = (Get-FileHash -Algorithm SHA256 $Artifact).Hash

    Write-Host ""
    Write-Host "== BUILD OK =="
    Write-Host "Artifact: $Artifact"
    Write-Host "Size:     $SizeMb MB"
    Write-Host "SHA-256:  $Sha256"
}
finally {
    Pop-Location
}
```

- [ ] **Step 3: Commit**

```bash
git add packaging/windows/backend/installer.iss \
        packaging/windows/backend/build_backend.ps1
git commit -m "feat(packaging): backend inno setup script + build pipeline"
```

---

## Task 7: HMI — PyInstaller spec + launcher + icon

**Files:**
- Create: `packaging/windows/hmi/run_hmi.py`
- Create: `packaging/windows/hmi/smart_pid_hmi.spec`
- Create: `packaging/windows/hmi/assets/icon.ico`

- [ ] **Step 1: Write the launcher**

Create `packaging/windows/hmi/run_hmi.py`:

```python
"""PyInstaller entry point for the Smart PID HMI desktop client."""
from __future__ import annotations

from smart_pid_hmi.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the PyInstaller spec**

Create `packaging/windows/hmi/smart_pid_hmi.spec`:

```python
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
```

- [ ] **Step 3: Place an icon**

Re-use the backend procedure from Task 4 Step 3 to produce `packaging/windows/hmi/assets/icon.ico`. Can be the same icon, or a different one if a dedicated HMI icon is available.

- [ ] **Step 4: Commit**

```bash
git add packaging/windows/hmi/run_hmi.py \
        packaging/windows/hmi/smart_pid_hmi.spec \
        packaging/windows/hmi/assets/icon.ico
git rm packaging/windows/hmi/assets/.gitkeep
git commit -m "feat(packaging): hmi pyinstaller spec + launcher"
```

---

## Task 8: HMI — Inno Setup installer + build script

**Files:**
- Create: `packaging/windows/hmi/installer.iss`
- Create: `packaging/windows/hmi/build_hmi.ps1`

- [ ] **Step 1: Write the Inno Setup script**

Create `packaging/windows/hmi/installer.iss`:

```iss
; Smart PID HMI — Windows desktop installer
; Produces: SmartPID-HMI-Setup-{AppVersion}.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\smart-pid-hmi"
#endif

[Setup]
AppId={{A2D1E4B5-7C38-4F9D-9C1A-8F32B4D6E7AC}
AppName=Smart PID HMI
AppVersion={#AppVersion}
AppPublisher=Smart PID
DefaultDirName={autopf}\SmartPID\HMI
DefaultGroupName=Smart PID
PrivilegesRequired=admin
OutputBaseFilename=SmartPID-HMI-Setup-{#AppVersion}
OutputDir=..\..\..\dist\windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\smart-pid-hmi.exe
SetupIconFile=assets\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Smart PID HMI"; Filename: "{app}\smart-pid-hmi.exe"
Name: "{commondesktop}\Smart PID HMI"; Filename: "{app}\smart-pid-hmi.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  BackendPage: TInputQueryWizardPage;

procedure InitializeWizard();
var
  AppData, HmiEnv, Line: String;
  Lines: TArrayOfString;
  i: Integer;
  Existing: TStringList;
begin
  BackendPage := CreateInputQueryPage(wpWelcome,
    'Backend connection',
    'Where does this HMI connect to the backend?',
    'Leave "Backend host" blank to use localhost. The ZMQ URL is ' +
    'composed automatically as tcp://<host>:<zmq port>.');
  BackendPage.Add('Backend host:',      False);
  BackendPage.Add('API port:',          False);
  BackendPage.Add('Telemetry port (ZMQ):', False);
  BackendPage.Values[0] := '';
  BackendPage.Values[1] := '8000';
  BackendPage.Values[2] := '5555';

  // Pre-fill from existing %APPDATA%\SmartPID\hmi.env if present
  AppData := ExpandConstant('{userappdata}\SmartPID');
  HmiEnv  := AppData + '\hmi.env';
  if FileExists(HmiEnv) and LoadStringsFromFile(HmiEnv, Lines) then begin
    for i := 0 to GetArrayLength(Lines) - 1 do begin
      Line := Lines[i];
      if Pos('SPID_HMI_SERVER_HOST=', Line) = 1 then
        BackendPage.Values[0] := Copy(Line, Length('SPID_HMI_SERVER_HOST=') + 1, Length(Line));
      if Pos('SPID_HMI_SERVER_PORT=', Line) = 1 then
        BackendPage.Values[1] := Copy(Line, Length('SPID_HMI_SERVER_PORT=') + 1, Length(Line));
      if Pos('SPID_HMI_ZMQ_URL=', Line) = 1 then begin
        // Extract port from tcp://host:port
        Existing := TStringList.Create;
        try
          Existing.Delimiter := ':';
          Existing.DelimitedText := Copy(Line, Length('SPID_HMI_ZMQ_URL=') + 1, Length(Line));
          if Existing.Count >= 3 then
            BackendPage.Values[2] := Existing[Existing.Count - 1];
        finally
          Existing.Free;
        end;
      end;
    end;
  end;
end;

procedure WriteHmiEnvIfMissing();
var
  AppData, HmiEnv, Host, ApiPort, ZmqPort, Content: String;
begin
  AppData := ExpandConstant('{userappdata}\SmartPID');
  HmiEnv  := AppData + '\hmi.env';
  if FileExists(HmiEnv) then Exit;

  if not DirExists(AppData) then
    if not CreateDir(AppData) then
      RaiseException('Failed to create ' + AppData);

  Host    := Trim(BackendPage.Values[0]);
  if Host = '' then Host := 'localhost';
  ApiPort := Trim(BackendPage.Values[1]);
  if ApiPort = '' then ApiPort := '8000';
  ZmqPort := Trim(BackendPage.Values[2]);
  if ZmqPort = '' then ZmqPort := '5555';

  Content :=
    '# Smart PID HMI — user settings written by the installer.' + #13#10 +
    '# Edit any line to override; restart the HMI after changes.' + #13#10 +
    'SPID_HMI_SERVER_HOST=' + Host + #13#10 +
    'SPID_HMI_SERVER_PORT=' + ApiPort + #13#10 +
    'SPID_HMI_ZMQ_URL=tcp://' + Host + ':' + ZmqPort + #13#10;

  if not SaveStringToFile(HmiEnv, Content, False) then
    RaiseException('Failed to write ' + HmiEnv);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteHmiEnvIfMissing();
end;
```

- [ ] **Step 2: Write the HMI build script**

Create `packaging/windows/hmi/build_hmi.ps1`:

```powershell
<#
.SYNOPSIS
    Build the Smart PID HMI Windows installer.

.DESCRIPTION
    Syncs dependencies, runs PyInstaller in onedir mode, then invokes
    Inno Setup to produce the installer.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..\..\..')
$DistDir   = Join-Path $RepoRoot 'dist\windows'

Write-Host "== Smart PID HMI installer build =="
Write-Host "Repo root: $RepoRoot"

Push-Location $RepoRoot
try {
    $Version = & (Join-Path $ScriptDir '..\common\version.ps1') `
        -PyprojectPath (Join-Path $RepoRoot 'packages\smart_pid_hmi\pyproject.toml')
    Write-Host "Version: $Version"

    Write-Host "-> uv sync --all-packages --extra dev"
    uv sync --all-packages --extra dev
    if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

    Push-Location $ScriptDir
    try {
        if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }
        if (Test-Path 'dist')  { Remove-Item -Recurse -Force 'dist' }

        Write-Host "-> uv run pyinstaller smart_pid_hmi.spec --clean --noconfirm"
        uv run --project $RepoRoot pyinstaller smart_pid_hmi.spec --clean --noconfirm
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    }
    finally {
        Pop-Location
    }

    $PyInstallerOut = Join-Path $ScriptDir 'dist\smart-pid-hmi'
    if (-not (Test-Path (Join-Path $PyInstallerOut 'smart-pid-hmi.exe'))) {
        throw "PyInstaller did not produce smart-pid-hmi.exe at $PyInstallerOut"
    }

    $Iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if (-not $Iscc) {
        $CandidateIscc = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
        if (Test-Path $CandidateIscc) { $IsccPath = $CandidateIscc }
        else { throw "iscc.exe not found." }
    } else {
        $IsccPath = $Iscc.Source
    }

    New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

    Write-Host "-> iscc installer.iss (version=$Version)"
    & $IsccPath "/DAppVersion=$Version" "/DDistDir=$PyInstallerOut" `
        (Join-Path $ScriptDir 'installer.iss')
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

    $Artifact = Join-Path $DistDir "SmartPID-HMI-Setup-$Version.exe"
    if (-not (Test-Path $Artifact)) { throw "Expected artifact not found: $Artifact" }
    $SizeMb  = [math]::Round((Get-Item $Artifact).Length / 1MB, 2)
    $Sha256  = (Get-FileHash -Algorithm SHA256 $Artifact).Hash

    Write-Host ""
    Write-Host "== BUILD OK =="
    Write-Host "Artifact: $Artifact"
    Write-Host "Size:     $SizeMb MB"
    Write-Host "SHA-256:  $Sha256"
}
finally {
    Pop-Location
}
```

- [ ] **Step 3: Commit**

```bash
git add packaging/windows/hmi/installer.iss \
        packaging/windows/hmi/build_hmi.ps1
git commit -m "feat(packaging): hmi inno setup script + build pipeline"
```

---

## Task 9: README finalization + build/install verification

**Files:**
- Modify: `packaging/windows/README.md`

- [ ] **Step 1: Replace the README stub with the full document**

Overwrite `packaging/windows/README.md` with:

````markdown
# Windows installers

Two Inno Setup installers:

- **`SmartPID-Backend-Setup-X.Y.Z.exe`** — installs `smart_pid_core` as a
  Windows service named `SmartPIDBackend`, wrapped by NSSM. Automatic
  start on boot, stdout/stderr logs rotated at 10 MB, restart-on-failure.
- **`SmartPID-HMI-Setup-X.Y.Z.exe`** — installs the PySide6 HMI under
  Program Files and creates a Start Menu shortcut. An installer page
  asks for backend host + API/ZMQ ports; the answers are written to
  `%APPDATA%\SmartPID\hmi.env`.

Both installers are produced on a Windows 10/11 build VM. Builds are
manual; there is no CI job (yet).

## Build prerequisites (Windows VM, one-time setup)

```powershell
# Python 3.13 and uv
winget install Python.Python.3.13
python -m pip install uv

# Inno Setup 6 — provides iscc.exe
choco install innosetup      # or download the installer from jrsoftware.org
```

Verify:

```powershell
python --version      # Python 3.13.x
uv --version
iscc.exe /?            # prints Inno Setup help
```

## Building

From the repo root on the Windows VM:

```powershell
# Backend
.\packaging\windows\backend\build_backend.ps1

# HMI
.\packaging\windows\hmi\build_hmi.ps1
```

Each script:

1. Reads the package version from `pyproject.toml`.
2. Runs `uv sync --all-packages --extra dev` (PyInstaller is a dev dep).
3. Runs PyInstaller (onedir) with the package-specific `.spec`.
4. Runs Inno Setup (`iscc.exe`) with the matching `.iss`.
5. Prints artifact path, size, and SHA-256.

Artifacts land in `dist\windows\` (git-ignored).

## Verification checklist (clean Windows 10/11 VM)

After a build, run both installers on a fresh VM and confirm:

- [ ] Backend installer runs without errors (accept UAC).
- [ ] `services.msc` → **Smart PID Backend** is *Running*, Startup Type
      *Automatic (Delayed Start)*.
- [ ] `curl http://localhost:8000/health` returns HTTP 200.
- [ ] `C:\ProgramData\SmartPID\logs\backend.out.log` contains `daemon_ready`.
- [ ] `C:\ProgramData\SmartPID\.env` exists; `SPID_JWT_SECRET` is a
      64-character hex string.
- [ ] HMI installer runs; default *Backend connection* values
      (localhost, 8000, 5555) install successfully.
- [ ] Start Menu shortcut opens the HMI; login `admin`/`admin` succeeds.
- [ ] Stopping the service via `services.msc` disconnects the HMI
      gracefully (no crash); starting it again reconnects.
- [ ] Uninstalling the backend (without ticking *also remove data*)
      removes the service, keeps `C:\ProgramData\SmartPID\`.
- [ ] Re-installing the backend preserves the JWT secret — existing
      `admin` login still works.
- [ ] On a second VM, installing the HMI with
      `Backend host = <first VM's IP or hostname>` connects to the
      remote backend.

## Where things live on the target machine

| Path                                      | Contents                                                 |
|-------------------------------------------|----------------------------------------------------------|
| `C:\Program Files\SmartPID\Backend\`      | Backend binaries + `nssm.exe`                            |
| `C:\ProgramData\SmartPID\.env`            | Backend env (auto-generated `JWT_SECRET`)                |
| `C:\ProgramData\SmartPID\users.db`        | User accounts                                            |
| `C:\ProgramData\SmartPID\project.spid`    | Default project DB                                       |
| `C:\ProgramData\SmartPID\projects\`       | Additional `.spid` projects                              |
| `C:\ProgramData\SmartPID\logs\`           | `backend.out.log`, `backend.err.log` (NSSM-rotated)      |
| `C:\Program Files\SmartPID\HMI\`          | HMI binaries                                             |
| `%APPDATA%\SmartPID\hmi.env`              | Per-user HMI settings (written by installer)             |
| `%APPDATA%\SmartPID\logs\hmi.log`         | HMI client log                                           |

## Troubleshooting

**Service fails to start.** Check `backend.err.log` first. Most common
cause: a malformed `.env`. Restore by deleting `.env` and reinstalling
(a fresh one will be generated, but the `JWT_SECRET` changes — existing
user sessions are invalidated).

**HMI can't connect.** Edit `%APPDATA%\SmartPID\hmi.env` to fix the
host/ports. No reinstall needed.

**PyInstaller misses a module at runtime.** Add it to the relevant
`.spec` under `hiddenimports` and rebuild.
````

- [ ] **Step 2: Commit**

```bash
git add packaging/windows/README.md
git commit -m "docs(packaging): finalize windows installers README"
```

---

## Self-review checklist (done by plan author)

- **Spec coverage**
  - § 3 Repository layout → Tasks 3, 4, 5, 6, 7, 8.
  - § 4 Backend installer (dirs, flow, uninstall, upgrade) → Task 6 (installer.iss implements all four) + Task 5 (env template + NSSM asset).
  - § 5 HMI installer (dirs, custom page, uninstall, upgrade) → Task 8 (installer.iss with `InitializeWizard` for custom page and `WriteHmiEnvIfMissing` for idempotent upgrade) + Task 2 (config.py teaches HMI about `%APPDATA%`).
  - § 6 Build workflow → Tasks 6 and 8 (build scripts), Task 3 (version extractor), Task 9 (README commands).
  - § 7 Verification checklist → Task 9 (README), executed manually after build.
  - § 8 Open items → intentionally deferred; no task needed.
- **Placeholder scan** — no "TBD"/"TODO"/"add appropriate X" language; every code step contains the actual content. The only soft spot is the `.ico` placeholder (Task 4 step 3) which is explicitly acceptable per design.
- **Type/name consistency** — env var names (`SPID_HMI_SERVER_HOST/PORT/ZMQ_URL`), service name (`SmartPIDBackend`), installer app IDs, artifact file names, and directory paths are identical across tasks, spec, and README.
