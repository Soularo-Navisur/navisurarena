# routes/contrats.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/contrats')
def contrats_list():
    conn = get_db()
    search = request.args.get('q', '')
    statut = request.args.get('statut', '')
    compagnie = request.args.get('compagnie', '')
    query = """SELECT ct.*, c.nom, c.prenom, b.nom_bateau,
               r.libelle as risque_libelle, r.type_risque
               FROM contrats ct
               JOIN clients c ON ct.client_id = c.id
               LEFT JOIN bateaux b ON ct.bateau_id = b.id
               LEFT JOIN risques r ON ct.risque_id = r.id
               WHERE 1=1"""
    params = []
    if search:
        query += " AND (ct.numero LIKE ? OR ct.compagnie LIKE ? OR ct.type_assurance LIKE ? OR c.nom LIKE ?)"
        params += [f'%{search}%'] * 4
    if statut:
        query += " AND ct.statut = ?"
        params.append(statut)
    if compagnie:
        query += " AND ct.compagnie = ?"
        params.append(compagnie)
    query += " ORDER BY ct.date_creation DESC"
    contrats = conn.execute(query, params).fetchall()
    compagnies = [r[0] for r in conn.execute(
        "SELECT DISTINCT compagnie FROM contrats WHERE compagnie != '' ORDER BY compagnie"
    ).fetchall()]
    conn.close()
    return render_template('contrats/index.html', contrats=contrats,
                           search=search, statut=statut, compagnie=compagnie,
                           compagnies=compagnies, STATUTS_CONTRAT=STATUTS_CONTRAT)

@app.route('/contrats/nouveau', methods=['GET', 'POST'])
def contrat_nouveau():
    conn = get_db()
    if request.method == 'POST':
        # NAVISUR v9.3 — Validation serveur
        errors = []
        try: validate_required(request.form.get('client_id'), 'Client')
        except ValueError as e: errors.append(str(e))
        try: validate_required(get_compagnie_from_form(), 'Compagnie')
        except ValueError as e: errors.append(str(e))
        try: validate_required(request.form.get('type_assurance'), "Type d'assurance")
        except ValueError as e: errors.append(str(e))
        try: prime = safe_float(request.form.get('prime_annuelle'), 0, 'Prime annuelle')
        except ValueError as e: errors.append(str(e)); prime = 0.0
        try: franchise = safe_float(request.form.get('franchise'), 0, 'Franchise')
        except ValueError as e: errors.append(str(e)); franchise = 0.0
        try: validate_dates(request.form.get('date_debut'), request.form.get('date_fin'), 'Date début', 'Date fin')
        except ValueError as e: errors.append(str(e))
        if errors:
            for e in errors: flash(f'❌ {e}', 'error')
            clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
            bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, b.modele, c.nom, b.client_id
                                       FROM bateaux b JOIN clients c ON b.client_id=c.id
                                       ORDER BY c.nom""").fetchall()
            conn.close()
            return render_template('contrats/form.html', contrat=None, clients=clients, bateaux=bateaux,
                                   titre='Nouveau contrat', preselect_client=request.form.get('client_id'),
                                   prefill=dict(request.form), produits=PRODUITS_PLAISANCE, devis_id='')
        client_id = request.form['client_id']
        numero = request.form.get('numero', '').strip()
        if not numero:
            annee = date.today().year
            nb = conn.execute(
                "SELECT COUNT(*)+1 FROM contrats WHERE strftime('%Y',date_creation)=?",
                (str(annee),)).fetchone()[0]
            numero = f"POL-{annee}-{nb:03d}"
        conn.close()
        try:
            with db_transaction() as c:
                c.execute('''INSERT INTO contrats (client_id, bateau_id, numero, compagnie, type_assurance,
                    objet, date_debut, date_fin, prime_annuelle, periodicite, statut, franchise, garanties, notes,
                    numero_police_cie, date_transmission_cie, date_acceptation_cie, date_emission_police,
                    tacite_reconduction, option_regate, option_skipper_pro, option_annexe, option_hauturier, option_solitaire, flotte_nom, co_assureurs)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (client_id, request.form.get('bateau_id') or None,
                     numero, get_compagnie_from_form(),
                     request.form.get('type_assurance', ''), request.form.get('objet', ''),
                     request.form.get('date_debut', ''), request.form.get('date_fin', ''),
                     prime, request.form.get('periodicite', 'annuelle'),
                     request.form.get('statut', 'en_cours'), franchise,
                     request.form.get('garanties', ''), request.form.get('notes', ''),
                     request.form.get('numero_police_cie',''),
                     request.form.get('date_transmission_cie','') or None,
                     request.form.get('date_acceptation_cie','') or None,
                     request.form.get('date_emission_police','') or None,
                     int(request.form.get('tacite_reconduction', '1')),
                     1 if request.form.get('option_regate') else 0,
                     1 if request.form.get('option_skipper_pro') else 0,
                     1 if request.form.get('option_annexe') else 0,
                     1 if request.form.get('option_hauturier') else 0,
                     1 if request.form.get('option_solitaire') else 0,
                     request.form.get('flotte_nom', '').strip(),
                     request.form.get('co_assureurs', '').strip()))
                new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                log_audit('contrats', new_id, 'INSERT', 'creation', None, numero)
            nlog('info', f'Contrat {numero} créé (client #{client_id})')
            flash(f'Contrat {numero} créé !', 'success')
        except ValueError as e:
            flash(f'❌ {e}', 'error'); return redirect(request.url)
        except Exception as e:
            nlog('error', f'Erreur création contrat : {e}', exc=True)
            flash('❌ Erreur lors de la création du contrat.', 'error'); return redirect(request.url)
        if request.form.get('from_client'):
            return redirect(url_for('client_detail', id=client_id) + '#contrats')
        return redirect(url_for('contrats_list'))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, b.modele, c.nom, b.client_id
                               FROM bateaux b JOIN clients c ON b.client_id=c.id
                               ORDER BY c.nom""").fetchall()
    client_id      = request.args.get('client_id', '')
    compagnie      = request.args.get('compagnie', '')
    type_assurance = request.args.get('type_assurance', '')
    prime          = request.args.get('prime_annuelle', '')
    franchise      = request.args.get('franchise', '')
    devis_id       = request.args.get('devis_id', '')
    prefill_risque = request.args.get('risque_id', '')
    annee = date.today().year
    nb = conn.execute(
        "SELECT COUNT(*)+1 FROM contrats WHERE strftime('%Y',date_creation)=?",
        (str(annee),)).fetchone()[0]
    numero_suggere = f"POL-{annee}-{nb:03d}"
    conn.close()
    garanties_pre  = request.args.get('garanties', '')
    notes_pre      = request.args.get('notes', '')
    return render_template('contrats/form.html', contrat=None, clients=clients, bateaux=bateaux,
                           titre='Nouveau contrat', preselect_client=client_id,
                           prefill={'compagnie': compagnie, 'type_assurance': type_assurance,
                                    'prime_annuelle': prime, 'franchise': franchise,
                                    'numero': numero_suggere, 'risque_id': prefill_risque,
                                    'garanties': garanties_pre, 'notes': notes_pre},
                           produits=PRODUITS_PLAISANCE, devis_id=devis_id)


