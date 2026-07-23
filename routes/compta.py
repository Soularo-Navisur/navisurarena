# routes/compta.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *
import json as _json  # utilisé pour sérialiser ca_par_mois

@app.route('/compta')
def compta_dashboard():
    annee = int(request.args.get('annee', date.today().year))
    conn = get_db()

    plafond    = float(get_param('micro_plafond_bnc', '77700'))
    taux_cot   = float(get_param('taux_cotisations', '21.1'))
    taux_vl    = float(get_param('taux_vl_ir', '2.2'))
    vl_actif   = get_param('vl_ir_actif', '0') == '1'
    seuil_ora  = float(get_param('alerte_plafond_orange', '70'))
    seuil_rou  = float(get_param('alerte_plafond_rouge', '90'))

    ca_annee = float(conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?",
        (annee,)).fetchone()[0])
    ca_prev_annee = float(conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?",
        (annee-1,)).fetchone()[0])

    # CA par mois (N et N-1)
    ca_par_mois = []
    ca_par_mois_prev = []
    for m in range(1,13):
        v = float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?",
            (annee, m)).fetchone()[0])
        vp = float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?",
            (annee-1, m)).fetchone()[0])
        ca_par_mois.append(round(v,2))
        ca_par_mois_prev.append(round(vp,2))

    # Répartition par nature
    repartition = conn.execute(
        """SELECT nature_recette, COALESCE(SUM(montant),0) as total
           FROM compta_recettes WHERE annee=? GROUP BY nature_recette
           ORDER BY total DESC""", (annee,)).fetchall()

    # Top commissions par compagnie
    par_compagnie = conn.execute(
        """SELECT compagnie, COALESCE(SUM(montant),0) as total, COUNT(*) as nb
           FROM compta_recettes WHERE annee=? AND compagnie IS NOT NULL AND compagnie != ''
           GROUP BY compagnie ORDER BY total DESC LIMIT 10""", (annee,)).fetchall()

    # Commissions en attente
    comm_attente = conn.execute(
        """SELECT COUNT(*), COALESCE(SUM(montant_attendu),0)
           FROM compta_commissions WHERE statut IN ('attendue','releve_recu')
           AND (strftime('%Y',date_prevue)=? OR date_prevue IS NULL)""", (annee,)).fetchone()
    try:
        nb_attente = comm_attente[0]
        mt_attente = float(comm_attente[1])
    except Exception:
        nb_attente, mt_attente = 0, 0.0

    # Cotisations estimées
    cot, vl, total_cot = calc_urssaf(ca_annee, taux_cot, taux_vl, vl_actif)

    pct_plafond = round(ca_annee / plafond * 100, 1) if plafond > 0 else 0
    couleur_jauge = ('danger' if pct_plafond >= seuil_rou
                     else 'warning' if pct_plafond >= seuil_ora
                     else 'success')

    # ── NAVISUR v9.3 — Indicateurs analytiques avancés ─────────

    # Graphique 2 — Répartition portefeuille par type de risque
    portefeuille_risques = conn.execute("""
        SELECT type_assurance, COUNT(*) as nb
        FROM contrats WHERE statut='en_cours'
          AND type_assurance IS NOT NULL AND type_assurance != ''
        GROUP BY type_assurance ORDER BY nb DESC
    """).fetchall()

    # Graphique 3 — Taux transformation devis → contrat par compagnie
    devis_par_cie = conn.execute("""
        SELECT compagnie,
               COUNT(*) as nb_devis,
               SUM(CASE WHEN statut IN ('accepte','transforme') THEN 1 ELSE 0 END) as nb_ok
        FROM devis
        WHERE compagnie IS NOT NULL AND compagnie != ''
          AND (substr(date_devis,1,4)=? OR date_devis IS NULL)
        GROUP BY compagnie ORDER BY nb_devis DESC LIMIT 8
    """, (str(annee),)).fetchall()

    # Graphique 4 — Top 5 compagnies par volume de primes
    top_compagnies = conn.execute("""
        SELECT compagnie, COUNT(*) as nb_contrats,
               COALESCE(SUM(prime_annuelle),0) as total_primes
        FROM contrats WHERE statut='en_cours'
          AND compagnie IS NOT NULL AND compagnie != ''
        GROUP BY compagnie ORDER BY total_primes DESC LIMIT 5
    """).fetchall()

    # Indicateur 5 — Prévisionnel commissions M, M+1, M+2
    from datetime import timedelta as _tdelta
    _today = date.today()
    def _ca_periode(d1, d2):
        r = conn.execute("""SELECT COALESCE(SUM(montant_attendu),0)
            FROM compta_commissions
            WHERE statut IN ('attendue','releve_recu')
              AND date_prevue BETWEEN ? AND ?""", (d1, d2)).fetchone()[0]
        return round(float(r), 2)
    _m0_start = _today.replace(day=1).isoformat()
    _m0_end   = (_today.replace(day=28) + _tdelta(days=4)).replace(day=1) - _tdelta(days=1)
    _m1_start = (_m0_end + _tdelta(days=1)).isoformat()
    _m1_end   = (_m0_end.replace(day=28) + _tdelta(days=4)).replace(day=1) - _tdelta(days=1)
    _m2_start = (_m1_end + _tdelta(days=1)).isoformat()
    _m2_end   = (_m1_end.replace(day=28) + _tdelta(days=4)).replace(day=1) - _tdelta(days=1)
    previsionnel = {
        'mois_0': {'label': _today.strftime('%B %Y'), 'montant': _ca_periode(_m0_start, _m0_end.isoformat())},
        'mois_1': {'label': _m1_start[:7], 'montant': _ca_periode(_m1_start, _m1_end.isoformat())},
        'mois_2': {'label': _m2_start[:7], 'montant': _ca_periode(_m2_start, _m2_end.isoformat())},
    }

    # Indicateur 6 — Alerte concentration
    alerte_concentration = None
    if top_compagnies:
        total_port = sum(r['total_primes'] for r in top_compagnies)
        if total_port > 0:
            top = top_compagnies[0]
            pct_top = round(top['total_primes'] / total_port * 100, 1)
            if pct_top >= 40:
                alerte_concentration = {'compagnie': top['compagnie'], 'pct': pct_top}

    conn.close()
    mois_noms = ['Jan','Fév','Mar','Avr','Mai','Jun',
                  'Jul','Aoû','Sep','Oct','Nov','Déc']

    # Vérifier si paramètres fiscaux année en cours existent
    _conn_f = get_db()
    _fiscal_ok = bool(_conn_f.execute(
        "SELECT 1 FROM parametres_fiscaux WHERE annee=?", (annee,)).fetchone())
    _conn_f.close()

    return render_template('compta/dashboard.html',
        annee=annee, plafond=plafond, ca_annee=ca_annee,
        ca_prev_annee=ca_prev_annee, pct_plafond=pct_plafond,
        couleur_jauge=couleur_jauge, seuil_orange=seuil_ora, seuil_rouge=seuil_rou,
        ca_par_mois=_json.dumps(ca_par_mois),
        ca_par_mois_prev=_json.dumps(ca_par_mois_prev),
        mois_noms=_json.dumps(mois_noms),
        repartition=repartition,
        par_compagnie=par_compagnie,
        nb_attente=nb_attente, mt_attente=mt_attente,
        cot_estimees=cot, vl_estime=vl, total_cot=total_cot,
        taux_cot=taux_cot, vl_actif=vl_actif,
        portefeuille_risques=portefeuille_risques,
        devis_par_cie=devis_par_cie,
        top_compagnies=top_compagnies,
        previsionnel=previsionnel,
        alerte_concentration=alerte_concentration,
        fiscal_ok=_fiscal_ok,
        annees=list(range(max(int(get_param('annee_debut_activite', str(date.today().year - 3))),
                              date.today().year - 5),
                          date.today().year + 2)))

# ── LIVRE DES RECETTES ─────────────────────────────────────────

@app.route('/compta/recettes')
def compta_recettes():
    annee = int(request.args.get('annee', date.today().year))
    mois  = request.args.get('mois', '')
    statut = request.args.get('statut', '')
    q = """SELECT r.*, c.nom, c.prenom, ct.numero as contrat_num
           FROM compta_recettes r
           LEFT JOIN clients c ON r.client_id=c.id
           LEFT JOIN contrats ct ON r.contrat_id=ct.id
           WHERE r.annee=?"""
    p = [annee]
    if mois:  q += " AND r.mois=?";    p.append(int(mois))
    if statut == 'valide':   q += " AND r.valide=1"
    elif statut == 'brouillon': q += " AND r.valide=0"
    q += " ORDER BY r.numero_ordre ASC"
    conn = get_db()
    recettes = conn.execute(q, p).fetchall()
    total = float(conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?",
        (annee,)).fetchone()[0])
    conn.close()
    mois_noms = ['Janvier','Février','Mars','Avril','Mai','Juin',
                  'Juillet','Août','Septembre','Octobre','Novembre','Décembre']
    return render_template('compta/recettes.html',
        recettes=recettes, annee=annee, mois=mois, statut=statut,
        total=total, mois_noms=mois_noms, natures=NATURES_RECETTE,
        annees=list(range(int(get_param('annee_debut_activite','2024')),
                          date.today().year+2)))

