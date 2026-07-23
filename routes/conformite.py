# routes/conformite.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/clients/<int:client_id>/comparatif-devis')
def comparatif_devis(client_id):
    """Affiche tous les devis en cours d'un client pour comparer."""
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client: conn.close(); abort(404)
    devis_list = conn.execute("""SELECT d.*,
        r.libelle as risque_libelle, r.type_risque
        FROM devis d
        LEFT JOIN risques r ON d.risque_id=r.id
        WHERE d.client_id=?
        ORDER BY d.statut='accepte' DESC, d.prime_proposee ASC""",
        (client_id,)).fetchall()
    conn.close()
    return render_template('devis/comparatif.html', client=client,
                           devis_list=devis_list, today=date.today().isoformat())

@app.route('/devis/multi/nouveau', methods=['GET','POST'])
def devis_multi_nouveau():
    """Créer plusieurs devis d'un coup pour un même risque (multi-compagnies)."""
    conn = get_db()
    if request.method == 'POST':
        client_id = request.form['client_id']
        type_assurance = request.form.get('type_assurance','')
        risque_id = request.form.get('risque_id') or None
        compagnies_list = request.form.getlist('compagnie[]')
        primes_list     = request.form.getlist('prime[]')
        notes_list      = request.form.getlist('note_conseil[]')
        d_devis = date.today().isoformat()
        nb_crees = 0
        for i, cp in enumerate(compagnies_list):
            if not cp.strip(): continue
            prime = float(primes_list[i]) if i < len(primes_list) and primes_list[i] else 0
            note  = notes_list[i] if i < len(notes_list) else ''
            conn.execute("""INSERT INTO devis
                (client_id, date_devis, compagnie, type_assurance, prime_proposee,
                 statut, risque_id, note_conseil, validite_jours)
                VALUES (?,?,?,?,?,'en_attente',?,?,30)""",
                (client_id, d_devis, cp, type_assurance,
                 prime, risque_id, note))
            nb_crees += 1
        conn.commit(); conn.close()
        flash(f'{nb_crees} devis créés !', 'success')
        return redirect(url_for('comparatif_devis', client_id=client_id))
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    client_id = request.args.get('client_id')
    risques = []
    if client_id:
        risques = conn.execute(
            "SELECT id,type_risque,libelle FROM risques WHERE client_id=? ORDER BY libelle",
            (client_id,)).fetchall()
    conn.close()
    return render_template('devis/multi_form.html', clients=clients, risques=risques,
                           client_id=client_id, today=date.today().isoformat(),
                           produits=PRODUITS_PLAISANCE)


# ═══════════════════════════════════════════════════════════════
#  AMÉLIORATIONS v8.9+ : Note de couverture PDF · Historique ·
#  Numérotation sinistres · Recherche enrichie · DDA indicateur
# ═══════════════════════════════════════════════════════════════

import json as _json2

# ── NOTE DE COUVERTURE PDF ────────────────────────────────────

