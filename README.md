# 🏢 NAVISUR — Logiciel de gestion pour courtiers

Logiciel CRM local, gratuit et open-source pour courtiers en assurance.
Inspiré de Courtigo, fonctionne 100% sur votre ordinateur, sans abonnement.

---

## ✅ Fonctionnalités incluses

| Module | Description |
|---|---|
| 👥 Clients & Prospects | Fiches complètes, recherche, filtres par statut |
| 📄 Contrats | Gestion des contrats par compagnie et type d'assurance |
| ⚠️ Sinistres | Déclaration, suivi, montants estimés et indemnisés |
| 💰 Commissions | Saisie des bordereaux, suivi reçu/attendu par période |
| 🧾 Facturation | Création de factures avec numérotation automatique, TVA |

---

## 🚀 Installation (1 minute)

### Prérequis : Python
Téléchargez Python sur **https://www.python.org/downloads/**
> ⚠️ Cochez **"Add Python to PATH"** lors de l'installation !

### Windows
Double-cliquez sur **`LANCER.bat`**

### Mac / Linux
```bash
chmod +x LANCER.sh
./LANCER.sh
```

### Lancement manuel
```bash
pip install Flask
python app.py
```

Puis ouvrez votre navigateur sur **http://127.0.0.1:5000**

---

## 📁 Structure des fichiers

```
crm-courtage/
├── app.py                  ← Application principale (routes + base de données)
├── navisur.db         ← Base de données SQLite (créée au 1er lancement)
├── requirements.txt        ← Dépendances Python
├── LANCER.bat              ← Lancement Windows
├── LANCER.sh               ← Lancement Mac/Linux
├── static/
│   └── css/style.css       ← Styles de l'interface
└── templates/
    ├── base.html           ← Template principal (sidebar, nav)
    ├── dashboard.html      ← Tableau de bord
    ├── clients/            ← Module clients
    ├── contrats/           ← Module contrats
    ├── sinistres/          ← Module sinistres
    ├── commissions/        ← Module commissions
    └── factures/           ← Module facturation
```

---

## 💾 Sauvegarde de vos données

Toutes vos données sont dans le fichier **`navisur.db`**.
Copiez ce fichier régulièrement pour sauvegarder vos données.

---

## 🔧 Évolutions possibles

- Export PDF des factures
- Import CSV de clients
- Module marketing / emailing
- Statistiques avancées avec graphiques
- Export Excel des commissions

---

*Développé avec Flask (Python) + SQLite + Bootstrap 5*
*Version 1.0 — 100% local, 100% gratuit*
