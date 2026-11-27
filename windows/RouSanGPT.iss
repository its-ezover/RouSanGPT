; The RouSanGPT setup program (Inno Setup 6). Built by windows\build.ps1, which first
; puts the whole app (Python, packages, FFmpeg, Graphviz, search model) in build\RouSanGPT.
;
; Installs for the current user only: no administrator rights needed.
;   Program: %LOCALAPPDATA%\Programs\RouSanGPT
;   Data:    %LOCALAPPDATA%\RouSanGPT\data   (kept on update and uninstall)
; Silent install (used by the tests): RouSanGPT-Setup.exe /VERYSILENT /TASKS=desktopicon

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define DataDir "{localappdata}\RouSanGPT\data"

[Setup]
AppId={{6F1C2B7E-4A0D-4E57-9C2A-52A1D3B8E901}
AppName=RouSanGPT
AppVersion={#AppVersion}
AppVerName=RouSanGPT {#AppVersion}
VersionInfoVersion={#AppVersion}
AppPublisher=AbdulAzez Sawalma
AppPublisherURL=https://github.com/its-ezover/RouSanGPT
AppComments=Computer Networks and Cryptography AI teaching assistant
DefaultDirName={localappdata}\Programs\RouSanGPT
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=RouSanGPT-Setup
SetupIconFile=..\icons\rousangpt.ico
UninstallDisplayIcon={app}\app\icons\rousangpt.ico
UninstallDisplayName=RouSanGPT
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LZMANumBlockThreads=4
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; an update starts from a clean program folder (old files and packages go away)
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"

[Files]
Source: "..\build\RouSanGPT\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{#DataDir}"; Flags: uninsneveruninstall

[Icons]
; pythonw.exe: no black console window
Name: "{autoprograms}\RouSanGPT"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\launcher.py"" --data-dir ""{localappdata}\RouSanGPT\data"""; \
  WorkingDir: "{app}\app"; IconFilename: "{app}\app\icons\rousangpt.ico"; Comment: "RouSanGPT - Networks and Cryptography tutor"
Name: "{autodesktop}\RouSanGPT"; Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\launcher.py"" --data-dir ""{localappdata}\RouSanGPT\data"""; \
  WorkingDir: "{app}\app"; IconFilename: "{app}\app\icons\rousangpt.ico"; Comment: "RouSanGPT - Networks and Cryptography tutor"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-X utf8 ""{app}\app\launcher.py"" --data-dir ""{localappdata}\RouSanGPT\data"""; WorkingDir: "{app}\app"; \
  Description: "{cm:LaunchProgram,RouSanGPT}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; __pycache__ folders and other files made after the install
Type: filesandordirs; Name: "{app}"

[Code]
function DataDir(): String;
begin
  Result := ExpandConstant('{#DataDir}');
end;

{ The port of a running RouSanGPT, from data\server.json ('' when there is none) }
function RunningPort(): String;
var
  Text: AnsiString;
  S: String;
  I: Integer;
begin
  Result := '';
  if not LoadStringFromFile(DataDir() + '\server.json', Text) then Exit;
  S := String(Text);
  I := Pos('"port":', S);
  if I = 0 then Exit;
  I := I + Length('"port":');
  while (I <= Length(S)) and (S[I] = ' ') do I := I + 1;
  while (I <= Length(S)) and (S[I] >= '0') and (S[I] <= '9') do
  begin
    Result := Result + S[I];
    I := I + 1;
  end;
end;

{ Ask a running RouSanGPT to quit (like Settings > Quit), so its files can be replaced }
procedure QuitRunningApp();
var
  Port: String;
  Http: Variant;
  I: Integer;
begin
  Port := RunningPort();
  if Port = '' then Exit;
  try
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.SetTimeouts(2000, 2000, 5000, 5000);
    Http.Open('POST', 'http://127.0.0.1:' + Port + '/api/quit', False);
    Http.Send('');
  except
    Exit;                    { not running (server.json left over from a crash) }
  end;
  { the app removes server.json when it has stopped }
  for I := 1 to 60 do
  begin
    if not FileExists(DataDir() + '\server.json') then Break;
    Sleep(500);
  end;
  Sleep(1000);
end;

{ Remove an install made by the old install.cmd script (the data stays) }
procedure RemoveScriptInstall();
var
  Root: String;
begin
  Root := ExpandConstant('{localappdata}\RouSanGPT');
  if not DirExists(Root + '\venv') then Exit;
  DelTree(Root + '\venv', True, True, True);
  DelTree(Root + '\app', True, True, True);
  DelTree(Root + '\app.new', True, True, True);
  DelTree(Root + '\uv-cache', True, True, True);
  DeleteFile(Root + '\uninstall.ps1');
  DeleteFile(Root + '\rousangpt-console.cmd');
  DeleteFile(ExpandConstant('{userdesktop}\RouSanGPT.lnk'));
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\RouSanGPT');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  QuitRunningApp();
  RemoveScriptInstall();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  QuitRunningApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) and DirExists(DataDir()) then
    if MsgBox('RouSanGPT was removed. Your data (chats, course files, settings and API key) is still in:' + #13#10 +
              DataDir() + #13#10#13#10 + 'Delete your data too?',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\RouSanGPT'), True, True, True);
end;
