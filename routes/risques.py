# routes/risques.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/audit-log')
def audit_log_list():
    conn = get_db()
    table_filter  = request.args.get('table', '')
    action_filter = request.args.get('action', '')
    limit = int(request.args.get('limit', 100))

    q = "SELECT a.*, cl.nom, cl.prenom FROM audit_log a LEFT JOIN clients cl ON (a.table_name='clients' AND a.record_id=cl.id) WHERE 1=1"
    p = []
    if table_filter:  q += " AND a.table_name=?"; p.append(table_filter)
    if action_filter: q += " AND a.action=?"; p.append(action_filter)
    q += " ORDER BY a.date_action DESC LIMIT ?"
    p.append(limit)

    logs = conn.execute(q, p).fetchall()
    tables = [r[0] for r in conn.execute(
        "SELECT DISTINCT table_name FROM audit_log ORDER BY table_name").fetchall()]
    nb_total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    conn.close()
    return render_template('audit_log.html', logs=logs, tables=tables,
                           table_filter=table_filter, action_filter=action_filter,
                           nb_total=nb_total, limit=limit)


# ═══════════════════════════════════════════════════════════════
#  MODULE RISQUES — Multi-risques polymorphes
#  Bateau · Jet Ski · Péniche · Yacht · Local Pro · Pro Nautisme
#  Habitation · Autre
# ═══════════════════════════════════════════════════════════════

import json as _json

TYPES_RISQUES = [
    ('bateau',       '⛵ Bateau de plaisance',        'plaisance'),
    ('jet_ski',      '🏄 Jet Ski / Scooter des mers', 'plaisance'),
    ('peniche',      '🚢 Péniche / Bateau fluvial',   'plaisance'),
    ('yacht',        '⚓ Yacht / Grande plaisance',    'plaisance'),
    ('local_pro',    '🏢 Local professionnel',         'pro'),
    ('pro_nautisme', '🔧 Professionnel du nautisme',   'pro'),
    ('habitation',   '🏠 Habitation',                 'autre'),
    ('autre',        '📋 Autre risque',               'autre'),
]
TYPES_RISQUES_MAP = {v: l for v, l, _ in TYPES_RISQUES}

def risque_details_from_form(type_risque):
    """Extrait les champs spécifiques du formulaire selon le type de risque."""
    f = request.form
    d = {}
    if type_risque in ('bateau', 'jet_ski', 'peniche', 'yacht'):
        d['immatriculation'] = f.get('immatriculation', '')
        d['marque']          = f.get('marque', '')
        d['modele']          = f.get('modele', '')
        d['annee']           = f.get('annee', '')
        d['longueur']        = f.get('longueur', '')
        d['largeur']         = f.get('largeur', '')
        d['pavillon']        = f.get('pavillon', 'FR')
        d['port_attache']    = f.get('port_attache', '')
        d['zone_navigation'] = f.get('zone_navigation', '')
        d['usage']           = f.get('usage', '')
        if type_risque != 'jet_ski':
            d['motorisation']   = f.get('motorisation', '')
            d['type_coque']     = f.get('type_coque', '')
        if type_risque == 'peniche':
            d['tirant_eau']     = f.get('tirant_eau', '')
            d['usage_peniche']  = f.get('usage_peniche', 'habitation')
        if type_risque == 'yacht':
            d['nb_cabines']         = f.get('nb_cabines', '')
            d['personnel_bord']     = 1 if f.get('personnel_bord') else 0
            d['nb_equipage']        = f.get('nb_equipage', '')
            d['contrat_pi_prevu']   = 1 if f.get('contrat_pi_prevu') else 0
        # Motorisation commune
        d['moteur_marque']    = f.get('moteur_marque', '')
        d['moteur_puissance'] = f.get('moteur_puissance', '')
        d['moteur_type']      = f.get('moteur_type', '')   # inboard/outboard/voile
        d['moteur_serie']     = f.get('moteur_serie', '')

    elif type_risque in ('local_pro', 'pro_nautisme'):
        d['activite']         = f.get('activite', '')
        d['forme_juridique']  = f.get('forme_juridique', '')
        d['ca_annuel']        = f.get('ca_annuel', '')
        d['nb_employes']      = f.get('nb_employes', '')
        d['surface_m2']       = f.get('surface_m2', '')
        d['type_bail']        = f.get('type_bail', '')
        if type_risque == 'pro_nautisme':
            d['nb_bateaux_flotte']    = f.get('nb_bateaux_flotte', '')
            d['valeur_flotte']        = f.get('valeur_flotte', '')
            d['garanties_rc']         = 1 if f.get('garanties_rc') else 0
            d['garanties_locaux']     = 1 if f.get('garanties_locaux') else 0
            d['garanties_flotte']     = 1 if f.get('garanties_flotte') else 0
            d['garanties_pj']         = 1 if f.get('garanties_pj') else 0

    elif type_risque == 'habitation':
        d['type_bien']          = f.get('type_bien', 'maison')
        d['statut_occupant']    = f.get('statut_occupant', 'proprietaire')
        d['surface_m2']         = f.get('surface_m2', '')
        d['nb_pieces_principales'] = f.get('nb_pieces_principales', '')
        d['etage']              = f.get('etage', '')
        d['annee_construction'] = f.get('annee_construction', '')
        d['type_chauffage']     = f.get('type_chauffage', '')
        d['alarme']             = 1 if f.get('alarme') else 0
        d['piscine']            = 1 if f.get('piscine') else 0
        d['dependances']        = 1 if f.get('dependances') else 0
        d['valeur_mobilier']    = f.get('valeur_mobilier', '')

    return d

