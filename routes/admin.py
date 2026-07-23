# routes/admin.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import (
    _urllib, _urlparse, _json_api, _threading, _load_api_keys, _save_api_keys,
    _api_active, _api_key, _safe_get, API_KEYS_FILE, PAYS_CACHE_FILE, API_TIMEOUT,
    app, get_db, nlog, log_audit, get_path, get_resource,
    BACKUP_DIR, CONFIG_DIR, DATABASE, BASE_DIR, RESOURCE_DIR, UPLOAD_FOLDER,
    request, jsonify, render_template, redirect, url_for, flash, abort,
    date, datetime, timedelta, os, get_all_params, get_param,
    load_pays_cache, format_telephone_fr, safe_int, safe_float,
)

@app.route('/admin/parametres-fiscaux', methods=['GET', 'POST'])
def admin_parametres_fiscaux():
    conn = get_db()
    annee_courante = date.today().year
    if request.method == 'POST':
        annee = safe_int(request.form.get('annee', annee_courante), annee_courante, 'Année')
        try:
            plafond = safe_float(request.form.get('plafond_micro_bnc', 77700), 0, 'Plafond micro-BNC')
            taux    = safe_float(request.form.get('taux_urssaf', 22), 0, 'Taux URSSAF')
        except ValueError as e:
            flash(f'❌ {e}', 'error')
            conn.close(); return redirect(request.url)
        conn.execute("""INSERT OR REPLACE INTO parametres_fiscaux
            (annee, plafond_micro_bnc, taux_urssaf, note, date_maj)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)""",
            (annee, plafond, taux, request.form.get('note', '')))
        conn.commit()
        nlog('info', f'Paramètres fiscaux {annee} mis à jour : plafond={plafond} taux={taux}')
        flash(f'✅ Paramètres fiscaux {annee} enregistrés.', 'success')
        conn.close()
        return redirect(url_for('admin_parametres_fiscaux'))
    annees_dispo = list(range(annee_courante - 2, annee_courante + 3))
    params_list = {r['annee']: dict(r) for r in conn.execute(
        "SELECT * FROM parametres_fiscaux ORDER BY annee DESC").fetchall()}
    conn.close()
    return render_template('admin/parametres_fiscaux.html',
        annees_dispo=annees_dispo, params_list=params_list,
        annee_courante=annee_courante)

# ── Route fichiers formations DDA ──────────────────────────────
@app.route('/documents/voir-formation/<int:formation_id>')
def documents_voir_formation(formation_id):
    conn = get_db()
    f = conn.execute("SELECT * FROM formations_dda WHERE id=?", (formation_id,)).fetchone()
    conn.close()
    if not f or not f['attestation_fichier']:
        abort(404)
    fpath = os.path.join(UPLOAD_FOLDER, f['attestation_fichier'])
    if not os.path.exists(fpath):
        flash("Fichier introuvable sur le disque.", 'error')
        return redirect(url_for('formations_list'))
    nlog('info', f'Téléchargement attestation formation #{formation_id}')
    ext = f['attestation_fichier'].rsplit('.', 1)[-1].lower()
    as_attachment = ext not in ('pdf', 'png', 'jpg', 'jpeg')
    return send_from_directory(UPLOAD_FOLDER, f['attestation_fichier'],
                               as_attachment=as_attachment,
                               download_name=f"attestation_formation_{formation_id}.{ext}")

# ── Route générique voir fichier (pour aperçu inline) ─────────
@app.route('/documents/voir-direct/<nom>')
def documents_voir_direct(nom):
    """Sert un fichier upload par nom de stockage (pour aperçu PDF/image)."""
    fpath = os.path.join(UPLOAD_FOLDER, secure_filename(nom))
    if not os.path.exists(fpath):
        abort(404)
    nlog('info', f'Accès direct fichier : {nom}')
    ext = nom.rsplit('.', 1)[-1].lower() if '.' in nom else ''
    as_attachment = ext not in ('pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp')
    return send_from_directory(UPLOAD_FOLDER, secure_filename(nom), as_attachment=as_attachment)



# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.4 — SUIVI FINANCIER : PRIMES + QUITTANCES
# ═══════════════════════════════════════════════════════════════

