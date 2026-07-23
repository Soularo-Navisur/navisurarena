"""
app.py — NAVISUR v9.9 (modulaire)
Point d'entrée unique. Importe core.py + tous les modules routes/.
"""

# ── Core : Flask app, DB, utils ────────────────────────────────────
from core import *

# ── Sécurité bootstrap (secret key + auth guard + users table) ─────
import security_bootstrap
from security_bootstrap import init_auth_db

# ── Modules de routes (ordre sans importance) ──────────────────────
from routes.auth         import *
from routes.accueil      import *
from routes.clients      import *
from routes.bateaux      import *
from routes.contrats     import *
from routes.contrats_ops import *
from routes.sinistres    import *
from routes.devis        import *
from routes.finances     import *
from routes.compta       import *
from routes.compagnies   import *
from routes.risques      import *
from routes.conformite   import *
from routes.admin        import *
from routes.apis         import *
from routes.parametres   import *
from routes.portail      import *

# ── Auto-init DB (lanceur PyInstaller) ─────────────────────────────
def _auto_init_db():
    try:
        init_db()
        init_auth_db()
        nlog('info', 'init_db() OK')
    except Exception as e:
        nlog('warning', f'init_db() auto échoué : {e}')

_auto_init_db()

# ── Lancement direct (développement) ──────────────────────────────
if __name__ == '__main__':
    sauvegarde_auto()
    _ok, _msg = check_db_integrity()
    nlog('info', f'=== NAVISUR démarré === intégrité DB : {"OK" if _ok else "ECHEC — " + _msg}')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    print("\n" + "="*50)
    print("  NAVISUR — CRM Riviera Marine Assurances")
    print("  Serveur sur port 5000")
    print("="*50 + "\n")
    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