@app.route('/compta/recettes/nouvelle', methods=['GET','POST'])
def compta_recette_nouvelle():
    conn = get_db()
    if request.method == 'POST':
        d = request.form.get('date_encaissement', date.today().isoformat())
        annee_val = int(d[:4])
        mois_val  = int(d[5:7])
        num = next_numero_ordre()
        conn.execute("""INSERT INTO compta_recettes
            (numero_ordre,date_encaissement,reference,client_id,compagnie,contrat_id,
             nature_recette,montant,mode_reglement,periode_couverte,notes,annee,mois)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (num, d, request.form.get('reference',''),
             request.form.get('client_id') or None,
             request.form.get('compagnie',''),
             request.form.get('contrat_id') or None,
             request.form['nature_recette'],
             float(request.form['montant']),
             request.form.get('mode_reglement','virement'),
             request.form.get('periode_couverte',''),
             request.form.get('notes',''),
             annee_val, mois_val))
        conn.commit()
        conn.close()
        flash(f'Recette n°{num} enregistrée !', 'success')
        return redirect(url_for('compta_recettes', annee=annee_val))
    clients  = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id,ct.numero,ct.type_assurance,c.nom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
    compagnies = conn.execute(
        "SELECT DISTINCT compagnie FROM compta_commissions WHERE compagnie!='' ORDER BY compagnie"
    ).fetchall()
    conn.close()
    return render_template('compta/recette_form.html',
        recette=None, clients=clients, contrats=contrats,
        compagnies=[c[0] for c in compagnies],
        natures=NATURES_RECETTE, modes=MODES_REGLEMENT,
        today=date.today().isoformat(),
        preselect_client=request.args.get('client_id'),
        preselect_contrat=request.args.get('contrat_id'))

@app.route('/compta/recettes/<int:id>/modifier', methods=['GET','POST'])
def compta_recette_modifier(id):
    conn = get_db()
    recette = conn.execute("SELECT * FROM compta_recettes WHERE id=?", (id,)).fetchone()
    if recette and recette['valide']:
        flash('Cette écriture est validée et verrouillée.', 'error')
        conn.close()
        return redirect(url_for('compta_recettes'))
    if request.method == 'POST':
        d = request.form['date_encaissement']
        conn.execute("""UPDATE compta_recettes SET date_encaissement=?,reference=?,
            client_id=?,compagnie=?,contrat_id=?,nature_recette=?,montant=?,
            mode_reglement=?,periode_couverte=?,notes=?,annee=?,mois=? WHERE id=?""",
            (d, request.form.get('reference',''),
             request.form.get('client_id') or None,
             request.form.get('compagnie',''),
             request.form.get('contrat_id') or None,
             request.form['nature_recette'],
             float(request.form['montant']),
             request.form.get('mode_reglement','virement'),
             request.form.get('periode_couverte',''),
             request.form.get('notes',''),
             int(d[:4]), int(d[5:7]), id))
        conn.commit(); conn.close()
        flash('Recette mise à jour !', 'success')
        return redirect(url_for('compta_recettes'))
    clients  = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id,ct.numero,ct.type_assurance,c.nom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('compta/recette_form.html',
        recette=recette, clients=clients, contrats=contrats,
        compagnies=[], natures=NATURES_RECETTE, modes=MODES_REGLEMENT,
        today=date.today().isoformat(), preselect_client=None, preselect_contrat=None)

@app.route('/compta/recettes/<int:id>/valider', methods=['POST'])
def compta_recette_valider(id):
    conn = get_db()
    conn.execute("UPDATE compta_recettes SET valide=1, date_validation=? WHERE id=?",
                 (date.today().isoformat(), id))
    conn.commit(); conn.close()
    flash('Écriture validée et verrouillée ✓', 'success')
    return redirect(url_for('compta_recettes'))

@app.route('/compta/recettes/<int:id>/supprimer', methods=['POST'])
def compta_recette_supprimer(id):
    conn = get_db()
    r = conn.execute("SELECT valide FROM compta_recettes WHERE id=?", (id,)).fetchone()
    if r and r['valide']:
        flash('Impossible de supprimer une écriture validée.', 'error')
    else:
        conn.execute("DELETE FROM compta_recettes WHERE id=?", (id,))
        conn.commit()
        flash('Recette supprimée.', 'info')
    conn.close()
    return redirect(url_for('compta_recettes'))

# ── SUIVI COMMISSIONS PAR COMPAGNIE ────────────────────────────

@app.route('/compta/commissions')
def compta_commissions():
    annee = int(request.args.get('annee', date.today().year))
    statut = request.args.get('statut', '')
    compagnie = request.args.get('compagnie', '')
    conn = get_db()
    q = """SELECT cc.*, c.nom as client_nom, c.prenom as client_prenom,
           ct.numero as contrat_num, ct.type_assurance
           FROM compta_commissions cc
           LEFT JOIN clients c ON cc.client_id=c.id
           LEFT JOIN contrats ct ON cc.contrat_id=ct.id
           WHERE 1=1"""
    p = []
    if annee:
        q += " AND (strftime('%Y',cc.date_prevue)=? OR (cc.date_prevue IS NULL AND strftime('%Y',cc.date_creation)=?))"
        p += [str(annee), str(annee)]
    if statut:   q += " AND cc.statut=?";    p.append(statut)
    if compagnie: q += " AND cc.compagnie=?"; p.append(compagnie)
    q += " ORDER BY cc.date_prevue DESC, cc.id DESC"
    commissions = conn.execute(q, p).fetchall()

    # Stats par compagnie
    stats_cie = conn.execute("""
        SELECT compagnie,
               COUNT(*) as nb,
               COALESCE(SUM(montant_attendu),0) as total_attendu,
               COALESCE(SUM(CASE WHEN statut='encaissee' THEN montant_percu ELSE 0 END),0) as total_percu,
               COALESCE(SUM(CASE WHEN statut IN ('attendue','releve_recu') THEN montant_attendu ELSE 0 END),0) as reste
        FROM compta_commissions
        WHERE strftime('%Y',COALESCE(date_prevue,date_creation))=?
        GROUP BY compagnie ORDER BY total_attendu DESC
    """, (str(annee),)).fetchall()

    compagnies = conn.execute(
        "SELECT DISTINCT compagnie FROM compta_commissions WHERE compagnie!='' ORDER BY compagnie"
    ).fetchall()

    totaux = {
        'attendu':  sum(r['montant_attendu'] for r in commissions),
        'percu':    sum(r['montant_percu'] for r in commissions if r['statut']=='encaissee'),
        'en_retard':sum(r['montant_attendu'] for r in commissions if r['statut']=='retard'),
    }
    conn.close()
    return render_template('compta/commissions.html',
        commissions=commissions, stats_cie=stats_cie, totaux=totaux,
        annee=annee, statut=statut, compagnie=compagnie,
        compagnies=[c[0] for c in compagnies],
        statuts=STATUTS_COMMISSION,
        annees=list(range(int(get_param('annee_debut_activite','2024')),date.today().year+2)),
        today=date.today().isoformat())

@app.route('/compta/commissions/nouvelle', methods=['GET','POST'])
def compta_commission_nouvelle():
    conn = get_db()
    if request.method == 'POST':
        errors = []
        try: validate_required(get_compagnie_from_form(), 'Compagnie')
        except ValueError as e: errors.append(str(e))
        try: mt_attendu = safe_float(request.form.get('montant_attendu'), 0, 'Montant attendu')
        except ValueError as e: errors.append(str(e)); mt_attendu = 0.0
        try: mt_percu = safe_float(request.form.get('montant_percu') or 0, 0, 'Montant perçu')
        except ValueError as e: errors.append(str(e)); mt_percu = 0.0
        if errors:
            for e in errors: flash(f'❌ {e}', 'error')
            clients  = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
            contrats = conn.execute("""SELECT ct.id,ct.numero,ct.type_assurance,ct.compagnie,c.nom
                FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
            conn.close()
            return render_template('compta/commission_form.html',
                commission=None, clients=clients, contrats=contrats,
                statuts=STATUTS_COMMISSION, today=date.today().isoformat(),
                preselect_client=request.form.get('client_id'),
                preselect_contrat=request.form.get('contrat_id'))
        conn.close()
        ecart = round(mt_percu - mt_attendu, 2) if mt_percu else 0
        try:
            with db_transaction() as c:
                c.execute("""INSERT INTO compta_commissions
                    (compagnie,contrat_id,client_id,type_commission,periode,
                     date_prevue,montant_attendu,date_encaissement,montant_percu,
                     ecart,statut,notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (get_compagnie_from_form(),
                     request.form.get('contrat_id') or None,
                     request.form.get('client_id') or None,
                     request.form.get('type_commission','apport'),
                     request.form.get('periode',''),
                     request.form.get('date_prevue',''),
                     mt_attendu,
                     request.form.get('date_encaissement') or None,
                     mt_percu, ecart,
                     request.form.get('statut','attendue'),
                     request.form.get('notes','')))
                new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                log_audit('commissions', new_id, 'INSERT', 'creation', None,
                          f'{get_compagnie_from_form()} {mt_attendu}€')
            nlog('info', f'Commission #{new_id} créée — {mt_attendu}€ attendu')
        except Exception as e:
            nlog('error', f'Erreur création commission : {e}', exc=True)
            flash("❌ Erreur lors de l'enregistrement.", 'error')
            return redirect(request.url)
        flash('Commission enregistrée !', 'success')
        return redirect(url_for('compta_commissions'))
    clients  = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id,ct.numero,ct.type_assurance,ct.compagnie,c.nom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('compta/commission_form.html',
        commission=None, clients=clients, contrats=contrats,
        statuts=STATUTS_COMMISSION, today=date.today().isoformat(),
        preselect_client=request.args.get('client_id'),
        preselect_contrat=request.args.get('contrat_id'))

@app.route('/compta/commissions/<int:id>/modifier', methods=['GET','POST'])
def compta_commission_modifier(id):
    conn = get_db()
    comm = conn.execute("SELECT * FROM compta_commissions WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        mt_attendu = float(request.form.get('montant_attendu',0))
        mt_percu   = float(request.form.get('montant_percu') or 0)
        ecart = round(mt_percu - mt_attendu, 2) if mt_percu else 0
        conn.execute("""UPDATE compta_commissions SET compagnie=?,contrat_id=?,client_id=?,
            type_commission=?,periode=?,date_prevue=?,montant_attendu=?,
            date_encaissement=?,montant_percu=?,ecart=?,statut=?,notes=? WHERE id=?""",
            (get_compagnie_from_form(),
             request.form.get('contrat_id') or None,
             request.form.get('client_id') or None,
             request.form.get('type_commission','apport'),
             request.form.get('periode',''),
             request.form.get('date_prevue',''),
             mt_attendu,
             request.form.get('date_encaissement') or None,
             mt_percu, ecart,
             request.form.get('statut','attendue'),
             request.form.get('notes',''), id))
        conn.commit(); conn.close()
        flash('Commission mise à jour !', 'success')
        return redirect(url_for('compta_commissions'))
    clients  = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id,ct.numero,ct.type_assurance,ct.compagnie,c.nom
        FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('compta/commission_form.html',
        commission=comm, clients=clients, contrats=contrats,
        statuts=STATUTS_COMMISSION, today=date.today().isoformat(),
        preselect_client=None, preselect_contrat=None)

@app.route('/compta/commissions/<int:id>/encaisser', methods=['POST'])
def compta_commission_encaisser(id):
    conn = get_db()
    comm = conn.execute("SELECT * FROM compta_commissions WHERE id=?", (id,)).fetchone()
    if comm:
        try:
            mt_percu = safe_float(request.form.get('montant_percu', comm['montant_attendu']), 0, 'Montant perçu')
        except ValueError as e:
            flash(f'❌ {e}', 'error')
            conn.close()
            return redirect(url_for('compta_commissions'))
        ecart = round(mt_percu - float(comm['montant_attendu']), 2)
        d_enc = request.form.get('date_encaissement', date.today().isoformat())
        conn.execute("""UPDATE compta_commissions SET statut='encaissee',
            date_encaissement=?,montant_percu=?,ecart=? WHERE id=?""",
            (d_enc, mt_percu, ecart, id))
        # NAVISUR v9.3 — Audit encaissement
        log_audit('commissions', id, 'ENCAISSEMENT', 'montant_percu',
                  str(comm['montant_attendu']), str(mt_percu))
        if abs(ecart) > 0.01:
            log_audit('commissions', id, 'ECART', 'ecart', '0', str(ecart))
            nlog('warning', f'Commission #{id} : écart de {ecart}€ détecté')
        else:
            nlog('info', f'Commission #{id} encaissée : {mt_percu}€')
        # Créer automatiquement une ligne dans le livre des recettes
        num = next_numero_ordre()
        conn.execute("""INSERT INTO compta_recettes
            (numero_ordre,date_encaissement,reference,client_id,compagnie,contrat_id,
             nature_recette,montant,mode_reglement,periode_couverte,notes,annee,mois)
            VALUES (?,?,?,?,?,?,?,?,'virement',?,?,?,?)""",
            (num, d_enc, f'Commission {comm["compagnie"]} {comm["periode"] or ""}',
             comm['client_id'], comm['compagnie'], comm['contrat_id'],
             f'commission_{comm["type_commission"]}',
             mt_percu, comm['periode'] or '',
             f'Encaissement commission - {comm["compagnie"]}',
             int(d_enc[:4]), int(d_enc[5:7])))
        conn.commit()
    conn.close()
    flash('Commission encaissée + ligne recette créée automatiquement !', 'success')
    return redirect(url_for('compta_commissions'))

@app.route('/compta/commissions/<int:id>/supprimer', methods=['POST'])
def compta_commission_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM compta_commissions WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Commission supprimée.', 'info')
    return redirect(url_for('compta_commissions'))

# ── URSSAF ──────────────────────────────────────────────────────

@app.route('/compta/urssaf')
def compta_urssaf():
    annee = int(request.args.get('annee', date.today().year))
    conn = get_db()
    taux_cot = float(get_param('taux_cotisations', '21.1'))
    taux_vl  = float(get_param('taux_vl_ir', '2.2'))
    vl_actif = get_param('vl_ir_actif', '0') == '1'
    periodicite = get_param('periodicite_urssaf', 'trimestriel')

    decls = conn.execute(
        "SELECT * FROM compta_urssaf WHERE annee=? ORDER BY COALESCE(trimestre,mois)",
        (annee,)).fetchall()

    # Initialiser les périodes si manquantes
    today_str = date.today().isoformat()
    dl = urssaf_dates_limites(annee)
    if periodicite == 'trimestriel' and not decls:
        tri_labels = [f'{annee}-T1',f'{annee}-T2',f'{annee}-T3',f'{annee}-T4']
        for i,(label, dl_t) in enumerate(zip(tri_labels, dl.values()), 1):
            # CA du trimestre
            mois_debut = (i-1)*3+1
            mois_fin = i*3
            ca_t = float(conn.execute(
                """SELECT COALESCE(SUM(montant),0) FROM compta_recettes
                   WHERE annee=? AND mois BETWEEN ? AND ?""",
                (annee, mois_debut, mois_fin)).fetchone()[0])
            cot, vl, total = calc_urssaf(ca_t, taux_cot, taux_vl, vl_actif)
            statut = 'en_retard' if today_str > dl_t and ca_t > 0 else 'a_faire'
            conn.execute("""INSERT OR IGNORE INTO compta_urssaf
                (type_periode,periode_label,annee,trimestre,ca_periode,
                 cotisations_sociales,versement_liberatoire,total_a_payer,
                 date_limite,statut)
                VALUES ('trimestriel',?,?,?,?,?,?,?,?,?)""",
                (label, annee, i, ca_t, cot, vl, total, dl_t, statut))
        conn.commit()
        decls = conn.execute(
            "SELECT * FROM compta_urssaf WHERE annee=? ORDER BY trimestre",
            (annee,)).fetchall()
    else:
        # Mettre à jour les CA calculés
        for d in decls:
            if d['trimestre']:
                m1 = (d['trimestre']-1)*3+1
                m2 = d['trimestre']*3
                ca_t = float(conn.execute(
                    """SELECT COALESCE(SUM(montant),0) FROM compta_recettes
                       WHERE annee=? AND mois BETWEEN ? AND ?""",
                    (annee,m1,m2)).fetchone()[0])
                cot, vl, total = calc_urssaf(ca_t, taux_cot, taux_vl, vl_actif)
                statut = d['statut']
                if statut != 'faite':
                    statut = 'en_retard' if today_str > d['date_limite'] and ca_t > 0 else 'a_faire'
                conn.execute("""UPDATE compta_urssaf SET ca_periode=?,
                    cotisations_sociales=?,versement_liberatoire=?,total_a_payer=?,statut=?
                    WHERE id=?""", (ca_t, cot, vl, total, statut, d['id']))
        conn.commit()
        decls = conn.execute(
            "SELECT * FROM compta_urssaf WHERE annee=? ORDER BY COALESCE(trimestre,mois)",
            (annee,)).fetchall()

    ca_annee = get_ca_annee(annee)
    cot_tot, vl_tot, tot_tot = calc_urssaf(ca_annee, taux_cot, taux_vl, vl_actif)
    total_declare = sum(d['ca_periode'] for d in decls if d['statut']=='faite')
    total_paye = sum(d['total_a_payer'] for d in decls if d['statut']=='faite')

    conn.close()
    lien_urssaf = 'https://www.autoentrepreneur.urssaf.fr'
    return render_template('compta/urssaf.html',
        annee=annee, decls=decls, periodicite=periodicite,
        ca_annee=ca_annee, cot_annee=cot_tot, vl_annee=vl_tot, tot_annee=tot_tot,
        taux_cot=taux_cot, taux_vl=taux_vl, vl_actif=vl_actif,
        total_declare=total_declare, total_paye=total_paye,
        lien_urssaf=lien_urssaf, today=date.today().isoformat(),
        annees=list(range(int(get_param('annee_debut_activite','2024')),date.today().year+2)))

@app.route('/compta/urssaf/<int:id>/marquer_faite', methods=['POST'])
def urssaf_marquer_faite(id):
    conn = get_db()
    conn.execute("UPDATE compta_urssaf SET statut='faite', date_declaration=? WHERE id=?",
                 (date.today().isoformat(), id))
    conn.commit(); conn.close()
    flash('Déclaration marquée comme effectuée ✓', 'success')
    return redirect(request.referrer or url_for('compta_urssaf'))

@app.route('/compta/urssaf/<int:id>/reinit', methods=['POST'])
def urssaf_reinit(id):
    conn = get_db()
    conn.execute("UPDATE compta_urssaf SET statut='a_faire', date_declaration=NULL WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Déclaration réinitialisée.', 'info')
    return redirect(request.referrer or url_for('compta_urssaf'))

# ── API COMPTA ──────────────────────────────────────────────────

@app.route('/api/compta/ca_mois/<int:annee>')
def api_ca_mois(annee):
    conn = get_db()
    data = []
    for m in range(1,13):
        v = float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?",
            (annee,m)).fetchone()[0])
        data.append(round(v,2))
    conn.close()
    return jsonify(data)

@app.route('/api/compta/stats_rapides')
def api_compta_stats():
    annee = date.today().year
    ca = get_ca_annee(annee)
    plafond = float(get_param('micro_plafond_bnc','77700'))
    return jsonify({'ca': ca, 'plafond': plafond, 'pct': round(ca/plafond*100,1) if plafond else 0})


# ═══════════════════════════════════════════════════════════════
#  COMPTABILITÉ PHASE 2
#  Exports PDF · Facturation courtage · Intégration CRM ·
#  Échéancier fiscal · Registre dépenses
# ═══════════════════════════════════════════════════════════════

import io, calendar

# ─── EXPORT PDF LIVRE DES RECETTES ────────────────────────────

@app.route('/compta/recettes/export-pdf/<int:annee>')
def compta_recettes_pdf(annee):
    conn = get_db()
    recettes = conn.execute(
        """SELECT r.*, c.nom, c.prenom FROM compta_recettes r
           LEFT JOIN clients c ON r.client_id=c.id
           WHERE r.annee=? ORDER BY r.numero_ordre""", (annee,)).fetchall()
    total = float(conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?", (annee,)).fetchone()[0])
    params = get_all_params()
    conn.close()
    # Générer HTML → PDF via WeasyPrint si dispo, sinon renvoyer HTML imprimable
    html = render_template('compta/recettes_pdf.html',
        recettes=recettes, total=total, annee=annee, params=params,
        natures=dict(NATURES_RECETTE), today=date.today().isoformat())
    try:
        from weasyprint import HTML as WHP
        pdf = WHP(string=html).write_pdf()
        return Response(pdf,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename=livre_recettes_{annee}.pdf'})
    except ImportError:
        # WeasyPrint non installé : renvoyer la page HTML prête à imprimer
        return html

@app.route('/compta/recettes/export-excel/<int:annee>')
def compta_recettes_excel(annee):
    conn = get_db()
    recettes = conn.execute(
        """SELECT r.*, c.nom, c.prenom FROM compta_recettes r
           LEFT JOIN clients c ON r.client_id=c.id
           WHERE r.annee=? ORDER BY r.numero_ordre""", (annee,)).fetchall()
    conn.close()
    wb = Workbook(); ws = wb.active
    ws.title = f'Recettes {annee}'
    natures_d = dict(NATURES_RECETTE)
    hdrs = ['N° ordre','Date encaissement','Référence','Client/Payeur','Compagnie',
            'Nature recette','Montant €','Mode règlement','Période','Validée']
    ws.append(hdrs); style_header(ws, 1, len(hdrs))
    total = 0
    for i, r in enumerate(recettes, 2):
        payeur = f'{r["prenom"] or ""} {r["nom"] or ""}'.strip() or r["compagnie"] or '—'
        ws.append([r['numero_ordre'], r['date_encaissement'], r['reference'] or '',
                   payeur, r['compagnie'] or '',
                   natures_d.get(r['nature_recette'], r['nature_recette']),
                   r['montant'], r['mode_reglement'], r['periode_couverte'] or '',
                   'Oui' if r['valide'] else 'Non'])
        style_alt(ws, i, len(hdrs), i % 2 == 0)
        total += r['montant']
    # Ligne total
    ws.append([])
    ws.append(['TOTAL','','','','','', round(total,2)])
    style_header(ws, ws.max_row, len(hdrs), 'c9a84c')
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return Response(buf.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename=recettes_{annee}.xlsx'})

# ─── REGISTRE DES DÉPENSES ─────────────────────────────────────

CATEGORIES_DEPENSES = [
    ('rc_pro',         'RC Pro / Garantie financière'),
    ('orias',          'ORIAS (cotisation annuelle)'),
    ('formation_dda',  'Formation DDA'),
    ('logiciels',      'Logiciels / CRM / Informatique'),
    ('telephone',      'Téléphone / Internet'),
    ('deplacements',   'Déplacements (carburant, péages, train)'),
    ('hebergement',    'Hébergement'),
    ('restauration',   'Restauration professionnelle'),
    ('fournitures',    'Fournitures de bureau'),
    ('frais_postaux',  'Frais postaux'),
    ('salon_nautique', 'Salon nautique'),
    ('marketing',      'Marketing / Publicité / Site web'),
    ('banque',         'Banque (frais de compte pro)'),
    ('expert_comptable','Expert-comptable'),
    ('loyer',          'Loyer / Coworking'),
    ('autre',          'Autre'),
]

@app.route('/compta/depenses')
def compta_depenses():
    annee = int(request.args.get('annee', date.today().year))
    categorie = request.args.get('categorie', '')
    conn = get_db()
    q = "SELECT * FROM compta_depenses WHERE annee=?"
    p = [annee]
    if categorie: q += " AND categorie=?"; p.append(categorie)
    q += " ORDER BY date_depense DESC"
    depenses = conn.execute(q, p).fetchall()
    # Totaux par catégorie
    totaux_cat = conn.execute(
        """SELECT categorie, COALESCE(SUM(montant),0) as total
           FROM compta_depenses WHERE annee=? GROUP BY categorie ORDER BY total DESC""",
        (annee,)).fetchall()
    total = float(conn.execute(
        "SELECT COALESCE(SUM(montant),0) FROM compta_depenses WHERE annee=?",
        (annee,)).fetchone()[0])
    conn.close()
    return render_template('compta/depenses.html',
        depenses=depenses, totaux_cat=totaux_cat, total=total,
        annee=annee, categorie=categorie,
        categories=CATEGORIES_DEPENSES,
        annees=list(range(int(get_param('annee_debut_activite','2024')), date.today().year+2)))

@app.route('/compta/depenses/nouvelle', methods=['GET','POST'])
def compta_depense_nouvelle():
    conn = get_db()
    if request.method == 'POST':
        d = request.form.get('date_depense', date.today().isoformat())
        num = conn.execute("SELECT COALESCE(MAX(numero_ordre),0)+1 FROM compta_depenses").fetchone()[0]
        conn.execute("""INSERT INTO compta_depenses
            (numero_ordre,date_depense,fournisseur,categorie,montant,
             mode_paiement,recurrence,notes,annee,mois)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (num, d, request.form.get('fournisseur',''),
             request.form['categorie'],
             float(request.form['montant']),
             request.form.get('mode_paiement','virement'),
             request.form.get('recurrence','ponctuel'),
             request.form.get('notes',''),
             int(d[:4]), int(d[5:7])))
        conn.commit(); conn.close()
        flash('Dépense enregistrée !', 'success')
        return redirect(url_for('compta_depenses', annee=int(d[:4])))
    conn.close()
    return render_template('compta/depense_form.html',
        depense=None, categories=CATEGORIES_DEPENSES,
        modes=MODES_REGLEMENT, today=date.today().isoformat())

@app.route('/compta/depenses/<int:id>/modifier', methods=['GET','POST'])
def compta_depense_modifier(id):
    conn = get_db()
    dep = conn.execute("SELECT * FROM compta_depenses WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        d = request.form['date_depense']
        conn.execute("""UPDATE compta_depenses SET date_depense=?,fournisseur=?,categorie=?,
            montant=?,mode_paiement=?,recurrence=?,notes=?,annee=?,mois=? WHERE id=?""",
            (d, request.form.get('fournisseur',''), request.form['categorie'],
             float(request.form['montant']),
             request.form.get('mode_paiement','virement'),
             request.form.get('recurrence','ponctuel'),
             request.form.get('notes',''),
             int(d[:4]), int(d[5:7]), id))
        conn.commit(); conn.close()
        flash('Dépense mise à jour !', 'success')
        return redirect(url_for('compta_depenses'))
    conn.close()
    return render_template('compta/depense_form.html',
        depense=dep, categories=CATEGORIES_DEPENSES,
        modes=MODES_REGLEMENT, today=date.today().isoformat())

@app.route('/compta/depenses/<int:id>/supprimer', methods=['POST'])
def compta_depense_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM compta_depenses WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Dépense supprimée.', 'info')
    return redirect(url_for('compta_depenses'))

# ─── FACTURATION FRAIS DE COURTAGE ────────────────────────────

@app.route('/compta/factures-courtage')
def compta_factures():
    conn = get_db()
    statut = request.args.get('statut', '')
    annee  = int(request.args.get('annee', date.today().year))
    q = """SELECT fc.*, c.nom, c.prenom, c.email FROM compta_factures fc
           LEFT JOIN clients c ON fc.client_id=c.id
           WHERE fc.annee=?"""
    p = [annee]
    if statut: q += " AND fc.statut=?"; p.append(statut)
    q += " ORDER BY fc.numero DESC"
    factures = conn.execute(q, p).fetchall()
    totaux = {
        'emises':  float(conn.execute("SELECT COALESCE(SUM(montant_ttc),0) FROM compta_factures WHERE annee=? AND statut='emise'", (annee,)).fetchone()[0]),
        'payees':  float(conn.execute("SELECT COALESCE(SUM(montant_ttc),0) FROM compta_factures WHERE annee=? AND statut='payee'", (annee,)).fetchone()[0]),
        'retard':  float(conn.execute("SELECT COALESCE(SUM(montant_ttc),0) FROM compta_factures WHERE annee=? AND statut='retard'", (annee,)).fetchone()[0]),
    }
    conn.close()
    return render_template('compta/factures_courtage.html',
        factures=factures, totaux=totaux, statut=statut, annee=annee,
        annees=list(range(int(get_param('annee_debut_activite','2024')), date.today().year+2)))

@app.route('/compta/factures-courtage/nouvelle', methods=['GET','POST'])
def compta_facture_nouvelle():
    conn = get_db()
    if request.method == 'POST':
        d = request.form.get('date_emission', date.today().isoformat())
        annee_val = int(d[:4])
        # Numérotation FC-2025-001
        nb = conn.execute(
            "SELECT COUNT(*)+1 FROM compta_factures WHERE annee=?", (annee_val,)).fetchone()[0]
        numero = f'FC-{annee_val}-{nb:03d}'
        montant = float(request.form['montant'])
        conn.execute("""INSERT INTO compta_factures
            (numero,client_id,date_emission,date_echeance,objet,montant_ht,
             taux_tva,montant_ttc,statut,notes,annee)
            VALUES (?,?,?,?,?,?,0,?,'brouillon',?,?)""",
            (numero, request.form.get('client_id') or None,
             d, request.form.get('date_echeance',''),
             request.form['objet'], montant, montant,
             request.form.get('notes',''), annee_val))
        conn.commit(); conn.close()
        flash(f'Facture {numero} créée !', 'success')
        return redirect(url_for('compta_factures'))
    clients = conn.execute("SELECT id,nom,prenom,email FROM clients ORDER BY nom").fetchall()
    params  = get_all_params()
    conn.close()
    return render_template('compta/facture_courtage_form.html',
        facture=None, clients=clients, params=params,
        today=date.today().isoformat(),
        preselect=request.args.get('client_id'))

@app.route('/compta/factures-courtage/<int:id>/modifier', methods=['GET','POST'])
def compta_facture_modifier(id):
    conn = get_db()
    fc = conn.execute("SELECT * FROM compta_factures WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        montant = float(request.form['montant'])
        conn.execute("""UPDATE compta_factures SET client_id=?,date_emission=?,
            date_echeance=?,objet=?,montant_ht=?,montant_ttc=?,statut=?,notes=? WHERE id=?""",
            (request.form.get('client_id') or None,
             request.form['date_emission'],
             request.form.get('date_echeance',''),
             request.form['objet'], montant, montant,
             request.form.get('statut','brouillon'),
             request.form.get('notes',''), id))
        conn.commit(); conn.close()
        flash('Facture mise à jour !', 'success')
        return redirect(url_for('compta_factures'))
    clients = conn.execute("SELECT id,nom,prenom,email FROM clients ORDER BY nom").fetchall()
    params  = get_all_params()
    conn.close()
    return render_template('compta/facture_courtage_form.html',
        facture=fc, clients=clients, params=params,
        today=date.today().isoformat(), preselect=None)

@app.route('/compta/factures-courtage/<int:id>/imprimer')
def compta_facture_imprimer(id):
    conn = get_db()
    fc = conn.execute("""SELECT fc.*, c.nom, c.prenom, c.email, c.adresse,
        c.code_postal, c.ville, c.siren, c.telephone
        FROM compta_factures fc LEFT JOIN clients c ON fc.client_id=c.id
        WHERE fc.id=?""", (id,)).fetchone()
    params = get_all_params()
    conn.close()
    if not fc:
        flash('Facture introuvable.', 'error')
        return redirect(url_for('compta_factures'))
    return render_template('compta/facture_courtage_print.html', fc=fc, params=params,
                           now=dt.now())

@app.route('/compta/factures-courtage/<int:id>/payer', methods=['POST'])
def compta_facture_payer(id):
    conn = get_db()
    conn.execute("UPDATE compta_factures SET statut='payee', date_paiement=? WHERE id=?",
                 (date.today().isoformat(), id))
    conn.commit(); conn.close()
    flash('Facture marquée comme payée ✓', 'success')
    return redirect(url_for('compta_factures'))

@app.route('/compta/factures-courtage/<int:id>/supprimer', methods=['POST'])
def compta_facture_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM compta_factures WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Facture supprimée.', 'info')
    return redirect(url_for('compta_factures'))

# ─── ÉCHÉANCIER FISCAL ANNUEL ──────────────────────────────────

@app.route('/compta/echeancier')
def compta_echeancier():
    annee = int(request.args.get('annee', date.today().year))
    today_str = date.today().isoformat()

    echeances = [
        # (mois, jour, label, categorie, details)
        (1,  31, 'Déclaration URSSAF T4',         'urssaf',    f'CA oct-déc {annee-1}'),
        (1,  31, 'Renouvellement ORIAS',           'orias',     'Cotisation annuelle ORIAS'),
        (3,  31, 'Renouvellement RC Pro',          'assurance', 'Vérifier renouvellement RC Professionnelle'),
        (4,  30, 'Déclaration URSSAF T1',          'urssaf',    f'CA jan-mar {annee}'),
        (5,  31, 'Déclaration revenus IR (2042)',  'impots',    '2042 + 2042-C-PRO'),
        (7,  31, 'Déclaration URSSAF T2',          'urssaf',    f'CA avr-juin {annee}'),
        (10, 15, 'Bilan formation DDA',            'formation', '15h atteintes ?'),
        (10, 31, 'Déclaration URSSAF T3',          'urssaf',    f'CA juil-sep {annee}'),
        (12, 15, 'CFE (Cotisation Foncière)',      'impots',    'Cotisation Foncière des Entreprises'),
        (12, 31, 'Clôture comptable',              'compta',    'Archivage, bilan annuel'),
    ]

    # Récupérer les statuts sauvegardés
    conn = get_db()
    statuts_sauv = {}
    for row in conn.execute(
            "SELECT cle, valeur FROM parametres WHERE cle LIKE 'echeance_%'").fetchall():
        statuts_sauv[row['cle']] = row['valeur']
    conn.close()

    items = []
    for mois, jour, label, cat, details in echeances:
        d_str = f'{annee}-{mois:02d}-{jour:02d}'
        cle = f'echeance_{annee}_{mois:02d}_{jour:02d}_{cat}'
        fait = statuts_sauv.get(cle, '0') == '1'
        retard = d_str < today_str and not fait
        urgence = (not fait and not retard and
                   (date.fromisoformat(d_str) - date.today()).days <= 15)
        items.append({
            'date': d_str, 'label': label, 'categorie': cat,
            'details': details, 'fait': fait, 'retard': retard,
            'urgence': urgence, 'cle': cle,
        })

    items.sort(key=lambda x: x['date'])
    return render_template('compta/echeancier.html',
        items=items, annee=annee, today=today_str,
        annees=list(range(int(get_param('annee_debut_activite','2024')), date.today().year+2)))

@app.route('/compta/echeancier/toggle', methods=['POST'])
def compta_echeancier_toggle():
    cle = request.form['cle']
    val = request.form.get('val', '1')
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO parametres (cle,valeur) VALUES (?,?)", (cle, val))
    conn.commit(); conn.close()
    return 'ok'

# ─── INTÉGRATION CRM : contrat → commission auto ───────────────

@app.route('/api/contrat_commission_auto/<int:contrat_id>', methods=['POST'])
def api_contrat_commission_auto(contrat_id):
    """Crée une commission attendue depuis la fiche contrat."""
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (contrat_id,)).fetchone()
    if not ct:
        conn.close(); return jsonify({'error': 'Contrat introuvable'}), 404
    # Calculer montant attendu = prime * taux commission (ou 10% par défaut)
    taux = float(request.form.get('taux', 10)) / 100
    mt_attendu = round(float(ct['prime_annuelle'] or 0) * taux, 2)
    type_c = request.form.get('type', 'apport')
    # Date prévue = date début contrat + 30 jours
    from datetime import timedelta
    try:
        d_debut = date.fromisoformat(ct['date_debut'] or date.today().isoformat())
        d_prevue = (d_debut + timedelta(days=30)).isoformat()
    except Exception:
        d_prevue = date.today().isoformat()
    conn.execute("""INSERT INTO compta_commissions
        (compagnie,contrat_id,client_id,type_commission,periode,
         date_prevue,montant_attendu,statut)
        VALUES (?,?,?,?,?,?,?,'attendue')""",
        (ct['compagnie'] or '—', contrat_id, ct['client_id'],
         type_c, str(date.today().year), d_prevue, mt_attendu))
    conn.commit(); conn.close()
    flash(f'Commission attendue créée ({mt_attendu:.2f} €) ✓', 'success')
    return redirect(url_for('contrat_detail', id=contrat_id))


# ═══════════════════════════════════════════════════════════════
#  V7 — Notifications · Sauvegarde · Renouvellement · Dashboard
# ═══════════════════════════════════════════════════════════════

import shutil, glob
from datetime import timedelta

# ── MOTEUR DE NOTIFICATIONS ────────────────────────────────────

def generer_notifications():
    """Génère/rafraîchit toutes les alertes automatiques."""
    conn = get_db()
    today = date.today()
    today_s = today.isoformat()
    # Vider les notifs auto (garde les manuelles)
    conn.execute("DELETE FROM notifications WHERE type != 'manuelle'")

    # 1. Contrats expirant dans 90 jours
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
            f"/contrats/{ct['id']}",
            prio))

    # 2. Contrats expirés (non renouvelés)
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

    # 3. Commissions en retard (>30j)
    comm_retard = conn.execute("""
        SELECT cc.id, cc.compagnie, cc.montant_attendu, cc.date_prevue,
               c.nom, c.prenom
        FROM compta_commissions cc LEFT JOIN clients c ON cc.client_id=c.id
        WHERE cc.statut IN ('attendue','releve_recu')
          AND cc.date_prevue < ?
          AND CAST(julianday(?) - julianday(cc.date_prevue) AS INTEGER) > 30
    """, (today_s, today_s)).fetchall()
    for cm in comm_retard:
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('commission',?,?,?,'haute')""", (
            f"💰 Commission en retard — {cm['compagnie']}",
            f"{cm['montant_attendu']:.0f} € attendus depuis le {cm['date_prevue']} "
            f"({cm['prenom'] or ''} {cm['nom'] or ''})".strip(),
            f"/compta/commissions"))

    # 4. Relances à faire aujourd'hui ou en retard
    relances_dues = conn.execute("""
        SELECT r.id, r.type_relance, r.date_prevue, c.nom, c.prenom, ct.numero
        FROM relances r JOIN clients c ON r.client_id=c.id
        JOIN contrats ct ON r.contrat_id=ct.id
        WHERE r.statut='a_faire' AND r.date_prevue <= ?
    """, (today_s,)).fetchall()
    for r in relances_dues:
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('relance',?,?,?,'normale')""", (
            f"📣 Relance — {r['prenom'] or ''} {r['nom']}",
            f"Relance {r['type_relance'] or ''} prévue le {r['date_prevue']} "
            f"(contrat {r['numero'] or ''})".strip(),
            f"/relances"))

    # 5. Déclaration URSSAF à faire
    urssaf_dues = conn.execute("""
        SELECT id, periode_label, date_limite, total_a_payer
        FROM compta_urssaf WHERE statut != 'faite' AND date_limite <= ?
    """, ((today + timedelta(days=15)).isoformat(),)).fetchall()
    for u in urssaf_dues:
        retard = u['date_limite'] < today_s
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('urssaf',?,?,?,'haute')""", (
            f"🏛️ URSSAF {u['periode_label']} {'— EN RETARD' if retard else 'à déclarer'}",
            f"CA à déclarer · {u['total_a_payer']:.2f} € à payer · Limite : {u['date_limite']}",
            f"/compta/urssaf"))

    # 6. RDV aujourd'hui
    rdvs_ajd = conn.execute("""
        SELECT r.id, r.titre, r.heure_debut, c.nom, c.prenom
        FROM rendez_vous r LEFT JOIN clients c ON r.client_id=c.id
        WHERE r.date_rdv=? AND r.statut IN ('prevu','confirme')
    """, (today_s,)).fetchall()
    for r in rdvs_ajd:
        conn.execute("""INSERT INTO notifications (type,titre,message,lien,priorite)
            VALUES ('rdv',?,?,?,'normale')""", (
            f"📅 RDV aujourd'hui{(' à ' + r['heure_debut'][:5]) if r['heure_debut'] else ''} — {r['titre']}",
            f"{r['prenom'] or ''} {r['nom'] or ''}".strip() or 'Sans client',
            f"/agenda"))

    # Notifications enrichies P1
    generer_notifications_enrichies(conn, today_s)

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

# Injecter nb_notifs dans tous les templates
@app.context_processor
def inject_notifs():
    try:
        return {'nb_notifs': get_nb_notifs()}
    except Exception:
        return {'nb_notifs': 0}

# ── ROUTES NOTIFICATIONS ───────────────────────────────────────

@app.route('/notifications')
def notifications_list():
    generer_notifications()
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications ORDER BY priorite='haute' DESC, date_creation DESC"
    ).fetchall()
    conn.close()
    return render_template('notifications.html', notifs=notifs)

@app.route('/notifications/lire/<int:id>', methods=['POST'])
def notif_lire(id):
    conn = get_db()
    conn.execute("UPDATE notifications SET lu=1 WHERE id=?", (id,))
    conn.commit(); conn.close()
    return redirect(request.referrer or url_for('notifications_list'))

@app.route('/notifications/tout-lire', methods=['POST'])
def notifs_tout_lire():
    conn = get_db()
    conn.execute("UPDATE notifications SET lu=1")
    conn.commit(); conn.close()
    flash('Toutes les notifications marquées comme lues.', 'success')
    return redirect(url_for('notifications_list'))

@app.route('/api/notifications/count')
def api_notif_count():
    generer_notifications()
    return jsonify({'count': get_nb_notifs()})

# ── SAUVEGARDE AUTOMATIQUE ─────────────────────────────────────

# (défini dans core.py)

@app.route('/sauvegarde')
def sauvegarde_page():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backups = []
    for f in sorted(glob.glob(os.path.join(BACKUP_DIR, '*.db')), reverse=True)[:20]:
        stat = os.stat(f)
        backups.append({
            'nom': os.path.basename(f),
            'taille': stat.st_size,
            'date': dt.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
        })
    db_size = os.path.getsize(DATABASE) if os.path.exists(DATABASE) else 0
    return render_template('sauvegarde.html', backups=backups, db_size=db_size,
                           backup_dir=BACKUP_DIR)

@app.route('/sauvegarde/creer', methods=['POST'])
def sauvegarde_creer():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    nom = f'riviera-marine_{dt.now().strftime("%Y%m%d_%H%M%S")}.db'
    dest = os.path.join(BACKUP_DIR, nom)
    try:
        # Copie sécurisée via sqlite3 backup API
        import sqlite3 as _sq
        src_conn = _sq.connect(DATABASE)
        dst_conn = _sq.connect(dest)
        src_conn.backup(dst_conn)
        dst_conn.close(); src_conn.close()
        size = os.path.getsize(dest)
        flash(f'✅ Sauvegarde créée : {nom} ({size//1024} Ko)', 'success')
    except Exception as e:
        flash(f'❌ Erreur sauvegarde : {e}', 'error')
    return redirect(url_for('sauvegarde_page'))

@app.route('/sauvegarde/telecharger/<nom>')
def sauvegarde_telecharger(nom):
    return send_from_directory(BACKUP_DIR, nom, as_attachment=True)

@app.route('/sauvegarde/supprimer/<nom>', methods=['POST'])
def sauvegarde_supprimer(nom):
    path = os.path.join(BACKUP_DIR, nom)
    if os.path.isfile(path) and nom.endswith('.db'):
        os.remove(path)
        flash('Sauvegarde supprimée.', 'info')
    return redirect(url_for('sauvegarde_page'))



# ── ONEDRIVE SYNC ──────────────────────────────────────────────

def _detect_onedrive_path():
    """Détecte automatiquement le dossier OneDrive sur Windows."""
    candidates = [
        os.environ.get("OneDrive"),
        os.environ.get("OneDriveCommercial"),
        os.path.join(os.path.expanduser("~"), "OneDrive"),
        os.path.join(os.path.expanduser("~"), "OneDrive - Personal"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def _sync_onedrive_if_enabled():
    """Sync silencieuse vers OneDrive si activée dans les paramètres."""
    try:
        params = get_all_params()
        if params.get('onedrive_enabled') != '1':
            return False
        sync_path = params.get('onedrive_path', '').strip()
        if not sync_path or not os.path.exists(sync_path):
            return False
        target_dir = os.path.join(sync_path, 'NAVISUR')
        os.makedirs(target_dir, exist_ok=True)
        target_db = os.path.join(target_dir, 'navisur.db')
        import sqlite3 as _sq2
        src = _sq2.connect(DATABASE)
        dst = _sq2.connect(target_db)
        src.backup(dst); dst.close(); src.close()
        return True
    except Exception as _e:
        app.logger.warning(f'OneDrive sync silencieuse échouée : {_e}')
        return False

@app.route('/sauvegarde/onedrive-detect')
def onedrive_detect():
    path = _detect_onedrive_path()
    return jsonify({'path': path or '', 'found': bool(path)})

@app.route('/sauvegarde/onedrive-sync', methods=['POST'])
def onedrive_sync_manual():
    params = get_all_params()
    sync_path = params.get('onedrive_path', '').strip()
    if not sync_path or not os.path.exists(sync_path):
        flash('❌ Chemin OneDrive introuvable. Vérifiez la configuration.', 'error')
        return redirect(url_for('parametres'))
    try:
        target_dir = os.path.join(sync_path, 'NAVISUR')
        os.makedirs(target_dir, exist_ok=True)
        target_db = os.path.join(target_dir, 'navisur.db')
        import sqlite3 as _sq3
        src = _sq3.connect(DATABASE)
        dst = _sq3.connect(target_db)
        src.backup(dst); dst.close(); src.close()
        size = os.path.getsize(target_db)
        flash(f'✅ Base synchronisée vers OneDrive ({size//1024} Ko) — {target_db}', 'success')
    except Exception as e:
        flash(f'❌ Erreur synchronisation OneDrive : {e}', 'error')
    return redirect(url_for('parametres'))

# ── ÉDITEUR MISE EN PAGE IMPRESSIONS ──────────────────────────

@app.route('/parametres/mise-en-page', methods=['GET', 'POST'])
def mise_en_page():
    conn = get_db()
    if request.method == 'POST':
        keys = ['print_couleur_principale', 'print_couleur_accent',
                'print_pied_page', 'print_sous_titre']
        for k in keys:
            val = request.form.get(k, '')
            conn.execute("INSERT OR REPLACE INTO parametres (cle,valeur) VALUES (?,?)", (k, val))
        conn.commit(); conn.close()
        flash('✅ Mise en page enregistrée !', 'success')
        return redirect(url_for('mise_en_page'))
    conn.close()
    params = get_all_params()
    return render_template('parametres/mise_en_page.html', params=params)


def sauvegarde_auto():
    """Sauvegarde quotidienne automatique (conserve 30 jours) + sync OneDrive."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today_s = date.today().strftime('%Y%m%d')
    dest = os.path.join(BACKUP_DIR, f'auto_{today_s}.db')
    if not os.path.exists(dest):
        try:
            import sqlite3 as _sq
            src = _sq.connect(DATABASE)
            dst = _sq.connect(dest)
            src.backup(dst); dst.close(); src.close()
            # Nettoyer les vieilles sauvegardes auto (> 30j)
            for f in glob.glob(os.path.join(BACKUP_DIR, 'auto_*.db')):
                if os.path.basename(f) < f'auto_{(date.today()-timedelta(days=30)).strftime("%Y%m%d")}.db':
                    os.remove(f)
        except Exception:
            pass
    # Synchronisation OneDrive automatique si activée
    _sync_onedrive_if_enabled()

