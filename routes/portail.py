# routes/portail.py — NAVISUR v9.9
# Espace client : login, dashboard, documents, attestations, demandes
from core import *
from werkzeug.security import generate_password_hash, check_password_hash
import secrets, time
from functools import wraps

# ── Helpers authentification portail ──────────────────────────────

MAX_ATTEMPTS = 5
LOCKOUT_SEC  = 900

def _hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')

def _check_password(stored, provided):
    return check_password_hash(stored, provided)

def _generate_token():
    return secrets.token_urlsafe(32)

def _is_locked():
    now = time.time()
    attempts = session.get('portail_attempts', [])
    attempts = [t for t in attempts if now - t < LOCKOUT_SEC]
    session['portail_attempts'] = attempts
    return len(attempts) >= MAX_ATTEMPTS

def _record_attempt():
    session.setdefault('portail_attempts', []).append(time.time())

def portail_login_required(f):
    """Décorateur : redirige vers login si client non connecté."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('portail_client_id'):
            return redirect(url_for('portail_login'))
        return f(*args, **kwargs)
    return decorated

def _get_portail_client():
    """Retourne le client connecté ou None."""
    cid = session.get('portail_client_id')
    if not cid:
        return None
    conn = get_db()
    c = conn.execute(
        "SELECT cp.*, cl.nom, cl.prenom, cl.email, cl.telephone, cl.civilite "
        "FROM clients_portail cp JOIN clients cl ON cp.client_id=cl.id "
        "WHERE cp.id=? AND cp.actif=1", (cid,)
    ).fetchone()
    conn.close()
    return dict(c) if c else None

# ── Routes portail ─────────────────────────────────────────────────

@app.route('/portail')
def portail_index():
    if session.get('portail_client_id'):
        return redirect(url_for('portail_dashboard'))
    return redirect(url_for('portail_login'))


@app.route('/portail/login', methods=['GET', 'POST'])
def portail_login():
    error = None
    if _is_locked():
        error = 'Trop de tentatives. Réessayez dans 15 minutes.'
        return render_template('portail/login.html', error=error)
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            error = 'Email et mot de passe requis.'
        else:
            conn = get_db()
            row = conn.execute(
                "SELECT cp.*, cl.nom, cl.prenom FROM clients_portail cp "
                "JOIN clients cl ON cp.client_id=cl.id "
                "WHERE cp.email_login=? AND cp.actif=1",
                (email,)
            ).fetchone()
            conn.close()

            if not row:
                _record_attempt()
                error = 'Compte introuvable ou désactivé.'
            elif not _check_password(row['mot_de_passe'], password):
                _record_attempt()
                error = 'Mot de passe incorrect.'
            else:
                session.pop('portail_attempts', None)
                session['portail_client_id'] = row['id']
                session['portail_nom'] = f"{row['prenom'] or ''} {row['nom']}"
                nlog('info', f"Portail login : {email} (client #{row['client_id']})")
                return redirect(url_for('portail_dashboard'))

    return render_template('portail/login.html', error=error)


@app.route('/portail/logout')
def portail_logout():
    session.pop('portail_client_id', None)
    session.pop('portail_nom', None)
    return redirect(url_for('portail_login'))


@app.route('/portail/dashboard')
@portail_login_required
def portail_dashboard():
    client_portail = _get_portail_client()
    if not client_portail:
        session.clear()
        return redirect(url_for('portail_login'))

    cid = client_portail['client_id']
    conn = get_db()

    # Contrats actifs
    contrats = conn.execute(
        "SELECT ct.*, b.nom_bateau FROM contrats ct "
        "LEFT JOIN bateaux b ON ct.bateau_id=b.id "
        "WHERE ct.client_id=? AND ct.statut='en_cours' ORDER BY ct.date_fin",
        (cid,)
    ).fetchall()

    # Sinistres en cours
    sinistres = conn.execute(
        "SELECT s.*, ct.numero as num_contrat FROM sinistres s "
        "LEFT JOIN contrats ct ON s.contrat_id=ct.id "
        "WHERE s.client_id=? AND s.statut NOT IN ('clos','indemnise') "
        "ORDER BY s.date_sinistre DESC LIMIT 5",
        (cid,)
    ).fetchall()

    # Demandes en cours
    demandes = conn.execute(
        "SELECT * FROM portail_demandes WHERE client_id=? "
        "ORDER BY date_creation DESC LIMIT 5",
        (cid,)
    ).fetchall()

    # Documents récents
    docs = conn.execute(
        "SELECT * FROM documents WHERE client_id=? "
        "ORDER BY date_upload DESC LIMIT 6",
        (cid,)
    ).fetchall()

    conn.close()

    return render_template('portail/dashboard.html',
        cp=client_portail,
        contrats=[dict(c) for c in contrats],
        sinistres=[dict(s) for s in sinistres],
        demandes=[dict(d) for d in demandes],
        docs=[dict(d) for d in docs],
    )


@app.route('/portail/contrats')
@portail_login_required
def portail_contrats():
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))
    conn = get_db()
    contrats = conn.execute(
        "SELECT ct.*, b.nom_bateau, b.immatriculation FROM contrats ct "
        "LEFT JOIN bateaux b ON ct.bateau_id=b.id "
        "WHERE ct.client_id=? ORDER BY ct.statut, ct.date_fin",
        (cp['client_id'],)
    ).fetchall()
    conn.close()
    return render_template('portail/contrats.html', cp=cp,
                           contrats=[dict(c) for c in contrats])


@app.route('/portail/documents')
@portail_login_required
def portail_documents():
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))
    type_filtre = request.args.get('type', '')
    conn = get_db()
    q = "SELECT * FROM documents WHERE client_id=?"
    params = [cp['client_id']]
    if type_filtre:
        q += " AND type_document=?"
        params.append(type_filtre)
    q += " ORDER BY date_upload DESC"
    docs = conn.execute(q, params).fetchall()
    types = conn.execute(
        "SELECT DISTINCT type_document FROM documents WHERE client_id=? AND type_document IS NOT NULL",
        (cp['client_id'],)
    ).fetchall()
    conn.close()
    return render_template('portail/documents.html', cp=cp,
                           docs=[dict(d) for d in docs],
                           types=[t[0] for t in types],
                           type_filtre=type_filtre)


@app.route('/portail/documents/<int:doc_id>/telecharger')
@portail_login_required
def portail_document_dl(doc_id):
    """Téléchargement sécurisé — vérifie que le doc appartient au client."""
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))
    conn = get_db()
    doc = conn.execute(
        "SELECT * FROM documents WHERE id=? AND client_id=?",
        (doc_id, cp['client_id'])
    ).fetchone()
    conn.close()
    if not doc:
        abort(403)
    return send_from_directory(
        UPLOAD_FOLDER, doc['nom_stockage'],
        as_attachment=True, download_name=doc['nom_original']
    )


@app.route('/portail/attestations')
@portail_login_required
def portail_attestations():
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))
    conn = get_db()
    contrats = conn.execute(
        "SELECT ct.*, b.nom_bateau, b.immatriculation FROM contrats ct "
        "LEFT JOIN bateaux b ON ct.bateau_id=b.id "
        "WHERE ct.client_id=? AND ct.statut='en_cours'",
        (cp['client_id'],)
    ).fetchall()
    conn.close()
    return render_template('portail/attestations.html', cp=cp,
                           contrats=[dict(c) for c in contrats])


@app.route('/portail/demandes', methods=['GET', 'POST'])
@portail_login_required
def portail_demandes():
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))

    if request.method == 'POST':
        type_demande = request.form.get('type_demande', '')
        message      = request.form.get('message', '').strip()
        contrat_id   = request.form.get('contrat_id') or None

        if not type_demande or not message:
            flash('Veuillez remplir tous les champs.', 'warning')
        else:
            conn = get_db()
            conn.execute(
                "INSERT INTO portail_demandes "
                "(client_id, contrat_id, type_demande, message, statut, date_creation) "
                "VALUES (?,?,?,?,'en_attente',?)",
                (cp['client_id'], contrat_id, type_demande, message,
                 datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            nlog('info', f"Portail demande : {type_demande} — client #{cp['client_id']}")
            flash('✅ Votre demande a bien été transmise. Nous vous répondons sous 48h.', 'success')
            return redirect(url_for('portail_demandes'))

    conn = get_db()
    demandes = conn.execute(
        "SELECT pd.*, ct.numero as num_contrat FROM portail_demandes pd "
        "LEFT JOIN contrats ct ON pd.contrat_id=ct.id "
        "WHERE pd.client_id=? ORDER BY pd.date_creation DESC",
        (cp['client_id'],)
    ).fetchall()
    contrats = conn.execute(
        "SELECT id, numero, compagnie FROM contrats "
        "WHERE client_id=? AND statut='en_cours'",
        (cp['client_id'],)
    ).fetchall()
    conn.close()

    return render_template('portail/demandes.html', cp=cp,
                           demandes=[dict(d) for d in demandes],
                           contrats=[dict(c) for c in contrats])


@app.route('/portail/profil', methods=['GET', 'POST'])
@portail_login_required
def portail_profil():
    cp = _get_portail_client()
    if not cp: return redirect(url_for('portail_login'))

    if request.method == 'POST':
        new_pass  = request.form.get('new_password', '').strip()
        confirm   = request.form.get('confirm_password', '').strip()
        if new_pass:
            if new_pass != confirm:
                flash('Les mots de passe ne correspondent pas.', 'danger')
            elif len(new_pass) < 8:
                flash('Le mot de passe doit faire au moins 8 caractères.', 'warning')
            else:
                conn = get_db()
                conn.execute(
                    "UPDATE clients_portail SET mot_de_passe=? WHERE id=?",
                    (_hash_password(new_pass), cp['id'])
                )
                conn.commit()
                conn.close()
                flash('✅ Mot de passe mis à jour.', 'success')

    return render_template('portail/profil.html', cp=cp)


# ── Routes Admin : gestion des accès portail ─────────────────────

@app.route('/clients/<int:client_id>/portail', methods=['GET', 'POST'])
def client_portail_admin(client_id):
    """Gestion de l'accès portail depuis la fiche client (admin)."""
    conn = get_db()
    client = dict(conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone() or {})
    if not client:
        conn.close()
        abort(404)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'creer':
            email_login = (request.form.get('email_login') or client.get('email', '')).strip().lower()
            if not email_login:
                flash('Email requis pour créer un accès.', 'danger')
            else:
                # Vérifier si accès déjà existant
                existing = conn.execute(
                    "SELECT id FROM clients_portail WHERE client_id=?", (client_id,)
                ).fetchone()
                if existing:
                    flash('Cet client a déjà un accès portail.', 'warning')
                else:
                    temp_pass = secrets.token_urlsafe(10)
                    token     = _generate_token()
                    conn.execute(
                        "INSERT INTO clients_portail "
                        "(client_id, email_login, mot_de_passe, token_reset, actif, date_creation) "
                        "VALUES (?,?,?,?,1,?)",
                        (client_id, email_login, _hash_password(temp_pass),
                         token, datetime.now().isoformat())
                    )
                    conn.commit()
                    nlog('info', f"Accès portail créé — client #{client_id} ({email_login})")
                    flash(
                        f'✅ Accès créé — Email : {email_login} — '
                        f'Mot de passe temporaire : <strong>{temp_pass}</strong> '
                        f'(à communiquer au client)',
                        'success'
                    )

        elif action == 'activer':
            conn.execute(
                "UPDATE clients_portail SET actif=1 WHERE client_id=?", (client_id,))
            conn.commit()
            flash('Accès portail activé.', 'success')

        elif action == 'desactiver':
            conn.execute(
                "UPDATE clients_portail SET actif=0 WHERE client_id=?", (client_id,))
            conn.commit()
            flash('Accès portail désactivé.', 'warning')

        elif action == 'reset_password':
            new_pass = secrets.token_urlsafe(10)
            conn.execute(
                "UPDATE clients_portail SET mot_de_passe=? WHERE client_id=?",
                (_hash_password(new_pass), client_id)
            )
            conn.commit()
            flash(f'Nouveau mot de passe temporaire : <strong>{new_pass}</strong>', 'success')

        conn.close()
        return redirect(url_for('client_portail_admin', client_id=client_id))

    portail_row = conn.execute(
        "SELECT * FROM clients_portail WHERE client_id=?", (client_id,)
    ).fetchone()
    demandes = conn.execute(
        "SELECT * FROM portail_demandes WHERE client_id=? ORDER BY date_creation DESC LIMIT 10",
        (client_id,)
    ).fetchall()
    conn.close()

    return render_template('portail/admin_client.html',
        client=client,
        portail=dict(portail_row) if portail_row else None,
        demandes=[dict(d) for d in demandes],
    )


@app.route('/portail/demandes/<int:demande_id>/repondre', methods=['POST'])
def portail_demande_repondre(demande_id):
    """Réponse du courtier à une demande client."""
    reponse = request.form.get('reponse', '').strip()
    statut  = request.form.get('statut', 'traitee')
    if reponse:
        conn = get_db()
        conn.execute(
            "UPDATE portail_demandes SET reponse=?, statut=?, date_reponse=? WHERE id=?",
            (reponse, statut, datetime.now().isoformat(), demande_id)
        )
        conn.commit()
        conn.close()
        flash('Réponse envoyée au client.', 'success')
    return redirect(request.referrer or url_for('accueil'))
