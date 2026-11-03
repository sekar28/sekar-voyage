; Inno Setup script for Sekar's System Utilities. Built by build.ps1 (which passes /DSourceDir and /DAppVersion).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F3C2A51-8B7E-4C0D-9A61-5E2B7D4F1C90}
AppName=Sekar's System Utilities
AppVersion={#AppVersion}
AppPublisher=Sekar's Voyage
AppVerName=Sekar's System Utilities {#AppVersion}
DefaultDirName={autopf}\Sekar's System Utilities
DefaultGroupName=Sekar's System Utilities
DisableProgramGroupPage=yes
; Installs for the current user without a UAC prompt; the dialog lets you install for everyone instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\ui\icon.ico
UninstallDisplayIcon={app}\SystemUtilities.exe
OutputDir=Output
OutputBaseFilename=SystemUtilities-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sekar's System Utilities"; Filename: "{app}\SystemUtilities.exe"; AppUserModelID: "SystemUtilities.App"
Name: "{group}\User guide"; Filename: "{app}\_internal\docs\HELP.md"
Name: "{group}\Uninstall Sekar's System Utilities"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sekar's System Utilities"; Filename: "{app}\SystemUtilities.exe"; AppUserModelID: "SystemUtilities.App"; Tasks: desktopicon

[Run]
Filename: "{app}\SystemUtilities.exe"; Description: "{cm:LaunchProgram,Sekar's System Utilities}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Quit a running copy (it may be hidden in the tray) so its files can be removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/IM SystemUtilities.exe /F"; Flags: runhidden; RunOnceId: "StopApp"

[Registry]
; Remove the "Run at startup" entry the app may have added.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "SystemUtilities"; Flags: uninsdeletevalue dontcreatekey

; Settings, keys and what Jarvis learned stay in %LOCALAPPDATA%\StorageAnalyzer and Credential Manager on uninstall.
