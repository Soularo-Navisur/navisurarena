; ============================================================
; setup_navisur.iss — Script Inno Setup pour NAVISUR v9.8
; Riviera Marine Assurances
;
; Pour générer l'installateur :
; 1. Télécharger Inno Setup : https://jrsoftware.org/isinfo.php
; 2. Ouvrir ce fichier avec Inno Setup
; 3. Menu Build → Compile (ou F9)
; 4. → génère Setup_NAVISUR_v98.exe
; ============================================================

#define AppName "NAVISUR"
#define AppVersion "9.8"
#define AppPublisher "Riviera Marine Assurances"
#define AppURL "https://www.rivieramarine-assurances.fr"
#define AppExeName "NAVISUR.exe"
#define AppContact "contact@rivieramarine-assurances.fr"
#define SourceDir "dist\NAVISUR"

[Setup]
AppId={{A7B3C2D4-E5F6-4789-ABCD-EF0123456789}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportEmail={#AppContact}
DefaultDirName=C:\NAVISUR
DefaultGroupName={#AppName}
AllowNoIcons=no
OutputDir=.
OutputBaseFilename=Setup_NAVISUR_v98
SetupIconFile=navisur.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=navisur_logo.jpg
WizardSmallImageFile=navisur_256.png
MinVersion=10.0
PrivilegesRequired=lowest
; Pas besoin d'admin (installation dans C:\NAVISUR, pas Program Files)
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#AppName} — CRM Courtage Plaisance
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} CRM Courtage Plaisance
VersionInfoVersion={#AppVersion}.0.0
VersionInfoProductName={#AppName}

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
french.WelcomeLabel1=Bienvenue dans l'assistant d'installation de NAVISUR
french.WelcomeLabel2=Ce programme va installer NAVISUR v9.8 sur votre ordinateur.%n%nNAVISUR est le CRM Courtage Plaisance de Riviera Marine Assurances.%n%nIl est recommandé de fermer toutes les applications avant de continuer.
french.KeepData=Voulez-vous conserver vos données (clients, contrats, documents, configuration) ?%n%nCliquez "Oui" pour garder vos données.%nCliquez "Non" pour tout supprimer.

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: checkedonce
Name: "startmenuicon"; Description: "Créer une entrée dans le menu Démarrer"; GroupDescription: "Raccourcis :"; Flags: checkedonce

[Files]
; Exe et dépendances PyInstaller
Source: "{#SourceDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ressources
Source: "{#SourceDir}\templates\*"; DestDir: "{app}\templates"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceDir}\static\*"; DestDir: "{app}\static"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "navisur.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "navisur_256.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "navisur_logo.jpg"; DestDir: "{app}"; Flags: ignoreversion
; Documentation
Source: "INSTALLATION.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "NOUVEAUTES_V96.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme; AfterInstall:
Source: "NOUVEAUTES_TACITE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Créer les dossiers de données (vides au premier lancement)
Name: "{app}\data"
Name: "{app}\data\documents"
Name: "{app}\config"
Name: "{app}\logs"
Name: "{app}\backups"

[Icons]
Name: "{autodesktop}\NAVISUR"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\navisur.ico"; Comment: "NAVISUR — CRM Courtage Plaisance"; Tasks: desktopicon
Name: "{autoprograms}\{#AppName}\NAVISUR"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\navisur.ico"; Tasks: startmenuicon
Name: "{autoprograms}\{#AppName}\Désinstaller NAVISUR"; Filename: "{uninstallexe}"; Tasks: startmenuicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Lancer NAVISUR maintenant"; Flags: nowait postinstall skipifsilent; StatusMsg: "Démarrage de NAVISUR..."

[UninstallRun]
; Arrêter NAVISUR si en cours
Filename: "taskkill"; Parameters: "/F /IM NAVISUR.exe"; Flags: runhidden; RunOnceId: "KillNavisur"

[Code]
var
  KeepDataPage: TInputOptionWizardPage;

procedure InitializeWizard;
begin
  // Page personnalisée pour garder les données lors de la désinstallation
end;

function InitializeUninstall(): Boolean;
var
  MsgResult: Integer;
begin
  MsgResult := MsgBox(
    'Voulez-vous conserver vos données ?' + #13#10 +
    '(clients, contrats, documents, configuration)' + #13#10 + #13#10 +
    'Cliquez "Oui" pour garder vos données.' + #13#10 +
    'Cliquez "Non" pour tout supprimer (IRRÉVERSIBLE).',
    mbConfirmation, MB_YESNO);
  if MsgResult = IDNO then begin
    // Supprimer les dossiers de données
    DelTree(ExpandConstant('{app}\data'), True, True, True);
    DelTree(ExpandConstant('{app}\config'), True, True, True);
    DelTree(ExpandConstant('{app}\logs'), True, True, True);
    DelTree(ExpandConstant('{app}\backups'), True, True, True);
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then begin
    // Supprimer le dossier principal s'il est vide
    RemoveDir(ExpandConstant('{app}'));
  end;
end;
