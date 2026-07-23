# ============================================================
# navisur.spec - Configuration PyInstaller pour NAVISUR v9.8
# ============================================================

import sys
import os
import glob

PROJECT_DIR = os.path.dirname(os.path.abspath(SPEC))

block_cipher = None

# Collecte tous les fichiers .py du projet
python_files = glob.glob(os.path.join(PROJECT_DIR, '*.py'))

datas = [
    (os.path.join(PROJECT_DIR, 'templates'), 'templates'),
    (os.path.join(PROJECT_DIR, 'static'), 'static'),
    (os.path.join(PROJECT_DIR, 'navisur.ico'), '.'),
    (os.path.join(PROJECT_DIR, 'navisur_256.png'), '.'),
]

# Ajouter navisur_logo.jpg si présent
if os.path.exists(os.path.join(PROJECT_DIR, 'navisur_logo.jpg')):
    datas.append((os.path.join(PROJECT_DIR, 'navisur_logo.jpg'), '.'))

# Ajouter config/ si présent
if os.path.exists(os.path.join(PROJECT_DIR, 'config')):
    datas.append((os.path.join(PROJECT_DIR, 'config'), 'config'))

# Ajouter TOUS les fichiers .py du projet comme datas
# pour qu'ils soient accessibles au runtime
for py_file in python_files:
    fname = os.path.basename(py_file)
    if fname not in ['navisur_launcher.py', 'create_icon.py']:
        datas.append((py_file, '.'))

# NAVISUR v9.9 — Ajouter le dossier routes/ (architecture modulaire)
routes_dir = os.path.join(PROJECT_DIR, 'routes')
if os.path.exists(routes_dir):
    datas.append((routes_dir, 'routes'))
    # Aussi ajouter chaque route individuellement pour PyInstaller
    for route_file in glob.glob(os.path.join(routes_dir, '*.py')):
        datas.append((route_file, 'routes'))

# NAVISUR v9.9 — Ajouter le dossier models/
models_dir = os.path.join(PROJECT_DIR, 'models')
if os.path.exists(models_dir):
    datas.append((models_dir, 'models'))
    for model_file in glob.glob(os.path.join(models_dir, '*')):
        datas.append((model_file, 'models'))

a = Analysis(
    [os.path.join(PROJECT_DIR, 'navisur_launcher.py')],
    pathex=[PROJECT_DIR, os.path.join(PROJECT_DIR, 'routes')],
    binaries=[],
    datas=datas,
hiddenimports=[
    'flask_login',
    'flask_login.mixins',
    'flask_login.utils',
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.encoders',
    'pkg_resources',
    'pkg_resources.extern',
    'flask',
    'flask_cors',
    'jinja2',
    'jinja2.ext',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.debug',
    'sqlite3',
    'json',
    'logging',
    'logging.handlers',
    'requests',
    'PIL',
    'PIL.Image',
    'webview',
    'webview.platforms.winforms',
    'clr',
    'openpyxl',
    'openpyxl.workbook',
    'openpyxl.worksheet',
    'openpyxl.styles',
    'openpyxl.utils',
    'openpyxl.writer',
    'openpyxl.reader',
],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
        'pytest',
        'sphinx',
        'lib2to3',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NAVISUR',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_DIR, 'navisur.ico'),
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NAVISUR',
)