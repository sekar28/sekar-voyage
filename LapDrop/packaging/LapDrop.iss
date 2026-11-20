; Inno Setup script for LapDrop. Built by build.ps1 (which passes /DSourceDir and /DAppVersion).
#ifndef AppVersion
  #define AppVersion "1.0.1"
#endif

[Setup]
AppId={{B41E7C2D-5A93-4F18-9C6E-2D7A0F3B8E15}
AppName=LapDrop
AppVersion={#AppVersion}
AppPublisher=Sekar's Voyage
AppVerName=LapDrop {#AppVersion}
DefaultDirName={autopf}\LapDrop
DefaultGroupName=LapDrop
DisableProgramGroupPage=yes
; Installs for the current user without a UAC prompt; the dialog lets you install for everyone instead.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\ui\icon.ico
UninstallDisplayIcon={app}\LapDrop.exe
OutputDir=Output
OutputBaseFilename=LapDrop-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Start LapDrop when Windows starts (window minimised)"; GroupDescription: "Start-up:"; Flags: unchecked
; Phones connect in, so Windows Firewall must allow LapDrop. Private (home) networks only; Public stays blocked.
; Adding the rule needs administrator rights: Windows asks once, and setup goes on if you say no.
Name: "firewall"; Description: "Allow LapDrop through Windows Firewall on home (Private) networks (asks for administrator approval)"; GroupDescription: "Network:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LapDrop"; Filename: "{app}\LapDrop.exe"
Name: "{group}\Uninstall LapDrop"; Filename: "{uninstallexe}"
Name: "{autodesktop}\LapDrop"; Filename: "{app}\LapDrop.exe"; Tasks: desktopicon

[Registry]
; Same per-user entry the "Start LapDrop when Windows starts" box inside the app switches on and off.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LapDrop"; ValueData: """{app}\LapDrop.exe"" --minimized"; Tasks: startup; Flags: uninsdeletevalue
; Remove the entry on uninstall even if it was switched on later from inside the app.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "LapDrop"; Flags: uninsdeletevalue dontcreatekey

[Run]
; One elevated call: drop our old rule (if any), then add it for this install folder, Private networks only.
Filename: "{cmd}"; Parameters: "/c netsh advfirewall firewall delete rule name=""LapDrop"" >nul 2>&1 & netsh advfirewall firewall add rule name=""LapDrop"" dir=in action=allow program=""{app}\LapDrop.exe"" profile=private enable=yes"; Verb: "runas"; Flags: runhidden shellexec waituntilterminated; Tasks: firewall; StatusMsg: "Allowing LapDrop on home networks in Windows Firewall..."
Filename: "{app}\LapDrop.exe"; Description: "{cm:LaunchProgram,LapDrop}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Quit a running copy so its files can be removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/IM LapDrop.exe /F"; Flags: runhidden; RunOnceId: "StopApp"

; Settings, the chat history and the pairing code stay in %APPDATA%\LapDrop on uninstall.
; Received files stay in Downloads\LapDrop.
