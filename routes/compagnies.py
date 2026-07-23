# routes/compagnies.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/compagnies')
def compagnies_list():
    conn = get_db()
    compagnies = conn.execute("""
        SELECT cp.*,
               COUNT(DISTINCT cc.id) as nb_contacts,
               COUNT(DISTINCT ct.id) as nb_contrats,
               COUNT(DISTINCT d.id)  as nb_docs
        FROM compagnies cp
        LEFT JOIN compagnie_contacts cc ON cc.compagnie_id=cp.id
        LEFT JOIN contrats ct ON ct.compagnie=cp.nom AND ct.statut='en_cours'
        LEFT JOIN documents  d  ON d.compagnie_id=cp.id
        GROUP BY cp.id
        ORDER BY cp.nom
    """).fetchall()
    conn.close()
    return render_template('compagnies/index.html', compagnies=compagnies)

@app.route('/compagnies/nouvelle', methods=['GET','POST'])
def compagnie_nouvelle():
    if request.method == 'POST':
        conn = get_db()
        conn.execute("""INSERT INTO compagnies
            (nom, code_courtier, taux_commission, type_convention,
             adresse, code_postal, ville, site_web,
             email_general, telephone_general, produits, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (request.form['nom'].strip(),
             request.form.get('code_courtier',''),
             float(request.form.get('taux_commission') or 0),
             request.form.get('type_convention','convention'),
             request.form.get('adresse',''),
             request.form.get('code_postal',''),
             request.form.get('ville',''),
             request.form.get('site_web',''),
             request.form.get('email_general',''),
             request.form.get('telephone_general',''),
             request.form.get('produits',''),
             request.form.get('notes','')))
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit(); conn.close()
        flash(f'Compagnie ajoutée !', 'success')
        return redirect(url_for('compagnie_detail', id=new_id))
    return render_template('compagnies/form.html', compagnie=None, titre='Nouvelle compagnie')

@app.route('/compagnies/<int:id>')
def compagnie_detail(id):
    conn = get_db()
    cp = conn.execute("SELECT * FROM compagnies WHERE id=?", (id,)).fetchone()
    if not cp:
        conn.close(); flash('Compagnie introuvable.','error'); return redirect(url_for('compagnies_list'))
    contacts  = conn.execute("SELECT * FROM compagnie_contacts WHERE compagnie_id=? ORDER BY nom", (id,)).fetchall()
    docs      = conn.execute("SELECT * FROM documents WHERE compagnie_id=? ORDER BY date_upload DESC", (id,)).fetchall()
    contrats  = conn.execute("""SELECT ct.*, c.nom as client_nom, c.prenom as client_prenom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.compagnie=? ORDER BY ct.date_creation DESC LIMIT 20""",
        (cp['nom'],)).fetchall()
    # Stats commissions
    comm_stats = conn.execute("""SELECT
        COALESCE(SUM(CASE WHEN statut='encaissee' THEN montant_percu ELSE 0 END),0) as total_encaisse,
        COALESCE(SUM(CASE WHEN statut IN ('attendue','releve_recu') THEN montant_attendu ELSE 0 END),0) as total_attendu,
        COUNT(*) as nb_total
        FROM compta_commissions WHERE compagnie=?""", (cp['nom'],)).fetchone()
    conn.close()
    return render_template('compagnies/detail.html',
        compagnie=cp, contacts=contacts, docs=docs,
        contrats=contrats, comm_stats=comm_stats,
        today=date.today().isoformat(),
        types_documents=['Convention','Grille tarifaire','Procédures','Formulaire souscription',
                          'CGV / CGU','Attestation code courtier','Correspondance','Autre'])

@app.route('/compagnies/<int:id>/modifier', methods=['GET','POST'])
def compagnie_modifier(id):
    conn = get_db()
    cp = conn.execute("SELECT * FROM compagnies WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        conn.execute("""UPDATE compagnies SET nom=?, code_courtier=?, taux_commission=?,
            type_convention=?, adresse=?, code_postal=?, ville=?, site_web=?,
            email_general=?, telephone_general=?, produits=?, notes=?, actif=? WHERE id=?""",
            (request.form['nom'].strip(),
             request.form.get('code_courtier',''),
             float(request.form.get('taux_commission') or 0),
             request.form.get('type_convention','convention'),
             request.form.get('adresse',''), request.form.get('code_postal',''),
             request.form.get('ville',''), request.form.get('site_web',''),
             request.form.get('email_general',''), request.form.get('telephone_general',''),
             request.form.get('produits',''), request.form.get('notes',''),
             1 if request.form.get('actif') else 0, id))
        conn.commit(); conn.close()
        flash('Compagnie mise à jour !', 'success')
        return redirect(url_for('compagnie_detail', id=id))
    conn.close()
    return render_template('compagnies/form.html', compagnie=cp, titre='Modifier la compagnie')

# ── CONTACTS ──────────────────────────────────────────────────

@app.route('/compagnies/<int:cp_id>/contacts/ajouter', methods=['POST'])
def compagnie_contact_ajouter(cp_id):
    conn = get_db()
    conn.execute("""INSERT INTO compagnie_contacts
        (compagnie_id, nom, prenom, poste, email, telephone, telephone_direct, notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (cp_id,
         request.form['nom'].strip(),
         request.form.get('prenom',''),
         request.form.get('poste',''),
         request.form.get('email',''),
         request.form.get('telephone',''),
         request.form.get('telephone_direct',''),
         request.form.get('notes','')))
    conn.commit(); conn.close()
    flash('Contact ajouté !', 'success')
    return redirect(url_for('compagnie_detail', id=cp_id) + '#contacts')

@app.route('/compagnies/contacts/<int:id>/supprimer', methods=['POST'])
def compagnie_contact_supprimer(id):
    conn = get_db()
    cc = conn.execute("SELECT compagnie_id FROM compagnie_contacts WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM compagnie_contacts WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Contact supprimé.', 'info')
    return redirect(url_for('compagnie_detail', id=cc['compagnie_id']) + '#contacts' if cc else url_for('compagnies_list'))

@app.route('/compagnies/contacts/<int:id>/modifier', methods=['POST'])
def compagnie_contact_modifier(id):
    conn = get_db()
    cc = conn.execute("SELECT compagnie_id FROM compagnie_contacts WHERE id=?", (id,)).fetchone()
    conn.execute("""UPDATE compagnie_contacts SET nom=?,prenom=?,poste=?,
        email=?,telephone=?,telephone_direct=?,notes=? WHERE id=?""",
        (request.form['nom'].strip(), request.form.get('prenom',''),
         request.form.get('poste',''), request.form.get('email',''),
         request.form.get('telephone',''), request.form.get('telephone_direct',''),
         request.form.get('notes',''), id))
    conn.commit(); conn.close()
    flash('Contact mis à jour !', 'success')
    return redirect(url_for('compagnie_detail', id=cc['compagnie_id']) + '#contacts' if cc else url_for('compagnies_list'))

# ── DOCUMENTS COMPAGNIE ────────────────────────────────────────

@app.route('/compagnies/<int:cp_id>/documents/upload', methods=['POST'])
def compagnie_document_upload(cp_id):
    conn = get_db()
    cp = conn.execute("SELECT id,nom FROM compagnies WHERE id=?", (cp_id,)).fetchone()
    if not cp: conn.close(); abort(404)
    file = request.files.get('fichier')
    type_doc = request.form.get('type_document', 'Convention')
    if not file or file.filename == '':
        flash('Aucun fichier.', 'error'); conn.close()
        return redirect(url_for('compagnie_detail', id=cp_id))
    if not allowed_file(file.filename):
        flash('Type non autorisé.', 'error'); conn.close()
        return redirect(url_for('compagnie_detail', id=cp_id))
    original = secure_filename(file.filename)
    ext = original.rsplit('.',1)[1].lower() if '.' in original else 'bin'
    storage_name = f"cp{cp_id}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, storage_name)
    file.save(filepath)
    size = os.path.getsize(filepath)
    conn.execute("""INSERT INTO documents
        (compagnie_id, type_document, nom_original, nom_stockage, nom_fichier, taille, date_upload)
        VALUES (?,?,?,?,?,?,?)""",
        (cp_id, type_doc, original, storage_name, original, size, date.today().isoformat()))
    conn.commit(); conn.close()
    flash(f'Document "{original}" ajouté !', 'success')
    return redirect(url_for('compagnie_detail', id=cp_id) + '#docs')


# ═══════════════════════════════════════════════════════════════
#  V8.4 — Améliorations filtres · Quittances contrat ·
#          Export données · Tableau commissions enrichi
# ═══════════════════════════════════════════════════════════════

# ── Export clients Excel ──────────────────────────────────────

@app.route('/clients/export-excel')
def clients_export_excel():
    conn = get_db()
    clients = conn.execute("""SELECT c.*,
        COUNT(DISTINCT ct.id) as nb_contrats,
        COUNT(DISTINCT b.id)  as nb_bateaux
        FROM clients c
        LEFT JOIN contrats ct ON ct.client_id=c.id AND ct.statut='en_cours'
        LEFT JOIN bateaux b  ON b.client_id=c.id
        GROUP BY c.id ORDER BY c.nom""").fetchall()
    conn.close()
    wb = Workbook(); ws = wb.active; ws.title = 'Clients'
    hdrs = ['Nom','Prénom','Email','Téléphone','Adresse','CP','Ville',
            'Statut','Date naissance','Commune naissance',
            'Permis mer','Date permis','Nb contrats','Nb bateaux','Créé le','Notes']
    ws.append(hdrs); style_header(ws, 1, len(hdrs))
    permis_labels = {'cotier':'Côtier','hauturier':'Hauturier','les_deux':'Côtier+Hauturier','fluvial':'Fluvial'}
    for i, c in enumerate(clients, 2):
        ws.append([c['nom'], c['prenom'] or '', c['email'] or '', c['telephone'] or '',
                   c['adresse'] or '', c['code_postal'] or '', c['ville'] or '',
                   c['statut'],
                   c['date_naissance'] or '', c['commune_naissance'] or '',
                   permis_labels.get(c['type_permis_mer'] or '', c['type_permis_mer'] or ''),
                   c['date_permis_mer'] or '',
                   c['nb_contrats'], c['nb_bateaux'],
                   c['date_creation'] or '', c['notes'] or ''])
        style_alt(ws, i, len(hdrs), i % 2 == 0)
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 16
    import io as _io2
    buf = _io2.BytesIO(); wb.save(buf); buf.seek(0)
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=clients_navisur.xlsx'})

# ── Quittances liées à un contrat ────────────────────────────

@app.route('/contrats/<int:id>/quittances')
def contrat_quittances(id):
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    quittances = conn.execute(
        "SELECT * FROM factures WHERE contrat_id=? ORDER BY date_emission DESC", (id,)).fetchall()
    conn.close()
    if not ct:
        abort(404)
    return render_template('contrats/quittances.html', contrat=ct, quittances=quittances,
                           today=date.today().isoformat())

# ── Tableau de bord des retards ──────────────────────────────

@app.route('/retards')
def retards():
    today_s = date.today().isoformat()
    conn = get_db()
    # Contrats expirés non renouvelés
    expires = conn.execute("""SELECT ct.*, c.nom, c.prenom, c.email, c.telephone,
        CAST(julianday(?) - julianday(ct.date_fin) AS INTEGER) as jours_retard
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        WHERE ct.statut='en_cours' AND ct.date_fin < ?
        ORDER BY ct.date_fin""", (today_s, today_s)).fetchall()
    # Commissions très en retard (> 60j)
    comm_retard = conn.execute("""SELECT cc.*, c.nom, c.prenom,
        CAST(julianday(?) - julianday(cc.date_prevue) AS INTEGER) as jours_retard
        FROM compta_commissions cc LEFT JOIN clients c ON cc.client_id=c.id
        WHERE cc.statut IN ('attendue','releve_recu') AND cc.date_prevue < ?
          AND julianday(?) - julianday(cc.date_prevue) > 60
        ORDER BY cc.date_prevue""", (today_s, today_s, today_s)).fetchall()
    # Relances en retard > 7j
    relances_retard = conn.execute("""SELECT r.*, c.nom, c.prenom, c.email,
        CAST(julianday(?) - julianday(r.date_prevue) AS INTEGER) as jours_retard
        FROM relances r JOIN clients c ON r.client_id=c.id
        JOIN contrats ct ON r.contrat_id=ct.id
        WHERE r.statut='a_faire' AND r.date_prevue < ?
          AND julianday(?) - julianday(r.date_prevue) > 7
        ORDER BY r.date_prevue""", (today_s, today_s, today_s)).fetchall()
    # Dossiers sans pièces depuis + 30j
    dossiers_incomplets = conn.execute("""SELECT ct.id, ct.numero, ct.type_assurance,
        ct.date_creation, c.nom, c.prenom,
        COUNT(cp.id) as total, SUM(cp.recu) as recues
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        JOIN checklist_pieces cp ON cp.contrat_id=ct.id
        WHERE ct.statut='en_cours' AND cp.obligatoire=1
          AND julianday(?) - julianday(ct.date_creation) > 30
        GROUP BY ct.id HAVING recues < total
        ORDER BY (total-recues) DESC""", (today_s,)).fetchall()
    conn.close()
    return render_template('retards.html',
        expires=expires, comm_retard=comm_retard,
        relances_retard=relances_retard,
        dossiers_incomplets=dossiers_incomplets,
        today=today_s)

# ── API refresh notifications (polling léger) ────────────────

@app.route('/api/notifs-count')
def api_notifs_count():
    """Endpoint léger pour le polling du badge notifications."""
    nb = get_nb_notifs()
    return jsonify({'count': nb})


# ═══════════════════════════════════════════════════════════════
#  MODULE RÉSILIATION
# ═══════════════════════════════════════════════════════════════

MOTIFS_RESILIATION = [
    ('client_vente',           'Vente du bateau'),
    ('client_autre_courtier',  'Départ chez un autre courtier'),
    ('client_direct',          'Souscription directe compagnie'),
    ('client_arret_navigation','Arrêt de la navigation'),
    ('client_prix',            'Prix / tarif trop élevé'),
    ('client_mecontentement',  'Mécontentement (sinistre / service)'),
    ('client_autre',           'Autre motif client'),
    ('cie_resiliation',        'Résiliation par la compagnie'),
    ('cie_non_renouvellement', 'Non-renouvellement compagnie'),
    ('cie_impaye',             'Résiliation pour impayé'),
    ('cie_aggravation',        'Aggravation du risque'),
    ('cie_autre',              'Autre motif compagnie'),
    ('commun_accord',          'Résiliation d\'un commun accord'),
    ('echeance',               'Non-renouvellement à échéance'),
]

