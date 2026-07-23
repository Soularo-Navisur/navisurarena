"""
migrate_brevo.py — Migration automatique Brevo
NAVISUR v9.9

Exécuté automatiquement au démarrage de NAVISUR.
Crée/modifie les tables nécessaires sans toucher aux données existantes.
"""
import sqlite3
import os
import sys
import logging

_log = logging.getLogger('navisur')


def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def run_migration(db_path: str):
    """Lance toutes les migrations Brevo sur la base SQLite donnée."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    nb = 0

    # ── 1. Table communications ──────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS communications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER REFERENCES clients(id),
        contrat_id INTEGER REFERENCES contrats(id),
        devis_id INTEGER REFERENCES devis(id),
        sinistre_id INTEGER REFERENCES sinistres(id),
        date_envoi DATETIME DEFAULT CURRENT_TIMESTAMP,
        type TEXT DEFAULT 'email_brevo',
        modele_utilise TEXT,
        destinataire_email TEXT,
        objet TEXT,
        corps_email TEXT,
        statut TEXT DEFAULT 'envoye',
        brevo_message_id TEXT,
        date_ouverture DATETIME,
        date_clic DATETIME,
        erreur_detail TEXT,
        pieces_jointes TEXT
    )''')

    # Index pour performance
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_comm_client ON communications(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_comm_date ON communications(date_envoi)",
        "CREATE INDEX IF NOT EXISTS idx_comm_statut ON communications(statut)",
    ]:
        try:
            c.execute(idx)
        except Exception:
            pass

    # ── 2. Colonnes manquantes sur journal_activites ─────────
    ja_cols = [
        ('brevo_message_id', 'TEXT'),
        ('email_statut', 'TEXT DEFAULT \'envoye\''),
    ]
    for col, typ in ja_cols:
        try:
            c.execute(f'ALTER TABLE journal_activites ADD COLUMN {col} {typ}')
            nb += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    _log.info(f'Migration Brevo terminée — {nb} colonne(s) ajoutée(s)')


if __name__ == '__main__':
    app_dir = get_app_dir()
    db = os.path.join(app_dir, 'data', 'navisur.db')
    if not os.path.exists(db):
        db = os.path.join(app_dir, 'riviera-marine.db')
    if os.path.exists(db):
        run_migration(db)
        print('✅ Migration Brevo terminée.')
    else:
        print(f'❌ Base de données introuvable : {db}')
