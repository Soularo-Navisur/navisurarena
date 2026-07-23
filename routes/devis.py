# routes/devis.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *
from flask_login import login_required

@app.route('/devis')
def devis_list():
    conn = get_db()
    statut = request.args.get('statut', '')
    q = """SELECT d.*, c.nom, c.prenom, c.email, c.telephone, c.statut as client_statut
           FROM devis d JOIN clients c ON d.client_id=c.id WHERE 1=1"""
    p = []
    if statut: q += " AND d.statut=?"; p.append(statut)
    q += " ORDER BY d.date_devis DESC"
    devis_list = conn.execute(q, p).fetchall()
    counts = {s[0]: conn.execute("SELECT COUNT(*) FROM devis WHERE statut=?", (s[0],)).fetchone()[0]
              for s in STATUTS_DEVIS}
    conn.close()
    return render_template('devis/index.html', devis_list=devis_list,
                           statut=statut, counts=counts, statuts=STATUTS_DEVIS,
                           today=date.today().isoformat())

@app.route('/devis/nouveau', methods=['GET','POST'])
def devis_nouveau():
    conn = get_db()
    if request.method == 'POST':
        # NAVISUR v9.3 — Validation
        errors = []
        try: validate_required(request.form.get('client_id'), 'Client')
        except ValueError as e: errors.append(str(e))
        try: validate_required(get_compagnie_from_form(), 'Compagnie')
        except ValueError as e: errors.append(str(e))
        try: prime = safe_float(request.form.get('prime_proposee'), 0, 'Prime proposée')
        except ValueError as e: errors.append(str(e)); prime = 0.0
        try: franchise = safe_float(request.form.get('franchise_proposee'), 0, 'Franchise')
        except ValueError as e: errors.append(str(e)); franchise = 0.0
        try: validite = safe_int(request.form.get('validite_jours') or 30, 30, 'Durée de validité')
        except ValueError as e: errors.append(str(e)); validite = 30
        if errors:
            for e in errors: flash(f'❌ {e}', 'error')
            conn.close(); return redirect(request.url)
        d_devis  = request.form.get('date_devis', date.today().isoformat())
        d_envoi  = request.form.get('date_envoi_client', '') or None
        try:
            from datetime import timedelta as _td
            base = date.fromisoformat(d_envoi or d_devis)
            d_exp = (base + _td(days=validite)).isoformat()
        except Exception:
            d_exp = None
        conn.close()
        try:
            with db_transaction() as c:
                c.execute("""INSERT INTO devis
                    (client_id, date_devis, compagnie, type_assurance, prime_proposee,
                     franchise_proposee, garanties, statut, notes, note_conseil,
                     date_envoi_client, moyen_envoi, validite_jours, date_expiration)
                    VALUES (?,?,?,?,?,?,?,'en_attente',?,?,?,?,?,?)""",
                    (request.form['client_id'], d_devis,
                     get_compagnie_from_form(),
                     request.form.get('type_assurance', ''),
                     prime, franchise,
                     request.form.get('garanties', ''),
                     request.form.get('notes', ''),
                     request.form.get('note_conseil', ''),
                     d_envoi, request.form.get('moyen_envoi', 'email'),
                     validite, d_exp))
                new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                log_audit('devis', new_id, 'INSERT', 'creation', None, get_compagnie_from_form())
            nlog('info', f'Devis #{new_id} créé — client #{request.form["client_id"]}')
        except Exception as e:
            nlog('error', f'Erreur création devis : {e}', exc=True)
            flash("❌ Erreur lors de l'enregistrement du devis.", 'error')
            return redirect(request.url)
        client_id = request.form['client_id']
        flash('Devis enregistré !', 'success')
        return redirect(url_for('client_detail', id=client_id) + '#devis')
    clients = conn.execute("SELECT id,nom,prenom,email,statut FROM clients ORDER BY nom").fetchall()
    client_id = request.args.get('client_id')
    risque_id = request.args.get('risque_id')
    # Load risques for selected client
    risques_client = []
    if client_id:
        risques_client = conn.execute(
            "SELECT id,type_risque,libelle FROM risques WHERE client_id=? ORDER BY libelle",
            (client_id,)).fetchall()
    conn.close()
    return render_template('devis/form.html', devis=None, clients=clients,
                           titre='Nouveau devis', preselect=client_id,
                           risques_client=risques_client, preselect_risque=risque_id,
                           today=date.today().isoformat(),
                           produits=PRODUITS_PLAISANCE)

