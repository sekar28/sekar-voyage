; Inno Setup script for Sekar's Dashboard. Built by build.ps1 (which passes /DSourceDir and /DAppVersion).
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{B2E7C4D9-5A31-4F6E-8C20-7D19A6E3F512}
AppName=Sekar's Dashboard
AppVersion={#AppVersion}
AppPublisher=Sekar's Voyage
AppVerName=Sekar's Dashboard {#AppVersion}
DefaultDirName={autopf}\Sekar's Dashboard
DefaultGroupName=Sekar's Dashboard
DisableProgramGroupPage=yes
; Per-user only: the wake-word models are downloaded into the app folder on first use, so it must stay writable.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
SetupIconFile=..\ui\dashboard.ico
UninstallDisplayIcon={app}\Dashboard.exe
OutputDir=Output
OutputBaseFilename=Dashboard-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Sekar's Dashboard"; Filename: "{app}\Dashboard.exe"
Name: "{group}\Read me"; Filename: "{app}\_internal\README.md"
Name: "{group}\Uninstall Sekar's Dashboard"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Sekar's Dashboard"; Filename: "{app}\Dashboard.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Dashboard.exe"; Parameters: "--window"; Description: "{cm:LaunchProgram,Sekar's Dashboard}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Quit a running copy (it may be hidden in the tray) so its files can be removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/IM Dashboard.exe /F"; Flags: runhidden; RunOnceId: "StopApp"

[UninstallDelete]
; Wake-word models downloaded into the app folder after installing.
Type: filesandordirs; Name: "{app}\_internal\openwakeword\resources\models"

; Settings, sign-ins (YouTube, WhatsApp), tasks and keys stay in %LOCALAPPDATA%\Dashboard and Credential Manager.