# ── CRUD RISQUES ──────────────────────────────────────────────

@app.route('/risques')
def risques_list():
    conn = get_db()
    type_filter = request.args.get('type', '')
    q = """SELECT r.*, c.nom, c.prenom, c.email
        FROM risques r JOIN clients c ON r.client_id=c.id WHERE 1=1"""
    p = []
    if type_filter:
        q += " AND r.type_risque=?"
        p.append(type_filter)
    q += " ORDER BY c.nom, r.date_creation DESC"
    risques = conn.execute(q, p).fetchall()
    conn.close()
    return render_template('risques/index.html', risques=risques,
                           type_filter=type_filter, types=TYPES_RISQUES)

@app.route('/risques/nouveau', methods=['GET', 'POST'])
def risque_nouveau():
    conn = get_db()
    if request.method == 'POST':
        categorie = request.form.get('categorie', 'Bateau')
        sous_categorie = request.form.get('sous_categorie', 'Bateau à moteur')
        conn.execute("""INSERT INTO risques
            (client_id, categorie, sous_categorie, libelle, valeur_assurance, valeur_a_neuf,
             adresse, code_postal, ville, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (request.form['client_id'], categorie, sous_categorie,
             request.form.get('libelle',''),
             float(request.form.get('valeur_assurance') or 0),
             float(request.form.get('valeur_a_neuf') or 0),
             request.form.get('adresse',''),
             request.form.get('code_postal',''),
             request.form.get('ville',''),
             request.form.get('notes','')))
        risque_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        client_id = request.form.get('client_id')
        conn.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.form.get('ajax') == '1':
            return jsonify({
                'success': True,
                'id': risque_id,
                'categorie': categorie,
                'libelle': request.form.get('libelle', ''),
                'valeur': float(request.form.get('valeur_assurance') or 0)
            })
        flash('Risque enregistré !', 'success')
        return redirect(url_for('client_detail', id=client_id) + '#risques')
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    client_id = request.args.get('client_id')
    conn.close()
    return render_template('risques/form.html', risque=None, clients=clients,
                           client_id=client_id, today=date.today().isoformat())

@app.route('/risques/<int:id>/modifier', methods=['GET', 'POST'])
def risque_modifier(id):
    conn = get_db()
    r = conn.execute("SELECT * FROM risques WHERE id=?", (id,)).fetchone()
    if not r: conn.close(); abort(404)
    if request.method == 'POST':
        categorie = request.form.get('categorie', 'Bateau')
        sous_categorie = request.form.get('sous_categorie', 'Bateau à moteur')
        conn.execute("""UPDATE risques SET client_id=?, categorie=?, sous_categorie=?, libelle=?,
            valeur_assurance=?, valeur_a_neuf=?, adresse=?, code_postal=?, ville=?,
            notes=? WHERE id=?""",
            (request.form['client_id'], categorie, sous_categorie,
             request.form.get('libelle',''),
             float(request.form.get('valeur_assurance') or 0),
             float(request.form.get('valeur_a_neuf') or 0),
             request.form.get('adresse',''),
             request.form.get('code_postal',''),
             request.form.get('ville',''),
             request.form.get('notes',''), id))
        conn.commit(); conn.close()
        flash('Risque mis à jour !', 'success')
        return redirect(url_for('client_detail', id=request.form['client_id']) + '#risques')
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    conn.close()
    return render_template('risques/form.html', risque=r,
                           clients=clients,
                           client_id=str(r['client_id']),
                           today=date.today().isoformat())

@app.route('/risques/<int:id>/supprimer', methods=['POST'])
def risque_supprimer(id):
    conn = get_db()
    r = conn.execute("SELECT client_id FROM risques WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM risques WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Risque supprimé.', 'info')
    return redirect(url_for('client_detail', id=r['client_id']) + '#risques' if r else url_for('risques_list'))

@app.route('/risques/<int:id>')
def risque_detail(id):
    conn = get_db()
    r  = conn.execute("""SELECT r.*, c.nom, c.prenom FROM risques r
        JOIN clients c ON r.client_id=c.id WHERE r.id=?""", (id,)).fetchone()
    if not r: conn.close(); abort(404)
    details = _json.loads(r['details'] or '{}')
    contrats = conn.execute("""SELECT ct.id, ct.numero, ct.type_assurance,
        ct.compagnie, ct.statut, ct.prime_annuelle
        FROM contrats ct WHERE ct.risque_id=? ORDER BY ct.date_creation DESC""",
        (id,)).fetchall()
    conn.close()
    return render_template('risques/detail.html', risque=r, details=details,
                           contrats=contrats, types_map=TYPES_RISQUES_MAP)

# ── API : risques d'un client (pour AJAX dans devis/contrat forms) ────────

@app.route('/api/clients/<int:client_id>/risques')
def api_client_risques(client_id):
    conn = get_db()
    type_filter = request.args.get('type', '')
    risques = conn.execute("""SELECT r.id, r.type_risque, r.libelle,
        r.valeur_assurance, r.details FROM risques r
        WHERE r.client_id=?""" + (" AND r.type_risque=?" if type_filter else "") + 
        " ORDER BY r.type_risque, r.libelle",
        (client_id, type_filter) if type_filter else (client_id,)).fetchall()
    bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, b.modele,
        b.immatriculation, b.valeur_assurance
        FROM bateaux b WHERE b.client_id=? ORDER BY b.nom_bateau""",
        (client_id,)).fetchall()
    conn.close()
    return _json_response({
        'risques': [{'id': r['id'], 'type': r['type_risque'],
                      'libelle': r['libelle'], 'valeur': r['valeur_assurance']}
                     for r in risques],
        'bateaux': [{'id': b['id'], 'libelle': f'{b["nom_bateau"] or "Bateau"} — {b["marque"] or ""} {b["immatriculation"] or ""}'.strip(),
                      'valeur': b['valeur_assurance']}
                     for b in bateaux],
    })

def _json_response(data):
    from flask import Response as _Resp
    return _Resp(_json.dumps(data, ensure_ascii=False),
                 mimetype='application/json')


# ═══════════════════════════════════════════════════════════════
#  COMPARATIF DEVIS — Vue côte à côte pour un client
# ═══════════════════════════════════════════════════════════════