def _calc_echeances(date_premiere, frequence, nb, montant_unitaire):
    """Génère la liste des dates d'échéances selon la fréquence."""
    import calendar, datetime
    d = datetime.date.fromisoformat(date_premiere)
    echeances = []
    mois_saut = {'annuel':12,'semestriel':6,'trimestriel':3,'mensuel':1}
    saut = mois_saut.get(frequence, 12)
    for i in range(nb):
        total_mois = d.month - 1 + i * saut
        y = d.year + total_mois // 12
        m = total_mois % 12 + 1
        jour = min(d.day, calendar.monthrange(y, m)[1])
        echeances.append(datetime.date(y, m, jour).isoformat())
    return echeances

# ── PRIMES HISTORIQUE ─────────────────────────────────────────

@app.route('/contrats/<int:id>/primes-historique', methods=['POST'])
def prime_historique_save(id):
    """Ajoute ou modifie une prime annuelle dans l'historique."""
    conn = get_db()
    contrat = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    if not contrat: conn.close(); abort(404)
    annee = safe_int(request.form.get('annee', date.today().year), date.today().year, 'Année')
    try:
        prime_ttc = safe_float(request.form.get('prime_ttc'), 0, 'Prime TTC')
        prime_ht  = safe_float(request.form.get('prime_ht') or 0, 0, 'Prime HT')
        frais     = safe_float(request.form.get('frais_compagnie') or 0, 0, 'Frais compagnie')
        taxes     = safe_float(request.form.get('taxes') or 0, 0, 'Taxes')
    except ValueError as e:
        flash(f'❌ {e}', 'error'); conn.close()
        return redirect(url_for('contrat_detail', id=id) + '#tab-financier')
    # Calcul variation vs année précédente
    prev = conn.execute(
        "SELECT prime_ttc FROM primes_historique WHERE contrat_id=? AND annee=?",
        (id, annee - 1)).fetchone()
    variation = None
    if prev and prev['prime_ttc']:
        variation = round((prime_ttc - float(prev['prime_ttc'])) / float(prev['prime_ttc']) * 100, 2)
    conn.execute("""INSERT OR REPLACE INTO primes_historique
        (contrat_id, annee, prime_ht, frais_compagnie, taxes, prime_ttc, variation_pct, note)
        VALUES (?,?,?,?,?,?,?,?)""",
        (id, annee, prime_ht, frais, taxes, prime_ttc, variation,
         request.form.get('note', '')))
    # Mettre à jour prime_annuelle sur le contrat si année courante
    if annee == date.today().year:
        conn.execute("UPDATE contrats SET prime_annuelle=? WHERE id=?", (prime_ttc, id))
    conn.commit(); conn.close()
    nlog('info', f'Prime historique contrat #{id} — {annee} : {prime_ttc}€')
    flash(f'✅ Prime {annee} enregistrée : {prime_ttc:.2f} €', 'success')
    return redirect(url_for('contrat_detail', id=id) + '#tab-financier')

@app.route('/contrats/<int:id>/primes-historique/<int:ph_id>/supprimer', methods=['POST'])
def prime_historique_supprimer(id, ph_id):
    conn = get_db()
    conn.execute("DELETE FROM primes_historique WHERE id=? AND contrat_id=?", (ph_id, id))
    conn.commit(); conn.close()
    flash('Prime supprimée.', 'info')
    return redirect(url_for('contrat_detail', id=id) + '#tab-financier')

# ── QUITTANCES : CRÉATION EN BATCH ───────────────────────────

