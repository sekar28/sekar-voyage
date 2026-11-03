# Run once on a PC where you want Windows to accept Sekar's System Utilities as signed by a known publisher.
# It adds the public certificate next to this script (no private key) to *your user's* trusted roots and publishers.
# Windows shows a security warning asking you to confirm the root certificate: check the name, then click Yes.
#   Right-click this file > Run with PowerShell,  or:  powershell -ExecutionPolicy Bypass -File Trust-Certificate.ps1
$cer = Join-Path $PSScriptRoot "SekarsVoyage-CodeSigning.cer"
if (-not (Test-Path $cer)) { Write-Error "SekarsVoyage-CodeSigning.cer must be next to this script."; exit 1 }
$c = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 $cer
Write-Host "Certificate: $($c.Subject)  thumbprint $($c.Thumbprint)  valid until $($c.NotAfter.ToString('yyyy-MM-dd'))"
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\TrustedPublisher | Out-Null
Write-Host "Done. You can now run SystemUtilities-Setup-*.exe; it will show 'Sekar's Voyage' as the verified publisher."
# To undo: certmgr.msc > Trusted Root Certification Authorities and Trusted Publishers > delete "Sekar's Voyage".
