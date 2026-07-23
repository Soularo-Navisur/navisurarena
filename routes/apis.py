# routes/apis.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import (
    _load_api_keys, _save_api_keys, _api_active, _api_key, _api_incr, _safe_get,
    _urllib, _urlparse, _json_api, _threading,
    API_TIMEOUT, API_KEYS_FILE, PAYS_CACHE_FILE,
    load_pays_cache, format_telephone_fr,
    app, get_db, nlog, log_audit, get_path, get_resource,
    request, jsonify, render_template, redirect, url_for, flash, abort,
    date, datetime, timedelta, os,
)

# def _load_api_keys(): → déplacé dans core.py

# def _save_api_keys(data): → déplacé dans core.py

# def _api_incr(service): → déplacé dans core.py

# def _api_active(service): → déplacé dans core.py

# def _api_key(service): → déplacé dans core.py

# def _safe_get(url, timeout=API_TIMEOUT): → déplacé dans core.py

# def load_pays_cache(): → déplacé dans core.py

def format_telephone_fr(numero):
    """Formate un numéro de téléphone français côté serveur."""
    if not numero: return numero
    import re
    n = re.sub(r'[^\d+]', '', numero)
    if n.startswith('+33'): n = '0' + n[3:]
    elif n.startswith('33') and len(n) == 11: n = '0' + n[2:]
    if re.match(r'^0[1-9]\d{8}$', n):
        return ' '.join([n[i:i+2] for i in range(0,10,2)])
    return numero  # retourner tel quel si format inconnu

# ── Routes API backend ───────────────────────────────────────

@app.route('/api/adresse-suggest')
def api_adresse_suggest():
    """Proxy suggestions adresse API gouv.fr."""
    q = request.args.get('q', '').strip()
    if len(q) < 3 or not _api_active('adresse_gouv'):
        return jsonify([])
    url = f"https://api-adresse.data.gouv.fr/search/?q={_urlparse.quote(q)}&limit=5"
    raw = _safe_get(url)
    if not raw:
        return jsonify([])
    try:
        data = _json_api.loads(raw)
        results = []
        for feat in data.get('features', []):
            props = feat.get('properties', {})
            results.append({
                'label': props.get('label',''),
                'housenumber': props.get('housenumber',''),
                'street': props.get('street','') or props.get('name',''),
                'postcode': props.get('postcode',''),
                'city': props.get('city',''),
            })
        nlog('info', f'API Adresse : {len(results)} résultats pour "{q[:20]}"')
        return jsonify(results)
    except Exception as e:
        nlog('warning', f'API Adresse parse erreur : {e}')
        return jsonify([])

@app.route('/api/siret-lookup')
def api_siret_lookup():
    """Recherche entreprise via SIRET (Pappers)."""
    siret = re.sub(r'\D', '', request.args.get('siret', ''))
    if len(siret) != 14:
        return jsonify({'found': False, 'error': 'SIRET invalide (14 chiffres requis)'})
    if not _api_active('pappers'):
        return jsonify({'found': False, 'error': 'API désactivée'})
    cle = _api_key('pappers')
    if not cle:
        return jsonify({'found': False, 'error': 'Clé API manquante'})
    # Essai 1 : Pappers
    url = f"https://api.pappers.fr/v2/entreprise?siret={siret}&api_token={cle}"
    raw = _safe_get(url)
    if raw:
        try:
            d = _json_api.loads(raw)
            if d.get('siren'):
                _api_incr('pappers')
                nlog('info', f'API Pappers OK SIRET {siret[:6]}...')
                siege = d.get('siege', {})
                return jsonify({
                    'found': True,
                    'raison_sociale': d.get('nom_entreprise', ''),
                    'adresse': siege.get('adresse_ligne_1', ''),
                    'code_postal': siege.get('code_postal', ''),
                    'ville': siege.get('ville', ''),
                    'dirigeant': d.get('representants', [{}])[0].get('nom_complet', '') if d.get('representants') else '',
                    'code_naf': d.get('code_naf', ''),
                    'forme_juridique': d.get('forme_juridique', ''),
                })
        except Exception as e:
            nlog('warning', f'Pappers parse erreur : {e}')
    # Essai 2 : INSEE SIRENE (cascade)
    url2 = f"https://api.insee.fr/entreprises/sirene/V3/siret/{siret}"
    raw2 = _safe_get(url2)
    if raw2:
        try:
            d2 = _json_api.loads(raw2)
            etab = d2.get('etablissement', {})
            ue = etab.get('uniteLegale', {})
            adresse = etab.get('adresseEtablissement', {})
            nlog('info', f'API INSEE SIRENE fallback OK SIRET {siret[:6]}...')
            return jsonify({
                'found': True,
                'raison_sociale': ue.get('denominationUniteLegale', '') or f"{ue.get('prenom1UniteLegale','')} {ue.get('nomUniteLegale','')}".strip(),
                'adresse': f"{adresse.get('numeroVoieEtablissement','')} {adresse.get('typeVoieEtablissement','')} {adresse.get('libelleVoieEtablissement','')}".strip(),
                'code_postal': adresse.get('codePostalEtablissement',''),
                'ville': adresse.get('libelleCommuneEtablissement',''),
                'dirigeant': '',
                'code_naf': ue.get('activitePrincipaleUniteLegale',''),
                'forme_juridique': ue.get('categorieJuridiqueUniteLegale',''),
            })
        except Exception:
            pass
    return jsonify({'found': False, 'error': 'SIRET non trouvé'})

