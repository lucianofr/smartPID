# Windows installers

One Inno Setup installer:

- **`SmartPID-Backend-Setup-X.Y.Z.exe`** — installs `smart_pid_core` as a
  Windows service named `SmartPIDBackend`, wrapped by NSSM. Automatic
  start on boot, stdout/stderr logs rotated at 10 MB, restart-on-failure.
  The web HMI is served by the backend itself (single origin); there is
  no separate client installer since the PySide6 desktop HMI was removed.

The installer is produced on a Windows 10/11 build VM. Builds are
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
.\packaging\windows\backend\build_backend.ps1
```

The script:

1. Reads the package version from `pyproject.toml`.
2. Runs `uv sync --all-packages --extra dev` (PyInstaller is a dev dep).
3. Runs PyInstaller (onedir) with the package-specific `.spec`.
4. Runs Inno Setup (`iscc.exe`) with the matching `.iss`.
5. Prints artifact path, size, and SHA-256.

Artifacts land in `dist\windows\` (git-ignored).

## Verification checklist (clean Windows 10/11 VM)

After a build, run the installer on a fresh VM and confirm:

- [ ] Backend installer runs without errors (accept UAC).
- [ ] `services.msc` → **Smart PID Backend** is *Running*, Startup Type
      *Automatic (Delayed Start)*.
- [ ] `curl http://localhost:8000/system/status` returns HTTP 200 (JSON body).
- [ ] `C:\ProgramData\SmartPID\logs\backend.out.log` contains `daemon_ready`.
- [ ] `C:\ProgramData\SmartPID\.env` exists; `SPID_JWT_SECRET` is a
      64-character hex string.
- [ ] Browsing to `http://localhost:8000/` serves the web HMI; login
      `admin`/`admin` succeeds.
- [ ] Stopping the service via `services.msc` drops the web client's
      realtime socket; starting it again reconnects.
- [ ] Uninstalling the backend (without ticking *also remove data*)
      removes the service, keeps `C:\ProgramData\SmartPID\`.
- [ ] Re-installing the backend preserves the JWT secret — existing
      `admin` login still works.
- [ ] From a second machine, `http://<VM host>:8000/` reaches the
      backend when the port is open.

## Where things live on the target machine

| Path                                      | Contents                                                 |
|-------------------------------------------|----------------------------------------------------------|
| `C:\Program Files\SmartPID\Backend\`      | Backend binaries + `nssm.exe`                            |
| `C:\ProgramData\SmartPID\.env`            | Backend env (auto-generated `JWT_SECRET`)                |
| `C:\ProgramData\SmartPID\users.db`        | User accounts                                            |
| `C:\ProgramData\SmartPID\project.spid`    | Default project DB                                       |
| `C:\ProgramData\SmartPID\projects\`       | Additional `.spid` projects                              |
| `C:\ProgramData\SmartPID\logs\`           | `backend.out.log`, `backend.err.log` (NSSM-rotated)      |

## Troubleshooting

**Service fails to start.** Check `backend.err.log` first. Most common
cause: a malformed `.env`. Restore by deleting `.env` and reinstalling
(a fresh one will be generated, but the `JWT_SECRET` changes — existing
user sessions are invalidated).

**Web HMI unreachable.** Confirm the service is running and that port
8000 is open; the client is served by the backend, so there is no
separate client config to fix.

**PyInstaller misses a module at runtime.** Add it to the relevant
`.spec` under `hiddenimports` and rebuild.