@app.route('/devis/<int:id>/modifier', methods=['GET','POST'])
def devis_modifier(id):
    conn = get_db()
    d = conn.execute("SELECT * FROM devis WHERE id=?", (id,)).fetchone()
    if not d:
        conn.close(); flash('Devis introuvable.', 'error'); return redirect(url_for('devis_list'))
    if request.method == 'POST':
        d_devis  = request.form.get('date_devis', d['date_devis'])
        d_envoi  = request.form.get('date_envoi_client', '') or None
        validite = int(request.form.get('validite_jours') or 30)
        try:
            from datetime import timedelta as _td
            base = date.fromisoformat(d_envoi or d_devis)
            d_exp = (base + _td(days=validite)).isoformat()
        except Exception:
            d_exp = None
        # NAVISUR v9.3 — Validation devis modifier
        errors2 = []
        try: prime_m = safe_float(request.form.get('prime_proposee'), 0, 'Prime proposée')
        except ValueError as e: errors2.append(str(e)); prime_m = float(d['prime_proposee'] or 0)
        try: franchise_m = safe_float(request.form.get('franchise_proposee'), 0, 'Franchise')
        except ValueError as e: errors2.append(str(e)); franchise_m = 0.0
        if errors2:
            for e in errors2: flash(f'❌ {e}', 'error')
            clients2 = conn.execute("SELECT id,nom,prenom,email,statut FROM clients ORDER BY nom").fetchall()
            conn.close()
            return render_template('devis/form.html', devis=d, clients=clients2, titre='Modifier le devis',
                                   preselect=d['client_id'], risques_client=[], preselect_risque=None,
                                   today=date.today().isoformat(), produits=PRODUITS_PLAISANCE)
        new_statut = request.form.get('statut', 'en_attente')
        old_statut = d['statut']
        conn.execute("""UPDATE devis SET client_id=?,date_devis=?,compagnie=?,
            type_assurance=?,prime_proposee=?,franchise_proposee=?,
            garanties=?,statut=?,date_reponse=?,notes=?,note_conseil=?,
            raison_non_retenu=?,date_envoi_client=?,moyen_envoi=?,
            validite_jours=?,date_expiration=?,type_acceptation=? WHERE id=?""",
            (request.form['client_id'], d_devis,
             get_compagnie_from_form(),
             request.form.get('type_assurance', ''),
             prime_m, franchise_m,
             request.form.get('garanties', ''),
             new_statut,
             request.form.get('date_reponse', '') or None,
             request.form.get('notes', ''),
             request.form.get('note_conseil', ''),
             request.form.get('raison_non_retenu', ''),
             d_envoi, request.form.get('moyen_envoi', 'email'),
             validite, d_exp,
             request.form.get('type_acceptation', '') or None,
             id))
        conn.commit()
        # NAVISUR v9.3 — Audit changement statut devis
        if old_statut != new_statut:
            log_audit('devis', id, 'UPDATE', 'statut', old_statut, new_statut)
            nlog('info', f'Devis #{id} : statut {old_statut} → {new_statut}')
        client_id = request.form['client_id']
        conn.close()
        flash('Devis mis à jour !', 'success')
        return redirect(url_for('client_detail', id=client_id) + '#devis')
    clients = conn.execute("SELECT id,nom,prenom FROM clients ORDER BY nom").fetchall()
    conn.close()
    return render_template('devis/form.html', devis=d, clients=clients,
                           titre='Modifier le devis', preselect=str(d['client_id']),
                           today=date.today().isoformat(),
                           produits=PRODUITS_PLAISANCE, statuts=STATUTS_DEVIS)

