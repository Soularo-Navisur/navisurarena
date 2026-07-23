@echo off
title Construction de NAVISUR.exe

echo.
echo ================================================
echo    NAVISUR v9.8 - Construction de l'exe
echo    Riviera Marine Assurances
echo ================================================
echo.

echo Verification de Python 3.11...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.11 non trouve via py -3.11
    echo Essai avec python...
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERREUR : Python introuvable
        echo Installez Python 3.11 depuis python.org
        echo IMPORTANT : cochez "Add Python to PATH"
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    set PYTHON=py -3.11
)

echo.
echo Installation des dependances...
%PYTHON% -m pip install pywebview pyinstaller pillow flask flask-cors Flask-Login openpyxl --quiet
if errorlevel 1 (
    echo ERREUR installation dependances
    %PYTHON% -m pip install pywebview pyinstaller pillow flask flask-cors Flask-Login openpyxl
    pause
    exit /b 1
)
echo      OK

echo.
echo Generation de l icone...
%PYTHON% create_icon.py
if errorlevel 1 (
    echo AVERTISSEMENT : icone non generee - on continue quand meme
)

echo.
echo Nettoyage...
if exist dist\NAVISUR rmdir /s /q dist\NAVISUR
if exist build rmdir /s /q build
echo      OK

echo.
echo Compilation en cours (2-5 minutes, c est normal)...
echo.
%PYTHON% -m PyInstaller navisur.spec --clean
if errorlevel 1 (
    echo.
    echo ERREUR lors de la compilation
    echo Consultez les messages ci-dessus
    pause
    exit /b 1
)

echo.
echo Preparation du dossier final...
if not exist dist\NAVISUR\data mkdir dist\NAVISUR\data
if not exist dist\NAVISUR\data\documents mkdir dist\NAVISUR\data\documents
if not exist dist\NAVISUR\config mkdir dist\NAVISUR\config
if not exist dist\NAVISUR\logs mkdir dist\NAVISUR\logs
if not exist dist\NAVISUR\backups mkdir dist\NAVISUR\backups

if exist config\api_keys.json copy config\api_keys.json dist\NAVISUR\config\ >nul
if exist config\pays_cache.json copy config\pays_cache.json dist\NAVISUR\config\ >nul
if exist config\parametres_courtier.json copy config\parametres_courtier.json dist\NAVISUR\config\ >nul
if exist INSTALLATION.txt copy INSTALLATION.txt dist\NAVISUR\ >nul
echo      OK

echo.
echo ================================================
echo  TERMINE ! NAVISUR.exe est dans dist\NAVISUR\
echo  Double-cliquez sur NAVISUR.exe pour tester
echo ================================================
echo.
echo Appuyez sur une touche pour ouvrir le dossier...
pause >nul
explorer dist\NAVISUR
