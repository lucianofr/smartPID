; Smart PID Backend - Windows service installer
; Produces: SmartPID-Backend-Setup-{AppVersion}.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\smart-pid-core"
#endif

[Setup]
AppId={{B3E4C3D2-5B9A-4A1C-9F7B-6A2C5D9E3F10}
AppName=Smart PID Backend
AppVersion={#AppVersion}
AppPublisher=Smart PID
DefaultDirName={autopf}\SmartPID\Backend
DefaultGroupName=Smart PID
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputBaseFilename=SmartPID-Backend-Setup-{#AppVersion}
OutputDir=..\..\..\dist\windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\smart-pid-core.exe
SetupIconFile=assets\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "assets\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "env.template"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{commonappdata}\SmartPID"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\logs"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\projects"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\exports"; Permissions: everyone-full
Name: "{commonappdata}\SmartPID\models"; Permissions: everyone-full

[Run]
Filename: "{app}\nssm.exe"; Parameters: "install SmartPIDBackend ""{app}\smart-pid-core.exe"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend DisplayName ""Smart PID Backend"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend Description ""Smart PID Edge Platform - Core Engine"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppDirectory ""{commonappdata}\SmartPID"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend Start SERVICE_DELAYED_AUTO_START"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppStdout ""{commonappdata}\SmartPID\logs\backend.out.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppStderr ""{commonappdata}\SmartPID\logs\backend.err.log"""; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppRotateFiles 1"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppRotateBytes 10485760"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "set SmartPIDBackend AppExit Default Restart"; Flags: runhidden waituntilterminated
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Smart PID Backend API"" dir=in action=allow protocol=TCP localport=8000"; Flags: runhidden waituntilterminated
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""Smart PID Backend ZMQ"" dir=in action=allow protocol=TCP localport=5555"; Flags: runhidden waituntilterminated
Filename: "{app}\nssm.exe"; Parameters: "start SmartPIDBackend"; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop SmartPIDBackend"; Flags: runhidden waituntilterminated; RunOnceId: "StopSvc"
Filename: "{app}\nssm.exe"; Parameters: "remove SmartPIDBackend confirm"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveSvc"
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Smart PID Backend API"""; Flags: runhidden waituntilterminated; RunOnceId: "RmFwApi"
Filename: "netsh"; Parameters: "advfirewall firewall delete rule name=""Smart PID Backend ZMQ"""; Flags: runhidden waituntilterminated; RunOnceId: "RmFwZmq"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  PurgeDataPage: TInputOptionWizardPage;

function GenerateRandomJwtSecret(): String;
var
  TmpFile, Cmd: String;
  ResultCode: Integer;
  Lines: TArrayOfString;
begin
  // Call PowerShell to produce a 64-char hex string from RNGCryptoServiceProvider.
  TmpFile := ExpandConstant('{tmp}\jwt_secret.txt');
  Cmd := '-NoProfile -ExecutionPolicy Bypass -Command ' +
    '"$b = New-Object byte[] 32; ' +
    '[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ' +
    '[BitConverter]::ToString($b).Replace(''-'','''').ToLower() | Set-Content -NoNewline ''' + TmpFile + '''"';
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Cmd, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    RaiseException('Failed to launch PowerShell for JWT secret generation.');
  if ResultCode <> 0 then
    RaiseException('PowerShell returned non-zero exit code generating JWT secret.');
  if not LoadStringsFromFile(TmpFile, Lines) then
    RaiseException('Could not read generated JWT secret file.');
  if GetArrayLength(Lines) = 0 then
    RaiseException('Generated JWT secret file is empty.');
  Result := Lines[0];
  DeleteFile(TmpFile);
end;

procedure WriteEnvFileIfMissing();
var
  Target, Template, Content, Line: String;
  Lines: TArrayOfString;
  i: Integer;
  Secret: String;
begin
  Target := ExpandConstant('{commonappdata}\SmartPID\.env');
  if FileExists(Target) then
    Exit;

  Template := ExpandConstant('{app}\env.template');
  if not LoadStringsFromFile(Template, Lines) then
    RaiseException('env.template not found at ' + Template);

  Secret := GenerateRandomJwtSecret();
  Content := '';
  for i := 0 to GetArrayLength(Lines) - 1 do begin
    Line := Lines[i];
    // StringChange is an Inno Setup PROCEDURE that edits Line in place
    // and returns an Integer count; it cannot be used as a String value.
    StringChange(Line, '{JWT_SECRET}', Secret);
    Content := Content + Line + #13#10;
  end;

  if not SaveStringToFile(Target, Content, False) then
    RaiseException('Failed to write ' + Target);
end;

procedure InitializeUninstallPage();
begin
  PurgeDataPage := CreateInputOptionPage(wpSelectDir,
    'Remove data?',
    'Smart PID stores projects and user accounts under ProgramData\SmartPID.',
    'By default this data is preserved so you can reinstall without losing anything. ' +
    'Tick the box below only if you really want to delete it - this cannot be undone.',
    False, False);
  PurgeDataPage.Add('Also remove data and configuration (not reversible)');
  PurgeDataPage.Values[0] := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteEnvFileIfMissing();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    if (PurgeDataPage <> nil) and PurgeDataPage.Values[0] then begin
      DataDir := ExpandConstant('{commonappdata}\SmartPID');
      DelTree(DataDir, True, True, True);
    end;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard();
begin
  // No custom install-time wizard pages for the backend.
end;