# ── RENOUVELLEMENT CONTRAT EN 1 CLIC ─────────────────────────

@app.route('/contrats/<int:id>/renouveler', methods=['GET','POST'])
def contrat_renouveler(id):
    conn = get_db()
    old = conn.execute("""SELECT ct.*,c.nom,c.prenom,c.email,b.nom_bateau
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id WHERE ct.id=?""", (id,)).fetchone()
    if not old:
        flash('Contrat introuvable.', 'error'); conn.close()
        return redirect(url_for('contrats_list'))

    if request.method == 'POST':
        # NAVISUR v9.3 — Validation renouvellement
        errors = []
        try: prime = safe_float(request.form.get('prime_annuelle'), 0, 'Prime annuelle')
        except ValueError as e: errors.append(str(e)); prime = 0.0
        try: taux_comm = safe_float(request.form.get('taux_commission', 10), 0, 'Taux commission')
        except ValueError as e: errors.append(str(e)); taux_comm = 10.0
        try: validate_dates(request.form.get('date_debut'), request.form.get('date_fin'))
        except ValueError as e: errors.append(str(e))
        if errors:
            for e in errors: flash(f'❌ {e}', 'error')
            conn.close(); return redirect(request.url)
        date_debut = request.form['date_debut']
        date_fin   = request.form['date_fin']
        compagnie  = request.form.get('compagnie', old['compagnie'] or '')
        notes      = request.form.get('notes', '')
        old_prime  = old['prime_annuelle']

        # 1. Archiver l'ancien contrat
        conn.execute(
            "UPDATE contrats SET statut='renouvele' WHERE id=?", (id,))

        # 2. Créer le nouveau contrat (copie + nouvelles valeurs)
        import re
        old_num = old['numero'] or ''
        # Incrémenter le numéro : POL-2025-001 → POL-2026-001
        new_year = date_debut[:4]
        new_num  = re.sub(r'\d{4}', new_year, old_num, count=1) if old_num else f'REN-{new_year}-{id:03d}'

        conn.execute("""INSERT INTO contrats
            (client_id, bateau_id, numero, type_assurance, compagnie,
             date_debut, date_fin, prime_annuelle, franchise, statut, notes)
            VALUES (?,?,?,?,?,?,?,?,?,'en_cours',?)""",
            (old['client_id'], old['bateau_id'], new_num,
             old['type_assurance'], compagnie,
             date_debut, date_fin, prime, old['franchise'] or 0, notes))
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        # NAVISUR v9.3 — Audit renouvellement
        log_audit('contrats', id, 'RENOUVELLEMENT', 'statut', 'en_cours', 'renouvele')
        log_audit('contrats', new_id, 'INSERT', 'prime_annuelle', str(old_prime), str(prime))
        nlog('info', f'Contrat #{id} renouvelé → nouveau contrat #{new_id} prime {prime}€')

        # 3. Copier la checklist (réinitialiser à non reçu)
        old_pieces = conn.execute(
            "SELECT libelle, obligatoire FROM checklist_pieces WHERE contrat_id=?", (id,)).fetchall()
        for p in old_pieces:
            conn.execute(
                "INSERT INTO checklist_pieces (contrat_id,libelle,obligatoire,recu) VALUES (?,?,?,0)",
                (new_id, p['libelle'], p['obligatoire']))

        # 4. Créer la commission attendue automatiquement
        mt_comm = round(prime * taux_comm / 100, 2)
        try:
            d_prevue = (date.fromisoformat(date_debut) + timedelta(days=30)).isoformat()
        except Exception:
            d_prevue = date_debut
        conn.execute("""INSERT INTO compta_commissions
            (compagnie,contrat_id,client_id,type_commission,periode,
             date_prevue,montant_attendu,statut)
            VALUES (?,?,?,'renouvellement',?,?,?,'attendue')""",
            (compagnie, new_id, old['client_id'],
             f'Renouvellement {date_debut[:4]}', d_prevue, mt_comm))

        # 5. Créer relance signature automatique
        conn.execute("""INSERT INTO relances
            (contrat_id,client_id,type_relance,date_prevue,moyen,statut,message)
            VALUES (?,?,'signature',?,'email','a_faire',?)""",
            (new_id, old['client_id'], date_debut,
             f'Renouvellement contrat {new_num} — faire signer le bulletin'))

        conn.commit()
        flash(f'✅ Contrat renouvelé ! Nouveau n° : {new_num} · Commission {mt_comm:.2f} € créée.', 'success')
        conn.close()
        return redirect(url_for('contrat_detail', id=new_id))

    # Calculer dates proposées (+1 an)
    try:
        d_debut = date.fromisoformat(old['date_fin'] or date.today().isoformat())
        d_fin   = date(d_debut.year+1, d_debut.month, d_debut.day).isoformat()
        d_debut_s = d_debut.isoformat()
    except Exception:
        d_debut_s = date.today().isoformat()
        d_fin     = date(date.today().year+1, date.today().month, date.today().day).isoformat()

    conn.close()
    return render_template('contrats/renouveler.html', contrat=old,
                           date_debut=d_debut_s, date_fin=d_fin,
                           today=date.today().isoformat())