@app.route('/api/email-validate')
def api_email_validate():
    """Validation email via Abstract API."""
    email = request.args.get('email', '').strip()
    import re as _re_em
    email_ok = bool(_re_em.match(r'^[^@\s]+@[^@\s]+\.[^@\s]{2,}$', email)) if email else False
    if not email:
        return jsonify({'status': 'skip'})
    if not _api_active('abstract_email') or not _api_key('abstract_email'):
        # Fallback : validation format local (toujours active)
        if email_ok:
            return jsonify({'status': 'format_ok', 'label': 'Format valide'})
        return jsonify({'status': 'invalid', 'label': '⚠️ Format email invalide'})
    cle = _api_key('abstract_email')
    url = f"https://emailvalidation.abstractapi.com/v1/?api_key={cle}&email={_urlparse.quote(email)}"
    raw = _safe_get(url)
    if not raw:
        if email_ok:
            return jsonify({'status': 'format_ok', 'label': 'Format valide (service indisponible)'})
        return jsonify({'status': 'unavailable'})
    try:
        d = _json_api.loads(raw)
        _api_incr('abstract_email')
        nlog('info', f'API Email validé : {email[:20]}...')
        deliverable = d.get('deliverability', '')
        if deliverable == 'DELIVERABLE':
            return jsonify({'status': 'valid', 'label': 'Email vérifié ✅'})
        elif deliverable == 'UNDELIVERABLE':
            return jsonify({'status': 'invalid', 'label': '⚠️ Email invalide ou inexistant'})
        else:
            return jsonify({'status': 'unknown', 'label': 'Format valide — vérification impossible'})
    except Exception as e:
        nlog('warning', f'Abstract API email parse : {e}')
        return jsonify({'status': 'unavailable'})

@app.route('/api/tel-validate')
def api_tel_validate():
    """Validation téléphone via NumVerify."""
    numero = request.args.get('numero', '').strip()
    if not numero or not _api_active('numverify'):
        return jsonify({'status': 'skip'})
    cle = _api_key('numverify')
    if not cle:
        return jsonify({'status': 'skip'})
    import re as _re
    clean = _re.sub(r'[^\d+]', '', numero)
    url = f"http://apilayer.net/api/validate?access_key={cle}&number={_urlparse.quote(clean)}&country_code=FR"
    raw = _safe_get(url)
    if not raw:
        # Fallback : formatage local seulement
        fmt = format_telephone_fr(numero)
        return jsonify({'status': 'formatted', 'formatted': fmt})
    try:
        d = _json_api.loads(raw)
        _api_incr('numverify')
        if d.get('valid'):
            fmt = format_telephone_fr(numero)
            country = d.get('country_name', 'France')
            line_type = d.get('line_type', '')
            intl = d.get('international_format', '')
            country_code = d.get('country_code', 'FR')
            nlog('info', f'NumVerify OK : {numero[:8]}...')
            return jsonify({
                'status': 'valid',
                'formatted': fmt,
                'country': country,
                'country_code': country_code,
                'line_type': line_type,
                'international': intl,
            })
        else:
            return jsonify({'status': 'invalid'})
    except Exception as e:
        nlog('warning', f'NumVerify parse : {e}')
        return jsonify({'status': 'skip'})

