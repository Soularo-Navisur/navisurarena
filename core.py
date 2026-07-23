"""core.py — NAVISUR v9.9 refactored (facade)"""
from flask import (request, jsonify, render_template, redirect, url_for,
                   flash, send_from_directory, abort, session)
from werkzeug.utils import secure_filename
import os, sys, sqlite3, traceback, uuid, logging, json, urllib.request, urllib.parse, uuid
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager

# ── Modules refactorés ──
from config import (app, BASE_DIR, DATABASE, UPLOAD_FOLDER, BACKUP_DIR, LOG_FILE,
                    CONFIG_DIR, RESOURCE_DIR, get_path, get_resource,
                    ALLOWED_EXTENSIONS, PRODUITS_PLAISANCE, TYPES_DOCUMENTS,
                    STATUTS_CONTRAT, TRANSITIONS_CONTRAT, STATUTS_DEVIS,
                    STATUTS_COMMISSION, NATURES_RECETTE, MODES_REGLEMENT)
from models.db import get_db, db_transaction, init_db
from models.migrations import run_migrations
from utils import (format_size, file_icon, _pays_flag, safe_float, safe_int,
                   validate_dates, validate_email, validate_required,
                   allowed_file, get_compagnie_from_form, format_telephone_fr,
                   calc_urssaf, nlog, navisur_logger,
                   _load_api_keys, _save_api_keys, _api_active, _api_key, _api_incr,
                   _safe_get, API_TIMEOUT, load_pays_cache, PAYS_CACHE_FILE)
# Re-export compatibilité routes anciennes
import urllib.request as _urllib
import urllib.parse as _urlparse
import json as _json_api
import threading as _threading
API_KEYS_FILE = os.path.join(CONFIG_DIR, 'api_keys.json')
PAYS_CACHE_FILE = os.path.join(CONFIG_DIR, 'pays_cache.json')

# ── Globals Jinja ──
app.jinja_env.globals['STATUTS_CONTRAT'] = STATUTS_CONTRAT
app.jinja_env.globals['get_param'] = lambda k, d='': None  # overriden below

# ── Brevo (optionnel) ──
try:
    from brevo_service import get_brevo, reload_brevo
    _BREVO_OK = True
except Exception as _e_brevo:
    _BREVO_OK = False
    def get_brevo():
        class _FakeBrevo:
            active = False
            expediteur_email = 'contact@rivieramarine-assurances.fr'
            expediteur_nom = 'Riviera Marine Assurances'
            def envoyer_email(self, *a, **kw):
                import urllib.parse as _up
                email = a[0] if a else ''
                sujet = a[2] if len(a)>2 else ''
                corps = kw.get('corps_texte', a[3] if len(a)>3 else '')
                p = _up.urlencode({'subject':sujet,'body':corps})
                return {'succes':False,'fallback_mailto':True,
                        'mailto_url':f'mailto:{_up.quote(email)}?{p}','erreur':'Brevo non disponible'}
            def tester_connexion(self): return {'ok':False,'message':'Module Brevo non chargé'}
            def get_quota(self): return {'aujourd_hui':0,'quota_jour':300,'ce_mois':0,'quota_mois':9000}
            def verifier_statuts(self,*a): return []
            def remplacer_variables(self,t,d): return t
        return _FakeBrevo()
    def reload_brevo(): return get_brevo()

# ── Paramètres ──
def get_param(cle, default=''):
    try:
        conn = get_db()
        row = conn.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,)).fetchone()
        conn.close()
        return row['valeur'] if row else default
    except Exception:
        return default

def get_all_params():
    try:
        conn = get_db()
        rows = conn.execute("SELECT cle, valeur FROM parametres").fetchall()
        conn.close()
        return {r['cle']: r['valeur'] for r in rows}
    except Exception:
        return {}

app.jinja_env.globals['get_param'] = get_param

# ── Audit ──
def log_audit(table, record_id, action, champ=None, old_val=None, new_val=None):
    try:
        conn = get_db()
        conn.execute("""INSERT INTO audit_log
            (table_name, record_id, action, champ_modifie, ancienne_valeur, nouvelle_valeur)
            VALUES (?,?,?,?,?,?)""",
            (table, record_id, action, champ,
             str(old_val) if old_val is not None else None,
             str(new_val) if new_val is not None else None))
        conn.commit(); conn.close()
    except Exception:
        pass

# ── Intégrité DB ──
DB_INTEGRITY_OK = True
DB_INTEGRITY_MSG = ''

