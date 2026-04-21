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
