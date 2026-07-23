# routes/clients.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import (
    _load_api_keys, _api_active, _api_key, _safe_get,
    _urllib, _urlparse, _json_api,
    load_pays_cache, format_telephone_fr,
    app, get_db, nlog, log_audit, get_path, get_resource, UPLOAD_FOLDER,
    TYPES_DOCUMENTS, allowed_file, secure_filename, send_from_directory,
    request, jsonify, render_template, redirect, url_for, flash, abort,
    date, datetime, timedelta, os,
)
import uuid

@app.route('/clients')
def clients_list():
    conn = get_db()
    search           = request.args.get('q', '')
    statut           = request.args.get('statut', '')
    permis           = request.args.get('permis', '')
    compagnie_filter = request.args.get('compagnie', '')
    ville_filter     = request.args.get('ville', '')

    query = """SELECT c.*,
        COUNT(DISTINCT ct.id) as nb_contrats_actifs,
        COUNT(DISTINCT b.id) as nb_bateaux,
        COALESCE(GROUP_CONCAT(DISTINCT b.nom_bateau), '') as noms_bateaux,
        COALESCE(SUM(ct.prime_annuelle), 0) as prime_totale,
        COALESCE(GROUP_CONCAT(DISTINCT ct.compagnie), '') as compagnies_actives
        FROM clients c
        LEFT JOIN contrats ct ON ct.client_id=c.id AND ct.statut='en_cours'
        LEFT JOIN bateaux b ON b.client_id=c.id
        WHERE 1=1"""
    params = []
    if search:
        query += " AND (c.nom LIKE ? OR c.prenom LIKE ? OR c.email LIKE ? OR c.telephone LIKE ?)"
        params += [f'%{search}%'] * 4
    if statut:
        query += " AND c.statut=?"
        params.append(statut)
    if permis:
        query += " AND c.type_permis_mer=?"
        params.append(permis)
    if ville_filter:
        query += " AND c.ville LIKE ?"
        params.append(f'%{ville_filter}%')
    if compagnie_filter:
        query += """ AND EXISTS (SELECT 1 FROM contrats ct2
            WHERE ct2.client_id=c.id AND ct2.compagnie=? AND ct2.statut='en_cours')"""
        params.append(compagnie_filter)
    query += " GROUP BY c.id ORDER BY c.nom"

    clients = [dict(r) for r in conn.execute(query, params).fetchall()]
    totals = {
        'tous':    conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
        'client':  conn.execute("SELECT COUNT(*) FROM clients WHERE statut='client'").fetchone()[0],
        'prospect':conn.execute("SELECT COUNT(*) FROM clients WHERE statut='prospect'").fetchone()[0],
        'inactif': conn.execute("SELECT COUNT(*) FROM clients WHERE statut='inactif'").fetchone()[0],
    }
    conn.close()
    return render_template('clients/index.html', clients=clients, search=search,
                           statut=statut, permis=permis,
                           compagnie_filter=compagnie_filter, ville_filter=ville_filter,
                           totals=totals)

