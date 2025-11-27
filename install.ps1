# Open Agent Kit (OAK) installer for Windows
# Usage: irm https://raw.githubusercontent.com/goondocks-co/open-agent-kit/main/install.ps1 | iex
#
# Detects available Python package managers and installs oak-ci from PyPI.
# Prefers: pipx > uv > pip (--user)
# Requires: Python >= 3.12
#
# Environment variables:
#   OAK_INSTALL_METHOD  - Force a specific method: pipx, uv, or pip
#   OAK_VERSION         - Install a specific version (e.g., "0.2.0")

$ErrorActionPreference = "Stop"

$Package = "oak-ci"
$MinPythonMajor = 3
$MinPythonMinor = 12

function Write-Info  { param($Msg) Write-Host "==> $Msg" -ForegroundColor Blue }
function Write-Ok    { param($Msg) Write-Host "==> $Msg" -ForegroundColor Green }
function Write-Warn  { param($Msg) Write-Host "warning: $Msg" -ForegroundColor Yellow }
function Write-Err   { param($Msg) Write-Host "error: $Msg" -ForegroundColor Red }

function Find-Python {
    foreach ($cmd in @("python3", "python", "py")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) { return $found.Source }
    }
    return $null
}

function Test-PythonVersion {
    param($PythonCmd)
    try {
        $version = & $PythonCmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $parts = $version.Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        if ($major -lt $MinPythonMajor -or ($major -eq $MinPythonMajor -and $minor -lt $MinPythonMinor)) {
            return $null
        }
        return $version
    } catch {
        return $null
    }
}

function Install-WithPipx {
    param($VersionSpec)
    Write-Info "Installing with pipx..."
    if ($VersionSpec) {
        pipx install --force "${Package}==${VersionSpec}"
    } else {
        pipx install --force $Package
    }
}

function Install-WithUv {
    param($VersionSpec)
    Write-Info "Installing with uv..."
    if ($VersionSpec) {
        uv tool install --force "${Package}==${VersionSpec}"
    } else {
        uv tool install --force $Package
    }
}

function Install-WithPip {
    param($PythonCmd, $VersionSpec)
    Write-Info "Installing with pip (--user)..."
    if ($VersionSpec) {
        & $PythonCmd -m pip install --user --upgrade "${Package}==${VersionSpec}"
    } else {
        & $PythonCmd -m pip install --user --upgrade $Package
    }
}

function Test-VersionMatch {
    param([string]$Actual, [string]$Expected)

    if ([string]::IsNullOrWhiteSpace($Expected)) {
        return $true
    }

    return $Actual -match [regex]::Escape($Expected)
}

function Test-PipxPackageInstalled {
    param($VersionSpec)

    $line = pipx list --short 2>$null | Where-Object { $_ -match "^$Package\s" } | Select-Object -First 1
    if (-not $line) {
        return $false
    }

    return (Test-VersionMatch -Actual $line -Expected $VersionSpec)
}

function Test-UvPackageInstalled {
    param($VersionSpec)

    $line = uv tool list 2>$null | Where-Object { $_ -match "^$Package\s" } | Select-Object -First 1
    if (-not $line) {
        return $false
    }

    return (Test-VersionMatch -Actual $line -Expected $VersionSpec)
}

function Test-PipPackageInstalled {
    param($PythonCmd, $VersionSpec)

    $show = & $PythonCmd -m pip show $Package 2>$null
    if (-not $show) {
        return $false
    }

    $versionLine = $show | Where-Object { $_ -match "^Version:\s" } | Select-Object -First 1
    if (-not $versionLine) {
        return $false
    }

    $installedVersion = $versionLine -replace "^Version:\s*", ""
    if ([string]::IsNullOrWhiteSpace($VersionSpec)) {
        return $true
    }

    return $installedVersion -eq $VersionSpec
}