# ── DASHBOARD "QUE FAIRE AUJOURD'HUI" ─────────────────────────

@app.route('/aujourdhui')
def aujourdhui():
    generer_notifications()
    today = date.today()
    today_s = today.isoformat()
    conn = get_db()

    # Relances du jour / en retard
    relances_ajd = conn.execute("""
        SELECT r.*, c.nom, c.prenom, c.email, c.telephone, ct.numero, ct.type_assurance
        FROM relances r JOIN clients c ON r.client_id=c.id
        JOIN contrats ct ON r.contrat_id=ct.id
        WHERE r.statut='a_faire' AND r.date_prevue <= ?
        ORDER BY r.date_prevue
    """, (today_s,)).fetchall()

    # Contrats expirant dans 30/90 jours (avec tacite)
    _ech_q2 = """SELECT ct.*, c.nom, c.prenom, c.email, b.nom_bateau,
               CAST(julianday(ct.date_fin) - julianday(?) AS INTEGER) as jours,
               COALESCE(ct.tacite_reconduction,1) as tacite_reconduction,
               ct.annee_prime_validee, ct.prime_annee_en_cours
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.statut='en_cours' AND ct.date_fin IS NOT NULL
          AND julianday(ct.date_fin) - julianday(?) BETWEEN {a} AND {b}
        ORDER BY ct.date_fin"""
    contrats_30j = conn.execute(_ech_q2.format(a=0, b=30), (today_s, today_s)).fetchall()
    contrats_90j = conn.execute(_ech_q2.format(a=31, b=90), (today_s, today_s)).fetchall()

    # RDV du jour
    rdvs_ajd = conn.execute("""
        SELECT r.*, c.nom, c.prenom, c.telephone
        FROM rendez_vous r LEFT JOIN clients c ON r.client_id=c.id
        WHERE r.date_rdv=? AND r.statut IN ('prevu','confirme')
        ORDER BY r.heure_debut
    """, (today_s,)).fetchall()

    # Commissions en retard
    comm_retard = conn.execute("""
        SELECT cc.*, c.nom, c.prenom
        FROM compta_commissions cc LEFT JOIN clients c ON cc.client_id=c.id
        WHERE cc.statut IN ('attendue','releve_recu')
          AND cc.date_prevue < ?
          AND cc.date_prevue IS NOT NULL
        ORDER BY cc.date_prevue
    """, (today_s,)).fetchall()

    # Pièces manquantes (contrats actifs avec checklist incomplète)
    pieces_manquantes = conn.execute("""
        SELECT ct.id, ct.numero, ct.type_assurance, c.nom, c.prenom,
               COUNT(cp.id) as total_pieces,
               SUM(cp.recu) as pieces_recues
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        JOIN checklist_pieces cp ON cp.contrat_id=ct.id
        WHERE ct.statut='en_cours' AND cp.obligatoire=1
        GROUP BY ct.id HAVING pieces_recues < total_pieces
        ORDER BY (total_pieces - pieces_recues) DESC
        LIMIT 10
    """).fetchall()

    # URSSAF à faire
    urssaf_dues = conn.execute("""
        SELECT * FROM compta_urssaf WHERE statut != 'faite'
          AND date_limite <= ?
    """, ((today + timedelta(days=15)).isoformat(),)).fetchall()

    # Tâches du jour
    taches_ajd = conn.execute("""
        SELECT t.*, c.nom, c.prenom FROM taches t
        LEFT JOIN clients c ON t.client_id=c.id
        WHERE t.statut='a_faire' AND t.date_echeance <= ?
        ORDER BY t.date_echeance
    """, (today_s,)).fetchall()

    # Stats rapides
    stats = {
        'nb_clients': conn.execute("SELECT COUNT(*) FROM clients WHERE statut='client'").fetchone()[0],
        'nb_contrats_actifs': conn.execute("SELECT COUNT(*) FROM contrats WHERE statut='en_cours'").fetchone()[0],
        'ca_mois': float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?",
            (today.year, today.month)).fetchone()[0]),
        'ca_annee': float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?",
            (today.year,)).fetchone()[0]),
        'plafond': float(get_param('micro_plafond_bnc','77700')),
    }
    conn.close()
    return render_template('aujourdhui.html',
        relances_ajd=relances_ajd, contrats_30j=contrats_30j,
        contrats_90j=contrats_90j, rdvs_ajd=rdvs_ajd,
        comm_retard=comm_retard, pieces_manquantes=pieces_manquantes,
        urssaf_dues=urssaf_dues, taches_ajd=taches_ajd,
        stats=stats, today=today_s,
        mois_nom=['Janvier','Février','Mars','Avril','Mai','Juin',
                  'Juillet','Août','Septembre','Octobre','Novembre','Décembre'][today.month-1],
        jour_semaine=['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche'][today.weekday()])


