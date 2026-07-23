"""models/db.py — Connexion SQLite + init schema complet"""
import os, sqlite3
from config import DATABASE, get_resource

# ── Connexion ──
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ── Context manager transactions ──
from contextlib import contextmanager

@contextmanager
def db_transaction():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

# ── Init schema ──
def init_db():
    """Crée toutes les tables et indexes si absents. Le schéma est dans schema.sql."""
    conn = get_db()
    # Exécute le schéma complet
    schema_path = get_resource('models', 'schema.sql')
    if not os.path.exists(schema_path):
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        conn.executescript(f.read())
    # Migrations colonnes contrats si absentes
    for col, typ in [
        ('option_regate', 'INTEGER DEFAULT 0'),
        ('option_skipper_pro', 'INTEGER DEFAULT 0'),
        ('option_annexe', 'INTEGER DEFAULT 0'),
        ('option_hauturier', 'INTEGER DEFAULT 0'),
        ('option_solitaire', 'INTEGER DEFAULT 0'),
        ('flotte_nom', 'TEXT DEFAULT ""'),
        ('co_assureurs', 'TEXT DEFAULT ""'),
    ]:
        try:
            conn.execute(f'ALTER TABLE contrats ADD COLUMN {col} {typ}')
        except Exception:
            pass

    # Migration colonnes risques si absentes
    for col, typ in [
        ('categorie', "TEXT NOT NULL DEFAULT 'Bateau'"),
        ('sous_categorie', "TEXT NOT NULL DEFAULT 'Bateau à moteur'"),
    ]:
        try:
            conn.execute(f'ALTER TABLE risques ADD COLUMN {col} {typ}')
        except Exception:
            pass

    # Migration des bateaux vers risques unifiés
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bateaux'")
        if cursor.fetchone():
            cursor.execute("SELECT * FROM bateaux")
            boats = cursor.fetchall()
            for b in boats:
                b_dict = dict(b)
                existing = cursor.execute("SELECT id FROM risques WHERE client_id=? AND libelle=?", 
                                          (b_dict.get('client_id'), b_dict.get('nom_bateau') or b_dict.get('marque') or 'Bateau')).fetchone()
                if not existing:
                    client_id = b_dict.get('client_id')
                    nom = b_dict.get('nom_bateau') or b_dict.get('marque') or 'Bateau'
                    type_b = b_dict.get('type_bateau') or 'Bateau à moteur'
                    val_ass = b_dict.get('valeur_assurance') or 0
                    val_neuf = b_dict.get('valeur_a_neuf') or 0
                    port = b_dict.get('port_attache') or ''
                    notes = b_dict.get('notes') or ''
                    import json as _json
                    details = _json.dumps({
                        'marque': b_dict.get('marque', ''),
                        'modele': b_dict.get('modele', ''),
                        'immatriculation': b_dict.get('immatriculation', ''),
                        'annee_fabrication': b_dict.get('annee_fabrication', ''),
                        'longueur': b_dict.get('longueur', ''),
                        'largeur': b_dict.get('largeur', ''),
                        'pavillon': b_dict.get('pavillon', ''),
                        'port_attache': port,
                        'zone_navigation': b_dict.get('zone_navigation', ''),
                        'usage': b_dict.get('usage', ''),
                        'moteur_marque': b_dict.get('moteur_marque', ''),
                        'moteur_modele': b_dict.get('moteur_modele', ''),
                        'moteur_puissance': b_dict.get('moteur_puissance', ''),
                    }, ensure_ascii=False)
                    cursor.execute("""INSERT INTO risques (client_id, categorie, sous_categorie, libelle, valeur_assurance, valeur_a_neuf, adresse, notes, details)
                                      VALUES (?, 'Bateau', ?, ?, ?, ?, ?, ?, ?)""",
                                   (client_id, type_b, nom, val_ass, val_neuf, port, notes, details))
                    new_risk_id = cursor.lastrowid
                    cursor.execute("UPDATE contrats SET risque_id=?, bateau_id=NULL WHERE bateau_id=?", (new_risk_id, b_dict['id']))
                    cursor.execute("UPDATE sinistres SET risque_id=? WHERE bateau_id=?", (new_risk_id, b_dict['id']))
            conn.commit()
    except Exception as e:
        pass
    # Table de version pour traçabilité (optionnel)
    conn.execute("""CREATE TABLE IF NOT EXISTS __schema_version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        version INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("INSERT OR IGNORE INTO __schema_version (id, version) VALUES (1, 0)")
    conn.commit()
    conn.close()
