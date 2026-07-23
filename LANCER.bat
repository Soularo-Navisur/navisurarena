@echo off
title NAVISUR — Riviera Marine Assurances
color 0B
chcp 65001 >nul 2>&1

echo.
echo  ====================================================
echo    NAVISUR — Riviera Marine Assurances
echo    Demarrage en cours...
echo  ====================================================
echo.

:: Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERREUR] Python n'est pas installe !
    echo.
    echo  Telechargez Python sur : https://www.python.org/downloads/
    echo  Cochez "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

echo  [1/3] Python detecte
echo  [2/3] Installation des dependances...

:: Installer seulement Flask et openpyxl (pas pywebview)
pip install Flask openpyxl --quiet 2>nul
if errorlevel 1 (
    pip install Flask openpyxl -q
)

echo  [3/3] Lancement de l'application...
echo.
echo  L'application va s'ouvrir dans une fenetre dediee.
echo  (Fermez la fenetre NAVISUR pour quitter)
echo.

:: Lancer le bureau (utilise Edge/Chrome en mode app)
python lancer_bureau.py

if errorlevel 1 (
    echo.
    echo  Ouverture dans le navigateur par defaut...
    python app.py
)

pause
