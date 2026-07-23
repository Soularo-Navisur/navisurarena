# routes/parametres.py — NAVISUR v9.9
# Ce fichier est un module de routes NAVISUR.
# Il importe tout depuis core.py (app, get_db, nlog, etc.)
from core import *

@app.route('/admin/parametres-courtier', methods=['GET', 'POST'])
def admin_parametres_courtier():
    import json as _json_pc
    _courtier_file = os.path.join(BASE_DIR, 'config', 'parametres_courtier.json')
    os.makedirs(os.path.dirname(_courtier_file), exist_ok=True)
    if request.method == 'POST':
        data = {
            'nom': request.form.get('nom', ''),
            'titre': request.form.get('titre', ''),
            'email': request.form.get('email', ''),
            'telephone': request.form.get('telephone', ''),
            'adresse': request.form.get('adresse', ''),
            'orias': request.form.get('orias', ''),
            'site_web': request.form.get('site_web', ''),
            'signature': request.form.get('signature', ''),
        }
        with open(_courtier_file, 'w', encoding='utf-8') as _f:
            _json_pc.dump(data, _f, indent=2, ensure_ascii=False)
        reload_brevo()
        nlog('info', 'Paramètres courtier mis à jour')
        flash('✅ Paramètres courtier enregistrés.', 'success')
        return redirect(url_for('admin_parametres_courtier'))
    try:
        with open(_courtier_file, 'r', encoding='utf-8') as _f:
            courtier = _json_pc.load(_f)
    except Exception:
        courtier = {}
    return render_template('admin/parametres_courtier.html', courtier=courtier)


# ═══════════════════════════════════════════════════════════════
#  MODULE DEVIS — Workflow complet prospect → client
# ═══════════════════════════════════════════════════════════════

STATUTS_DEVIS = [
    ('en_attente',  '⏳ En attente de réponse', 'badge-attendu'),
    ('accepte',     '✅ Accepté',                'badge-clos'),
    ('refuse',      '❌ Refusé',                 'badge-resilie'),
    ('sans_suite',  '⛔ Sans suite',             'badge-inactif'),
    ('expire',      '⏰ Expiré',                 'badge-echu'),
]

