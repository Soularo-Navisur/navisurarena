#!/bin/bash
echo ""
echo "================================================"
echo "  Riviera Marine Assurances — CRM"
echo "  Démarrage..."
echo "================================================"
echo ""

# Installe les dépendances
pip3 install Flask pywebview openpyxl --quiet 2>/dev/null || \
pip install Flask pywebview openpyxl --quiet 2>/dev/null

# Lance en mode bureau
python3 lancer_bureau.py 2>/dev/null || python lancer_bureau.py
