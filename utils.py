"""utils.py — Helpers formatage, validation, APIs"""
import re, os, json, urllib.request, urllib.parse, logging
from datetime import date
from werkzeug.utils import secure_filename
from config import app, ALLOWED_EXTENSIONS, UPLOAD_FOLDER

# ── Filtres Jinja ──
def format_size(nb):
    if not nb: return '0 o'
    if nb < 1024: return f"{nb} o"
    elif nb < 1024*1024: return f"{nb//1024} Ko"
    return f"{nb/(1024*1024):.1f} Mo"

def file_icon(filename):
    ext = filename.rsplit('.',1)[-1].lower() if filename and '.' in filename else ''
    icons = {'pdf':'bi-file-earmark-pdf','doc':'bi-file-earmark-word','docx':'bi-file-earmark-word',
             'xls':'bi-file-earmark-excel','xlsx':'bi-file-earmark-excel','csv':'bi-file-earmark-spreadsheet',
             'jpg':'bi-file-earmark-image','jpeg':'bi-file-earmark-image','png':'bi-file-earmark-image',
             'gif':'bi-file-earmark-image','txt':'bi-file-earmark-text','odt':'bi-file-earmark-text'}
    return icons.get(ext, 'bi-file-earmark')

def _pays_flag(code):
    if not code or len(code) != 2: return '🌍'
    return ''.join(chr(127397 + ord(c)) for c in code.upper())

app.jinja_env.filters['format_size'] = format_size
app.jinja_env.filters['file_icon'] = file_icon
app.jinja_env.filters['pays_flag'] = _pays_flag

# ── Validation ──
def safe_float(val, default=0.0, label='Montant', min_val=0.0):
    try:
        result = float(val or default)
        if result < min_val: raise ValueError(f"{label} doit être >= {min_val}")
        return result
    except (TypeError, ValueError):
        raise ValueError(f"{label} doit être un nombre valide (valeur reçue : {val!r})")

def safe_int(val, default=0, label='Valeur'):
    try: return int(val or default)
    except (TypeError, ValueError):
        raise ValueError(f"{label} doit être un entier valide (valeur reçue : {val!r})")

def validate_dates(d_debut, d_fin, ld='Date début', lf='Date fin'):
    if d_debut and d_fin:
        from datetime import date as _d
        if _d.fromisoformat(d_fin) < _d.fromisoformat(d_debut):
            raise ValueError(f"{lf} doit être postérieure à {ld}")
    return True

def validate_email(email):
    if email and ('@' not in email or '.' not in email.split('@')[-1]):
        raise ValueError("L'adresse email n'est pas valide")
    return True

def validate_required(val, label):
    if not (val or '').strip():
        raise ValueError(f"Le champ « {label} » est obligatoire")
    return True

# ── Fichiers ──
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def get_compagnie_from_form():
    from flask import request
    val = request.form.get('compagnie','').strip()
    if val == '__autre__': return request.form.get('compagnie_libre','').strip()
    return val

# ── Téléphone ──
def format_telephone_fr(numero):
    if not numero: return numero
    n = re.sub(r'[^\d+]', '', numero)
    if n.startswith('+33'): n = '0'+n[3:]
    elif n.startswith('33') and len(n)==11: n = '0'+n[2:]
    if re.match(r'^0[1-9]\d{8}$', n):
        return ' '.join([n[i:i+2] for i in range(0,10,2)])
    return numero

# ── URSSAF ──
def calc_urssaf(ca, taux_cot=21.1, taux_vl=2.2, vl_actif=False):
    cot = round(ca * taux_cot / 100, 2)
    vl  = round(ca * taux_vl  / 100, 2) if vl_actif else 0.0
    return cot, vl, round(cot + vl, 2)

# ── API helpers ──
API_TIMEOUT = 3
PAYS_CACHE_FILE = None  # initialisé après config

def _load_api_keys():
    from config import get_path
    try:
        with open(get_path('config','api_keys.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception: return {}

def _save_api_keys(data):
    from config import get_path
    try:
        os.makedirs(get_path('config'), exist_ok=True)
        with open(get_path('config','api_keys.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        pass

def _api_active(service):
    return _load_api_keys().get(service, {}).get('active', False)

def _api_key(service):
    return _load_api_keys().get(service, {}).get('cle', '')

def _api_incr(service):
    try:
        keys = _load_api_keys()
        ym = date.today().strftime('%Y-%m')
        svc = keys.get(service, {})
        if svc.get('dernier_reset','') != ym and date.today().day == 1:
            svc['requetes_ce_mois'] = 0; svc['dernier_reset'] = ym
        svc['requetes_ce_mois'] = svc.get('requetes_ce_mois',0)+1
        keys[service] = svc; _save_api_keys(keys)
    except Exception: pass

def _safe_get(url, timeout=API_TIMEOUT):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'NAVISUR/9.9'})
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
    except Exception: return None

def load_pays_cache():
    from config import get_path, get_resource
    pc = get_path('config','pays_cache.json')
    if not os.path.exists(pc): pc = get_resource('config','pays_cache.json')
    try:
        with open(pc, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception: return []

# ── Logging ──
from logging.handlers import RotatingFileHandler
import logging
from config import LOG_FILE
_log_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
_log_handler.setLevel(logging.INFO)
navisur_logger = logging.getLogger('navisur')
navisur_logger.setLevel(logging.INFO)
navisur_logger.addHandler(_log_handler)

def nlog(level, msg, exc=False):
    fn = getattr(navisur_logger, level, navisur_logger.info)
    fn(msg, exc_info=exc)
