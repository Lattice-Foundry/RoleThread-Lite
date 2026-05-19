#ifndef AppVersion
#define AppVersion "1.4.45"
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
Name: "{group}\RoleThread Uninstaller"; Filename: "{uninstallexe}"
Name: "{autodesktop}\RoleThread Lite"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch RoleThread Lite"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveLocalDataOnUninstall: Boolean;

const
  SW_RESTORE = 9;

function ShowWindow(hWnd: HWND; nCmdShow: Integer): Boolean;
  external 'ShowWindow@user32.dll stdcall';
function SetForegroundWindow(hWnd: HWND): Boolean;
  external 'SetForegroundWindow@user32.dll stdcall';
function SetActiveWindow(hWnd: HWND): HWND;
  external 'SetActiveWindow@user32.dll stdcall';

procedure BringWizardToFront();
begin
  WizardForm.Show;
  ShowWindow(WizardForm.Handle, SW_RESTORE);
  WizardForm.BringToFront;
  SetActiveWindow(WizardForm.Handle);
  SetForegroundWindow(WizardForm.Handle);
end;

procedure InitializeWizard();
begin
  BringWizardToFront();
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpWelcome then
    BringWizardToFront();
end;

function RoleThreadAppDataRoot(): string;
begin
  Result := ExpandConstant('{localappdata}\RoleThread');
end;

function RoleThreadWorkspaceRoot(): string;
begin
  Result := AddBackslash(GetEnv('USERPROFILE')) + 'RoleThread';
end;

function IsSafeRoleThreadRoot(Path: string): Boolean;
begin
  Result := (ExtractFileName(RemoveBackslashUnlessRoot(Path)) = 'RoleThread');
end;

function IsRoleThreadLauncherRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec(
    ExpandConstant('{cmd}'),
    '/C tasklist /FI "IMAGENAME eq RoleThreadLauncher.exe" | find /I "RoleThreadLauncher.exe" >NUL',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    Result := (ResultCode = 0);
end;

function InitializeUninstall(): Boolean;
var
  RemoveAnswer: Integer;
begin
  Result := True;
  RemoveLocalDataOnUninstall := False;

  if IsRoleThreadLauncherRunning() then
  begin
    MsgBox(
      'RoleThread Lite appears to be running.' + #13#10#13#10 +
      'Close RoleThread Lite before uninstalling so the installed files and local backend process can shut down cleanly.',
      mbError,
      MB_OK
    );
    Result := False;
    Exit;
  end;

  if UninstallSilent() then
    Exit;

  RemoveAnswer := MsgBox(
    'Remove local RoleThread user data?' + #13#10#13#10 +
    'Choosing Yes deletes local database/app state, preferences, logs, cache, training data, imports, exports, backups, and workspace data under:' + #13#10#13#10 +
    RoleThreadAppDataRoot() + #13#10 +
    RoleThreadWorkspaceRoot() + #13#10#13#10 +
    'Cloud backup copies stored outside these local RoleThread folders are not removed. Delete those manually from the cloud provider or sync folder if desired.' + #13#10#13#10 +
    'Choose No for a normal uninstall that preserves user data.',
    mbConfirmation,
    MB_YESNO or MB_DEFBUTTON2
  );
  RemoveLocalDataOnUninstall := (RemoveAnswer = IDYES);
end;

procedure DeleteRoleThreadRoot(Path: string; Description: string);
begin
  if Path = '' then
    Exit;

  if not IsSafeRoleThreadRoot(Path) then
  begin
    Log('Skipping unsafe RoleThread cleanup target: ' + Path);
    Exit;
  end;

  if DirExists(Path) then
  begin
    Log('Removing ' + Description + ': ' + Path);
    DelTree(Path, True, True, True);
  end
  else
    Log('Skipping missing ' + Description + ': ' + Path);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if RemoveLocalDataOnUninstall then
    begin
      Log('Full local RoleThread user-data removal requested.');
      DeleteRoleThreadRoot(RoleThreadAppDataRoot(), 'RoleThread local app data');
      DeleteRoleThreadRoot(RoleThreadWorkspaceRoot(), 'RoleThread workspace data');
      Log('External/cloud backup destinations outside RoleThread-owned local roots are preserved.');
    end
    else
      Log('Normal uninstall selected. RoleThread local user data preserved.');
  end;
end;