# ═══════════════════════════════════════════════════════════════
#  MODULE ENVOI EMAILS (via mailto: + prévisualisation)
# ═══════════════════════════════════════════════════════════════

import urllib.parse

# Variables disponibles dans les templates email
EMAIL_VARIABLES = {
    '{prenom}':          'Prénom du client',
    '{nom}':             'Nom du client',
    '{email}':           'Email du client',
    '{telephone}':       'Téléphone du client',
    '{num_contrat}':     'Numéro de contrat',
    '{type_assurance}':  "Type d'assurance",
    '{compagnie}':       "Compagnie d'assurance",
    '{date_echeance}':   "Date d'échéance du contrat",
    '{prime_annuelle}':  'Prime annuelle',
    '{nom_bateau}':      'Nom du bateau',
    '{cabinet_nom}':     'Nom du cabinet',
    '{cabinet_telephone}': 'Téléphone du cabinet',
    '{cabinet_email}':   'Email du cabinet',
    '{cabinet_orias}':   'N° ORIAS',
}

def remplacer_variables(texte, client=None, contrat=None):
    """Remplace les variables {xxx} par les vraies valeurs."""
    params = get_all_params()
    valeurs = {
        '{prenom}':         client['prenom'] or '' if client else '',
        '{nom}':            client['nom'] or '' if client else '',
        '{email}':          client['email'] or '' if client else '',
        '{telephone}':      client['telephone'] or '' if client else '',
        '{num_contrat}':    contrat['numero'] or '' if contrat else '',
        '{type_assurance}': contrat['type_assurance'] or '' if contrat else '',
        '{compagnie}':      contrat['compagnie'] or '' if contrat else '',
        '{date_echeance}':  contrat['date_fin'] or '' if contrat else '',
        '{prime_annuelle}': str(contrat['prime_annuelle']) + ' €' if contrat else '',
        '{nom_bateau}':     '',
        '{cabinet_nom}':    params.get('cabinet_nom', 'Riviera Marine Assurances'),
        '{cabinet_telephone}': params.get('cabinet_telephone', ''),
        '{cabinet_email}':  params.get('cabinet_email', ''),
        '{cabinet_orias}':  params.get('cabinet_orias', ''),
    }
    for var, val in valeurs.items():
        texte = texte.replace(var, val)
    return texte

