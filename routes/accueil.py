# routes/accueil.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/documents')
def documents_list():
    conn = get_db()
    search = request.args.get('q', '')
    type_doc = request.args.get('type', '')
    query = """SELECT d.*, c.nom, c.prenom FROM documents d
               JOIN clients c ON d.client_id = c.id WHERE 1=1"""
    params = []
    if search:
        query += " AND (d.nom_original LIKE ? OR c.nom LIKE ? OR d.type_document LIKE ?)"
        params += [f'%{search}%'] * 3
    if type_doc:
        query += " AND d.type_document = ?"
        params.append(type_doc)
    query += " ORDER BY d.date_upload DESC"
    documents = conn.execute(query, params).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    return render_template('documents/index.html', documents=documents,
                           search=search, type_doc=type_doc,
                           types_documents=TYPES_DOCUMENTS, total=total)

# ─── DASHBOARD ───────────────────────────────────────────────────────────────


# ─── ACCUEIL (tableau de bord + aujourd'hui fusionnés) ────────

@app.route('/accueil')
@app.route('/')
def accueil():
    generer_notifications()
    today = date.today()
    today_s = today.isoformat()
    conn = get_db()

    annee = today.year
    plafond   = float(get_param('micro_plafond_bnc', '77700'))
    taux_cot  = float(get_param('taux_cotisations', '21.1'))

    # ── Stats clés ──────────────────────────────────────────────
    stats = {
        'nb_clients':        conn.execute("SELECT COUNT(*) FROM clients WHERE statut='client'").fetchone()[0],
        'nb_prospects':      conn.execute("SELECT COUNT(*) FROM clients WHERE statut='prospect'").fetchone()[0],
        'nb_contrats_actifs':conn.execute("SELECT COUNT(*) FROM contrats WHERE statut='en_cours'").fetchone()[0],
        'nb_sinistres_ouverts':conn.execute("SELECT COUNT(*) FROM sinistres WHERE statut='ouvert'").fetchone()[0],
        'ca_annee':  float(conn.execute("SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=?", (annee,)).fetchone()[0]),
        'ca_mois':   float(conn.execute("SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?", (annee, today.month)).fetchone()[0]),
        'comm_attente_mt': float(conn.execute("SELECT COALESCE(SUM(montant_attendu),0) FROM compta_commissions WHERE statut IN ('attendue','releve_recu')").fetchone()[0]),
        'comm_attente_nb': conn.execute("SELECT COUNT(*) FROM compta_commissions WHERE statut IN ('attendue','releve_recu')").fetchone()[0],
    }
    pct_plafond = round(stats['ca_annee'] / plafond * 100, 1) if plafond else 0
    cot_estimees = round(stats['ca_annee'] * taux_cot / 100, 2)

    # CA par mois (graphique)
    ca_par_mois = []
    for m in range(1, 13):
        v = float(conn.execute("SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?", (annee, m)).fetchone()[0])
        ca_par_mois.append(round(v, 2))

    # ── Actions du jour ─────────────────────────────────────────
    rdvs_ajd = conn.execute("""
        SELECT r.*, c.nom, c.prenom, c.telephone FROM rendez_vous r
        LEFT JOIN clients c ON r.client_id=c.id
        WHERE r.date_rdv=? AND r.statut IN ('prevu','confirme') ORDER BY r.heure_debut
    """, (today_s,)).fetchall()

    relances_dues = conn.execute("""
        SELECT r.*, c.nom, c.prenom, c.email, c.telephone, ct.numero, ct.type_assurance
        FROM relances r JOIN clients c ON r.client_id=c.id
        JOIN contrats ct ON r.contrat_id=ct.id
        WHERE r.statut='a_faire' AND r.date_prevue <= ? ORDER BY r.date_prevue
    """, (today_s,)).fetchall()

    taches_dues = conn.execute("""
        SELECT t.*, c.nom, c.prenom FROM taches t
        LEFT JOIN clients c ON t.client_id=c.id
        WHERE t.statut='a_faire' AND t.date_echeance <= ? ORDER BY t.date_echeance
    """, (today_s,)).fetchall()

    # ── Renouvellements à venir ──────────────────────────────────
    # NAVISUR v9.7 — Tacite vs Manuel
    _ech_query = """
        SELECT ct.*, c.nom, c.prenom, c.email, b.nom_bateau,
               CAST(julianday(ct.date_fin) - julianday(?) AS INTEGER) as jours,
               COALESCE(ct.tacite_reconduction, 1) as tacite_reconduction,
               ct.annee_prime_validee, ct.prime_annee_en_cours
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.statut='en_cours' AND ct.date_fin IS NOT NULL
          AND julianday(ct.date_fin) - julianday(?) BETWEEN {a} AND {b}
        ORDER BY ct.date_fin
    """
    contrats_30j = conn.execute(_ech_query.format(a=0, b=30), (today_s, today_s)).fetchall()
    contrats_90j = conn.execute(_ech_query.format(a=31, b=90), (today_s, today_s)).fetchall()
    # Contrats expirés (date_fin passée) mais toujours en_cours et prime non saisie
    contrats_expires_tacite = conn.execute("""
        SELECT ct.*, c.nom, c.prenom, b.nom_bateau,
               CAST(julianday(?) - julianday(ct.date_fin) AS INTEGER) as jours_retard
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.statut='en_cours' AND ct.date_fin < ?
          AND COALESCE(ct.tacite_reconduction,1)=1
          AND (ct.annee_prime_validee IS NULL OR ct.annee_prime_validee < ?)
        ORDER BY ct.date_fin
    """, (today_s, today_s, today.year)).fetchall()

    # Séparer tacite vs manuel pour le dashboard
    tacite_30j = [c for c in contrats_30j if c['tacite_reconduction']]
    manuel_30j  = [c for c in contrats_30j if not c['tacite_reconduction']]
    tacite_90j  = [c for c in contrats_90j if c['tacite_reconduction']]
    manuel_90j  = [c for c in contrats_90j if not c['tacite_reconduction']]
    # Prime déjà saisie pour l'année en cours ?
    annee_courante = today.year
    tacite_a_saisir = [c for c in tacite_30j + tacite_90j + contrats_expires_tacite
                       if not c['annee_prime_validee'] or c['annee_prime_validee'] < annee_courante]

    # ── Commissions en retard ────────────────────────────────────
    comm_retard = conn.execute("""
        SELECT cc.*, c.nom, c.prenom FROM compta_commissions cc
        LEFT JOIN clients c ON cc.client_id=c.id
        WHERE cc.statut IN ('attendue','releve_recu') AND cc.date_prevue < ?
          AND cc.date_prevue IS NOT NULL ORDER BY cc.date_prevue
    """, (today_s,)).fetchall()

    # ── Devis en attente ────────────────────────────────────────
    devis_attente = conn.execute("""
        SELECT d.*, c.nom, c.prenom FROM devis d
        JOIN clients c ON d.client_id=c.id
        WHERE d.statut='en_attente' ORDER BY d.date_devis DESC LIMIT 5
    """).fetchall()

    # URSSAF urgent
    urssaf_dues = conn.execute("""
        SELECT * FROM compta_urssaf WHERE statut != 'faite'
          AND date_limite <= ?
    """, ((today + __import__('datetime').timedelta(days=15)).isoformat(),)).fetchall()

    # Derniers clients ajoutés
    derniers_clients = conn.execute("""
        SELECT * FROM clients ORDER BY id DESC LIMIT 5
    """).fetchall()

    # Yachts avec personnel à bord sans contrat P&I prévu
    try:
        yachts_sans_pi = conn.execute("""
            SELECT r.id, r.libelle, c.nom, c.prenom, c.id as cid
            FROM risques r JOIN clients c ON r.client_id=c.id
            WHERE r.type_risque='yacht'
            AND json_extract(r.details,'$.personnel_bord')=1
            AND (json_extract(r.details,'$.contrat_pi_prevu') IS NULL
                 OR json_extract(r.details,'$.contrat_pi_prevu')=0)
        """).fetchall()
        nb_risques = conn.execute("SELECT COUNT(*) FROM risques").fetchone()[0]
    except Exception:
        yachts_sans_pi = []
        nb_risques = 0

    # NAVISUR v9.3 — Réclamations en retard + formations insuffisantes
    today_s_temp = today.isoformat()
    reclamations_retard = conn.execute("""
        SELECT COUNT(*) FROM reclamations
        WHERE statut NOT IN ('resolue','classee')
          AND date_reponse_prevue IS NOT NULL
          AND date_reponse_prevue < ?""", (today_s_temp,)).fetchone()[0]
    heures_formations = float(conn.execute("""
        SELECT COALESCE(SUM(duree_heures),0) FROM formations_dda
        WHERE substr(date_formation,1,4)=?""", (str(annee),)).fetchone()[0])

    # NAVISUR v9.4 — Alertes suivi financier
    horizon_15j = (today + timedelta(days=15)).isoformat()
    # Alertes communications Brevo
    nb_emails_erreur = 0
    nb_emails_non_ouverts = 0
    try:
        nb_emails_erreur = conn.execute(
            "SELECT COUNT(*) FROM communications WHERE statut='erreur'").fetchone()[0]
        _seuil_7j = (today - timedelta(days=7)).isoformat()
        nb_emails_non_ouverts = conn.execute(
            """SELECT COUNT(*) FROM communications
               WHERE statut='envoye' AND date_envoi < ?""",
            (_seuil_7j,)).fetchone()[0]
    except Exception:
        pass

    nb_quitt_impayees = 0
    nb_quitt_envoyer = 0
    mt_comm_non_recues = 0.0
    nb_prelev_mois = 0
    try:
        nb_quitt_impayees = conn.execute(
            "SELECT COUNT(*) FROM quittances_suivi WHERE statut_paiement='impayee'").fetchone()[0]
        nb_quitt_envoyer = conn.execute(
            """SELECT COUNT(*) FROM quittances_suivi
               WHERE envoyee_client=0 AND mode_paiement!='prelevement'
                 AND date_echeance <= ?""", (horizon_15j,)).fetchone()[0]
        mt_comm_non_recues = float(conn.execute(
            """SELECT COALESCE(SUM(commission_attendue),0) FROM quittances_suivi
               WHERE (commission_recue IS NULL OR commission_recue=0)
                 AND commission_attendue > 0""").fetchone()[0])
        nb_prelev_mois = conn.execute(
            """SELECT COUNT(*) FROM calendrier_prelevements cp
               JOIN quittances_suivi qs ON cp.quittance_id=qs.id
               WHERE cp.statut='prevu' AND substr(cp.date_prelevement,1,7)=?""",
            (today.strftime('%Y-%m'),)).fetchone()[0]
    except Exception:
        pass

    # Variables dashboard premium (patches v9.9)
    nb_bateaux = 0
    ca_mois_precedent = 0.0
    activite_recente = []
    try:
        nb_bateaux = conn.execute("SELECT COUNT(*) FROM bateaux").fetchone()[0]
        mois_prec = today.month - 1 if today.month > 1 else 12
        annee_prec_m = annee if today.month > 1 else annee - 1
        ca_mois_precedent = float(conn.execute(
            "SELECT COALESCE(SUM(montant),0) FROM compta_recettes WHERE annee=? AND mois=?",
            (annee_prec_m, mois_prec)).fetchone()[0])
        activite_recente = conn.execute("""
            SELECT j.date_activite as date_evt, j.type_contact as type_evt,
                   j.objet as titre, c.nom, c.prenom, c.id as client_id
            FROM journal_activites j
            LEFT JOIN clients c ON j.client_id=c.id
            WHERE j.date_activite >= ?
            ORDER BY j.date_activite DESC LIMIT 15
        """, ((today - timedelta(days=7)).isoformat(),)).fetchall()
    except Exception:
        pass

    # tacite_a_afficher (dédoublonné côté Python)
    _seen = set()
    tacite_a_afficher = []
    for _c in (list(contrats_expires_tacite[:3]) + list(tacite_30j[:3])):
        if _c['id'] not in _seen:
            _seen.add(_c['id'])
            tacite_a_afficher.append(_c)

    conn.close()

    import json as _j
    mois_noms = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
    jour_noms = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche']

    return render_template('accueil.html',
        stats=stats, pct_plafond=pct_plafond, plafond=plafond,
        cot_estimees=cot_estimees, taux_cot=taux_cot,
        ca_par_mois=_j.dumps(ca_par_mois),
        mois_noms=_j.dumps(mois_noms),
        rdvs_ajd=rdvs_ajd, relances_dues=relances_dues,
        taches_dues=taches_dues, contrats_30j=contrats_30j,
        contrats_90j=contrats_90j, comm_retard=comm_retard,
        tacite_30j=tacite_30j, manuel_30j=manuel_30j,
        tacite_90j=tacite_90j, manuel_90j=manuel_90j,
        tacite_a_saisir=tacite_a_saisir,
        contrats_expires_tacite=contrats_expires_tacite,
        annee_courante=annee_courante,
        devis_attente=devis_attente, urssaf_dues=urssaf_dues,
        derniers_clients=derniers_clients,
        yachts_sans_pi=yachts_sans_pi, nb_risques=nb_risques,
        today=today_s, annee=annee,
        jour_nom=jour_noms[today.weekday()],
        mois_nom=['Janvier','Février','Mars','Avril','Mai','Juin',
                  'Juillet','Août','Septembre','Octobre','Novembre','Décembre'][today.month-1],
        reclamations_retard=reclamations_retard,
        heures_formations=heures_formations,
        nb_emails_erreur=nb_emails_erreur,
        nb_emails_non_ouverts=nb_emails_non_ouverts,
        nb_quitt_impayees=nb_quitt_impayees,
        nb_quitt_envoyer=nb_quitt_envoyer,
        mt_comm_non_recues=mt_comm_non_recues,
        nb_prelev_mois=nb_prelev_mois,
        nb_bateaux=nb_bateaux,
        ca_mois_precedent=ca_mois_precedent,
        activite_recente=activite_recente,
        tacite_a_afficher=tacite_a_afficher,
        today_yesterday=(today - timedelta(days=1)).isoformat(),
        stats_manuel_30j=manuel_30j)


