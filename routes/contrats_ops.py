# routes/contrats_ops.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *
from flask_login import login_required

@app.route('/contrats/<int:id>/resilier', methods=['GET','POST'])
def contrat_resilier(id):
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom,c.email,c.id as cid,
        b.nom_bateau FROM contrats ct
        JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.id=?""", (id,)).fetchone()
    if not ct:
        conn.close(); flash('Contrat introuvable.', 'error')
        return redirect(url_for('contrats_list'))

    # Commission déjà encaissée sur ce contrat
    comm_encaissee = float(conn.execute(
        """SELECT COALESCE(SUM(montant_percu),0) FROM compta_commissions
           WHERE contrat_id=? AND statut='encaissee'""", (id,)).fetchone()[0])

    # Résiliation déjà enregistrée ?
    resil_existante = conn.execute(
        "SELECT * FROM resiliations WHERE contrat_id=?", (id,)).fetchone()

    if request.method == 'POST':
        date_resil    = request.form['date_resiliation']
        date_effet    = request.form.get('date_effet', '') or date_resil
        motif         = request.form['motif']
        motif_detail  = request.form.get('motif_detail', '')
        ristourne     = float(request.form.get('ristourne_montant') or 0)
        comm_initiale = float(request.form.get('commission_initiale') or comm_encaissee)
        comm_deduire  = float(request.form.get('commission_a_deduire') or 0)
        comm_mode     = request.form.get('commission_mode', 'aucun')
        frais_appliquer = 1 if request.form.get('frais_courtage_appliquer') else 0
        frais_montant   = float(request.form.get('frais_courtage_montant') or 0)
        notes = request.form.get('notes', '')

        # Déterminer le nouveau statut contrat selon initiateur
        if motif.startswith('cie_'):
            new_statut = 'resilie_cie'
        elif motif in ('echeance', 'commun_accord'):
            new_statut = 'echu'
        else:
            new_statut = 'resilie_client'

        if resil_existante:
            # Mise à jour
            conn.execute("""UPDATE resiliations SET date_resiliation=?,date_effet=?,
                motif=?,motif_detail=?,ristourne_montant=?,
                commission_initiale=?,commission_a_deduire=?,commission_mode=?,
                frais_courtage_appliquer=?,frais_courtage_montant=?,notes=?
                WHERE contrat_id=?""",
                (date_resil, date_effet, motif, motif_detail, ristourne,
                 comm_initiale, comm_deduire, comm_mode,
                 frais_appliquer, frais_montant, notes, id))
        else:
            conn.execute("""INSERT INTO resiliations
                (contrat_id,client_id,date_resiliation,date_effet,motif,motif_detail,
                 ristourne_montant,commission_initiale,commission_a_deduire,commission_mode,
                 frais_courtage_appliquer,frais_courtage_montant,notes)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (id, ct['client_id'], date_resil, date_effet, motif, motif_detail,
                 ristourne, comm_initiale, comm_deduire, comm_mode,
                 frais_appliquer, frais_montant, notes))

        # Mettre à jour le statut du contrat
        conn.execute("UPDATE contrats SET statut=?, date_fin=? WHERE id=?",
                     (new_statut, date_effet, id))

        # Si commission à déduire → créer un ajustement dans compta_commissions
        if comm_deduire > 0 and comm_mode != 'aucun':
            conn.execute("""INSERT INTO compta_commissions
                (compagnie,contrat_id,client_id,type_commission,periode,
                 date_prevue,montant_attendu,statut,notes)
                VALUES (?,?,?,'regularisation_resiliation',?,?,?,'attendue',?)""",
                (ct['compagnie'] or '', id, ct['client_id'],
                 date_resil[:7],
                 (date.fromisoformat(date_resil) + __import__('datetime').timedelta(days=15)).isoformat(),
                 -comm_deduire,
                 f'Régularisation résiliation — {dict(MOTIFS_RESILIATION).get(motif, motif)}'))

        # Si frais de courtage → créer une facture brouillon
        if frais_appliquer and frais_montant > 0:
            annee_v = date.today().year
            nb = conn.execute("SELECT COUNT(*) FROM factures").fetchone()[0] + 1
            num = f'FC-RESIL-{annee_v}-{nb:04d}'
            conn.execute("""INSERT INTO factures
                (client_id,contrat_id,numero,objet,date_emission,montant_ht,tva,montant_ttc,statut,notes)
                VALUES (?,?,?,?,?,?,0,?,'brouillon',?)""",
                (ct['client_id'], id, num,
                 f'Frais de courtage — résiliation {ct["numero"] or ct["type_assurance"] or ""}'.strip(),
                 date_resil, frais_montant, frais_montant,
                 f'Résiliation {date_resil} — {dict(MOTIFS_RESILIATION).get(motif, motif)}'))

        conn.commit()
        conn.close()
        flash(f'✅ Résiliation enregistrée. Contrat passé en « {new_statut.replace("_"," ").title()} ».', 'success')
        return redirect(url_for('client_detail', id=ct['cid']) + '#contrats')

    conn.close()
    # Calculer commission à déduire suggérée (prorata temporis si applicable)
    try:
        if ct['date_debut'] and ct['date_fin']:
            d_debut  = date.fromisoformat(ct['date_debut'])
            d_fin    = date.fromisoformat(ct['date_fin'])
            d_resil  = date.today()
            duree_totale = (d_fin - d_debut).days or 1
            duree_ecoulee = (d_resil - d_debut).days
            duree_restante = max(0, duree_totale - duree_ecoulee)
            pct_restant = duree_restante / duree_totale
            comm_suggeree = round(comm_encaissee * pct_restant, 2)
        else:
            comm_suggeree = 0
            pct_restant = 0
    except Exception:
        comm_suggeree = 0
        pct_restant = 0

    return render_template('contrats/resilier.html',
        contrat=ct, resil=resil_existante,
        motifs=MOTIFS_RESILIATION,
        comm_encaissee=comm_encaissee,
        comm_suggeree=comm_suggeree,
        pct_restant=round(pct_restant*100, 1),
        today=date.today().isoformat())