def check_db_integrity():
    global DB_INTEGRITY_OK, DB_INTEGRITY_MSG
    try:
        conn = sqlite3.connect(DATABASE)
        result = conn.execute('PRAGMA integrity_check').fetchone()
        conn.close()
        ok = (result and result[0] == 'ok')
        DB_INTEGRITY_OK = ok
        DB_INTEGRITY_MSG = result[0] if result else 'Aucun résultat'
        nlog('info', f'PRAGMA integrity_check : {result[0]}')
        return ok, DB_INTEGRITY_MSG
    except Exception as e:
        DB_INTEGRITY_OK = False; DB_INTEGRITY_MSG = str(e)
        nlog('error', f"Impossible de vérifier l'intégrité : {e}")
        return False, str(e)

# ── Context processor ──
@app.context_processor
def inject_globals():
    return {'db_integrity_ok': DB_INTEGRITY_OK, 'db_integrity_msg': DB_INTEGRITY_MSG}

@app.context_processor
def inject_notifs():
    try:
        conn = get_db()
        notifs = conn.execute("SELECT * FROM notifications ORDER BY id DESC LIMIT 15").fetchall()
        conn.close()
        return {'nb_notifs': get_nb_notifs(), 'notifs_list': notifs}
    except Exception:
        return {'nb_notifs': 0, 'notifs_list': []}

# ── Error handlers ──
@app.errorhandler(404)
def page_not_found(e):
    nlog('warning', f'404 — {request.path}')
    try:
        return render_template('errors/404.html'), 404
    except Exception:
        return f'<h2>404 — Page introuvable</h2><p>{request.path}</p>', 404

@app.errorhandler(500)
def internal_error(e):
    nlog('error', f'500 — {request.path} — {e}', exc=True)
    try:
        return render_template('errors/500.html'), 500
    except Exception:
        return '<h2>500 — Erreur serveur</h2>', 500

@app.errorhandler(Exception)
def handle_exception(e):
    if hasattr(e, 'code') and e.code in (404, 405):
        return page_not_found(e) if e.code == 404 else ('', 405)
    nlog('error', f'Exception non gérée [{request.path}] : {e}', exc=True)
    try:
        return render_template('errors/500.html', error_detail=str(e)), 500
    except Exception:
        return f'<h2>Erreur interne</h2><p>{str(e)[:200]}</p>', 500

# ── Notifications ──
def generer_notifications():
    conn = get_db()
    today = date.today(); today_s = today.isoformat()
    conn.execute("DELETE FROM notifications WHERE type != 'manuelle'")

    contrats_exp = conn.execute("""
        SELECT ct.id, ct.numero, ct.type_assurance, ct.date_fin,
               c.nom, c.prenom, c.email,
               CAST(julianday(ct.date_fin) - julianday(?) AS INTEGER) as jours
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.statut='en_cours' AND ct.date_fin IS NOT NULL AND ct.date_fin != ''
          AND julianday(ct.date_fin) - julianday(?) BETWEEN 0 AND 90
        ORDER BY ct.date_fin
    """, (today_s, today_s)).fetchall()
    for ct in contrats_exp:
        j = ct['jours']
        prio = 'haute' if j <= 15 else 'normale' if j <= 30 else 'basse'
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('echeance',?,?,?,?)""", (
            f"Échéance dans {j}j — {ct['prenom'] or ''} {ct['nom']}",
            f"Contrat {ct['numero'] or ct['type_assurance']} expire le {ct['date_fin']}",
            f"/contrats/{ct['id']}", prio))

    expires = conn.execute("""
        SELECT ct.id, ct.numero, ct.type_assurance, ct.date_fin, c.nom, c.prenom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.statut='en_cours' AND ct.date_fin < ? AND ct.date_fin != ''
    """, (today_s,)).fetchall()
    for ct in expires:
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('expiration',?,?,?,'haute')""", (
            f"⚠️ Contrat expiré — {ct['prenom'] or ''} {ct['nom']}",
            f"Contrat {ct['numero'] or ct['type_assurance']} expiré depuis le {ct['date_fin']}",
            f"/contrats/{ct['id']}"))

    conn.commit()
    nb = conn.execute("SELECT COUNT(*) FROM notifications WHERE lu=0").fetchone()[0]
    conn.close()
    return nb

def get_nb_notifs():
    try:
        conn = get_db()
        nb = conn.execute("SELECT COUNT(*) FROM notifications WHERE lu=0").fetchone()[0]
        conn.close()
        return nb
    except Exception:
        return 0