@app.route('/emails/<int:id>/utiliser')
def email_utiliser(id):
    conn = get_db()
    tmpl = conn.execute("SELECT * FROM email_templates WHERE id=?", (id,)).fetchone()
    clients = conn.execute("SELECT id, nom, prenom, email FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id, ct.numero, ct.type_assurance, ct.date_fin,
        ct.compagnie, c.nom, c.prenom, c.id as cid
        FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('emails/utiliser.html', template=tmpl,
                           clients=clients, contrats=contrats,
                           variables=EMAIL_VARIABLES)

@app.route('/emails/<int:id>/apercu', methods=['POST'])
def email_apercu(id):
    """AJAX : retourne sujet + corps avec variables remplacées."""
    conn = get_db()
    tmpl = conn.execute("SELECT * FROM email_templates WHERE id=?", (id,)).fetchone()
    client_id  = request.form.get('client_id')
    contrat_id = request.form.get('contrat_id')
    client  = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone() if client_id else None
    contrat = conn.execute("SELECT * FROM contrats WHERE id=?", (contrat_id,)).fetchone() if contrat_id else None
    conn.close()
    if not tmpl:
        return jsonify({'error': 'Template introuvable'}), 404
    sujet = remplacer_variables(tmpl['sujet'] or '', client, contrat)
    corps = remplacer_variables(tmpl['corps'] or '', client, contrat)
    email_dest = client['email'] if client and client['email'] else ''
    # Construire le lien mailto:
    mailto = 'mailto:' + urllib.parse.quote(email_dest)
    params_mailto = {'subject': sujet, 'body': corps}
    mailto += '?' + urllib.parse.urlencode(params_mailto)
    return jsonify({'sujet': sujet, 'corps': corps, 'mailto': mailto,
                    'email_dest': email_dest})

@app.route('/emails/<int:id>/envoyer', methods=['POST'])
def email_envoyer(id):
    """Envoie via Brevo (ou fallback mailto) + journal."""
    conn = get_db()
    client_id  = request.form.get('client_id')
    contrat_id = request.form.get('contrat_id')
    devis_id   = request.form.get('devis_id')
    sinistre_id = request.form.get('sinistre_id')
    sujet = request.form.get('sujet', '')
    corps = request.form.get('corps', '')
    email_dest = request.form.get('email_dest', '')
    nom_dest   = request.form.get('nom_dest', '')
    modele_nom = request.form.get('modele_nom', '')
    force_mailto = request.form.get('force_mailto') == '1'

    # Récupérer email si non fourni
    if not email_dest and client_id:
        cl = conn.execute("SELECT email, nom, prenom FROM clients WHERE id=?", (client_id,)).fetchone()
        if cl:
            email_dest = cl['email'] or ''
            nom_dest = f"{cl['prenom'] or ''} {cl['nom'] or ''}".strip()

    # NAVISUR v9.9 — Tentative d'envoi Brevo
    brevo = get_brevo()
    statut_comm = 'envoye'
    brevo_msg_id = ''
    erreur_detail = ''
    mailto_url = ''

    if force_mailto or not brevo.active or not email_dest:
        # Fallback mailto direct
        params_mailto = {'subject': sujet, 'body': corps}
        mailto_url = 'mailto:' + urllib.parse.quote(email_dest or '') + '?' + urllib.parse.urlencode(params_mailto)
        statut_comm = 'mailto'
    else:
        # Corps HTML : convertir les sauts de ligne en <br> si pas de balises HTML
        corps_html = corps if '<' in corps else corps.replace('\n', '<br>')
        result = brevo.envoyer_email(
            destinataire_email=email_dest,
            destinataire_nom=nom_dest,
            objet=sujet,
            corps_html=corps_html,
            corps_texte=corps,
        )
        if result['succes']:
            statut_comm = 'envoye'
            brevo_msg_id = result.get('message_id', '')
        else:
            statut_comm = 'mailto' if result.get('fallback_mailto') else 'erreur'
            erreur_detail = result.get('erreur', '')
            mailto_url = result.get('mailto_url', '')

    # Journal d'activité
    if client_id:
        conn.execute("""INSERT INTO journal_activites
            (client_id, contrat_id, date_activite, type_contact, sens,
             objet, contenu, auteur, brevo_message_id, email_statut)
            VALUES (?,?,?,'email','sortant',?,?,?,?,?)""",
            (client_id, contrat_id or None, datetime.now().isoformat(),
             sujet, corps,
             get_param('cabinet_nom', 'Riviera Marine Assurances'),
             brevo_msg_id, statut_comm))

        # Table communications
        conn.execute("""INSERT INTO communications
            (client_id, contrat_id, devis_id, sinistre_id,
             type, modele_utilise, destinataire_email, objet, corps_email,
             statut, brevo_message_id, erreur_detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (client_id, contrat_id or None, devis_id or None, sinistre_id or None,
             'email_brevo' if statut_comm == 'envoye' else 'email_mailto',
             modele_nom, email_dest, sujet, corps,
             statut_comm, brevo_msg_id, erreur_detail))
        conn.commit()

    conn.close()
    nlog('info', f'Email {statut_comm} → {email_dest[:20]}... sujet: {sujet[:40]}...')

    if statut_comm == 'envoye':
        flash(f'✅ Email envoyé à {email_dest} via Brevo.', 'success')
        return jsonify({'succes': True, 'statut': 'envoye', 'message': f'Email envoyé à {email_dest}'})
    else:
        flash(f'📧 Email préparé pour {email_dest} — Ouverture de votre messagerie…', 'info')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'succes': False, 'statut': statut_comm,
                           'mailto_url': mailto_url, 'fallback': True})
        return render_template('emails/envoi_mailto.html',
                               mailto=mailto_url, email_dest=email_dest,
                               sujet=sujet, client_id=client_id)


# NAVISUR v9.9 — Route envoi rapide Brevo (AJAX depuis modale)
@app.route('/brevo/envoyer', methods=['POST'])
def brevo_envoyer():
    """Envoi direct depuis la modale Brevo."""
    data = request.get_json() or request.form
    client_id   = data.get('client_id')
    contrat_id  = data.get('contrat_id')
    devis_id    = data.get('devis_id')
    sinistre_id = data.get('sinistre_id')
    email_dest  = data.get('email_dest', '')
    nom_dest    = data.get('nom_dest', '')
    sujet       = data.get('sujet', '')
    corps       = data.get('corps', '')
    modele_nom  = data.get('modele_nom', '')

    brevo = get_brevo()
    if not email_dest:
        return jsonify({'succes': False, 'erreur': 'Email destinataire manquant'})

    corps_html = corps if '<' in corps else corps.replace('\n', '<br>')
    result = brevo.envoyer_email(
        destinataire_email=email_dest,
        destinataire_nom=nom_dest,
        objet=sujet,
        corps_html=corps_html,
        corps_texte=corps,
    )

    # Enregistrer dans communications
    conn = get_db()
    statut = 'envoye' if result['succes'] else ('mailto' if result.get('fallback_mailto') else 'erreur')
    try:
        conn.execute("""INSERT INTO communications
            (client_id, contrat_id, devis_id, sinistre_id,
             type, modele_utilise, destinataire_email, objet, corps_email,
             statut, brevo_message_id, erreur_detail)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (client_id or None, contrat_id or None, devis_id or None, sinistre_id or None,
             'email_brevo' if result['succes'] else 'email_mailto',
             modele_nom, email_dest, sujet, corps,
             statut, result.get('message_id', ''), result.get('erreur', '')))
        if client_id:
            conn.execute("""INSERT INTO journal_activites
                (client_id, contrat_id, date_activite, type_contact, sens,
                 objet, contenu, auteur, brevo_message_id, email_statut)
                VALUES (?,?,?,'email','sortant',?,?,?,?,?)""",
                (client_id, contrat_id or None, datetime.now().isoformat(),
                 sujet, corps,
                 get_param('cabinet_nom', 'Riviera Marine Assurances'),
                 result.get('message_id', ''), statut))
        conn.commit()
    except Exception as e:
        nlog('warning', f'Enregistrement communication échoué : {e}')
    conn.close()
    return jsonify(result)


# NAVISUR v9.9 — Quota Brevo (pour la modale)
@app.route('/brevo/quota')
def brevo_quota():
    return jsonify(get_brevo().get_quota())


# NAVISUR v9.9 — Vérifier statuts emails d'un client
@app.route('/brevo/verifier-statuts/<int:client_id>', methods=['POST'])
def brevo_verifier_statuts(client_id):
    conn = get_db()
    cl = conn.execute("SELECT email FROM clients WHERE id=?", (client_id,)).fetchone()
    if not cl or not cl['email']:
        conn.close()
        return jsonify({'ok': False, 'message': 'Client ou email introuvable'})
    events = get_brevo().verifier_statuts(cl['email'])
    nb_maj = 0
    for ev in events:
        msg_id = ev.get('messageId', '')
        event_type = ev.get('event', '')
        ts = ev.get('date', '')
        if not msg_id:
            continue
        if event_type == 'opened' and ts:
            conn.execute(
                "UPDATE communications SET statut='ouvert', date_ouverture=? WHERE brevo_message_id=?",
                (ts, msg_id))
            nb_maj += 1
        elif event_type == 'clicked' and ts:
            conn.execute(
                "UPDATE communications SET statut='clique', date_clic=? WHERE brevo_message_id=?",
                (ts, msg_id))
            nb_maj += 1
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'message': f'{nb_maj} statut(s) mis à jour', 'nb': nb_maj})