@app.route('/devis/<int:id>/accepter', methods=['POST'])
def devis_accepter(id):
    """Accepte le devis → passe le client en 'client' et redirige vers création contrat."""
    conn = get_db()
    d = conn.execute("SELECT * FROM devis WHERE id=?", (id,)).fetchone()
    if not d:
        conn.close()
        flash('Devis introuvable.', 'error')
        return redirect(url_for('devis_list'))
    # Mettre à jour statut devis
    conn.execute("UPDATE devis SET statut='accepte', date_reponse=? WHERE id=?",
                 (date.today().isoformat(), id))
    # Passer le client en statut 'client'
    conn.execute("UPDATE clients SET statut='client' WHERE id=?", (d['client_id'],))
    conn.commit()
    conn.close()
    flash('✅ Devis accepté ! Créez maintenant le contrat.', 'success')
    # Rediriger vers création de contrat avec pré-remplissage complet
    from urllib.parse import urlencode as _ue
    _params = {
        'client_id':      d['client_id'],
        'compagnie':      d['compagnie'] or '',
        'type_assurance': d['type_assurance'] or '',
        'prime_annuelle': d['prime_proposee'] or 0,
        'franchise':      d['franchise_proposee'] or 0,
        'devis_id':       id,
        'garanties':      d['garanties'] or '',
        'notes':          d['note_conseil'] or '',
    }
    if 'risque_id' in d.keys() and d['risque_id']:
        _params['risque_id'] = d['risque_id']
    # Lier le DDA du client si présent
    from urllib.parse import urlencode as _ue2
    return redirect(url_for('contrat_nouveau') + '?' + _ue(_params))

@app.route('/devis/<int:id>/refuser', methods=['POST'])
def devis_refuser(id):
    conn = get_db()
    conn.execute("UPDATE devis SET statut='refuse', date_reponse=? WHERE id=?",
                 (date.today().isoformat(), id))
    d = conn.execute("SELECT client_id FROM devis WHERE id=?", (id,)).fetchone()
    conn.commit(); conn.close()
    flash('Devis marqué comme refusé.', 'info')
    return redirect(url_for('client_detail', id=d['client_id']) + '#devis' if d else url_for('devis_list'))

@app.route('/devis/<int:id>/supprimer', methods=['POST'])
def devis_supprimer(id):
    conn = get_db()
    d = conn.execute("SELECT client_id FROM devis WHERE id=?", (id,)).fetchone()
    conn.execute("DELETE FROM devis WHERE id=?", (id,))
    conn.commit(); conn.close()
    flash('Devis supprimé.', 'info')
    return redirect(url_for('client_detail', id=d['client_id']) + '#devis' if d else url_for('devis_list'))


# ═══════════════════════════════════════════════════════════════
#  V8.2 — Quittance depuis contrat · Import CSV · Filtres clients
# ═══════════════════════════════════════════════════════════════

import csv, io as _io

# ── Quittance rapide depuis fiche contrat ──────────────────────

@app.route('/contrats/<int:id>/quittance-rapide', methods=['GET','POST'])
def contrat_quittance_rapide(id):
    conn = get_db()
    ct = conn.execute("""SELECT ct.*,c.nom,c.prenom,c.email FROM contrats ct
        JOIN clients c ON ct.client_id=c.id WHERE ct.id=?""", (id,)).fetchone()
    if not ct:
        conn.close()
        flash('Contrat introuvable.', 'error')
        return redirect(url_for('contrats_list'))

    if request.method == 'POST':
        montant_ht = float(request.form.get('montant_ht') or ct['prime_annuelle'] or 0)
        annee_val  = date.today().year
        count = conn.execute("SELECT COUNT(*) FROM factures").fetchone()[0] + 1
        numero = f"QUI-{annee_val}-{count:04d}"
        conn.execute("""INSERT INTO factures
            (client_id, contrat_id, numero, objet, date_emission, date_echeance,
             montant_ht, tva, montant_ttc, statut, notes)
            VALUES (?,?,?,?,?,?,?,0,?,?,?)""",
            (ct['client_id'], id, numero,
             request.form.get('objet', f'Quittance {ct["type_assurance"] or ""} — {ct["numero"] or ""}').strip(),
             date.today().isoformat(),
             request.form.get('date_echeance', ''),
             montant_ht, montant_ht,
             request.form.get('statut', 'envoyee'),
             request.form.get('notes', '')))
        conn.commit()
        conn.close()
        flash(f'Quittance {numero} créée !', 'success')
        return redirect(url_for('client_detail', id=ct['client_id']) + '#contrats')

    conn.close()
    return render_template('contrats/quittance_rapide.html', contrat=ct,
                           today=date.today().isoformat())