@app.route('/api/pays-list')
def api_pays_list():
    """Retourne la liste des pays depuis le cache."""
    return jsonify(load_pays_cache())

@app.route('/api/test-connexion/<service>')
def api_test_connexion(service):
    """Teste la connexion d'une API et retourne le résultat."""
    if service == 'adresse_gouv':
        raw = _safe_get("https://api-adresse.data.gouv.fr/search/?q=paris&limit=1")
        ok = bool(raw and b'features' in raw)
        return jsonify({'ok': ok, 'message': "API Adresse opérationnelle" if ok else "Impossible de joindre l'API"})
    elif service == 'pappers':
        cle = _api_key('pappers')
        raw = _safe_get(f"https://api.pappers.fr/v2/entreprise?siret=35600000000048&api_token={cle}")
        ok = bool(raw and (b'siren' in raw or b'entreprise' in raw))
        return jsonify({'ok': ok, 'message': 'Pappers opérationnel' if ok else 'Erreur Pappers (quota ou clé ?)'})
    elif service == 'abstract_email':
        cle = _api_key('abstract_email')
        raw = _safe_get(f"https://emailvalidation.abstractapi.com/v1/?api_key={cle}&email=test@example.com")
        ok = bool(raw and b'deliverability' in raw)
        return jsonify({'ok': ok, 'message': 'Abstract Email opérationnel' if ok else 'Erreur Abstract (quota ou clé ?)'})
    elif service == 'numverify':
        cle = _api_key('numverify')
        raw = _safe_get(f"http://apilayer.net/api/validate?access_key={cle}&number=0612345678&country_code=FR")
        ok = bool(raw and b'valid' in raw)
        return jsonify({'ok': ok, 'message': 'NumVerify opérationnel' if ok else 'Erreur NumVerify (quota ou clé ?)'})
    elif service == 'restcountries':
        ok = os.path.exists(PAYS_CACHE_FILE)
        return jsonify({'ok': ok, 'message': f'Cache pays disponible ({len(load_pays_cache())} pays)' if ok else 'Cache absent'})
    return jsonify({'ok': False, 'message': 'Service inconnu'})

# ── Page de configuration des API ───────────────────────────

@app.route('/admin/api-config', methods=['GET', 'POST'])
def admin_api_config():
    keys = _load_api_keys()
    if request.method == 'POST':
        action = request.form.get('action', '')
        service = request.form.get('service', '')
        if action == 'toggle' and service in keys:
            keys[service]['active'] = not keys[service].get('active', True)
            _save_api_keys(keys)
            etat = 'activée' if keys[service]['active'] else 'désactivée'
            flash(f'API {service} {etat}.', 'success')
        elif action == 'update_key' and service in keys:
            new_key = request.form.get('new_key', '').strip()
            if new_key:
                keys[service]['cle'] = new_key
                _save_api_keys(keys)
                flash(f'Clé API {service} mise à jour.', 'success')
        elif action == 'refresh_pays':
            # Tenter de rafraîchir le cache pays
            raw = _safe_get("https://restcountries.com/v3.1/all?fields=name,cca2,translations,flag")
            if raw:
                try:
                    data = _json_api.loads(raw)
                    pays_list = []
                    for c in data:
                        code = c.get('cca2','')
                        if not code: continue
                        nom_fr = c.get('translations',{}).get('fra',{}).get('common','') or c['name']['common']
                        emoji = c.get('flag','')
                        pays_list.append({'code':code,'nom_fr':nom_fr,'emoji':emoji})
                    pays_list.sort(key=lambda x: x['nom_fr'])
                    with open(PAYS_CACHE_FILE, 'w', encoding='utf-8') as pf:
                        _json_api.dump(pays_list, pf, ensure_ascii=False)
                    keys['restcountries']['cache_date'] = date.today().isoformat()
                    _save_api_keys(keys)
                    flash(f'✅ Cache pays rafraîchi : {len(pays_list)} pays.', 'success')
                except Exception as e:
                    flash(f'❌ Erreur rafraîchissement : {e}', 'error')
            else:
                flash('❌ Impossible de joindre RestCountries.', 'error')
        return redirect(url_for('admin_api_config'))
    # NAVISUR v9.9 — Quota Brevo en temps réel pour la page de config
    brevo_quota = {}
    try:
        brevo_quota = get_brevo().get_quota()
    except Exception:
        pass
    return render_template('admin/api_config.html', keys=keys,
                           nb_pays=len(load_pays_cache()),
                           brevo_quota=brevo_quota)



