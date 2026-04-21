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
