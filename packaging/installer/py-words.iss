; py-words, a Latin dictionary and parser.
; Copyright (C) 2026 Nicolas Vaughan <nicolasvaughan@proton.me>
;
; This program is free software: you can redistribute it and/or modify it
; under the terms of the GNU General Public License as published by the
; Free Software Foundation, either version 3 of the License, or (at your
; option) any later version. This program is distributed WITHOUT ANY
; WARRANTY; see the LICENCE.txt file, or <https://www.gnu.org/licenses/>.
;
; El instalador de py-words para Windows, hecho con Inno Setup 6.
; tools/bundle-installer.py arma la carpeta SourceDir (python\, program\,
; bin\, launcher.py, py-words.ico) y corre ISCC con /D para cada valor:
;
;   ISCC /DAppVersion=3.28 /DFileVersion=3.28.0.0 /DSourceDir=... \
;        /DOutputDir=... /DOutputName=... py-words.iss
;
; Instala para el usuario (sin permisos de administrador) o para todos,
; según se elija al empezar (o /CURRENTUSER, /ALLUSERS).  Silencioso:
; /VERYSILENT /SUPPRESSMSGBOXES [/TASKS="terminal,path,desktopicon"].

#ifndef AppVersion
  #error Give the version: ISCC /DAppVersion=... (tools/bundle-installer.py does)
#endif
#ifndef FileVersion
  #define FileVersion AppVersion + ".0.0"
#endif
#ifndef SourceDir
  #define SourceDir "image"
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef OutputName
  #define OutputName "py-words-v." + AppVersion + "-windows-x64-setup"
#endif