@app.route('/contrats/<int:id>/note-couverture')
def contrat_note_couverture(id):
    """Génère une note de couverture imprimable pour le client."""
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom,c.email,c.adresse,c.code_postal,c.ville,c.telephone,
        b.nom_bateau,b.immatriculation,b.marque,b.modele,b.longueur,b.valeur_assurance as val_bateau,
        r.libelle as risque_libelle,r.type_risque,r.details as risque_details,r.valeur_assurance as val_risque
        FROM contrats ct
        JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        LEFT JOIN risques r ON ct.risque_id=r.id
        WHERE ct.id=?""", (id,)).fetchone()
    if not ct:
        conn.close(); abort(404)
    avenants = conn.execute(
        "SELECT * FROM avenants WHERE contrat_id=? AND statut='accepte' ORDER BY date_avenant",
        (id,)).fetchall()
    params = get_all_params()
    conn.close()
    risque_details = {}
    if ct['risque_details']:
        try: risque_details = _json2.loads(ct['risque_details'])
        except: pass
    return render_template('contrats/note_couverture.html',
        contrat=ct, avenants=avenants, params=params,
        risque_details=risque_details,
        today=date.today().isoformat())

# ── HISTORIQUE MODIFICATIONS CONTRAT ─────────────────────────

@app.route('/contrats/<int:id>/historique')
def contrat_historique(id):
    """Onglet historique : audit_log filtré sur ce contrat."""
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    if not ct: conn.close(); abort(404)

    logs_contrat = conn.execute(
        """SELECT * FROM audit_log WHERE table_name='contrats' AND record_id=?
           ORDER BY date_action DESC""", (id,)).fetchall()
    logs_avenants = conn.execute(
        """SELECT a.*, al.action, al.champ_modifie, al.ancienne_valeur,
            al.nouvelle_valeur, al.date_action
           FROM avenants a
           LEFT JOIN audit_log al ON al.table_name='avenants' AND al.record_id=a.id
           WHERE a.contrat_id=?
           ORDER BY a.date_avenant DESC""", (id,)).fetchall()
    conn.close()
    return render_template('contrats/historique.html',
        contrat=ct, logs=logs_contrat, avenants=logs_avenants)

# ── NUMÉROTATION AUTOMATIQUE SINISTRES ───────────────────────

def gen_numero_sinistre():
    """Génère SIN-YYYY-NNN unique."""
    conn = get_db()
    annee = date.today().year
    nb = conn.execute(
        "SELECT COUNT(*)+1 FROM sinistres WHERE strftime('%Y',date_creation)=?",
        (str(annee),)).fetchone()[0]
    conn.close()
    return f'SIN-{annee}-{nb:03d}'

# ── RECHERCHE GLOBALE ENRICHIE ────────────────────────────────

@app.route('/recherche/globale')
def recherche_globale():
    q = request.args.get('q','').strip()
    if not q or len(q) < 2:
        return render_template('recherche_globale.html', q=q,
                               resultats={}, total=0)
    conn = get_db()
    p = f'%{q}%'

    clients = conn.execute(
        "SELECT id,nom,prenom,email,telephone,statut FROM clients WHERE nom LIKE ? OR prenom LIKE ? OR email LIKE ?",
        (p,p,p)).fetchall()

    contrats = conn.execute(
        """SELECT ct.id,ct.numero,ct.type_assurance,ct.compagnie,ct.statut,
               ct.numero_police_cie,c.nom,c.prenom
           FROM contrats ct JOIN clients c ON ct.client_id=c.id
           WHERE ct.numero LIKE ? OR ct.compagnie LIKE ? OR ct.type_assurance LIKE ?
              OR ct.numero_police_cie LIKE ? OR c.nom LIKE ?""",
        (p,p,p,p,p)).fetchall()

    devis = conn.execute(
        """SELECT d.id,d.compagnie,d.type_assurance,d.statut,d.prime_proposee,
               c.nom,c.prenom
           FROM devis d JOIN clients c ON d.client_id=c.id
           WHERE d.compagnie LIKE ? OR d.type_assurance LIKE ? OR c.nom LIKE ?""",
        (p,p,p)).fetchall()

    risques = conn.execute(
        """SELECT r.id,r.type_risque,r.libelle,r.valeur_assurance,c.nom,c.prenom,c.id as cid
           FROM risques r JOIN clients c ON r.client_id=c.id
           WHERE r.libelle LIKE ? OR r.details LIKE ? OR c.nom LIKE ?""",
        (p,p,p)).fetchall()

    sinistres = conn.execute(
        """SELECT s.id,s.numero,s.type_sinistre,s.statut,s.numero_sinistre_cie,
               s.gestionnaire_cie,c.nom,c.prenom
           FROM sinistres s JOIN clients c ON s.client_id=c.id
           WHERE s.numero LIKE ? OR s.numero_sinistre_cie LIKE ?
              OR s.gestionnaire_cie LIKE ? OR s.description LIKE ? OR c.nom LIKE ?""",
        (p,p,p,p,p)).fetchall()

    avenants = conn.execute(
        """SELECT a.id,a.numero,a.type_avenant,a.description,a.contrat_id,
               c.nom,c.prenom
           FROM avenants a
           JOIN contrats ct ON a.contrat_id=ct.id
           JOIN clients c ON ct.client_id=c.id
           WHERE a.numero LIKE ? OR a.description LIKE ? OR c.nom LIKE ?""",
        (p,p,p)).fetchall()

    conn.close()
    resultats = {
        'clients':  clients,
        'contrats': contrats,
        'devis':    devis,
        'risques':  risques,
        'sinistres':sinistres,
        'avenants': avenants,
    }
    total = sum(len(v) for v in resultats.values())
    return render_template('recherche_globale.html', q=q,
                           resultats=resultats, total=total)

# ── API : STATUT DDA D'UN CLIENT ──────────────────────────────

@app.route('/api/clients/<int:client_id>/dda-status')
def api_dda_status(client_id):
    conn = get_db()
    dda = conn.execute(
        """SELECT id,date_recueil,date_signature,statut,version
           FROM dda_recueils WHERE client_id=?
           ORDER BY date_recueil DESC LIMIT 1""",
        (client_id,)).fetchone()
    conn.close()
    if not dda:
        return _json_response({'status':'absent','label':'DDA manquant','color':'red'})
    # DDA > 2 ans → à renouveler
    try:
        from datetime import datetime as _dt
        age_days = (_dt.now() - _dt.fromisoformat(dda['date_recueil'])).days
        if age_days > 730:
            return _json_response({'status':'old','label':f'DDA à renouveler ({dda["date_recueil"][:7]})','color':'orange'})
    except Exception:
        pass
    if dda['statut'] == 'valide':
        return _json_response({'status':'ok','label':f'DDA valide ({dda["date_recueil"][:7]})','color':'green'})
    return _json_response({'status':'draft','label':f'DDA brouillon ({dda["date_recueil"][:7]})','color':'orange'})



# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.3 — ADMINISTRATION : LOGS + SANTÉ SYSTÈME
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/logs')
def admin_logs():
    """Affiche les 200 dernières lignes du log navisur.log."""
    lines = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
        lines = list(reversed(all_lines[-200:]))
    return render_template('admin/logs.html', lines=lines, log_file=LOG_FILE)

@app.route('/admin/sante')
def admin_sante():
    """Page de santé système : DB, sauvegardes, documents."""
    import glob as _glob
    # Taille DB
    db_size = os.path.getsize(DATABASE) if os.path.exists(DATABASE) else 0
    # Dernière sauvegarde
    backups = sorted(_glob.glob(os.path.join(BACKUP_DIR, '*.db')), reverse=True)
    last_backup = None
    last_backup_size = 0
    if backups:
        last_backup = {
            'nom': os.path.basename(backups[0]),
            'date': datetime.fromtimestamp(os.path.getmtime(backups[0])).strftime('%d/%m/%Y à %H:%M'),
            'taille': os.path.getsize(backups[0]),
        }
        last_backup_size = os.path.getsize(backups[0])
    # Nombre de documents
    upload_count = 0
    upload_size = 0
    if os.path.exists(UPLOAD_FOLDER):
        files = os.listdir(UPLOAD_FOLDER)
        upload_count = len(files)
        upload_size = sum(os.path.getsize(os.path.join(UPLOAD_FOLDER, f)) for f in files if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)))
    # Dernières erreurs du log
    last_errors = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if '[ERROR]' in line or '[WARNING]' in line:
                    last_errors.append(line.strip())
        last_errors = list(reversed(last_errors[-5:]))
    return render_template('admin/sante.html',
        db_integrity_ok=DB_INTEGRITY_OK, db_integrity_msg=DB_INTEGRITY_MSG,
        db_size=db_size, last_backup=last_backup, nb_backups=len(backups),
        upload_count=upload_count, upload_size=upload_size,
        last_errors=last_errors, log_file=LOG_FILE)

@app.route('/admin/sante/verifier', methods=['POST'])
def admin_integrity_check():
    ok, msg = check_db_integrity()
    if ok:
        flash('✅ Intégrité vérifiée : base de données saine.', 'success')
    else:
        flash(f'❌ Problème détecté : {msg}', 'error')
    return redirect(url_for('admin_sante'))

# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.3 — MODULE RÉCLAMATIONS ACPR
# ═══════════════════════════════════════════════════════════════

def _jours_ouvrables(date_debut, nb_jours):
    """Calcule une date en ajoutant nb_jours ouvrables (lun-ven)."""
    from datetime import timedelta
    d = datetime.strptime(date_debut, '%Y-%m-%d').date() if isinstance(date_debut, str) else date_debut
    compteur = 0
    while compteur < nb_jours:
        d += timedelta(days=1)
        if d.weekday() < 5:
            compteur += 1
    return d.isoformat()

@app.route('/reclamations')
def reclamations_list():
    conn = get_db()
    statut = request.args.get('statut', '')
    q = """SELECT r.*, c.nom, c.prenom, c.email
           FROM reclamations r JOIN clients c ON r.client_id=c.id
           WHERE 1=1"""
    params = []
    if statut:
        q += " AND r.statut=?"
        params.append(statut)
    q += " ORDER BY r.date_reception DESC"
    reclamations = conn.execute(q, params).fetchall()
    # Compter les délais dépassés
    today = date.today().isoformat()
    en_retard = [r for r in reclamations if r['statut'] not in ('resolue', 'classee')
                 and r['date_reponse_prevue'] and r['date_reponse_prevue'] < today]
    conn.close()
    return render_template('reclamations/index.html',
        reclamations=reclamations, statut=statut, en_retard=len(en_retard))

@app.route('/reclamations/nouvelle', methods=['GET', 'POST'])
def reclamation_nouvelle():
    conn = get_db()
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        date_rec = request.form.get('date_reception', date.today().isoformat())
        objet = request.form.get('objet', '').strip()
        if not client_id or not objet:
            flash('Client et objet sont obligatoires.', 'error')
            clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
            conn.close()
            return render_template('reclamations/form.html', clients=clients, reclamation=None)
        # Calcul délais légaux
        date_accuse = _jours_ouvrables(date_rec, 10)
        from datetime import timedelta
        date_rep_prevue = (datetime.strptime(date_rec, '%Y-%m-%d') + timedelta(days=60)).strftime('%Y-%m-%d')
        with db_transaction() as c:
            c.execute("""INSERT INTO reclamations
                (client_id, contrat_id, date_reception, canal, objet, description,
                 statut, date_accuse, date_reponse_prevue, notes)
                VALUES (?,?,?,?,?,?,'recue',?,?,?)""",
                (client_id, request.form.get('contrat_id') or None,
                 date_rec, request.form.get('canal', 'email'), objet,
                 request.form.get('description', ''),
                 date_accuse, date_rep_prevue,
                 request.form.get('notes', '')))
            new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        nlog('info', f'Réclamation #{new_id} créée — client #{client_id} — {objet}')
        log_audit('reclamations', new_id, 'INSERT', 'creation', None, objet)
        flash('✅ Réclamation enregistrée. Accusé de réception à envoyer avant le ' + date_accuse[:10].replace('-', '/')[8:] + '/' + date_accuse[5:7] + '/' + date_accuse[:4] + '.', 'success')
        return redirect(url_for('reclamation_detail', id=new_id))
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("SELECT id,numero,compagnie,client_id FROM contrats WHERE statut='en_cours' ORDER BY numero").fetchall()
    conn.close()
    return render_template('reclamations/form.html', clients=clients, contrats=contrats, reclamation=None)

@app.route('/reclamations/<int:id>')
def reclamation_detail(id):
    conn = get_db()
    r = conn.execute("""SELECT r.*, c.nom, c.prenom, c.email, c.telephone,
                        ct.numero as contrat_numero, ct.compagnie
                        FROM reclamations r JOIN clients c ON r.client_id=c.id
                        LEFT JOIN contrats ct ON r.contrat_id=ct.id
                        WHERE r.id=?""", (id,)).fetchone()
    if not r: conn.close(); abort(404)
    historique = conn.execute("""SELECT * FROM audit_log WHERE table_name='reclamations' AND record_id=?
                                  ORDER BY date_action DESC""", (id,)).fetchall()
    conn.close()
    today = date.today().isoformat()
    return render_template('reclamations/detail.html', r=r, historique=historique, today=today)

@app.route('/reclamations/<int:id>/modifier', methods=['GET', 'POST'])
def reclamation_modifier(id):
    conn = get_db()
    r = conn.execute("SELECT * FROM reclamations WHERE id=?", (id,)).fetchone()
    if not r: conn.close(); abort(404)
    if request.method == 'POST':
        old_statut = r['statut']
        new_statut = request.form.get('statut', old_statut)
        conn.execute("""UPDATE reclamations SET statut=?, date_accuse=?, date_reponse_effective=?,
            reponse_apportee=?, satisfait=?, mediateur_saisi=?, date_mediateur=?, notes=?
            WHERE id=?""",
            (new_statut, request.form.get('date_accuse', ''),
             request.form.get('date_reponse_effective', '') or None,
             request.form.get('reponse_apportee', ''),
             1 if request.form.get('satisfait') else 0,
             1 if request.form.get('mediateur_saisi') else 0,
             request.form.get('date_mediateur', '') or None,
             request.form.get('notes', ''), id))
        conn.commit()
        conn.close()
        if old_statut != new_statut:
            log_audit('reclamations', id, 'UPDATE', 'statut', old_statut, new_statut)
        nlog('info', f'Réclamation #{id} mise à jour → {new_statut}')
        flash('Réclamation mise à jour.', 'success')
        return redirect(url_for('reclamation_detail', id=id))
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    conn.close()
    return render_template('reclamations/form.html', clients=clients, reclamation=r, contrats=[])

@app.route('/reclamations/export-pdf')
def reclamations_export_rapport():
    """Rapport annuel réclamations (HTML imprimable pour PDF)."""
    conn = get_db()
    annee = int(request.args.get('annee', date.today().year))
    reclamations = conn.execute("""SELECT r.*, c.nom, c.prenom
        FROM reclamations r JOIN clients c ON r.client_id=c.id
        WHERE substr(r.date_reception,1,4)=?
        ORDER BY r.date_reception""", (str(annee),)).fetchall()
    stats = {
        'total': len(reclamations),
        'resolues': sum(1 for r in reclamations if r['statut'] == 'resolue'),
        'en_cours': sum(1 for r in reclamations if r['statut'] in ('recue','en_cours')),
        'mediateur': sum(1 for r in reclamations if r['mediateur_saisi']),
        'satisfaits': sum(1 for r in reclamations if r['satisfait']),
    }
    params = get_all_params()
    conn.close()
    return render_template('reclamations/rapport_pdf.html',
        reclamations=reclamations, stats=stats, annee=annee, params=params)

# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.3 — MODULE FORMATIONS DDA
# ═══════════════════════════════════════════════════════════════

@app.route('/conformite/formations')
def formations_list():
    conn = get_db()
    annee = int(request.args.get('annee', date.today().year))
    formations = conn.execute("""SELECT * FROM formations_dda
        WHERE substr(date_formation,1,4)=? ORDER BY date_formation DESC""",
        (str(annee),)).fetchall()
    total_heures = sum(f['duree_heures'] for f in formations)
    # Toutes les années disponibles
    annees = [r[0] for r in conn.execute(
        "SELECT DISTINCT substr(date_formation,1,4) FROM formations_dda ORDER BY 1 DESC").fetchall()]
    if str(annee) not in annees:
        annees.insert(0, str(annee))
    conn.close()
    return render_template('conformite/formations.html',
        formations=formations, total_heures=total_heures,
        annee=annee, annees=annees, objectif=15)

@app.route('/conformite/formations/nouvelle', methods=['GET', 'POST'])
def formation_nouvelle():
    if request.method == 'POST':
        titre = request.form.get('titre', '').strip()
        duree = request.form.get('duree_heures', '0')
        date_f = request.form.get('date_formation', '')
        if not titre or not date_f:
            flash('Titre et date sont obligatoires.', 'error')
            return render_template('conformite/formation_form.html', formation=None)
        try:
            duree_f = float(duree)
        except ValueError:
            duree_f = 0.0
        # Gérer upload attestation
        attestation_fichier = None
        att_file = request.files.get('attestation')
        if att_file and att_file.filename and allowed_file(att_file.filename):
            att_name = f"formation_{uuid.uuid4().hex[:10]}_{secure_filename(att_file.filename)}"
            att_path = os.path.join(UPLOAD_FOLDER, att_name)
            att_file.save(att_path)
            attestation_fichier = att_name
        with db_transaction() as c:
            c.execute("""INSERT INTO formations_dda
                (titre, organisme, date_formation, duree_heures, type_formation, attestation_fichier, notes)
                VALUES (?,?,?,?,?,?,?)""",
                (titre, request.form.get('organisme', ''),
                 date_f, duree_f,
                 request.form.get('type_formation', 'continue'),
                 attestation_fichier, request.form.get('notes', '')))
        nlog('info', f'Formation DDA ajoutée : {titre} ({duree_f}h)')
        flash(f'✅ Formation "{titre}" ({duree_f}h) enregistrée.', 'success')
        return redirect(url_for('formations_list'))
    return render_template('conformite/formation_form.html', formation=None)

@app.route('/conformite/formations/<int:id>/supprimer', methods=['POST'])
def formation_supprimer(id):
    conn = get_db()
    f = conn.execute("SELECT * FROM formations_dda WHERE id=?", (id,)).fetchone()
    if f and f['attestation_fichier']:
        fp = os.path.join(UPLOAD_FOLDER, f['attestation_fichier'])
        if os.path.exists(fp): os.remove(fp)
    conn.execute("DELETE FROM formations_dda WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Formation supprimée.', 'info')
    return redirect(url_for('formations_list'))

@app.route('/api/formations/heures/<int:annee>')
def api_formations_heures(annee):
    conn = get_db()
    total = conn.execute("""SELECT COALESCE(SUM(duree_heures),0) FROM formations_dda
        WHERE substr(date_formation,1,4)=?""", (str(annee),)).fetchone()[0]
    conn.close()
    return jsonify({'annee': annee, 'total_heures': float(total), 'objectif': 15,
                    'pct': round(float(total)/15*100, 1)})

# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.3 — PARAMÈTRES FISCAUX PAR ANNÉE
# ═══════════════════════════════════════════════════════════════