@app.route('/contrats/<int:id>/resiliation')
def contrat_resiliation_detail(id):
    """Vue détail d'une résiliation existante."""
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom,c.id as cid
        FROM contrats ct JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    resil = conn.execute("SELECT * FROM resiliations WHERE contrat_id=?", (id,)).fetchone()
    facture = None
    if resil and resil['frais_courtage_facture_id']:
        facture = conn.execute("SELECT * FROM factures WHERE id=?",
                               (resil['frais_courtage_facture_id'],)).fetchone()
    elif resil:
        facture = conn.execute(
            "SELECT * FROM factures WHERE contrat_id=? AND numero LIKE 'FC-RESIL-%'",
            (id,)).fetchone()
    conn.close()
    if not resil:
        flash('Aucune résiliation enregistrée pour ce contrat.', 'info')
        return redirect(url_for('contrat_detail', id=id))
    return render_template('contrats/resiliation_detail.html',
        contrat=ct, resil=resil, facture=facture,
        motifs_dict=dict(MOTIFS_RESILIATION))

@app.route('/resiliations')
def resiliations_list():
    """Liste de toutes les résiliations."""
    conn = get_db()
    annee = int(request.args.get('annee', date.today().year))
    motif_filter = request.args.get('motif', '')
    q = """SELECT r.*,c.nom,c.prenom,c.email,
        ct.numero,ct.type_assurance,ct.compagnie,ct.prime_annuelle
        FROM resiliations r
        JOIN clients c ON r.client_id=c.id
        JOIN contrats ct ON r.contrat_id=ct.id
        WHERE strftime('%Y',r.date_resiliation)=?"""
    p = [str(annee)]
    if motif_filter:
        q += " AND r.motif=?"
        p.append(motif_filter)
    q += " ORDER BY r.date_resiliation DESC"
    resiliations = conn.execute(q, p).fetchall()

    stats = {
        'nb':              len(resiliations),
        'ristourne_total': sum(float(r['ristourne_montant'] or 0) for r in resiliations),
        'comm_deduire':    sum(float(r['commission_a_deduire'] or 0) for r in resiliations),
        'nb_frais':        sum(1 for r in resiliations if r['frais_courtage_appliquer']),
        'frais_total':     sum(float(r['frais_courtage_montant'] or 0) for r in resiliations if r['frais_courtage_appliquer']),
        'client':          sum(1 for r in resiliations if not r['motif'].startswith('cie_')),
        'cie':             sum(1 for r in resiliations if r['motif'].startswith('cie_')),
    }
    conn.close()
    return render_template('contrats/resiliations_list.html',
        resiliations=resiliations, stats=stats,
        annee=annee, motif_filter=motif_filter,
        motifs=MOTIFS_RESILIATION,
        annees=list(range(int(get_param('annee_debut_activite','2024')), date.today().year+1)))

