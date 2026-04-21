; Smart PID HMI - Windows desktop installer
; Produces: SmartPID-HMI-Setup-{AppVersion}.exe

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef DistDir
  #define DistDir "dist\smart-pid-hmi"
#endif

[Setup]
AppId={{A2D1E4B5-7C38-4F9D-9C1A-8F32B4D6E7AC}
AppName=Smart PID HMI
AppVersion={#AppVersion}
AppPublisher=Smart PID
DefaultDirName={autopf}\SmartPID\HMI
DefaultGroupName=Smart PID
PrivilegesRequired=admin
OutputBaseFilename=SmartPID-HMI-Setup-{#AppVersion}
OutputDir=..\..\..\dist\windows
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\smart-pid-hmi.exe
SetupIconFile=assets\icon.ico
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Smart PID HMI"; Filename: "{app}\smart-pid-hmi.exe"
Name: "{commondesktop}\Smart PID HMI"; Filename: "{app}\smart-pid-hmi.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  BackendPage: TInputQueryWizardPage;

procedure InitializeWizard();
var
  AppData, HmiEnv, Line: String;
  Lines: TArrayOfString;
  i: Integer;
  Existing: TStringList;
begin
  BackendPage := CreateInputQueryPage(wpWelcome,
    'Backend connection',
    'Where does this HMI connect to the backend?',
    'Leave "Backend host" blank to use localhost. The ZMQ URL is ' +
    'composed automatically as tcp://<host>:<zmq port>.');
  BackendPage.Add('Backend host:',      False);
  BackendPage.Add('API port:',          False);
  BackendPage.Add('Telemetry port (ZMQ):', False);
  BackendPage.Values[0] := '';
  BackendPage.Values[1] := '8000';
  BackendPage.Values[2] := '5555';

  // Pre-fill from existing %APPDATA%\SmartPID\hmi.env if present
  AppData := ExpandConstant('{userappdata}\SmartPID');
  HmiEnv  := AppData + '\hmi.env';
  if FileExists(HmiEnv) and LoadStringsFromFile(HmiEnv, Lines) then begin
    for i := 0 to GetArrayLength(Lines) - 1 do begin
      Line := Lines[i];
      if Pos('SPID_HMI_SERVER_HOST=', Line) = 1 then
        BackendPage.Values[0] := Copy(Line, Length('SPID_HMI_SERVER_HOST=') + 1, Length(Line));
      if Pos('SPID_HMI_SERVER_PORT=', Line) = 1 then
        BackendPage.Values[1] := Copy(Line, Length('SPID_HMI_SERVER_PORT=') + 1, Length(Line));
      if Pos('SPID_HMI_ZMQ_URL=', Line) = 1 then begin
        // Extract port from tcp://host:port
        Existing := TStringList.Create;
        try
          Existing.Delimiter := ':';
          Existing.DelimitedText := Copy(Line, Length('SPID_HMI_ZMQ_URL=') + 1, Length(Line));
          if Existing.Count >= 3 then
            BackendPage.Values[2] := Existing[Existing.Count - 1];
        finally
          Existing.Free;
        end;
      end;
    end;
  end;
end;

procedure WriteHmiEnvIfMissing();
var
  AppData, HmiEnv, Host, ApiPort, ZmqPort, Content: String;
begin
  AppData := ExpandConstant('{userappdata}\SmartPID');
  HmiEnv  := AppData + '\hmi.env';
  if FileExists(HmiEnv) then Exit;

  if not DirExists(AppData) then
    if not CreateDir(AppData) then
      RaiseException('Failed to create ' + AppData);

  Host    := Trim(BackendPage.Values[0]);
  if Host = '' then Host := 'localhost';
  ApiPort := Trim(BackendPage.Values[1]);
  if ApiPort = '' then ApiPort := '8000';
  ZmqPort := Trim(BackendPage.Values[2]);
  if ZmqPort = '' then ZmqPort := '5555';

  Content :=
    '# Smart PID HMI - user settings written by the installer.' + #13#10 +
    '# Edit any line to override; restart the HMI after changes.' + #13#10 +
    'SPID_HMI_SERVER_HOST=' + Host + #13#10 +
    'SPID_HMI_SERVER_PORT=' + ApiPort + #13#10 +
    'SPID_HMI_ZMQ_URL=tcp://' + Host + ':' + ZmqPort + #13#10;

  if not SaveStringToFile(HmiEnv, Content, False) then
    RaiseException('Failed to write ' + HmiEnv);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteHmiEnvIfMissing();
end;