# ── Import CSV clients ─────────────────────────────────────────

@app.route('/clients/import', methods=['GET','POST'])
def clients_import():
    if request.method == 'POST':
        f = request.files.get('fichier_csv')
        if not f:
            flash('Aucun fichier sélectionné.', 'error')
            return redirect(url_for('clients_import'))

        content = f.read().decode('utf-8-sig')  # gère le BOM Excel
        reader = csv.DictReader(_io.StringIO(content), delimiter=request.form.get('separateur', ','))

        conn = get_db()
        nb_ok = 0; nb_err = 0; errors = []

        for i, row in enumerate(reader, 1):
            try:
                # Mapping flexible des colonnes
                nom      = (row.get('nom') or row.get('Nom') or row.get('NOM') or '').strip()
                prenom   = (row.get('prenom') or row.get('Prénom') or row.get('PRENOM') or '').strip()
                email    = (row.get('email') or row.get('Email') or row.get('EMAIL') or '').strip()
                telephone= (row.get('telephone') or row.get('Téléphone') or row.get('Tel') or '').strip()
                ville    = (row.get('ville') or row.get('Ville') or '').strip()
                cp       = (row.get('code_postal') or row.get('CP') or '').strip()
                adresse  = (row.get('adresse') or row.get('Adresse') or '').strip()
                statut   = (row.get('statut') or 'client').strip().lower()
                if statut not in ('client', 'prospect', 'inactif'): statut = 'client'

                if not nom:
                    errors.append(f"Ligne {i}: nom manquant"); nb_err += 1; continue

                conn.execute("""INSERT INTO clients
                    (nom, prenom, email, telephone, adresse, code_postal, ville, statut)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (nom, prenom, email, telephone, adresse, cp, ville, statut))
                nb_ok += 1
            except Exception as e:
                errors.append(f"Ligne {i}: {str(e)[:50]}"); nb_err += 1

        conn.commit()
        conn.close()
        flash(f'✅ Import terminé : {nb_ok} client(s) importé(s){f", {nb_err} erreur(s)" if nb_err else ""}', 'success' if nb_ok else 'error')
        if errors:
            flash(f'Erreurs : {"; ".join(errors[:5])}', 'warning')
        return redirect(url_for('clients_list'))

    return render_template('clients/import_csv.html')

# ── Export PDF fiche client ────────────────────────────────────

@app.route('/clients/<int:id>/fiche-pdf')
def client_fiche_pdf(id):
    conn = get_db()
    client   = conn.execute("SELECT * FROM clients WHERE id=?", (id,)).fetchone()
    contrats = conn.execute("""SELECT ct.*, b.nom_bateau FROM contrats ct
        LEFT JOIN bateaux b ON ct.bateau_id=b.id WHERE ct.client_id=?
        ORDER BY ct.date_creation DESC""", (id,)).fetchall()
    bateaux  = conn.execute("SELECT * FROM bateaux WHERE client_id=?", (id,)).fetchall()
    sinistres = conn.execute("SELECT * FROM sinistres WHERE client_id=? AND statut='ouvert'", (id,)).fetchall()
    params   = get_all_params()
    conn.close()
    if not client:
        abort(404)
    return render_template('clients/fiche_pdf.html', client=client, contrats=contrats,
                           bateaux=bateaux, sinistres=sinistres, params=params,
                           now=dt.now())

# ── Statistiques bateaux ──────────────────────────────────────

@app.route('/stats/bateaux')
def stats_bateaux():
    conn = get_db()
    annee = date.today().year

    par_type = conn.execute("""SELECT type_bateau, COUNT(*) as nb,
        COALESCE(AVG(valeur_assurance),0) as valeur_moy,
        COALESCE(SUM(valeur_assurance),0) as valeur_tot
        FROM bateaux WHERE type_bateau IS NOT NULL AND type_bateau != ''
        GROUP BY type_bateau ORDER BY nb DESC""").fetchall()

    par_zone = conn.execute("""SELECT zone_navigation, COUNT(*) as nb
        FROM bateaux WHERE zone_navigation IS NOT NULL AND zone_navigation != ''
        GROUP BY zone_navigation ORDER BY nb DESC LIMIT 10""").fetchall()

    par_port = conn.execute("""SELECT port_attache, COUNT(*) as nb
        FROM bateaux WHERE port_attache IS NOT NULL AND port_attache != ''
        GROUP BY port_attache ORDER BY nb DESC LIMIT 10""").fetchall()

    top_valeur = conn.execute("""SELECT b.*, c.nom, c.prenom FROM bateaux b
        JOIN clients c ON b.client_id=c.id
        WHERE b.valeur_assurance > 0 ORDER BY b.valeur_assurance DESC LIMIT 10""").fetchall()

    tranches = conn.execute("""SELECT
        CASE
            WHEN valeur_assurance < 10000 THEN '< 10 000 €'
            WHEN valeur_assurance < 30000 THEN '10 - 30 000 €'
            WHEN valeur_assurance < 50000 THEN '30 - 50 000 €'
            WHEN valeur_assurance < 100000 THEN '50 - 100 000 €'
            ELSE '> 100 000 €'
        END as tranche, COUNT(*) as nb
        FROM bateaux WHERE valeur_assurance > 0
        GROUP BY tranche ORDER BY MIN(valeur_assurance)""").fetchall()

    totaux = {
        'nb_bateaux': conn.execute("SELECT COUNT(*) FROM bateaux").fetchone()[0],
        'valeur_totale': float(conn.execute("SELECT COALESCE(SUM(valeur_assurance),0) FROM bateaux").fetchone()[0]),
        'valeur_moy': float(conn.execute("SELECT COALESCE(AVG(valeur_assurance),0) FROM bateaux WHERE valeur_assurance > 0").fetchone()[0]),
        'nb_sans_contrat': conn.execute("""SELECT COUNT(DISTINCT b.id) FROM bateaux b
            WHERE NOT EXISTS (SELECT 1 FROM contrats ct WHERE ct.bateau_id=b.id AND ct.statut='en_cours')""").fetchone()[0],
    }
    import json as _j
    conn.close()
    return render_template('stats/bateaux.html',
        par_type=par_type, par_zone=par_zone, par_port=par_port,
        top_valeur=top_valeur, tranches=tranches, totaux=totaux,
        par_type_json=_j.dumps([r['type_bateau'] for r in par_type]),
        par_type_nb_json=_j.dumps([r['nb'] for r in par_type]))


@app.route('/devis/<int:id>/dda-pdf')
@login_required
def devis_dda_pdf(id):
    conn = get_db()
    d = conn.execute("SELECT * FROM devis WHERE id=?", (id,)).fetchone()
    if not d:
        conn.close()
        flash('Devis introuvable.', 'error')
        return redirect(url_for('devis_list'))
    client = conn.execute("SELECT * FROM clients WHERE id=?", (d['client_id'],)).fetchone()
    params = get_all_params()
    conn.close()

    # Validation bloquante des informations manquantes
    missing = []
    if not params.get('cabinet_nom') or not params.get('cabinet_orias'):
        missing.append("Informations de la société dans les Paramètres (Nom du cabinet, N° ORIAS)")
    if not client or not client['nom'] or not client['adresse'] or not client['ville']:
        missing.append("Informations du client (Nom, Adresse, Ville)")
    if not d['compagnie'] or not d['type_assurance'] or not d['prime_proposee'] or not d['note_conseil']:
        missing.append("Informations du devis ou Note de conseil DDA (Compagnie, Type d'assurance, Prime, Argumentaire de conseil)")

    if missing:
        flash(f"❌ Impossible de générer la Fiche DDA : Il manque les informations suivantes : {'; '.join(missing)}.", 'error')
        return redirect(url_for('devis_modifier', id=id))

    return render_template('devis/fiche_dda_pdf.html', devis=d, client=client, params=params, today=date.today().strftime('%d/%m/%Y'))

def get_compagnies_actives():
    """Retourne la liste des compagnies actives pour les dropdowns."""
    conn = get_db()
    result = conn.execute(
        "SELECT id, nom, taux_commission, code_courtier FROM compagnies WHERE actif=1 ORDER BY nom"
    ).fetchall()
    conn.close()
    return result

# Injecter la liste des compagnies dans tous les templates
@app.context_processor
def inject_compagnies():
    try:
        return {'compagnies_liste': get_compagnies_actives()}
    except Exception:
        return {'compagnies_liste': []}

