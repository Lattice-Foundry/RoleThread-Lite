#ifndef AppVersion
#define AppVersion "1.3.81"
#endif

#define AppName "RoleThread Lite"
#define AppExeName "RoleThreadLauncher.exe"
#define BundleDir "..\dist\RoleThreadLauncher"

[Setup]
AppId={{9A0351E9-0D10-48D9-ACB3-DA34C9464055}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=LatticeFoundry
AppPublisherURL=https://latticefoundry.dev
AppSupportURL=https://github.com/Lattice-Foundry/RoleThread-Lite
AppUpdatesURL=https://github.com/Lattice-Foundry/RoleThread-Lite/releases
DefaultDirName={autopf}\RoleThread Lite
DefaultGroupName=RoleThread Lite
DisableProgramGroupPage=yes
OutputDir=..\output
OutputBaseFilename=RoleThreadLiteSetup-v{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName=RoleThread Lite
UninstallDisplayIcon={app}\{#AppExeName}
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RoleThread Lite"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\RoleThread Lite"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch RoleThread Lite"; Flags: nowait postinstall skipifsilent
