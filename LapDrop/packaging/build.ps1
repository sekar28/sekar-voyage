# Builds and signs the LapDrop installer:  powershell -ExecutionPolicy Bypass -File build.ps1 [-Version 1.0.0]
# Output: packaging\Output\  (LapDrop-Setup-<version>.exe, the public .cer and Trust-Certificate.ps1)
# Needs: pip install pyinstaller segno cryptography pywebview, Inno Setup 6.
# Signing uses the same self-signed certificate as Sekar's System Utilities (Cert:\CurrentUser\My,
# created on first use). Its private key never leaves this PC. Adapted from the System Utilities build script.
# The version is also written in version_info.txt: change both.
param([string]$Version = "1.0.1")
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$build = Join-Path $env:TEMP "LapDrop-build"                    # outside OneDrive, so build files don't sync
$dist = Join-Path $build "dist\LapDrop"
$out = Join-Path $here "Output"
$subject = "CN=Sekar's Voyage"
$timestamp = "http://timestamp.digicert.com"

$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found (winget install JRSoftware.InnoSetup)." }

$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -eq $subject -and $_.NotAfter -gt (Get-Date) } |
        Sort-Object NotAfter -Descending | Select-Object -First 1
if (-not $cert) {
    Write-Host "Creating the code-signing certificate '$subject' in your user store..."
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject -CertStoreLocation Cert:\CurrentUser\My `
            -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(5)
}

function Sign($file) {
    $s = Set-AuthenticodeSignature -FilePath $file -Certificate $cert -HashAlgorithm SHA256 -TimestampServer $timestamp
    # On this PC the self-signed root isn't trusted, so the status reads UnknownError; anything else is a real failure.
    if (-not $s.SignerCertificate -or $s.Status -notin @("Valid", "UnknownError")) { throw "Signing $file failed: $($s.StatusMessage)" }
    Write-Host "Signed $(Split-Path $file -Leaf)"
}

Push-Location $here
try {
    python -m PyInstaller --noconfirm --clean --log-level WARN --distpath (Join-Path $build "dist") `
        --workpath (Join-Path $build "work") LapDrop.spec
    if ($LASTEXITCODE) { throw "PyInstaller failed." }

    Sign (Join-Path $dist "LapDrop.exe")
    New-Item -ItemType Directory -Force $out | Out-Null
    # Output\ is in OneDrive, so sync or the virus scanner can briefly lock the file: try once more before giving up.
    foreach ($try in 1, 2) {
        $log = & $iscc "/DSourceDir=$dist" "/DAppVersion=$Version" LapDrop.iss 2>&1
        if (-not $LASTEXITCODE) { break }
        if ($try -eq 2) { $log | Select-Object -Last 15 | Write-Host; throw "Inno Setup failed." }
        Start-Sleep 5
    }
    $setup = Join-Path $out "LapDrop-Setup-$Version.exe"
    Sign $setup

    Export-Certificate -Cert $cert -FilePath (Join-Path $out "SekarsVoyage-CodeSigning.cer") | Out-Null
    Copy-Item (Join-Path $here "Trust-Certificate.ps1") $out -Force
    Write-Host ("Done: {0} ({1:N0} MB), certificate thumbprint {2}" -f $setup, ((Get-Item $setup).Length / 1MB), $cert.Thumbprint)
} finally { Pop-Location }