function Test-InstallVerification {
    param($Method, $PythonCmd, $VersionSpec)

    switch ($Method) {
        "pipx" { return Test-PipxPackageInstalled -VersionSpec $VersionSpec }
        "uv" { return Test-UvPackageInstalled -VersionSpec $VersionSpec }
        "pip" { return Test-PipPackageInstalled -PythonCmd $PythonCmd -VersionSpec $VersionSpec }
        default { return $false }
    }
}

function Main {
    Write-Host ""
    Write-Host "  Open Agent Kit (OAK) Installer" -ForegroundColor White
    Write-Host "  The Intelligence Layer for AI Agents"
    Write-Host ""

    Write-Info "Detected OS: Windows"

    # Find Python
    $pythonCmd = Find-Python
    if (-not $pythonCmd) {
        Write-Err "Python not found. Please install Python ${MinPythonMajor}.${MinPythonMinor}+ first."
        Write-Host ""
        Write-Info "Install from: https://www.python.org/downloads/"
        exit 1
    }

    # Check Python version
    $pythonVersion = Test-PythonVersion $pythonCmd
    if (-not $pythonVersion) {
        $actual = & $pythonCmd --version 2>&1
        Write-Err "Python ${MinPythonMajor}.${MinPythonMinor}+ required, found: $actual"
        exit 1
    }
    Write-Info "Found Python $pythonVersion ($pythonCmd)"

    # Determine version spec
    $versionSpec = $env:OAK_VERSION
    if ($versionSpec) {
        Write-Info "Installing version: $versionSpec"
    }

    # Choose install method
    $method = $env:OAK_INSTALL_METHOD
    $actualMethod = $null

    if ($method) {
        Write-Info "Using requested method: $method"
        switch ($method) {
            "pipx" {
                if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) { Write-Err "pipx not found"; exit 1 }
                Install-WithPipx $versionSpec
                $actualMethod = "pipx"
            }
            "uv" {
                if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Write-Err "uv not found"; exit 1 }
                Install-WithUv $versionSpec
                $actualMethod = "uv"
            }
            "pip" {
                Install-WithPip $pythonCmd $versionSpec
                $actualMethod = "pip"
            }
            default {
                Write-Err "Unknown method: $method (use: pipx, uv, or pip)"
                exit 1
            }
        }
    } elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
        Install-WithPipx $versionSpec
        $actualMethod = "pipx"
    } elseif (Get-Command uv -ErrorAction SilentlyContinue) {
        Install-WithUv $versionSpec
        $actualMethod = "uv"
    } else {
        Write-Warn "Neither pipx nor uv found, falling back to pip"
        Install-WithPip $pythonCmd $versionSpec
        $actualMethod = "pip"
    }

    if (-not (Test-InstallVerification -Method $actualMethod -PythonCmd $pythonCmd -VersionSpec $versionSpec)) {
        Write-Err "Installation verification failed for method: $actualMethod"
        Write-Info "Try setting OAK_INSTALL_METHOD=pipx|uv|pip and rerun installer"
        exit 1
    }

    # Verify installation
    Write-Host ""
    $oakCmd = Get-Command oak -ErrorAction SilentlyContinue
    if ($oakCmd) {
        $installedVersion = & oak --version 2>$null
        if (-not $installedVersion) { $installedVersion = "unknown" }
        if (-not (Test-VersionMatch -Actual $installedVersion -Expected $versionSpec)) {
            Write-Err "Detected oak command does not match requested version ($versionSpec)"
            Write-Info "Restart your terminal and verify with: oak --version"
            exit 1
        }
        Write-Ok "OAK installed successfully! ($installedVersion)"
        Write-Host ""
        Write-Info "Get started:"
        Write-Host "  cd \path\to\your\project"
        Write-Host "  oak init"
        Write-Host "  oak ci start"
        Write-Host ""
    } else {
        Write-Warn "oak command not found in PATH"
        Write-Info "You may need to restart your terminal or add Python Scripts to PATH"
        Write-Host ""
        Write-Info "Then verify with: oak --version"
    }
}

Main
