# routes/sinistres.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/sinistres')
def sinistres_list():
    conn = get_db()
    statut = request.args.get('statut', '')
    search = request.args.get('q', '')
    query = """SELECT s.*, c.nom, c.prenom, ct.numero as contrat_num, b.nom_bateau
               FROM sinistres s JOIN clients c ON s.client_id = c.id
               LEFT JOIN contrats ct ON s.contrat_id = ct.id
               LEFT JOIN bateaux b ON s.bateau_id = b.id WHERE 1=1"""
    params = []
    if search:
        query += " AND (s.numero LIKE ? OR c.nom LIKE ? OR s.type_sinistre LIKE ?)"
        params += [f'%{search}%'] * 3
    if statut:
        query += " AND s.statut = ?"
        params.append(statut)
    query += " ORDER BY s.date_creation DESC"
    sinistres = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('sinistres/index.html', sinistres=sinistres, statut=statut, search=search)

@app.route('/sinistres/nouveau', methods=['GET', 'POST'])
def sinistre_nouveau():
    conn = get_db()
    if request.method == 'POST':
        # NAVISUR v9.3 — Validation
        errors = []
        try: validate_required(request.form.get('client_id'), 'Client')
        except ValueError as e: errors.append(str(e))
        try: validate_required(request.form.get('type_sinistre'), 'Type de sinistre')
        except ValueError as e: errors.append(str(e))
        try: mt_estime = safe_float(request.form.get('montant_estime'), 0, 'Montant estimé')
        except ValueError as e: errors.append(str(e)); mt_estime = 0.0
        try: mt_indemnise = safe_float(request.form.get('montant_indemnise'), 0, 'Montant indemnisé')
        except ValueError as e: errors.append(str(e)); mt_indemnise = 0.0
        if errors:
            for e in errors: flash(f'❌ {e}', 'error')
            clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
            contrats = conn.execute("SELECT ct.id, ct.numero, ct.type_assurance, c.nom FROM contrats ct JOIN clients c ON ct.client_id=c.id ORDER BY c.nom").fetchall()
            bateaux = conn.execute("SELECT b.id, b.nom_bateau, b.marque, c.nom FROM bateaux b JOIN clients c ON b.client_id=c.id ORDER BY c.nom").fetchall()
            conn.close()
            return render_template('sinistres/form.html', sinistre=None, clients=clients, contrats=contrats, bateaux=bateaux, titre='Nouveau sinistre')
        conn.close()
        auto_num = gen_numero_sinistre() if not request.form.get('numero','').strip() else request.form['numero'].strip()
        try:
            with db_transaction() as c:
                c.execute('''INSERT INTO sinistres (client_id, contrat_id, bateau_id, numero,
                    date_declaration, date_sinistre, type_sinistre, lieu_sinistre, description,
                    montant_estime, montant_indemnise, statut, notes,
                    numero_sinistre_cie, gestionnaire_cie, telephone_gestionnaire,
                    date_declaration_cie, date_expertise, date_cloture,
                    cause_refus, recours_possible, recours_date, recours_notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (request.form['client_id'], request.form.get('contrat_id') or None,
                     request.form.get('bateau_id') or None,
                     auto_num, request.form.get('date_declaration', ''),
                     request.form.get('date_sinistre', ''), request.form.get('type_sinistre', ''),
                     request.form.get('lieu_sinistre', ''), request.form.get('description', ''),
                     mt_estime, mt_indemnise,
                     request.form.get('statut', 'declare'), request.form.get('notes', ''),
                     request.form.get('numero_sinistre_cie', ''),
                     request.form.get('gestionnaire_cie', ''),
                     request.form.get('telephone_gestionnaire', ''),
                     request.form.get('date_declaration_cie', '') or None,
                     request.form.get('date_expertise', '') or None,
                     request.form.get('date_cloture', '') or None,
                     request.form.get('cause_refus', ''),
                     1 if request.form.get('recours_possible') else 0,
                     request.form.get('recours_date', '') or None,
                     request.form.get('recours_notes', '')))
                new_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                log_audit('sinistres', new_id, 'INSERT', 'creation', None, auto_num)
            nlog('info', f'Sinistre {auto_num} déclaré (client #{request.form["client_id"]})')
        except Exception as e:
            nlog('error', f'Erreur création sinistre : {e}', exc=True)
            flash('❌ Erreur lors de la déclaration du sinistre.', 'error')
            return redirect(request.url)
        flash('Sinistre déclaré !', 'success')
        return redirect(url_for('sinistres_list'))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id, ct.numero, ct.type_assurance, c.nom
                               FROM contrats ct JOIN clients c ON ct.client_id=c.id
                               ORDER BY c.nom""").fetchall()
    bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, c.nom
                              FROM bateaux b JOIN clients c ON b.client_id=c.id
                              ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('sinistres/form.html', sinistre=None, clients=clients,
                           contrats=contrats, bateaux=bateaux, titre='Nouveau sinistre')

@app.route('/sinistres/<int:id>/modifier', methods=['GET', 'POST'])
def sinistre_modifier(id):
    conn = get_db()
    sinistre = conn.execute("SELECT * FROM sinistres WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        conn.execute('''UPDATE sinistres SET client_id=?, contrat_id=?, bateau_id=?, numero=?,
            date_declaration=?, date_sinistre=?, type_sinistre=?, lieu_sinistre=?, description=?,
            montant_estime=?, montant_indemnise=?, statut=?, notes=?,
            numero_sinistre_cie=?, gestionnaire_cie=?, telephone_gestionnaire=?,
            date_declaration_cie=?, date_expertise=?, date_cloture=?,
            cause_refus=?, recours_possible=?, recours_date=?, recours_notes=?
            WHERE id=?''',
            (request.form['client_id'], request.form.get('contrat_id') or None,
             request.form.get('bateau_id') or None,
             request.form.get('numero', ''), request.form.get('date_declaration', ''),
             request.form.get('date_sinistre', ''), request.form.get('type_sinistre', ''),
             request.form.get('lieu_sinistre', ''), request.form.get('description', ''),
             float(request.form.get('montant_estime') or 0),
             float(request.form.get('montant_indemnise') or 0),
             request.form.get('statut', 'ouvert'), request.form.get('notes', ''),
             request.form.get('numero_sinistre_cie', ''),
             request.form.get('gestionnaire_cie', ''),
             request.form.get('telephone_gestionnaire', ''),
             request.form.get('date_declaration_cie', '') or None,
             request.form.get('date_expertise', '') or None,
             request.form.get('date_cloture', '') or None,
             request.form.get('cause_refus', ''),
             1 if request.form.get('recours_possible') else 0,
             request.form.get('recours_date', '') or None,
             request.form.get('recours_notes', ''),
             id))
        conn.commit()
        conn.close()
        flash('Sinistre mis à jour !', 'success')
        return redirect(url_for('sinistres_list'))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    contrats = conn.execute("""SELECT ct.id, ct.numero, ct.type_assurance, c.nom
                               FROM contrats ct JOIN clients c ON ct.client_id=c.id
                               ORDER BY c.nom""").fetchall()
    bateaux = conn.execute("""SELECT b.id, b.nom_bateau, b.marque, c.nom
                              FROM bateaux b JOIN clients c ON b.client_id=c.id
                              ORDER BY c.nom""").fetchall()
    conn.close()
    return render_template('sinistres/form.html', sinistre=sinistre, clients=clients,
                           contrats=contrats, bateaux=bateaux, titre='Modifier le sinistre')

@app.route('/sinistres/<int:id>/supprimer', methods=['POST'])
def sinistre_supprimer(id):
    conn = get_db()
    conn.execute("DELETE FROM sinistres WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Sinistre supprimé.', 'info')
    return redirect(url_for('sinistres_list'))

# ─── COMMISSIONS ─────────────────────────────────────────────────────────────