# NAVISUR v9.9 — Aperçu email avec variables remplacées (Brevo)
@app.route('/emails/<int:id>/apercu-brevo', methods=['POST'])
def email_apercu_brevo(id):
    conn = get_db()
    tmpl = conn.execute("SELECT * FROM email_templates WHERE id=?", (id,)).fetchone()
    client_id  = request.form.get('client_id')
    contrat_id = request.form.get('contrat_id')
    client  = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone() if client_id else None
    contrat = conn.execute("SELECT * FROM contrats WHERE id=?", (contrat_id,)).fetchone() if contrat_id else None
    bateau = None
    if contrat and contrat['bateau_id']:
        bateau = conn.execute("SELECT * FROM bateaux WHERE id=?", (contrat['bateau_id'],)).fetchone()
    conn.close()
    if not tmpl:
        return jsonify({'error': 'Template introuvable'}), 404
    brevo = get_brevo()
    donnees = {'client': dict(client) if client else {},
               'contrat': dict(contrat) if contrat else {},
               'bateau': dict(bateau) if bateau else {}}
    sujet = brevo.remplacer_variables(tmpl['sujet'] or '', donnees)
    corps = brevo.remplacer_variables(tmpl['corps'] or '', donnees)
    email_dest = client['email'] if client and client['email'] else ''
    nom_dest = f"{client.get('prenom','') or ''} {client.get('nom','') or ''}".strip() if client else ''
    return jsonify({'sujet': sujet, 'corps': corps,
                    'email_dest': email_dest, 'nom_dest': nom_dest,
                    'brevo_actif': brevo.active})


# NAVISUR v9.9 — Historique communications d'un client
@app.route('/clients/<int:client_id>/communications')
def client_communications(client_id):
    conn = get_db()
    cl = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not cl:
        conn.close(); abort(404)
    comms = conn.execute("""
        SELECT cm.*, ct.numero as contrat_num
        FROM communications cm
        LEFT JOIN contrats ct ON cm.contrat_id=ct.id
        WHERE cm.client_id=?
        ORDER BY cm.date_envoi DESC LIMIT 100
    """, (client_id,)).fetchall()
    conn.close()
    return render_template('communications/historique.html',
                           client=cl, communications=comms)


# NAVISUR v9.9 — Paramètres courtier