@app.route('/resiliations/<int:id>/regulariser', methods=['POST'])
def resiliation_regulariser(id):
    """Marquer la commission comme régularisée."""
    conn = get_db()
    r = conn.execute("SELECT contrat_id,client_id FROM resiliations WHERE id=?", (id,)).fetchone()
    conn.execute("""UPDATE resiliations SET commission_regularisee=1,
        commission_regularisation_date=? WHERE id=?""",
        (date.today().isoformat(), id))
    conn.commit(); conn.close()
    flash('Commission marquée comme régularisée ✓', 'success')
    return redirect(url_for('resiliations_list'))

@app.route('/resiliations/<int:id>/ristourne-recue', methods=['POST'])
def resiliation_ristourne_recue(id):
    """Marquer la ristourne comme reçue par le client."""
    conn = get_db()
    conn.execute("""UPDATE resiliations SET ristourne_recue=1,
        ristourne_date=? WHERE id=?""",
        (date.today().isoformat(), id))
    conn.commit(); conn.close()
    flash('Ristourne marquée comme reçue par le client ✓', 'success')
    return redirect(url_for('resiliations_list'))


# ═══════════════════════════════════════════════════════════════
#  P0/P1 — Avenants · Impayés · Notifications enrichies ·
#           Validation souscription · Audit log
# ═══════════════════════════════════════════════════════════════

TYPES_AVENANT = [
    ('changement_garanties',    'Modification des garanties'),
    ('changement_prime',        'Révision de prime'),
    ('changement_bateau',       'Changement de bateau'),
    ('changement_zone',         'Modification zone de navigation'),
    ('changement_usage',        'Changement d\'usage'),
    ('suspension',              'Suspension des garanties'),
    ('reprise',                 'Reprise des garanties'),
    ('regularisation',          'Régularisation'),
    ('autre',                   'Autre modification'),
]

# ── AVENANTS ──────────────────────────────────────────────────

@app.route('/contrats/<int:id>/avenants')
def contrat_avenants(id):
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    avenants = conn.execute(
        "SELECT * FROM avenants WHERE contrat_id=? ORDER BY date_avenant DESC", (id,)).fetchall()
    conn.close()
    if not ct: abort(404)
    return render_template('contrats/avenants.html', contrat=ct, avenants=avenants,
                           types=TYPES_AVENANT)