@app.route('/contrats/<int:id>/quittances-suivi/creer', methods=['POST'])
def quittances_creer(id):
    """Génère toutes les quittances d'une année selon fréquence + mode."""
    conn = get_db()
    contrat = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    if not contrat: conn.close(); abort(404)
    try:
        annee        = safe_int(request.form.get('annee', date.today().year), date.today().year, 'Année')
        prime_ttc    = safe_float(request.form.get('prime_ttc', contrat['prime_annuelle']), 0, 'Prime TTC')
        taux_comm    = safe_float(request.form.get('taux_commission', contrat['taux_commission'] or 15), 0, 'Taux commission')
    except ValueError as e:
        flash(f'❌ {e}', 'error'); conn.close()
        return redirect(url_for('contrat_detail', id=id) + '#tab-financier')
    frequence    = request.form.get('frequence', 'annuel')
    mode_paiement = request.form.get('mode_paiement', 'prelevement')
    date_premiere = request.form.get('date_premiere_echeance', '')
    if not date_premiere:
        flash('❌ Date de première échéance obligatoire.', 'error')
        conn.close()
        return redirect(url_for('contrat_detail', id=id) + '#tab-financier')
    nb_map = {'annuel':1,'semestriel':2,'trimestriel':4,'mensuel':12}
    nb = nb_map.get(frequence, 1)
    montant_unit = round(prime_ttc / nb, 2)
    echeances = _calc_echeances(date_premiere, frequence, nb, montant_unit)
    # Supprimer les quittances existantes de cette année
    conn.execute("DELETE FROM quittances_suivi WHERE contrat_id=? AND annee=?", (id, annee))
    # Créer les nouvelles quittances
    for i, ech in enumerate(echeances):
        comm_att = round(montant_unit * taux_comm / 100, 2)
        statut_p = 'prelevement_auto' if mode_paiement == 'prelevement' else 'en_attente'
        conn.execute("""INSERT INTO quittances_suivi
            (contrat_id, annee, frequence, mode_paiement, numero_quittance, total_quittances,
             montant_ttc, date_echeance, statut_paiement, taux_commission, commission_attendue)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (id, annee, frequence, mode_paiement, i+1, nb,
             montant_unit, ech, statut_p, taux_comm, comm_att))
    conn.commit()
    # Si prélèvement : créer aussi le calendrier des prélèvements
    if mode_paiement == 'prelevement':
        quitt_id = conn.execute(
            "SELECT id FROM quittances_suivi WHERE contrat_id=? AND annee=? LIMIT 1", (id, annee)).fetchone()[0]
        for i, ech in enumerate(echeances):
            conn.execute("""INSERT INTO calendrier_prelevements
                (quittance_id, numero_echeance, date_prelevement, montant, statut)
                VALUES (?,?,?,?,'prevu')""", (quitt_id, i+1, ech, montant_unit))
        conn.commit()
    # Mettre à jour taux_commission sur le contrat
    conn.execute("UPDATE contrats SET taux_commission=? WHERE id=?", (taux_comm, id))
    conn.commit(); conn.close()
    nlog('info', f'Quittances {annee} créées contrat #{id} — {nb} × {montant_unit}€ ({frequence}/{mode_paiement})')
    flash(f'✅ {nb} quittance(s) {annee} créées ({frequence}, {mode_paiement}).', 'success')
    return redirect(url_for('contrat_detail', id=id) + '#tab-financier')

# ── ACTIONS QUITTANCE INDIVIDUELLE ───────────────────────────

@app.route('/quittances-suivi/<int:qid>/action', methods=['POST'])
def quittance_action(qid):
    conn = get_db()
    q = conn.execute("SELECT * FROM quittances_suivi WHERE id=?", (qid,)).fetchone()
    if not q: conn.close(); abort(404)
    action = request.form.get('action', '')
    today_s = date.today().isoformat()
    if action == 'marquer_envoyee':
        conn.execute("""UPDATE quittances_suivi SET envoyee_client=1,
            date_envoi_client=?, canal_envoi=? WHERE id=?""",
            (today_s, request.form.get('canal_envoi', 'email'), qid))
        flash('✅ Quittance marquée comme envoyée.', 'success')
    elif action == 'marquer_payee':
        try: mt_paye = safe_float(request.form.get('montant_paye', q['montant_ttc']), 0, 'Montant payé')
        except ValueError as e: flash(f'❌ {e}', 'error'); conn.close(); return redirect(request.referrer or '/')
        conn.execute("""UPDATE quittances_suivi SET statut_paiement='payee',
            date_paiement=? WHERE id=?""",
            (request.form.get('date_paiement', today_s), qid))
        flash('✅ Quittance marquée comme payée.', 'success')
        nlog('info', f'Quittance #{qid} payée — contrat #{q["contrat_id"]}')
    elif action == 'signaler_impayee':
        conn.execute("UPDATE quittances_suivi SET statut_paiement='impayee' WHERE id=?", (qid,))
        flash('⚠️ Quittance signalée impayée.', 'warning')
        nlog('warning', f'Quittance #{qid} impayée — contrat #{q["contrat_id"]}')
    elif action == 'relance':
        conn.execute("""UPDATE quittances_suivi SET relance_envoyee=1,
            date_relance=?, note_relance=? WHERE id=?""",
            (today_s, request.form.get('note_relance', ''), qid))
        flash('📧 Relance enregistrée.', 'success')
    elif action == 'commission_recue':
        try: mt_recu = safe_float(request.form.get('commission_recue', 0), 0, 'Commission reçue')
        except ValueError as e: flash(f'❌ {e}', 'error'); conn.close(); return redirect(request.referrer or '/')
        ecart = round(mt_recu - float(q['commission_attendue'] or 0), 2)
        conn.execute("""UPDATE quittances_suivi SET commission_recue=?,
            date_reception_commission=?, bordereau_reference=?, ecart_commission=? WHERE id=?""",
            (mt_recu, request.form.get('date_reception', today_s),
             request.form.get('bordereau_reference', ''), ecart, qid))
        if abs(ecart) > 0.01:
            flash(f'⚠️ Commission enregistrée — écart de {ecart:+.2f} € à vérifier.', 'warning')
            nlog('warning', f'Commission quittance #{qid} : écart {ecart}€')
        else:
            flash('✅ Commission enregistrée.', 'success')
    elif action == 'prelev_statut':
        pl_id = request.form.get('prelev_id')
        statut_pl = request.form.get('statut_prelev', 'effectue')
        conn.execute("UPDATE calendrier_prelevements SET statut=?, date_confirmation=? WHERE id=?",
                     (statut_pl, today_s, pl_id))
        flash(f'Prélèvement mis à jour : {statut_pl}.', 'success')
    conn.commit(); conn.close()
    return redirect(url_for('contrat_detail', id=q['contrat_id']) + '#tab-financier')

# ── PAGE GLOBALE QUITTANCES & COMMISSIONS ────────────────────

@app.route('/suivi-financier')
def suivi_financier_global():
    conn = get_db()
    today_s = date.today().isoformat()
    horizon_15j = (date.today() + __import__('datetime').timedelta(days=15)).isoformat()
    onglet = request.args.get('onglet', 'envoyer')
    annee_f  = request.args.get('annee', '')
    compagnie_f = request.args.get('compagnie', '')

    def _base_query(extra_where='', extra_params=None):
        q = """SELECT qs.*, ct.numero as ct_numero, ct.compagnie,
                      ct.type_assurance, c.nom, c.prenom, c.email
               FROM quittances_suivi qs
               JOIN contrats ct ON qs.contrat_id=ct.id
               JOIN clients c ON ct.client_id=c.id
               WHERE 1=1"""
        p = []
        if annee_f:  q += " AND qs.annee=?"; p.append(int(annee_f))
        if compagnie_f: q += " AND ct.compagnie LIKE ?"; p.append(f'%{compagnie_f}%')
        if extra_where: q += extra_where
        if extra_params: p.extend(extra_params)
        return q, p

    if onglet == 'envoyer':
        q, p = _base_query(
            " AND qs.envoyee_client=0 AND qs.mode_paiement != 'prelevement' AND qs.date_echeance <= ?",
            [horizon_15j])
        q += " ORDER BY qs.date_echeance"
        rows = conn.execute(q, p).fetchall()
    elif onglet == 'attente':
        q, p = _base_query(
            " AND qs.envoyee_client=1 AND qs.statut_paiement='en_attente' AND qs.mode_paiement != 'prelevement'")
        q += " ORDER BY qs.date_echeance"
        rows = conn.execute(q, p).fetchall()
    elif onglet == 'impayes':
        q, p = _base_query(" AND qs.statut_paiement='impayee'")
        q += " ORDER BY qs.date_echeance"
        rows = conn.execute(q, p).fetchall()
    elif onglet == 'a_reverser':
        q, p = _base_query(
            " AND qs.statut_paiement='payee' AND (qs.net_a_reverser IS NULL OR qs.net_a_reverser=0)")
        q += " ORDER BY qs.date_echeance"
        rows = conn.execute(q, p).fetchall()
    else:
        q, p = _base_query()
        q += " ORDER BY qs.annee DESC, qs.date_echeance"
        rows = conn.execute(q, p).fetchall()

    # Compteurs pour les badges
    nb_envoyer  = conn.execute(
        "SELECT COUNT(*) FROM quittances_suivi WHERE envoyee_client=0 AND mode_paiement!='prelevement' AND date_echeance<=?",
        (horizon_15j,)).fetchone()[0]
    nb_impayes  = conn.execute(
        "SELECT COUNT(*) FROM quittances_suivi WHERE statut_paiement='impayee'").fetchone()[0]
    nb_a_reverser = conn.execute(
        "SELECT COUNT(*) FROM quittances_suivi WHERE statut_paiement='payee' AND (net_a_reverser IS NULL OR net_a_reverser=0)").fetchone()[0]
    mt_frais = float(conn.execute(
        "SELECT COALESCE(SUM(frais_courtage),0) FROM quittances_suivi WHERE statut_paiement='payee'").fetchone()[0])
    mt_reverser = float(conn.execute(
        "SELECT COALESCE(SUM(montant_ttc - frais_courtage),0) FROM quittances_suivi WHERE statut_paiement='payee'").fetchone()[0])
    nb_prelev_mois = conn.execute(
        """SELECT COUNT(*) FROM calendrier_prelevements cp
           JOIN quittances_suivi qs ON cp.quittance_id=qs.id
           WHERE cp.statut='prevu' AND substr(cp.date_prelevement,1,7)=?""",
        (date.today().strftime('%Y-%m'),)).fetchone()[0]
    annees_dispo = [r[0] for r in conn.execute(
        "SELECT DISTINCT annee FROM quittances_suivi ORDER BY annee DESC").fetchall()]
    compagnies_dispo = [r[0] for r in conn.execute(
        "SELECT DISTINCT compagnie FROM contrats WHERE compagnie IS NOT NULL AND compagnie!='' ORDER BY compagnie").fetchall()]
    conn.close()
    return render_template('suivi_financier/index.html',
        rows=rows, onglet=onglet,
        nb_envoyer=nb_envoyer, nb_impayes=nb_impayes,
        nb_a_reverser=nb_a_reverser, mt_frais=mt_frais, mt_reverser=mt_reverser,
        nb_prelev_mois=nb_prelev_mois,
        annee_f=annee_f, compagnie_f=compagnie_f,
        annees_dispo=annees_dispo, compagnies_dispo=compagnies_dispo,
        today=today_s)

@app.route('/suivi-financier/export-excel')
def suivi_financier_export():
    """Export Excel des quittances selon l'onglet actif."""
    import io
    conn = get_db()
    onglet = request.args.get('onglet', 'tout')
    annee_f = request.args.get('annee', '')
    rows = conn.execute("""SELECT qs.*, ct.numero as ct_numero, ct.compagnie,
        ct.type_assurance, c.nom, c.prenom
        FROM quittances_suivi qs
        JOIN contrats ct ON qs.contrat_id=ct.id
        JOIN clients c ON ct.client_id=c.id
        ORDER BY qs.annee DESC, qs.date_echeance""").fetchall()
    conn.close()
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Suivi financier"
        headers = ['Contrat','Compagnie','Client','Année','N°','Fréquence','Mode',
                   'Montant TTC','Échéance','Envoyée','Date envoi','Statut paiement',
                   'Date paiement','Comm. attendue','Comm. reçue','Écart','Bordereau']
        ws.append(headers)
        for r in rows:
            ws.append([r['ct_numero'], r['compagnie'], f"{r['nom']} {r['prenom'] or ''}",
                       r['annee'], f"{r['numero_quittance']}/{r['total_quittances']}",
                       r['frequence'], r['mode_paiement'], r['montant_ttc'],
                       r['date_echeance'], 'Oui' if r['envoyee_client'] else 'Non',
                       r['date_envoi_client'] or '', r['statut_paiement'],
                       r['date_paiement'] or '',
                       r['commission_attendue'] or 0, r['commission_recue'] or 0,
                       r['ecart_commission'] or 0, r['bordereau_reference'] or ''])
        buf = io.BytesIO()
        wb.save(buf); buf.seek(0)
        from flask import send_file
        return send_file(buf, as_attachment=True,
                         download_name=f'suivi_financier_{date.today()}.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except ImportError:
        flash('Export Excel indisponible (openpyxl requis).', 'error')
        return redirect(url_for('suivi_financier_global'))



# ─── QUITTANCE INDIVIDUELLE : MODIF + IMPRESSION ─────────────

def _prochain_numero_facture(conn):
    annee = date.today().year
    row = conn.execute("SELECT dernier_numero FROM numerotation_factures WHERE annee=?", (annee,)).fetchone()
    num = (row['dernier_numero'] if row else 0) + 1
    conn.execute("INSERT OR REPLACE INTO numerotation_factures (annee, dernier_numero) VALUES (?,?)", (annee, num))
    return f"FAC-{annee}-{num:04d}"

@app.route('/quittances-suivi/<int:qid>/modifier', methods=['GET','POST'])
def quittance_modifier(qid):
    conn = get_db()
    q = conn.execute("""SELECT qs.*, ct.numero as ct_numero, ct.compagnie,
        c.nom, c.prenom, ct.type_assurance, ct.prime_annuelle
        FROM quittances_suivi qs
        JOIN contrats ct ON qs.contrat_id=ct.id
        JOIN clients c ON ct.client_id=c.id
        WHERE qs.id=?""", (qid,)).fetchone()
    if not q: conn.close(); abort(404)
    if request.method == 'POST':
        try:
            prime_ht = safe_float(request.form.get('prime_ht'), 0, 'Prime HT')
            taux_taxe = safe_float(request.form.get('taux_taxe'), 0, 'Taux taxe')
            frais = safe_float(request.form.get('frais_courtage'), 0, 'Frais courtage')
            prime_ttc = safe_float(request.form.get('prime_ttc'), q['montant_ttc'] or 0, 'Prime TTC')
            taux_tva = safe_float(request.form.get('taux_tva'), 0, 'Taux TVA')
        except ValueError as e:
            flash(f'❌ {e}', 'error'); conn.close(); return redirect(request.url)
        taxe = round(prime_ht * taux_taxe / 100, 2) if taux_taxe else 0
        net = round(prime_ttc - frais, 2)
        rib = request.form.get('rib_courtier', get_param('cabinet_iban',''))
        num_facture = request.form.get('numero_facture','').strip()
        date_facture = request.form.get('date_facture','').strip()
        if not num_facture:
            num_facture = q['numero_facture'] or _prochain_numero_facture(conn)
        if not date_facture:
            date_facture = date.today().isoformat()
        tva_collectee = round(prime_ht * taux_tva / 100, 2) if taux_tva else 0
        conn.execute("""UPDATE quittances_suivi SET
            prime_ht=?, taux_taxe=?, montant_taxe=?, frais_courtage=?,
            net_a_reverser=?, montant_ttc=?, rib_courtier=?,
            numero_facture=?, date_facture=?, taux_tva=?, tva_collectee=?
            WHERE id=?""",
            (prime_ht, taux_taxe, taxe, frais, net, prime_ttc, rib,
             num_facture, date_facture, taux_tva, tva_collectee, qid))
        conn.commit(); conn.close()
        flash('Facture mise à jour.', 'success')
        return redirect(url_for('contrat_detail', id=q['contrat_id']) + '#tab-financier')
    conn.close()
    return render_template('quittances/modifier.html', q=q,
                           rib_defaut=get_param('cabinet_iban',''),
                           today=date.today().isoformat())

@app.route('/quittances-suivi/<int:qid>/imprimer')
def quittance_imprimer(qid):
    conn = get_db()
    q = conn.execute("""SELECT qs.*, ct.numero as police, ct.type_assurance,
        ct.compagnie, c.nom, c.prenom, c.adresse, c.code_postal, c.ville,
        c.email, c.telephone, ct.date_debut, ct.date_fin
        FROM quittances_suivi qs
        JOIN contrats ct ON qs.contrat_id=ct.id
        JOIN clients c ON ct.client_id=c.id
        WHERE qs.id=?""", (qid,)).fetchone()
    conn.close()
    if not q: abort(404)
    params = get_all_params()
    return render_template('quittances/print.html', q=q, params=params, now=datetime.now())


# ─── BORDEREAUX ASSUREURS ────────────────────────────────────

@app.route('/bordereaux')
def bordereaux_list():
    conn = get_db()
    statut = request.args.get('statut','')
    q = "SELECT * FROM bordereaux_assureurs WHERE 1=1"
    p = []
    if statut: q += " AND statut=?"; p.append(statut)
    q += " ORDER BY date_bordereau DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return render_template('bordereaux/index.html', rows=rows, statut=statut)

@app.route('/bordereaux/nouveau', methods=['GET','POST'])
def bordereau_nouveau():
    conn = get_db()
    compagnie = request.args.get('compagnie','')
    if request.method == 'POST':
        comp = request.form.get('compagnie','').strip()
        quittance_ids = request.form.getlist('quittance_ids')
        if not comp or not quittance_ids:
            flash('Sélectionnez une compagnie et au moins une quittance.', 'warning')
        else:
            total_ttc = 0; total_frais = 0
            lignes = []
            for qid in quittance_ids:
                q = conn.execute("""SELECT qs.*, ct.numero as police, ct.type_assurance,
                    c.nom, c.prenom FROM quittances_suivi qs
                    JOIN contrats ct ON qs.contrat_id=ct.id
                    JOIN clients c ON ct.client_id=c.id
                    WHERE qs.id=? AND qs.statut_paiement='payee'""", (qid,)).fetchone()
                if q:
                    total_ttc += float(q['montant_ttc'] or 0)
                    total_frais += float(q['frais_courtage'] or 0)
                    lignes.append(dict(q))
            virement = round(total_ttc - total_frais, 2)
            ref = request.form.get('reference_virement','')
            rib = request.form.get('rib_courtier', get_param('cabinet_iban',''))
            cur = conn.execute("""INSERT INTO bordereaux_assureurs
                (compagnie, montant_total_ttc, total_frais_courtage, montant_virement,
                 rib_courtier, reference_virement, statut, notes)
                VALUES (?,?,?,?,?,?,?,?)""",
                (comp, total_ttc, total_frais, virement, rib, ref, 'brouillon',
                 request.form.get('notes','')))
            bord_id = cur.lastrowid
            for lg in lignes:
                conn.execute("""INSERT INTO bordereaux_lignes
                    (bordereau_id, contrat_id, client_nom, police_numero,
                     prime_ttc, frais_courtage, net_a_reverser)
                    VALUES (?,?,?,?,?,?,?)""",
                    (bord_id, lg['contrat_id'],
                     f"{lg['prenom'] or ''} {lg['nom']}".strip(),
                     lg['police'], lg['montant_ttc'],
                     lg['frais_courtage'] or 0,
                     round(float(lg['montant_ttc'] or 0) - float(lg['frais_courtage'] or 0), 2)))
            conn.commit()
            nlog('info', f"Bordereau #{bord_id} créé — {comp} — {len(lignes)} lignes")
            flash(f'✅ Bordereau créé ({len(lignes)} lignes). Virement : {virement:.2f} €', 'success')
            return redirect(url_for('bordereau_imprimer', id=bord_id))
    # GET : liste des quittances payées par compagnie
    compagnies = [r[0] for r in conn.execute(
        "SELECT DISTINCT ct.compagnie FROM quittances_suivi qs JOIN contrats ct ON qs.contrat_id=ct.id WHERE qs.statut_paiement='payee' AND ct.compagnie IS NOT NULL AND ct.compagnie!='' ORDER BY ct.compagnie").fetchall()]
    quittances = []
    if compagnie:
        quittances = conn.execute("""SELECT qs.*, ct.numero as police, ct.compagnie, ct.type_assurance,
            c.nom, c.prenom FROM quittances_suivi qs
            JOIN contrats ct ON qs.contrat_id=ct.id
            JOIN clients c ON ct.client_id=c.id
            WHERE ct.compagnie=? AND qs.statut_paiement='payee'
            AND qs.id NOT IN (SELECT COALESCE(contrat_id,0) FROM bordereaux_lignes)
            ORDER BY qs.date_echeance""", (compagnie,)).fetchall()
    conn.close()
    return render_template('bordereaux/form.html', compagnies=compagnies,
                           compagnie=compagnie, quittances=quittances,
                           rib_defaut=get_param('cabinet_iban',''))

@app.route('/bordereaux/<int:id>/imprimer')
def bordereau_imprimer(id):
    conn = get_db()
    b = conn.execute("SELECT * FROM bordereaux_assureurs WHERE id=?", (id,)).fetchone()
    if not b: conn.close(); abort(404)
    lignes = conn.execute("""SELECT bl.*, ct.numero as police, c.nom, c.prenom
        FROM bordereaux_lignes bl
        LEFT JOIN contrats ct ON bl.contrat_id=ct.id
        LEFT JOIN clients c ON ct.client_id=c.id
        WHERE bl.bordereau_id=?""", (id,)).fetchall()
    conn.close()
    params = get_all_params()
    return render_template('bordereaux/print.html', b=b, lignes=lignes, params=params, now=datetime.now())

@app.route('/bordereaux/<int:id>/supprimer', methods=['POST'])
def bordereau_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM bordereaux_lignes WHERE bordereau_id=?", (id,))
    conn.execute("DELETE FROM bordereaux_assureurs WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Bordereau supprimé.', 'info')
    return redirect(url_for('bordereaux_list'))


# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.6 — MODULE API EXTERNES (offline-first)
# ═══════════════════════════════════════════════════════════════
import json as _json_api
import urllib.request as _urllib
import urllib.parse as _urlparse
import threading as _threading

# (défini dans core.py)
# (défini dans core.py)
# (défini dans core.py)



@app.route('/admin/nettoyer-doublons', methods=['GET', 'POST'])
def admin_nettoyer_doublons():
    """Détecte et supprime les contrats en doublon."""
    conn = get_db()
    if request.method == 'POST':
        ids_a_supprimer = request.form.getlist('supprimer_ids')
        supprimes = 0
        for sid in ids_a_supprimer:
            try:
                sid = int(sid)
                conn.execute("DELETE FROM relances WHERE contrat_id=?", (sid,))
                conn.execute("DELETE FROM quittances_suivi WHERE contrat_id=?", (sid,))
                conn.execute("DELETE FROM contrats WHERE id=?", (sid,))
                supprimes += 1
            except Exception as e:
                nlog('warning', f'Erreur suppression doublon #{sid} : {e}')
        conn.commit(); conn.close()
        flash(f'✅ {supprimes} doublon(s) supprimé(s).', 'success')
        return redirect(url_for('admin_nettoyer_doublons'))

    doublons = conn.execute("""
        SELECT c1.id, c1.numero, c1.compagnie, c1.type_assurance,
               c1.date_creation, c1.prime_annuelle, cl.nom, cl.prenom, c1.client_id
        FROM contrats c1
        JOIN clients cl ON c1.client_id=cl.id
        WHERE EXISTS (
            SELECT 1 FROM contrats c2
            WHERE c2.client_id=c1.client_id
            AND c2.compagnie=c1.compagnie
            AND c2.type_assurance=c1.type_assurance
            AND c2.date_creation=c1.date_creation
            AND c2.id != c1.id
        )
        ORDER BY c1.client_id, c1.compagnie, c1.date_creation, c1.id
    """).fetchall()
    conn.close()
    return render_template('admin/nettoyer_doublons.html',
                           doublons=[dict(d) for d in doublons],
                           breadcrumbs=[{'label':'Accueil','url':'/'},
                                        {'label':'Administration','url':'/admin/sante'},
                                        {'label':'Nettoyer les doublons','url':None}])
