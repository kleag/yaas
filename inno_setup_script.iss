; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

[Setup]
AppId=51bf107a-58a8-4256-82db-d1bb714a8423
AppName=Yaas
AppVersion=0.2.0
AppPublisher=Gaël de Chalendar
AppPublisherURL=https://github.com/kleag/yaas
AppContact=kleagg@gmail.com
DefaultDirName={autopf}\YAAS
DefaultGroupName=Yaas
OutputDir=.
OutputBaseFilename=yaas_installer
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\yaas.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Yaas"; Filename: "{app}\yaas.exe"
Name: "{group}\{cm:UninstallProgram,Yaas}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Yaas"; Filename: "{app}\yaas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\yaas.exe"; Description: "{cm:LaunchProgram,Yaas}"; Flags: nowait postinstall skipifsilent