@app.route('/contrats/<int:id>/avenants/nouveau', methods=['GET','POST'])
def avenant_nouveau(id):
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    if not ct: conn.close(); abort(404)
    if request.method == 'POST':
        # Numérotation avenant
        nb = conn.execute(
            "SELECT COUNT(*)+1 FROM avenants WHERE contrat_id=?", (id,)).fetchone()[0]
        num = f'AVN-{ct["numero"] or id}-{nb:02d}'
        prime_nouv = request.form.get('prime_nouvelle')
        conn.execute("""INSERT INTO avenants
            (contrat_id,numero,date_avenant,type_avenant,description,
             ancienne_valeur,nouvelle_valeur,prime_nouvelle,statut,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (id, num,
             request.form['date_avenant'],
             request.form['type_avenant'],
             request.form['description'],
             request.form.get('ancienne_valeur',''),
             request.form.get('nouvelle_valeur',''),
             float(prime_nouv) if prime_nouv else None,
             request.form.get('statut','en_cours'),
             request.form.get('notes','')))
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # Si la prime change, mettre à jour le contrat
        if prime_nouv and float(prime_nouv) > 0:
            old_prime = ct['prime_annuelle']
            conn.execute("UPDATE contrats SET prime_annuelle=? WHERE id=?",
                         (float(prime_nouv), id))
            log_audit('contrats', id, 'UPDATE', 'prime_annuelle', old_prime, prime_nouv)
        # Log de l'avenant
        log_audit('avenants', new_id, 'INSERT',
                  request.form['type_avenant'],
                  request.form.get('ancienne_valeur',''),
                  request.form.get('nouvelle_valeur',''))
        conn.execute("""INSERT INTO journal_activites
            (client_id,contrat_id,date_activite,type_contact,sens,objet,contenu,auteur)
            VALUES (?,?,?,'autre','entrant',?,?,?)""",
            (ct['client_id'], id, date.today().isoformat(),
             f'Avenant {num} — {request.form["type_avenant"].replace("_"," ").title()}',
             request.form['description'],
             get_param('cabinet_nom','')))
        conn.commit(); conn.close()
        flash(f'Avenant {num} enregistré !', 'success')
        return redirect(url_for('contrat_detail', id=id) + '#journal')
    conn.close()
    return render_template('contrats/avenant_form.html', contrat=ct,
                           types=TYPES_AVENANT, today=date.today().isoformat())

@app.route('/avenants/<int:id>/supprimer', methods=['POST'])
def avenant_supprimer(id):
    conn = get_db()
    av = conn.execute("SELECT contrat_id FROM avenants WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM avenants WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Avenant supprimé.', 'info')
    return redirect(url_for('contrat_avenants', id=av['contrat_id']) if av else url_for('contrats_list'))

# ── TRANSMISSION COMPAGNIE (workflow souscription) ────────────

@app.route('/contrats/<int:id>/transmettre', methods=['POST'])
def contrat_transmettre(id):
    conn = get_db()
    ct = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    conn.execute("""UPDATE contrats SET statut='transmis_cie',
        date_transmission_cie=? WHERE id=?""",
        (date.today().isoformat(), id))
    conn.execute("""INSERT INTO journal_activites
        (client_id,contrat_id,date_activite,type_contact,sens,objet,auteur)
        VALUES (?,?,?,'courrier','sortant','Dossier transmis à la compagnie',?)""",
        (ct['client_id'], id, date.today().isoformat(),
         get_param('cabinet_nom','')))
    _old_st_trans = ct['statut']
    conn.commit(); conn.close()
    log_audit('contrats', id, 'UPDATE', 'statut', _old_st_trans, 'transmis_cie')
    flash('Dossier marqué comme transmis à la compagnie ✓', 'success')
    return redirect(url_for('contrat_detail', id=id))

@app.route('/contrats/<int:id>/accepter-cie', methods=['POST'])
def contrat_accepter_cie(id):
    conn = get_db()
    ct = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    num_police = request.form.get('numero_police_cie','')
    date_emiss  = request.form.get('date_emission_police', date.today().isoformat())
    conn.execute("""UPDATE contrats SET statut='accepte_cie',
        date_acceptation_cie=?, numero_police_cie=?, date_emission_police=? WHERE id=?""",
        (date.today().isoformat(), num_police, date_emiss, id))
    if num_police:
        _log_police = num_police
    conn.execute("""INSERT INTO journal_activites
        (client_id,contrat_id,date_activite,type_contact,sens,objet,contenu,auteur)
        VALUES (?,?,?,'courrier','entrant','Acceptation compagnie — police émise',?,?)""",
        (ct['client_id'], id, date.today().isoformat(),
         f'N° police compagnie : {num_police}' if num_police else 'En attente de la police',
         get_param('cabinet_nom','')))
    conn.commit(); conn.close()
    if num_police:
        log_audit('contrats', id, 'UPDATE', 'numero_police_cie', '', num_police)
    flash('Acceptation compagnie enregistrée ✓', 'success')
    return redirect(url_for('contrat_detail', id=id))

@app.route('/contrats/<int:id>/activer', methods=['POST'])
def contrat_activer(id):
    """Passage en_cours depuis accepte_cie — contrat officiellement actif."""
    conn = get_db()
    ct = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    old = ct['statut']
    conn.execute("UPDATE contrats SET statut='en_cours' WHERE id=?", (id,))
    _old_statut_act = old
    conn.execute("""INSERT INTO journal_activites
        (client_id,contrat_id,date_activite,type_contact,sens,objet,auteur)
        VALUES (?,?,?,'autre','entrant','Contrat mis en place — actif',?)""",
        (ct['client_id'], id, date.today().isoformat(),
         get_param('cabinet_nom','')))
    conn.commit(); conn.close()
    log_audit('contrats', id, 'UPDATE', 'statut', _old_statut_act, 'en_cours')
    flash('Contrat activé ✅', 'success')
    return redirect(url_for('contrat_detail', id=id))

# ── VALIDATION CHAMPS OBLIGATOIRES SOUSCRIPTION ───────────────

CHAMPS_OBLIGATOIRES_CONTRAT = [
    ('client_id',       'Client'),
    ('type_assurance',  'Type d\'assurance'),
    ('compagnie',       'Compagnie'),
    ('date_debut',      'Date de début'),
    ('date_fin',        'Date de fin / échéance'),
    ('prime_annuelle',  'Prime annuelle'),
]

# ── NOTIFICATIONS ENRICHIES P1 ────────────────────────────────

# generer_notifications_enrichies → définie dans core.py

@app.route('/contrats/<int:id>/suspendre', methods=['POST'])
def contrat_suspendre(id):
    """Passe le contrat en suspendu pour impayé et crée une tâche de relance."""
    conn = get_db()
    ct = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    if not ct:
        conn.close(); flash('Contrat introuvable.', 'error')
        return redirect(url_for('contrats_list'))

    motif = request.form.get('motif', 'impaye')
    conn.execute("UPDATE contrats SET statut='suspendu' WHERE id=?", (id,))
    _old_statut_susp = ct['statut']

    # Marquer les primes en retard comme impayées
    conn.execute("""UPDATE primes_paiements SET statut='impaye'
        WHERE contrat_id=? AND statut='retard'""", (id,))

    # Créer une tâche de relance impayé
    conn.execute("""INSERT INTO taches (client_id, contrat_id, titre, description,
        date_echeance, priorite, statut)
        VALUES (?,?,?,?,?,'haute','a_faire')""",
        (ct['client_id'], id,
         f'Relance impayé — {ct["type_assurance"] or ""} {ct["numero"] or ""}'.strip(),
         f'Contrat suspendu pour impayé le {date.today().isoformat()}. Contacter le client.',
         (date.today() + __import__('datetime').timedelta(days=3)).isoformat()))

    # Journal
    conn.execute("""INSERT INTO journal_activites
        (client_id, contrat_id, date_activite, type_contact, sens, objet, auteur)
        VALUES (?,?,?,'autre','sortant','Contrat suspendu — impayé',?)""",
        (ct['client_id'], id, date.today().isoformat(),
         get_param('cabinet_nom','')))

    conn.commit(); conn.close()
    log_audit('contrats', id, 'UPDATE', 'statut', _old_statut_susp, 'suspendu')
    flash('Contrat suspendu pour impayé. Tâche de relance créée.', 'warning')
    return redirect(url_for('contrat_detail', id=id))

@app.route('/contrats/<int:id>/reactivation', methods=['POST'])
def contrat_reactiver_impaye(id):
    """Réactive un contrat suspendu après régularisation de l'impayé."""
    conn = get_db()
    ct = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    conn.execute("UPDATE contrats SET statut='en_cours' WHERE id=?", (id,))
    log_audit('contrats', id, 'UPDATE', 'statut', ct['statut'], 'en_cours')

    # Marquer les primes impayées comme payées si demandé
    if request.form.get('regulariser_primes'):
        conn.execute("""UPDATE primes_paiements SET statut='paye', date_paiement=?
            WHERE contrat_id=? AND statut IN ('impaye','retard')""",
            (date.today().isoformat(), id))

    conn.execute("""INSERT INTO journal_activites
        (client_id, contrat_id, date_activite, type_contact, sens, objet, auteur)
        VALUES (?,?,?,'autre','entrant','Impayé régularisé — contrat réactivé',?)""",
        (ct['client_id'], id, date.today().isoformat(),
         get_param('cabinet_nom','')))

    conn.commit(); conn.close()
    flash('Contrat réactivé ✅', 'success')
    return redirect(url_for('contrat_detail', id=id))

# ── EXPORT DOSSIER CLIENT ZIP ─────────────────────────────────

@app.route('/clients/<int:id>/export-dossier')
def client_export_dossier(id):
    """Exporte le dossier complet du client en ZIP :
    documents GED + fiche PDF + résumé contrats."""
    conn = get_db()
    client = conn.execute('SELECT * FROM clients WHERE id=?', (id,)).fetchone()
    if not client:
        conn.close(); abort(404)

    docs = conn.execute(
        "SELECT * FROM documents WHERE client_id=? ORDER BY type_document, date_upload",
        (id,)).fetchall()
    contrats = conn.execute("""SELECT ct.*, b.nom_bateau FROM contrats ct
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.client_id=? ORDER BY ct.date_creation""", (id,)).fetchall()
    sinistres = conn.execute(
        "SELECT * FROM sinistres WHERE client_id=? ORDER BY date_sinistre", (id,)).fetchall()
    devis = conn.execute(
        "SELECT * FROM devis WHERE client_id=? ORDER BY date_devis DESC", (id,)).fetchall()
    params = get_all_params()
    conn.close()

    buf = _zip_io.BytesIO()
    nom_client = f'{client["nom"]}_{client["prenom"] or ""}'.strip('_').replace(' ','_')

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 1. README / résumé texte
        resume_lines = [
            f'DOSSIER CLIENT — {client["prenom"] or ""} {client["nom"]}',
            f'Exporté le {date.today().isoformat()} via NAVISUR',
            f'Cabinet : {params.get("cabinet_nom","Riviera Marine Assurances")}',
            '',
            '=== INFORMATIONS CLIENT ===',
            f'Email      : {client["email"] or "—"}',
            f'Téléphone  : {client["telephone"] or "—"}',
            f'Adresse    : {client["adresse"] or ""} {client["code_postal"] or ""} {client["ville"] or ""}',
            f'Statut     : {client["statut"]}',
            f'Naissance  : {client["date_naissance"] or "—"} ({client["commune_naissance"] or "—"})',
            '',
            '=== CONTRATS ===',
        ]
        for ct in contrats:
            resume_lines += [
                f'  [{ct["statut"].upper()}] {ct["type_assurance"] or "?"} — {ct["compagnie"] or "?"}',
                f'    N° police  : {ct["numero"] or "—"} | N° cie : {ct["numero_police_cie"] or "—"}',
                f'    Période    : {ct["date_debut"] or "?"} → {ct["date_fin"] or "?"}',
                f'    Prime      : {ct["prime_annuelle"]:.2f} €/an',
                '',
            ]
        resume_lines += ['', '=== SINISTRES ===']
        for s in sinistres:
            resume_lines.append(f'  [{s["statut"].upper()}] {s["type_sinistre"] or "?"} — {s["date_sinistre"] or "?"} — {s["montant_estime"] or 0:.0f} €')
        resume_lines += ['', '=== DEVIS ===']
        for d in devis:
            resume_lines.append(f'  [{d["statut"].upper()}] {d["compagnie"] or "?"} — {d["type_assurance"] or "?"} — {d["prime_proposee"] or 0:.0f} €/an ({d["date_devis"]})')

        zf.writestr(f'{nom_client}/00_RESUME.txt', '\n'.join(resume_lines))

        # 2. Documents GED
        for doc in docs:
            filepath = os.path.join(UPLOAD_FOLDER, doc['nom_stockage'])
            if os.path.exists(filepath):
                type_dir = (doc['type_document'] or 'divers').replace('/','-').replace(' ','_')
                arcname = f'{nom_client}/{type_dir}/{doc["nom_original"]}'
                try:
                    zf.write(filepath, arcname)
                except Exception:
                    pass

    buf.seek(0)
    conn_p = get_db()
    log_audit('clients', id, 'EXPORT', 'dossier_zip', None, date.today().isoformat())
    conn_p.commit(); conn_p.close()

    return Response(
        buf.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition':
                 f'attachment; filename=dossier_{nom_client}_{date.today().strftime("%Y%m%d")}.zip'})