# ═══════════════════════════════════════════════════════════════
# NAVISUR v9.7 — TACITE RECONDUCTION
# ═══════════════════════════════════════════════════════════════

@app.route('/contrats/<int:id>/mise-a-jour-prime', methods=['POST'])
def contrat_maj_prime_tacite(id):
    """Saisie rapide prime tacite reconduction : met à jour l'historique + date_fin + quittance."""
    conn = get_db()
    ct = conn.execute("""SELECT ct.*, c.nom, c.prenom, b.nom_bateau
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id WHERE ct.id=?""", (id,)).fetchone()
    if not ct:
        conn.close(); return jsonify({'ok': False, 'error': 'Contrat introuvable'})

    try:
        nouvelle_prime = safe_float(request.form.get('nouvelle_prime'), 0, 'Nouvelle prime')
    except ValueError as e:
        conn.close(); return jsonify({'ok': False, 'error': str(e)})

    annee_cible = safe_int(request.form.get('annee', date.today().year), date.today().year, 'Année')
    note = request.form.get('note', '')
    date_effet = request.form.get('date_effet', '')
    creer_quittance = request.form.get('creer_quittance') == '1'
    frequence = request.form.get('frequence', 'annuel')
    mode_paiement = request.form.get('mode_paiement', 'prelevement')

    # Prime précédente pour calcul variation
    prev = conn.execute(
        "SELECT prime_ttc FROM primes_historique WHERE contrat_id=? AND annee=?",
        (id, annee_cible - 1)).fetchone()
    # Aussi regarder prime_annuelle si pas d'historique
    prime_precedente = float(prev['prime_ttc']) if prev else float(ct['prime_annuelle'] or 0)
    variation = None
    if prime_precedente > 0:
        variation = round((nouvelle_prime - prime_precedente) / prime_precedente * 100, 2)

    # 1. Ajouter dans primes_historique
    conn.execute("""INSERT OR REPLACE INTO primes_historique
        (contrat_id, annee, prime_ttc, variation_pct, note)
        VALUES (?,?,?,?,?)""",
        (id, annee_cible, nouvelle_prime, variation, note))

    # 2. Mettre à jour le contrat (prime + date_fin + marqueur)
    nouvelle_date_fin = None
    if date_effet:
        try:
            from datetime import timedelta as _td2
            d_effet = date.fromisoformat(date_effet)
            # Calculer nouvelle date_fin = date_effet + 1 an - 1 jour
            import calendar as _cal
            d_fin = d_effet.replace(year=d_effet.year + 1) - timedelta(days=1)
            nouvelle_date_fin = d_fin.isoformat()
        except Exception:
            pass

    conn.execute("""UPDATE contrats SET prime_annuelle=?,
        annee_prime_validee=?, prime_annee_en_cours=?, date_derniere_maj_prime=?
        {date_fin_clause} WHERE id=?""".format(
        date_fin_clause=', date_fin=?' if nouvelle_date_fin else ''),
        ([nouvelle_prime, annee_cible, nouvelle_prime, date.today().isoformat()]
         + ([nouvelle_date_fin] if nouvelle_date_fin else [])
         + [id]))

    # 3. Créer quittance si demandé
    quittance_msg = ''
    if creer_quittance and date_effet:
        try:
            nb_map = {'annuel':1,'semestriel':2,'trimestriel':4,'mensuel':12}
            nb = nb_map.get(frequence, 1)
            montant_unit = round(nouvelle_prime / nb, 2)
            echeances = _calc_echeances(date_effet, frequence, nb, montant_unit)
            taux_comm = float(ct['taux_commission'] or 15)
            # Supprimer quittances existantes de cette année
            conn.execute("DELETE FROM quittances_suivi WHERE contrat_id=? AND annee=?",
                         (id, annee_cible))
            for i, ech in enumerate(echeances):
                statut_p = 'prelevement_auto' if mode_paiement == 'prelevement' else 'en_attente'
                comm_att = round(montant_unit * taux_comm / 100, 2)
                conn.execute("""INSERT INTO quittances_suivi
                    (contrat_id, annee, frequence, mode_paiement, numero_quittance,
                     total_quittances, montant_ttc, date_echeance, statut_paiement,
                     taux_commission, commission_attendue)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (id, annee_cible, frequence, mode_paiement, i+1, nb,
                     montant_unit, ech, statut_p, taux_comm, comm_att))
            quittance_msg = f' — {nb} quittance(s) créée(s)'
        except Exception as e:
            nlog('warning', f'Création quittance tacite #{id} : {e}')

    # 4. Journal d'activité
    var_str = f' (+{variation:.1f}%)' if variation and variation > 0 else (f' ({variation:.1f}%)' if variation else '')
    journal_msg = f'Prime {annee_cible} saisie : {nouvelle_prime:.2f} €{var_str} — Tacite reconduction{quittance_msg}'
    conn.execute("""INSERT INTO journal_activites
        (client_id, contrat_id, type_activite, date_activite, objet, contenu, auteur)
        VALUES (?,?,'note',?,?,?,'Système')""",
        (ct['client_id'], id, date.today().isoformat(),
         f'Mise à jour prime {annee_cible}', journal_msg))

    # 5. Audit log
    log_audit('contrats', id, 'UPDATE', 'prime_tacite',
              str(prime_precedente), f'{nouvelle_prime} (annee={annee_cible})')
    nlog('info', f'Tacite reconduction contrat #{id} : prime {annee_cible} = {nouvelle_prime}€{var_str}')

    conn.commit(); conn.close()

    confirmation = (f'✅ Prime {annee_cible} enregistrée : {nouvelle_prime:.2f} €'
                    + (f' ({variation:+.1f}%)' if variation is not None else '')
                    + (f' — Échéance mise à jour au {nouvelle_date_fin}' if nouvelle_date_fin else '')
                    + quittance_msg)
    return jsonify({'ok': True, 'message': confirmation,
                    'variation': variation, 'nouvelle_date_fin': nouvelle_date_fin})


@app.route('/echeances')
def echeances_page():
    """Page dédiée échéances : tacite vs manuel, avec filtres."""
    conn = get_db()
    today_s = date.today().isoformat()
    annee_c = date.today().year
    periode = request.args.get('periode', '90')  # jours
    filtre = request.args.get('filtre', 'tous')   # tous/tacite/manuel/a_traiter

    try: nb_jours = int(periode)
    except Exception: nb_jours = 90
    horizon = (date.today() + timedelta(days=nb_jours)).isoformat()
    avant_hier = (date.today() - timedelta(days=30)).isoformat()

    q = """SELECT ct.*, c.nom, c.prenom, c.email, c.telephone, b.nom_bateau,
               CAST(julianday(ct.date_fin) - julianday(?) AS INTEGER) as jours,
               COALESCE(ct.tacite_reconduction, 1) as tacite_reconduction,
               ct.annee_prime_validee, ct.prime_annee_en_cours
           FROM contrats ct JOIN clients c ON ct.client_id=c.id
           LEFT JOIN bateaux b ON ct.bateau_id=b.id
           WHERE ct.statut='en_cours' AND ct.date_fin IS NOT NULL
             AND ct.date_fin BETWEEN ? AND ?
           ORDER BY ct.date_fin"""
    rows = conn.execute(q, (today_s, avant_hier, horizon)).fetchall()

    if filtre == 'tacite':
        rows = [r for r in rows if r['tacite_reconduction']]
    elif filtre == 'manuel':
        rows = [r for r in rows if not r['tacite_reconduction']]
    elif filtre == 'a_traiter':
        rows = [r for r in rows if (r['tacite_reconduction'] and (not r['annee_prime_validee'] or r['annee_prime_validee'] < annee_c))
                or (not r['tacite_reconduction'])]

    tacite_rows = [r for r in rows if r['tacite_reconduction']]
    manuel_rows = [r for r in rows if not r['tacite_reconduction']]
    conn.close()
    return render_template('echeances.html',
        tacite_rows=tacite_rows, manuel_rows=manuel_rows,
        all_rows=rows, periode=periode, filtre=filtre,
        annee_c=annee_c, today=today_s)

@app.route('/echeances/export-excel')
def echeances_export():
    """Export Excel des échéances."""
    import io
    conn = get_db()
    today_s = date.today().isoformat()
    periode = int(request.args.get('periode', 90))
    horizon = (date.today() + timedelta(days=periode)).isoformat()
    rows = conn.execute("""SELECT ct.numero, c.nom, c.prenom, ct.compagnie,
        ct.type_assurance, b.nom_bateau, ct.date_fin, ct.prime_annuelle,
        COALESCE(ct.tacite_reconduction,1) as tacite,
        ct.annee_prime_validee, ct.prime_annee_en_cours
        FROM contrats ct JOIN clients c ON ct.client_id=c.id
        LEFT JOIN bateaux b ON ct.bateau_id=b.id
        WHERE ct.statut='en_cours' AND ct.date_fin BETWEEN ? AND ?
        ORDER BY ct.date_fin""", (today_s, horizon)).fetchall()
    conn.close()
    try:
        import openpyxl
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Echéances"
        ws.append(['N° Contrat','Client','Compagnie','Type','Bateau','Date fin',
                   'Prime actuelle','Mode','Prime saisie','Année validée'])
        for r in rows:
            ws.append([r['numero'], f"{r['prenom'] or ''} {r['nom']}",
                       r['compagnie'], r['type_assurance'], r['nom_bateau'] or '',
                       r['date_fin'], r['prime_annuelle'],
                       'Tacite' if r['tacite'] else 'Manuel',
                       r['prime_annee_en_cours'] or '', r['annee_prime_validee'] or ''])
        buf = io.BytesIO(); wb.save(buf); buf.seek(0)
        from flask import send_file
        return send_file(buf, as_attachment=True,
                         download_name=f'echeances_{date.today()}.xlsx',
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except ImportError:
        flash('Export Excel indisponible.', 'error')
        return redirect(url_for('echeances_page'))


# NAVISUR v9.8 — Route d'arrêt propre pour le launcher pywebview
@app.route('/shutdown', methods=['GET', 'POST'])
def app_shutdown():
    """Arrêt propre de Flask depuis le launcher."""
    import threading as _t
    def _stop():
        import time as _time; _time.sleep(0.5)
        import os as _os; _os._exit(0)
    _t.Thread(target=_stop, daemon=True).start()
    return 'OK', 200


if __name__ == '__main__':
    import webbrowser
    init_db()
    sauvegarde_auto()
    # NAVISUR v9.3 — Vérification intégrité + log démarrage
    _ok, _msg = check_db_integrity()
    nlog('info', f'=== NAVISUR démarré === intégrité DB : {"OK" if _ok else "ECHEC — " + _msg}')
    _wlog = logging.getLogger('werkzeug')
    _wlog.setLevel(logging.ERROR)
    print("\n" + "="*50)
    print("  NAVISUR — CRM Riviera Marine Assurances")
    print("  Serveur interne demarre sur port 5000")
    if not _ok:
        print(f"  ⚠️  ATTENTION : Intégrité DB : {_msg}")
    print("="*50 + "\n")

@app.route('/api/communes')
def api_communes():
    """Autocomplete communes françaises via geo.api.gouv.fr (gratuit, sans clé)."""
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify([])
    try:
        import urllib.request as _ur, urllib.parse as _up
        url = f"https://geo.api.gouv.fr/communes?nom={_up.quote(q)}&fields=nom,codesPostaux,departement&boost=population&limit=8"
        req = _ur.Request(url, headers={'User-Agent': 'NAVISUR/9.9'})
        with _ur.urlopen(req, timeout=3) as r:
            data = _json_api.loads(r.read())
        results = []
        for c in data:
            cp   = c.get('codesPostaux', [''])[0]
            dept = c.get('departement', {}).get('nom', '')
            results.append({
                'nom': c['nom'], 'code_postal': cp,
                'departement': dept,
                'label': f"{c['nom']} ({cp}) — {dept}"
            })
        return jsonify(results)
    except Exception:
        return jsonify([])