@app.route('/clients/nouveau', methods=['GET', 'POST'])
def client_nouveau():
    if request.method == 'POST':
        conn = get_db()
        _tel_fmt2 = format_telephone_fr(request.form.get('telephone', ''))
        conn.execute('''INSERT INTO clients
            (type, nom, prenom, email, telephone, adresse, code_postal, ville, siren,
             statut, notes, date_naissance, commune_naissance, date_permis_mer, type_permis_mer,
             civilite, telephone_fixe, pays_code, pays_nom,
             forme_juridique, code_naf, nom_dirigeant, telephone_formate,
             telephone_pays, email_statut)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (request.form['type'], request.form['nom'], request.form.get('prenom', ''),
             request.form.get('email', ''), request.form.get('telephone', ''),
             request.form.get('adresse', ''), request.form.get('code_postal', ''),
             request.form.get('ville', ''), request.form.get('siren', ''),
             request.form.get('statut', 'prospect'), request.form.get('notes', ''),
             request.form.get('date_naissance', ''), request.form.get('commune_naissance', ''),
             request.form.get('date_permis_mer', ''), request.form.get('type_permis_mer', ''),
             request.form.get('civilite', ''), request.form.get('telephone_fixe', ''),
             request.form.get('pays_code', 'FR'), request.form.get('pays_nom', 'France'),
             request.form.get('forme_juridique', ''), request.form.get('code_naf', ''),
             request.form.get('nom_dirigeant', ''), _tel_fmt2,
             request.form.get('telephone_pays', 'FR'), request.form.get('email_statut', '')))
        conn.commit()
        conn.close()
        flash('Client créé avec succès !', 'success')
        return redirect(url_for('clients_list'))
    return render_template('clients/form.html', client=None, titre='Nouveau client', pays_list=load_pays_cache())

@app.route('/clients/<int:id>')
def client_detail(id):
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id=?', (id,)).fetchone()
    if client:
        client = dict(client)
    if not client:
        flash('Client introuvable.', 'error')
        return redirect(url_for('clients_list'))
    bateaux = conn.execute("SELECT * FROM bateaux WHERE client_id=?", (id,)).fetchall()
    contrats = conn.execute("""SELECT ct.*, b.nom_bateau FROM contrats ct
                               LEFT JOIN bateaux b ON ct.bateau_id = b.id
                               WHERE ct.client_id=?""", (id,)).fetchall()
    sinistres = conn.execute("""SELECT s.*, ct.numero as contrat_num, b.nom_bateau
                                FROM sinistres s LEFT JOIN contrats ct ON s.contrat_id=ct.id
                                LEFT JOIN bateaux b ON s.bateau_id=b.id
                                WHERE s.client_id=?""", (id,)).fetchall()
    factures = conn.execute(
        "SELECT * FROM factures WHERE client_id=? ORDER BY date_emission DESC", (id,)).fetchall()
    taches = conn.execute(
        "SELECT * FROM taches WHERE client_id=? AND statut='a_faire' ORDER BY date_echeance",
        (id,)).fetchall()
    documents = conn.execute(
        "SELECT * FROM documents WHERE client_id=? ORDER BY date_upload DESC, id DESC",
        (id,)).fetchall()
    journal = conn.execute(
        """SELECT * FROM journal_activites
           WHERE client_id=? ORDER BY date_activite DESC, id DESC LIMIT 20""",
        (id,)).fetchall()
    rdvs = conn.execute(
        """SELECT * FROM rendez_vous
           WHERE client_id=? AND date_rdv >= ? AND statut != 'annule'
           ORDER BY date_rdv LIMIT 5""",
        (id, date.today().isoformat())).fetchall()
    devis = conn.execute(
        "SELECT * FROM devis WHERE client_id=? ORDER BY date_devis DESC",
        (id,)).fetchall()
    conn.close()
    # Risques du client
    conn2 = get_db()
    risques = conn2.execute(
        "SELECT * FROM risques WHERE client_id=? ORDER BY type_risque, libelle",
        (id,)).fetchall()
    conn2.close()
    # NAVISUR v9.3 — Réclamations client
    conn3 = get_db()
    reclamations_client = conn3.execute(
        "SELECT * FROM reclamations WHERE client_id=? ORDER BY date_reception DESC", (id,)).fetchall()
    today_str = date.today().isoformat()
    recl_retard = sum(1 for r in reclamations_client
                      if r['statut'] not in ('resolue','classee')
                      and r['date_reponse_prevue'] and r['date_reponse_prevue'] < today_str)
    conn3.close()
    conn_audit = get_db()
    audit_logs = conn_audit.execute("SELECT * FROM audit_log WHERE table_name='clients' AND record_id=? ORDER BY date_action DESC", (id,)).fetchall()
    conn_audit.close()
    breadcrumbs = [
        {'label': 'Clients', 'url': url_for('clients_list')},
        {'label': f"{client['prenom'] or ''} {client['nom']}".strip(), 'url': None}
    ]
    return render_template('clients/detail.html', client=client, bateaux=bateaux,
                           contrats=contrats, sinistres=sinistres, factures=factures,
                           taches=taches, documents=documents, journal=journal, rdvs=rdvs,
                           devis=devis, risques=risques, types_documents=TYPES_DOCUMENTS,
                           reclamations_client=reclamations_client, recl_retard=recl_retard,
                           today=date.today().isoformat(), breadcrumbs=breadcrumbs,
                           audit_logs=audit_logs)

@app.route('/clients/<int:id>/modifier', methods=['GET', 'POST'])
def client_modifier(id):
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id=?', (id,)).fetchone()
    if client:
        client = dict(client)
    if request.method == 'POST':
        # NAVISUR v9.3 — Audit modifications client
        for _fld in ['nom', 'prenom', 'email', 'telephone', 'statut']:
            _old = client[_fld] if client and client[_fld] else ''
            _new = request.form.get(_fld, '')
            if _old != _new:
                log_audit('clients', id, 'UPDATE', _fld, _old, _new)
        _tel_fmt = format_telephone_fr(request.form.get('telephone', ''))
        _pays_code = request.form.get('pays_code', 'FR')
        _pays_nom = request.form.get('pays_nom', 'France')
        conn.execute('''UPDATE clients SET type=?, nom=?, prenom=?, email=?, telephone=?,
            adresse=?, code_postal=?, ville=?, siren=?, statut=?, notes=?,
            date_naissance=?, commune_naissance=?, date_permis_mer=?, type_permis_mer=?,
            civilite=?, telephone_fixe=?, pays_code=?, pays_nom=?,
            forme_juridique=?, code_naf=?, nom_dirigeant=?, telephone_formate=?
            WHERE id=?''',
            (request.form['type'], request.form['nom'], request.form.get('prenom', ''),
             request.form.get('email', ''), request.form.get('telephone', ''),
             request.form.get('adresse', ''), request.form.get('code_postal', ''),
             request.form.get('ville', ''), request.form.get('siren', ''),
             request.form.get('statut', 'prospect'), request.form.get('notes', ''),
             request.form.get('date_naissance', ''), request.form.get('commune_naissance', ''),
             request.form.get('date_permis_mer', ''), request.form.get('type_permis_mer', ''),
             request.form.get('civilite', ''), request.form.get('telephone_fixe', ''),
             _pays_code, _pays_nom,
             request.form.get('forme_juridique', ''), request.form.get('code_naf', ''),
             request.form.get('nom_dirigeant', ''), _tel_fmt, id))
        conn.commit()
        conn.close()
        nlog('info', f'Client #{id} modifié')
        flash('Client mis à jour !', 'success')
        return redirect(url_for('client_detail', id=id))
    conn.close()
    return render_template('clients/form.html', client=client, titre='Modifier le client', pays_list=load_pays_cache())

@app.route('/clients/<int:id>/supprimer', methods=['POST'])
def client_supprimer(id):
    conn = get_db()
    # Delete associated documents files
    docs = conn.execute("SELECT nom_stockage FROM documents WHERE client_id=?", (id,)).fetchall()
    for doc in docs:
        fpath = os.path.join(UPLOAD_FOLDER, doc['nom_stockage'])
        if os.path.exists(fpath):
            os.remove(fpath)
    conn.execute("DELETE FROM documents WHERE client_id=?", (id,))
    conn.execute("DELETE FROM clients WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Client supprimé.', 'info')
    return redirect(url_for('clients_list'))

# ─── DOCUMENTS ───────────────────────────────────────────────────────────────

@app.route('/clients/<int:client_id>/documents/upload', methods=['POST'])
def document_upload(client_id):
    conn = get_db()
    client = conn.execute("SELECT id FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        conn.close(); abort(404)

    file = request.files.get('fichier')
    type_doc = request.form.get('type_document', 'Autre document')
    description = request.form.get('description', '')
    contrat_id = request.form.get('contrat_id') or None

    if not file or file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        conn.close()
        redir = request.form.get('redirect_to', url_for('client_detail', id=client_id))
        return redirect(redir)

    if not allowed_file(file.filename):
        flash('Type de fichier non autorisé.', 'error')
        conn.close()
        return redirect(url_for('client_detail', id=client_id))

    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'bin'
    storage_name = f"{client_id}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, storage_name)
    file.save(filepath)
    size = os.path.getsize(filepath)

    conn.execute(
        "INSERT INTO documents (client_id, contrat_id, type_document, nom_original, "
        "nom_stockage, nom_fichier, taille, description, date_upload) VALUES (?,?,?,?,?,?,?,?,?)",
        (client_id, contrat_id, type_doc, original, storage_name, original,
         size, description, date.today().isoformat()))
    conn.commit()
    conn.close()

    flash(f'Document "{original}" ajouté !', 'success')
    redir = request.form.get('redirect_to')
    if redir:
        return redirect(redir)
    return redirect(url_for('client_detail', id=client_id) + '#docs')

@app.route('/contrats/<int:contrat_id>/documents/upload', methods=['POST'])
def contrat_document_upload(contrat_id):
    conn = get_db()
    ct = conn.execute("SELECT id, client_id FROM contrats WHERE id=?", (contrat_id,)).fetchone()
    if not ct:
        conn.close(); abort(404)
    client_id = ct['client_id']

    file = request.files.get('fichier')
    type_doc = request.form.get('type_document', 'Contrat signé')

    if not file or file.filename == '':
        flash('Aucun fichier sélectionné.', 'error')
        conn.close()
        return redirect(url_for('contrat_detail', id=contrat_id))

    if not allowed_file(file.filename):
        flash('Type de fichier non autorisé.', 'error')
        conn.close()
        return redirect(url_for('contrat_detail', id=contrat_id))

    original = secure_filename(file.filename)
    ext = original.rsplit('.', 1)[1].lower() if '.' in original else 'bin'
    storage_name = f"ct{contrat_id}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, storage_name)
    file.save(filepath)
    size = os.path.getsize(filepath)

    conn.execute(
        "INSERT INTO documents (client_id, contrat_id, type_document, nom_original, "
        "nom_stockage, nom_fichier, taille, date_upload) VALUES (?,?,?,?,?,?,?,?)",
        (client_id, contrat_id, type_doc, original, storage_name, original,
         size, date.today().isoformat()))
    conn.commit()
    conn.close()

    flash(f'Document "{original}" ajouté au contrat !', 'success')
    return redirect(url_for('contrat_detail', id=contrat_id) + '#docs')

@app.route('/documents/<int:doc_id>/telecharger')
def document_telecharger(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not doc:
        abort(404)
    return send_from_directory(
        UPLOAD_FOLDER,
        doc['nom_stockage'],
        as_attachment=True,
        download_name=doc['nom_original']
    )

@app.route('/documents/<int:doc_id>/voir')
def document_voir(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    if not doc:
        abort(404)
    return send_from_directory(
        UPLOAD_FOLDER,
        doc['nom_stockage'],
        as_attachment=False,
        download_name=doc['nom_original']
    )

@app.route('/documents/<int:doc_id>/supprimer', methods=['POST'])
def document_supprimer(doc_id):
    conn = get_db()
    doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if doc:
        client_id = doc['client_id']
        fpath = os.path.join(UPLOAD_FOLDER, doc['nom_stockage'])
        if os.path.exists(fpath):
            os.remove(fpath)
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        conn.commit()
        conn.close()
        flash('Document supprimé.', 'info')
        return redirect(url_for('client_detail', id=client_id) + '#docs')
    conn.close()
    abort(404)

# ─── BATEAUX ─────────────────────────────────────────────────────────────────

