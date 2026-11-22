; ─── Splice Installer Script ───────────────────────────────────
; Inno Setup 6.x

#define MyAppName "Splice"
; Версию НЕ дублируем: берём из собранного exe, а туда она попадает из
; splice/constants.py (см. Splice.spec).
#define MyAppExe "dist\Splice.exe"
#if !FileExists(AddBackslash(SourcePath) + MyAppExe)
  #error Сначала соберите exe: pyinstaller --clean --noconfirm Splice.spec
#endif
#define MyAppVersion GetStringFileInfo(AddBackslash(SourcePath) + MyAppExe, PRODUCT_VERSION)
#if MyAppVersion == ""
  #error В exe нет ресурса версии. Пересоберите его текущей Splice.spec.
#endif
#define MyAppExeName "Splice.exe"
#define MyAppPublisher "SmeshidoJoe"
#define MyAppUrl "https://github.com/SmeshidoJoe/Splice"

[Setup]
AppId={{9B3F6E21-7C4A-4D58-A1E2-5F0C8D2B6A47}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppUrl}
AppSupportURL={#MyAppUrl}
AppUpdatesURL={#MyAppUrl}/releases

; Папка программ текущего пользователя (%LOCALAPPDATA%\Programs): без прав
; администратора, и самообновление может подменить exe на месте.
DefaultDirName={autopf}\{#MyAppName}
DisableDirPage=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest

OutputDir=installer_output
OutputBaseFilename=Splice-Setup-{#MyAppVersion}
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

; Открытое окно держит exe. Имя мьютекса — INSTANCE_NAME + "-Mutex"
; (splice/constants.py, splice/instance.py).
CloseApplications=yes
RestartApplications=no
AppMutex=Splice-Single-Instance-Mutex

; Пункты меню проводника меняют ассоциации — пусть проводник их перечитает.
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.DirNotWritable=This folder cannot be written to without administrator rights.%n%nSplice updates itself and needs write access to its own folder, so please pick another location — for example the default one.
russian.DirNotWritable=В эту папку нельзя записывать без прав администратора.%n%nSplice обновляет себя сам и должен иметь доступ на запись в свою папку, поэтому выберите другое место — например, предложенное по умолчанию.
english.KeepData=Keep settings and downloaded FFmpeg
russian.KeepData=Оставить настройки и скачанный FFmpeg
english.ContextMenu=Add "Chop with Splice" and "Merge with Splice" to the Explorer menu for video files
russian.ContextMenu=Добавить «Нарезать в Splice» и «Склеить в Splice» в меню проводника для видео
english.AutoStart=Start Splice with Windows (stays in the tray)
russian.AutoStart=Запускать Splice вместе с Windows (в трее)
english.Registering=Adding Explorer menu items…
russian.Registering=Добавляю пункты в меню проводника…

[Code]
// Проверяем, что в выбранную папку можно писать БЕЗ прав администратора.
function NextButtonClick(CurPageID: Integer): Boolean;
var
  Probe: string;
begin
  Result := True;
  if CurPageID <> wpSelectDir then
    Exit;
  ForceDirectories(WizardDirValue);
  Probe := AddBackslash(WizardDirValue) + 'splice_write_test.tmp';
  if SaveStringToFile(Probe, 'x', False) then
    DeleteFile(Probe)
  else begin
    Result := False;
    MsgBox(ExpandConstant('{cm:DirNotWritable}'), mbError, MB_OK);
  end;
end;

// При удалении спрашиваем, оставлять ли FFmpeg и настройки: FFmpeg весит под
// сотню мегабайт. Журнал падений не нужен никому — убираем молча. Нарезанные
// файлы лежат рядом с исходниками и программе не принадлежат.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: string;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  DataDir := ExpandConstant('{userappdata}\{#MyAppName}');
  if not DirExists(DataDir) then
    Exit;
  DelTree(DataDir + '\crash-reports', True, True, True);
  if MsgBox(ExpandConstant('{cm:KeepData}') + '?', mbConfirmation, MB_YESNO) = IDNO then
    DelTree(DataDir, True, True, True);
end;

[Tasks]
Name: "contextmenu"; Description: "{cm:ContextMenu}"
Name: "autostart"; Description: "{cm:AutoStart}"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_update"

[Registry]
; Тот же ключ, что пишет галочка в настройках (splice/autostart.py).
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "{#MyAppName}"; Flags: deletevalue; Tasks: not autostart

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Пункты меню пишет сам exe (splice/shell.py): список расширений и подписи —
; в одном месте, на языке системы. Без галочки — убираем оставшиеся от
; прошлой установки.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--register"; StatusMsg: "{cm:Registering}"; Flags: runhidden waituntilterminated; Tasks: contextmenu
Filename: "{app}\{#MyAppExeName}"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; Tasks: not contextmenu
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterMenu"
