""" security_bootstrap.py — secret key + auth guard """
import os, secrets
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from core import app, get_db, nlog, request, redirect, url_for

# ── secret key depuis fichier ──
_secret_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'secret.key')
if os.path.exists(_secret_path):
    with open(_secret_path, 'r') as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = secrets.token_hex(32)
    with open(_secret_path, 'w') as f:
        f.write(app.secret_key)

# ── Flask-Login ──
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, email):
        self.id = id; self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT id,email FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return User(row['id'], row['email']) if row else None

# ── Guard global ──
PUBLIC_ENDPOINTS = {
    'login','logout','static','portail_index','portail_login','portail_logout',
    'api_adresse_suggest','api_communes','api_siret_lookup','api_email_validate',
    'api_tel_validate','api_pays_list','api_test_connexion','app_shutdown'
}

@app.before_request
def _auth_guard():
    if request.path.startswith('/static/'): return
    if request.endpoint in PUBLIC_ENDPOINTS: return
    if request.path.startswith('/portail/'): return
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

def init_auth_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    if not conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        h = generate_password_hash('admin123', method='pbkdf2:sha256')
        conn.execute("INSERT INTO users (email,password_hash) VALUES (?,?)",
                     ('admin@navisur.local', h))
        conn.commit()
        nlog('warning','Admin créé : admin@navisur.local / admin123 — CHANGEZ LE MOT DE PASSE')
    conn.close()
