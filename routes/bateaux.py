# routes/bateaux.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/bateaux')
def bateaux_list():
    conn = get_db()
    search = request.args.get('q', '')
    query = """SELECT b.*, c.nom, c.prenom FROM bateaux b
               JOIN clients c ON b.client_id = c.id WHERE 1=1"""
    params = []
    if search:
        query += " AND (b.nom_bateau LIKE ? OR b.marque LIKE ? OR b.immatriculation LIKE ? OR c.nom LIKE ?)"
        params += [f'%{search}%'] * 4
    query += " ORDER BY b.id DESC"
    bateaux = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('bateaux/index.html', bateaux=bateaux, search=search)

@app.route('/bateaux/nouveau', methods=['GET', 'POST'])
def bateau_nouveau():
    conn = get_db()
    if request.method == 'POST':
        secours_data = {
            'marque': request.form.get('secours_marque', ''),
            'puissance': request.form.get('secours_puissance', ''),
            'energie': request.form.get('secours_energie', ''),
            'serie': request.form.get('secours_serie', ''),
        }
        annexe_data = {
            'type': request.form.get('annexe_type', ''),
            'puissance': request.form.get('annexe_puissance', ''),
            'immatriculation': request.form.get('annexe_immat', ''),
        }
        moteur_secours_json = _json.dumps(secours_data, ensure_ascii=False)
        annexe_json = _json.dumps(annexe_data, ensure_ascii=False)

        conn.execute('''INSERT INTO bateaux (client_id, nom_bateau, marque, modele, type_bateau,
            immatriculation, annee_fabrication, longueur, largeur, valeur_assurance, valeur_a_neuf,
            pavillon, port_attache, zone_navigation, usage,
            moteur_marque, moteur_modele, moteur_puissance, moteur_annee,
            moteur_type, moteur_carburant, moteur_serie,
            moteur2_marque, moteur2_puissance, moteur2_serie, notes,
            moteur_secours_json, annexe_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (request.form['client_id'],
             request.form.get('nom_bateau', ''), request.form.get('marque', ''),
             request.form.get('modele', ''), request.form.get('type_bateau', ''),
             request.form.get('immatriculation', ''),
             request.form.get('annee_fabrication') or None,
             request.form.get('longueur') or None, request.form.get('largeur') or None,
             float(request.form.get('valeur_assurance') or 0),
             float(request.form.get('valeur_a_neuf') or 0),
             request.form.get('pavillon', 'Français'),
             request.form.get('port_attache', ''), request.form.get('zone_navigation', ''),
             request.form.get('usage', 'privé uniquement'),
             request.form.get('moteur_marque', ''), request.form.get('moteur_modele', ''),
             request.form.get('moteur_puissance') or None,
             request.form.get('moteur_annee') or None,
             request.form.get('moteur_type', 'hors_bord'),
             request.form.get('moteur_carburant', 'essence'),
             request.form.get('moteur_serie', ''),
             request.form.get('moteur2_marque', ''),
             request.form.get('moteur2_puissance') or None,
             request.form.get('moteur2_serie', ''),
             request.form.get('notes', ''),
             moteur_secours_json, annexe_json))
        conn.commit()
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        client_id = request.form['client_id']
        conn.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.form.get('ajax') == '1':
            return jsonify({
                'success': True,
                'id': new_id,
                'nom_bateau': request.form.get('nom_bateau', ''),
                'marque': request.form.get('marque', ''),
                'modele': request.form.get('modele', ''),
                'valeur_assurance': float(request.form.get('valeur_assurance') or 0)
            })
        flash('Fiche bateau créée !', 'success')
        return redirect(url_for('client_detail', id=client_id))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    client_id = request.args.get('client_id')
    conn.close()
    return render_template('bateaux/form.html', bateau=None, clients=clients,
                           titre='Nouveau bateau', preselect_client=client_id)

@app.route('/bateaux/<int:id>')
def bateau_detail(id):
    conn = get_db()
    bateau = conn.execute("""SELECT b.*, c.nom, c.prenom FROM bateaux b
                             JOIN clients c ON b.client_id = c.id WHERE b.id=?""", (id,)).fetchone()
    contrats = conn.execute("SELECT * FROM contrats WHERE bateau_id=?", (id,)).fetchall()
    sinistres = conn.execute("""SELECT s.*, c.nom, c.prenom FROM sinistres s
                                JOIN clients c ON s.client_id=c.id WHERE s.bateau_id=?""",
                             (id,)).fetchall()
    conn.close()
    if not bateau:
        return redirect(url_for('bateaux_list'))
    breadcrumbs = [
        {'label': 'Clients', 'url': url_for('clients_list')},
        {'label': f"{bateau['prenom'] or ''} {bateau['nom']}".strip(), 'url': url_for('client_detail', id=bateau['client_id'])},
        {'label': f"Bateau : {bateau['nom_bateau'] or bateau['marque'] or 'Fiche'}", 'url': None}
    ]
    return render_template('bateaux/detail.html', bateau=bateau, contrats=contrats, sinistres=sinistres, breadcrumbs=breadcrumbs)

@app.route('/bateaux/<int:id>/modifier', methods=['GET', 'POST'])
def bateau_modifier(id):
    conn = get_db()
    bateau = conn.execute("SELECT * FROM bateaux WHERE id=?", (id,)).fetchone()
    if request.method == 'POST':
        secours_data = {
            'marque': request.form.get('secours_marque', ''),
            'puissance': request.form.get('secours_puissance', ''),
            'energie': request.form.get('secours_energie', ''),
            'serie': request.form.get('secours_serie', ''),
        }
        annexe_data = {
            'type': request.form.get('annexe_type', ''),
            'puissance': request.form.get('annexe_puissance', ''),
            'immatriculation': request.form.get('annexe_immat', ''),
        }
        moteur_secours_json = _json.dumps(secours_data, ensure_ascii=False)
        annexe_json = _json.dumps(annexe_data, ensure_ascii=False)

        conn.execute('''UPDATE bateaux SET client_id=?, nom_bateau=?, marque=?, modele=?, type_bateau=?,
            immatriculation=?, annee_fabrication=?, longueur=?, largeur=?, valeur_assurance=?, valeur_a_neuf=?,
            pavillon=?, port_attache=?, zone_navigation=?, usage=?,
            moteur_marque=?, moteur_modele=?, moteur_puissance=?, moteur_annee=?,
            moteur_type=?, moteur_carburant=?, moteur_serie=?,
            moteur2_marque=?, moteur2_puissance=?, moteur2_serie=?, notes=?,
            moteur_secours_json=?, annexe_json=? WHERE id=?''',
            (request.form['client_id'],
             request.form.get('nom_bateau', ''), request.form.get('marque', ''),
             request.form.get('modele', ''), request.form.get('type_bateau', ''),
             request.form.get('immatriculation', ''),
             request.form.get('annee_fabrication') or None,
             request.form.get('longueur') or None, request.form.get('largeur') or None,
             float(request.form.get('valeur_assurance') or 0),
             float(request.form.get('valeur_a_neuf') or 0),
             request.form.get('pavillon', 'Français'),
             request.form.get('port_attache', ''), request.form.get('zone_navigation', ''),
             request.form.get('usage', 'privé uniquement'),
             request.form.get('moteur_marque', ''), request.form.get('moteur_modele', ''),
             request.form.get('moteur_puissance') or None,
             request.form.get('moteur_annee') or None,
             request.form.get('moteur_type', 'hors_bord'),
             request.form.get('moteur_carburant', 'essence'),
             request.form.get('moteur_serie', ''),
             request.form.get('moteur2_marque', ''),
             request.form.get('moteur2_puissance') or None,
             request.form.get('moteur2_serie', ''),
             request.form.get('notes', ''),
             moteur_secours_json, annexe_json, id))
        conn.commit()
        client_id = request.form['client_id']
        conn.close()
        flash('Fiche bateau mise à jour !', 'success')
        return redirect(url_for('client_detail', id=client_id))
    clients = conn.execute("SELECT id, nom, prenom FROM clients ORDER BY nom").fetchall()
    conn.close()
    return render_template('bateaux/form.html', bateau=bateau, clients=clients,
                           titre='Modifier le bateau', preselect_client=None)

@app.route('/bateaux/<int:id>/supprimer', methods=['POST'])
def bateau_supprimer(id):
    conn = get_db()
    b = conn.execute("SELECT client_id FROM bateaux WHERE id=?", (id,)).fetchone()
    client_id = b['client_id'] if b else None
    conn.execute("DELETE FROM bateaux WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash('Bateau supprimé.', 'info')
    return redirect(url_for('client_detail', id=client_id) if client_id else url_for('bateaux_list'))

# ─── CONTRATS ────────────────────────────────────────────────────────────────