@app.route('/contrats/<int:id>/modifier', methods=['GET', 'POST'])
def contrat_modifier(id):
    conn = get_db()
    contrat = conn.execute("SELECT * FROM contrats WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        for _fld in ['numero', 'compagnie', 'type_assurance', 'prime_annuelle', 'statut', 'franchise']:
            _old = contrat[_fld] if contrat and contrat[_fld] is not None else ''
            _new = request.form.get(_fld, '')
            if str(_old) != str(_new):
                log_audit('contrats', id, 'UPDATE', _fld, _old, _new)
        new_statut = request.form.get('statut', contrat['statut'] if contrat else 'en_cours')
        if contrat and contrat['statut'] != new_statut:
            ok, msg = valider_transition(contrat['statut'], new_statut)
            if not ok:
                flash(f'⚠️ {msg}', 'warning')
            else:
                log_audit('contrats', id, 'UPDATE', 'statut', contrat['statut'], new_statut)
        conn.execute('''UPDATE contrats SET client_id=?, bateau_id=?, numero=?, compagnie=?,
            type_assurance=?, objet=?, date_debut=?, date_fin=?, prime_annuelle=?,
            periodicite=?, statut=?, franchise=?, garanties=?, notes=?,
            numero_police_cie=?, date_transmission_cie=?,
            date_acceptation_cie=?, date_emission_police=?,
            tacite_reconduction=?, option_regate=?, option_skipper_pro=?,
            option_annexe=?, option_hauturier=?, option_solitaire=?,
            flotte_nom=?, co_assureurs=? WHERE id=?''',
            (request.form['client_id'], request.form.get('bateau_id') or None,
             request.form.get('numero', ''), get_compagnie_from_form(),
             request.form.get('type_assurance', ''), request.form.get('objet', ''),
             request.form.get('date_debut', ''), request.form.get('date_fin', ''),
             float(request.form.get('prime_annuelle') or 0),
             request.form.get('periodicite', 'annuelle'), request.form.get('statut', 'en_cours'),
             float(request.form.get('franchise') or 0),
             request.form.get('garanties', ''), request.form.get('notes', ''),
             request.form.get('numero_police_cie',''),
             request.form.get('date_transmission_cie','') or None,
             request.form.get('date_acceptation_cie','') or None,
             request.form.get('date_emission_police','') or None,
             int(request.form.get('tacite_reconduction', '1')),
             1 if request.form.get('option_regate') else 0,
             1 if request.form.get('option_skipper_pro') else 0,
             1 if request.form.get('option_annexe') else 0,
             1 if request.form.get('option_hauturier') else 0,
             1 if request.form.get('option_solitaire') else 0,
             request.form.get('flotte_nom', '').strip(),
             request.form.get('co_assureurs', '').strip(), id))
        conn.commit()
        conn.close()
        nlog('info', f'Contrat #{id} modifié')
        flash('Contrat mis à jour !', 'success')
        return redirect(url_for('contrats_list'))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, b.modele, c.nom
                               FROM bateaux b JOIN clients c ON b.client_id=c.id
                               ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('contrats/form.html', contrat=contrat, clients=clients, bateaux=bateaux,
                           titre='Modifier le contrat', preselect_client=None,
                           produits=PRODUITS_PLAISANCE)

@app.route('/contrats/<int:id>/supprimer', methods=['POST'])
def contrat_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM contrats WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Contrat supprimé.', 'info')
    return redirect(url_for('contrats_list'))

# ─── SINISTRES ───────────────────────────────────────────────────────────────