def generer_notifications_enrichies(conn, today_s):
    # primes retard
    primes_retard = conn.execute("""
        SELECT pp.id, pp.montant, pp.date_echeance,
               ct.id as contrat_id, ct.numero, ct.type_assurance,
               c.nom, c.prenom
        FROM primes_paiements pp
        JOIN contrats ct ON pp.contrat_id=ct.id
        JOIN clients c ON ct.client_id=c.id
        WHERE pp.statut IN ('retard','impaye')
          AND pp.date_echeance < ?
    """, (today_s,)).fetchall()
    for p in primes_retard:
        conn.execute("""INSERT INTO notifications
            (type,titre,message,lien,priorite) VALUES ('impaye',?,?,?,'haute')""",
            (f'⚠️ Impayé — {p["prenom"] or ""} {p["nom"]}',
             f'Prime {p["montant"]:.0f} € échue le {p["date_echeance"]} ({p["type_assurance"] or ""})',
             f'/contrats/{p["contrat_id"]}'))

    transmis = conn.execute("""
        SELECT ct.id, ct.numero, ct.compagnie, ct.type_assurance,
               ct.date_transmission_cie, c.nom, c.prenom,
               CAST(julianday(?) - julianday(ct.date_transmission_cie) AS INTEGER) as jours
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.statut='transmis_cie'
          AND ct.date_transmission_cie IS NOT NULL
          AND julianday(?) - julianday(ct.date_transmission_cie) > 15
    """, (today_s, today_s)).fetchall()
    for ct in transmis:
        conn.execute("""INSERT INTO notifications
            (type,titre,message,lien,priorite) VALUES ('transmission',?,?,?,'normale')""",
            (f'⏳ Attente compagnie ({ct["jours"]}j) — {ct["prenom"] or ""} {ct["nom"]}',
             f'{ct["type_assurance"] or ""} transmis le {ct["date_transmission_cie"]} chez {ct["compagnie"] or ""}',
             f'/contrats/{ct["id"]}'))

    devis_exp = conn.execute("""
        SELECT d.id, d.compagnie, d.type_assurance, d.date_expiration,
               c.nom, c.prenom, c.id as cid
        FROM devis d JOIN clients c ON d.client_id=c.id
        WHERE d.statut='en_attente'
          AND d.date_expiration IS NOT NULL
          AND d.date_expiration < ?
    """, (today_s,)).fetchall()
    for d in devis_exp:
        conn.execute("""INSERT INTO notifications
            (type,titre,message,lien,priorite) VALUES ('devis',?,?,?,'basse')""",
            (f'📋 Devis expiré — {d["prenom"] or ""} {d["nom"]}',
             f'{d["type_assurance"] or ""} chez {d["compagnie"] or ""} — expiré le {d["date_expiration"]}',
             f'/clients/{d["cid"]}#devis'))

    sans_dda = conn.execute("""
        SELECT ct.id, ct.numero, ct.type_assurance, c.nom, c.prenom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.statut='en_cours'
        AND NOT EXISTS (
            SELECT 1 FROM dda_recueils d
            WHERE d.client_id=ct.client_id AND d.statut='valide'
        )
        LIMIT 10
    """).fetchall()
    for ct in sans_dda:
        conn.execute("""INSERT INTO notifications
            (type,titre,message,lien,priorite) VALUES ('dda',?,?,?,'basse')""",
            (f'📋 DDA manquant — {ct["prenom"] or ""} {ct["nom"]}',
             f'Contrat {ct["type_assurance"] or ""} sans recueil DDA valide',
             f'/dda/nouveau?client_id={ct["id"]}'))

# ── Backup ──
def sauvegarde_auto():
    import shutil
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = os.path.join(BACKUP_DIR, f'navisur_backup_{ts}.db')
        shutil.copy2(DATABASE, dest)
        nlog('info', f'Sauvegarde auto : {dest}')
    except Exception as e:
        nlog('warning', f'Sauvegarde auto échouée : {e}')

CATEGORIES_RISQUES = {
    'Bateau': [
        'Bateau à moteur',
        'Voilier',
        'Pneumatique',
        'Jet-ski',
        'Semi-rigide',
        'Catamaran',
        'Autre'
    ],
    'Habitation': [
        'Maison',
        'Appartement',
        'Immeuble',
        'Résidence secondaire',
        'Autre'
    ],
    'Local professionnel': [
        'Bureau',
        'Commerce',
        'Entrepôt',
        'Atelier',
        'Restaurant',
        'Autre'
    ],
    'Véhicule': [
        'Voiture',
        'Moto',
        'Utilitaire',
        'Camion',
        'Camping-car',
        'Remorque',
        'Autre'
    ]
}
app.jinja_env.globals['CATEGORIES_RISQUES'] = CATEGORIES_RISQUES
