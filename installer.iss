[Setup]
AppName=Cortes Virais
AppVersion=1.0.0
DefaultDirName={autopf}\Cortes Virais
DefaultGroupName=Cortes Virais
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=CortesVirais-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na area de trabalho"; Flags: unchecked

[Files]
Source: "dist\CortesVirais\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Cortes Virais"; Filename: "{app}\CortesVirais.exe"
Name: "{autodesktop}\Cortes Virais"; Filename: "{app}\CortesVirais.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CortesVirais.exe"; Description: "Abrir o Cortes Virais"; Flags: nowait postinstall skipifsilent