[Setup]
; (no cambiar nunca: así Windows reconoce las versiones como un programa)
AppId={{A9367516-180D-4B55-922F-6353A6F6561F}
AppName=py-words
AppVersion={#AppVersion}
AppVerName=py-words {#AppVersion}
AppPublisher=Nicolas Vaughan
AppPublisherURL=https://github.com/nivaca/py-words
AppSupportURL=https://github.com/nivaca/py-words/issues
AppUpdatesURL=https://github.com/nivaca/py-words/releases
AppContact=nicolasvaughan@proton.me
AppCopyright=Copyright (C) 2026 Nicolas Vaughan
AppComments=A Latin dictionary. GPL-3.0-or-later.
VersionInfoVersion={#FileVersion}
VersionInfoDescription=py-words setup
DefaultDirName={autopf}\py-words
DefaultGroupName=py-words
DisableProgramGroupPage=auto
AllowNoIcons=yes
LicenseFile={#SourceDir}\program\LICENCE.txt
; Per user by default; the first page offers to install for everyone
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
SetupIconFile={#SourceDir}\py-words.ico
UninstallDisplayIcon={app}\py-words.ico
UninstallDisplayName=py-words {#AppVersion}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ChangesEnvironment=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
english.Comment=A Latin dictionary
spanish.Comment=Diccionario latino
english.TaskTerminal=Start menu entries for the &command line, the full-screen terminal version and the web page
spanish.TaskTerminal=Entradas del menú Inicio para la &línea de órdenes, la versión de pantalla completa en la terminal y la página web
english.TaskPath=Add the py-words &command to the PATH
spanish.TaskPath=Añadir la &orden py-words al PATH
english.GroupOther=Other tasks:
spanish.GroupOther=Otras tareas:
english.RemoveSettings=Remove also your settings, search history and cache of py-words?%n%n(Only those of the current user; they are kept if you choose No.)
spanish.RemoveSettings=¿Quitar también sus ajustes, historial de búsquedas y caché de py-words?%n%n(Solo los del usuario actual; con No se conservan.)

[Tasks]
Name: "terminal"; Description: "{cm:TaskTerminal}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "path"; Description: "{cm:TaskPath}"; GroupDescription: "{cm:GroupOther}"

[InstallDelete]
; Lo de la versión anterior, para que no queden archivos que ya no son
; del programa (los ajustes del usuario están en otra parte)
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\program"
Type: filesandordirs; Name: "{app}\bin"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "\program\data\dictionary.xml"; Flags: ignoreversion recursesubdirs createallsubdirs
; The dictionary is read-only, as in the other packages: an update would
; overwrite any edits (to edit it, copy the data folder elsewhere)
Source: "{#SourceDir}\program\data\dictionary.xml"; DestDir: "{app}\program\data"; Attribs: readonly; Flags: ignoreversion overwritereadonly uninsremovereadonly

[Icons]
Name: "{group}\py-words (GUI)"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\program\words_gui.py"""; WorkingDir: "{%USERPROFILE}"; IconFilename: "{app}\py-words.ico"; Comment: "{cm:Comment}"
Name: "{group}\py-words (CLI)"; Filename: "{app}\python\python.exe"; Parameters: """{app}\launcher.py"" cli"; WorkingDir: "{%USERPROFILE}"; IconFilename: "{app}\py-words.ico"; Comment: "{cm:Comment}"; Tasks: terminal
Name: "{group}\py-words (TUI)"; Filename: "{app}\python\python.exe"; Parameters: """{app}\launcher.py"" tui"; WorkingDir: "{%USERPROFILE}"; IconFilename: "{app}\py-words.ico"; Comment: "{cm:Comment}"; Tasks: terminal
Name: "{group}\py-words (Web)"; Filename: "{app}\python\python.exe"; Parameters: """{app}\launcher.py"" web"; WorkingDir: "{%USERPROFILE}"; IconFilename: "{app}\py-words.ico"; Comment: "{cm:Comment}"; Tasks: terminal
Name: "{group}\{cm:UninstallProgram,py-words}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\py-words"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\program\words_gui.py"""; WorkingDir: "{%USERPROFILE}"; IconFilename: "{app}\py-words.ico"; Comment: "{cm:Comment}"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\program\words_gui.py"""; WorkingDir: "{%USERPROFILE}"; Description: "{cm:LaunchProgram,py-words}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; (the bytecode Python writes while it runs, if it could)
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\program"
Type: dirifempty; Name: "{app}"

[Code]
const
  UserEnvironment = 'Environment';
  SystemEnvironment = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

{ El PATH que se cambia: el del usuario, o el de todos si se instala para todos }
function EnvironmentRoot: Integer;
begin
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function EnvironmentKey: String;
begin
  if IsAdminInstallMode then
    Result := SystemEnvironment
  else
    Result := UserEnvironment;
end;

function BinDir: String;
begin
  Result := ExpandConstant('{app}\bin');
end;

{ Where DIR is in PATHS (a PATH, with ; between folders), or 0 }
function PathPosition(Paths, Dir: String): Integer;
begin
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';');
end;

procedure AddToPath(Dir: String);
var
  Paths: String;
begin
  if not RegQueryStringValue(EnvironmentRoot, EnvironmentKey, 'Path', Paths) then
    Paths := '';
  if PathPosition(Paths, Dir) > 0 then
    exit;
  if (Paths <> '') and (Paths[Length(Paths)] <> ';') then
    Paths := Paths + ';';
  Paths := Paths + Dir;
  if not RegWriteExpandStringValue(EnvironmentRoot, EnvironmentKey, 'Path', Paths) then
    Log('Could not add ' + Dir + ' to the PATH');
end;

procedure RemoveFromPath(Dir: String);
var
  Paths: String;
  P: Integer;
begin
  if not RegQueryStringValue(EnvironmentRoot, EnvironmentKey, 'Path', Paths) then
    exit;
  P := PathPosition(Paths, Dir);
  if P = 0 then
    exit;
  { (en ';' + Paths + ';', P es el ';' de antes de Dir) }
  Paths := ';' + Paths + ';';
  Delete(Paths, P, Length(Dir) + 1);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  if not RegWriteExpandStringValue(EnvironmentRoot, EnvironmentKey, 'Path', Paths) then
    Log('Could not remove ' + Dir + ' from the PATH');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('path') then
      AddToPath(BinDir)
    else
      RemoveFromPath(BinDir);
  end;
end;

{ Los ajustes (%APPDATA%\py-words) y el historial y la caché
  (%LOCALAPPDATA%\py-words) del usuario solo se quitan si él lo pide }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveFromPath(BinDir);
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    if MsgBox(CustomMessage('RemoveSettings'), mbConfirmation,
              MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\py-words'), True, True, True);
      DelTree(ExpandConstant('{localappdata}\py-words'), True, True, True);
    end;
  end;
end;