# ── ÉCRAN AUDIT LOG ───────────────────────────────────────────


@app.route('/contrats/<int:id>/attestation-capitainerie')
@login_required
def attestation_capitainerie(id):
    conn = get_db()
    contrat = conn.execute("""
        SELECT ct.*, c.nom, c.prenom, c.adresse, c.code_postal, c.ville,
               b.nom_bateau, b.marque, b.modele, b.immatriculation, b.port_attache, b.zone_navigation
        FROM contrats ct
        JOIN clients c ON ct.client_id = c.id
        LEFT JOIN bateaux b ON ct.bateau_id = b.id
        WHERE ct.id = ?
    """, (id,)).fetchone()
    if not contrat:
        conn.close()
        abort(404)
    params = {row['cle']: row['valeur'] for row in conn.execute("SELECT cle, valeur FROM parametres").fetchall()}
    conn.close()
    return render_template('contrats/attestation_capitainerie.html', contrat=contrat, params=params, today=date.today().strftime('%d/%m/%Y'))

@app.route('/contrats/<int:id>/attestation-non-sinistralite')
@login_required
def attestation_non_sinistralite(id):
    conn = get_db()
    contrat = conn.execute("""
        SELECT ct.*, c.nom, c.prenom, c.adresse, c.code_postal, c.ville,
               b.nom_bateau, b.marque, b.modele, b.immatriculation
        FROM contrats ct
        JOIN clients c ON ct.client_id = c.id
        LEFT JOIN bateaux b ON ct.bateau_id = b.id
        WHERE ct.id = ?
    """, (id,)).fetchone()
    if not contrat:
        conn.close()
        abort(404)
    resil = conn.execute("SELECT * FROM resiliations WHERE contrat_id=?", (id,)).fetchone()
    sinistres = conn.execute("SELECT * FROM sinistres WHERE contrat_id=? OR client_id=?", 
                             (id, contrat['client_id'])).fetchall()
    params = {row['cle']: row['valeur'] for row in conn.execute("SELECT cle, valeur FROM parametres").fetchall()}
    conn.close()
    return render_template('contrats/attestation_non_sinistralite.html', 
                           contrat=contrat, resil=resil, sinistres=sinistres, 
                           nb_sinistres=len(sinistres), params=params, today=date.today().strftime('%d/%m/%Y'))


