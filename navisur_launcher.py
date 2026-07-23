# ============================================================
# NAVISUR v9.8 — Launcher principal
# Splash screen tkinter + Flask + pywebview
# Riviera Marine Assurances
# ============================================================

import sys
import os
import threading
import socket
import time
import webbrowser
import subprocess

# ── Résolution des chemins (compatible PyInstaller) ──────────
def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_DIR = get_app_dir()

# ── Créer les dossiers nécessaires ──────────────────────────
for _d in ['data', os.path.join('data', 'documents'),
           'logs', 'backups', 'config']:
    os.makedirs(os.path.join(APP_DIR, _d), exist_ok=True)

# ── Instance unique via fichier .lock ────────────────────────
LOCK_FILE = os.path.join(APP_DIR, 'logs', 'navisur.lock')

def is_already_running():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Vérifier si ce PID est toujours vivant
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
        os.remove(LOCK_FILE)
    return False

def write_lock():
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))

def remove_lock():
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

# ── Trouver un port libre ────────────────────────────────────
def find_free_port(start=5000, max_tries=20):
    for port in range(start, start + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError("Aucun port disponible entre {} et {}".format(start, start + max_tries))

# ── Attendre que Flask réponde ────────────────────────────────
def wait_for_flask(port, timeout=30):
    import urllib.request
    url = f'http://127.0.0.1:{port}/'
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False

# ══════════════════════════════════════════════════════════════
# SPLASH SCREEN TKINTER
# ══════════════════════════════════════════════════════════════
import tkinter as tk
from tkinter import ttk

BG_DARK = '#080d1a'
CARD_BG = '#0f1e3c'
GOLD    = '#c9a84c'
WHITE   = '#ffffff'
MUTED   = '#94a3b8'

class SplashScreen:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # Sans barre de titre
        self.root.configure(bg=BG_DARK)
        self.root.attributes('-topmost', True)

        # Centrer la fenêtre (légèrement plus spacieuse et élégante)
        w, h = 500, 360
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f'{w}x{h}+{x}+{y}')

        # Cadre principal avec bordure subtile dorée
        self.main_frame = tk.Frame(self.root, bg=CARD_BG, highlightbackground=GOLD, highlightcolor=GOLD, highlightthickness=1)
        self.main_frame.place(x=4, y=4, width=w-8, height=h-8)

        # Icône de la fenêtre
        ico_path = os.path.join(APP_DIR, 'navisur.ico')
        if os.path.exists(ico_path):
            try:
                self.root.iconbitmap(ico_path)
            except Exception:
                pass

        self._build_ui(w, h)
        self.root.update()

    def _build_ui(self, w, h):
        # Logo image si disponible
        logo_path = os.path.join(APP_DIR, 'navisur_256.png')
        if os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path).resize((82, 82), Image.LANCZOS)
                self._photo = ImageTk.PhotoImage(img)
                tk.Label(self.main_frame, image=self._photo, bg=CARD_BG).pack(pady=(28, 6))
            except Exception:
                tk.Label(self.main_frame, text='⚓', font=('Georgia', 38), fg=GOLD, bg=CARD_BG).pack(pady=(28, 6))
        else:
            tk.Label(self.main_frame, text='⚓', font=('Georgia', 38), fg=GOLD, bg=CARD_BG).pack(pady=(28, 6))

        # Titre
        tk.Label(self.main_frame, text='NAVISUR',
                 font=('Georgia', 26, 'bold'), fg=GOLD, bg=CARD_BG).pack()

        # Sous-titre
        tk.Label(self.main_frame, text='CRM Courtage & Gestion Plaisance',
                 font=('Segoe UI', 12, 'bold'), fg=WHITE, bg=CARD_BG).pack(pady=(2, 2))

        # Société
        tk.Label(self.main_frame, text='Riviera Marine Assurances',
                 font=('Segoe UI', 9), fg=MUTED, bg=CARD_BG).pack(pady=(0, 18))

        # Barre de progression moderne
        style = ttk.Style()
        style.theme_use('default')
        style.configure('ModernGold.Horizontal.TProgressbar',
                        troughcolor='#080d1a',
                        background=GOLD,
                        bordercolor=CARD_BG,
                        lightcolor=GOLD,
                        darkcolor=GOLD)
        self.progress = ttk.Progressbar(self.main_frame, style='ModernGold.Horizontal.TProgressbar',
                                         length=380, mode='indeterminate')
        self.progress.pack(pady=(0, 14))
        self.progress.start(10)

        # Message statut
        self.status_var = tk.StringVar(value='Initialisation du système...')
        tk.Label(self.main_frame, textvariable=self.status_var,
                 font=('Segoe UI', 9), fg=MUTED, bg=CARD_BG).pack()

        # Version & Mode
        tk.Label(self.main_frame, text='NAVISUR v9.9 — 100% Local & Sécurisé',
                 font=('Segoe UI', 8), fg='#475569', bg=CARD_BG).pack(side=tk.BOTTOM, pady=10)

    def set_status(self, msg):
        try:
            self.status_var.set(msg)
            self.root.update()
        except Exception:
            pass

    def show_error(self, msg):
        """Remplace le contenu par un message d'erreur."""
        try:
            self.progress.stop()
            self.status_var.set('')
            # Frame erreur moderne
            frame = tk.Frame(self.main_frame, bg='#7f1d1d', bd=0)
            frame.place(x=20, y=240, width=452, height=60)
            tk.Label(frame, text=msg, font=('Segoe UI', 9), fg='#fecaca', bg='#7f1d1d',
                     wraplength=430, justify='center').pack(expand=True)

            log_dir = os.path.join(APP_DIR, 'logs')
            btn_frame = tk.Frame(self.main_frame, bg=CARD_BG)
            btn_frame.place(x=20, y=308, width=452, height=30)
            tk.Button(btn_frame, text='Ouvrir les logs', fg=CARD_BG, bg=GOLD,
                      font=('Segoe UI', 9, 'bold'), bd=0, padx=10,
                      command=lambda: subprocess.Popen(f'explorer "{log_dir}"')).pack(side=tk.LEFT, padx=4)
            tk.Button(btn_frame, text='Quitter', fg=WHITE, bg='#374151',
                      font=('Segoe UI', 9), bd=0, padx=10,
                      command=lambda: sys.exit(1)).pack(side=tk.LEFT)
            self.root.update()
        except Exception:
            pass

    def close(self):
        try:
            self.progress.stop()
            self.root.destroy()
        except Exception:
            pass

    def update(self):
        try:
            self.root.update()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# DÉMARRAGE FLASK EN THREAD
# ══════════════════════════════════════════════════════════════
flask_error = None
flask_port  = None

def start_flask(port):
    global flask_error
    try:
        # Ajouter _MEIPASS (PyInstaller) et APP_DIR au path
        if hasattr(sys, '_MEIPASS') and sys._MEIPASS not in sys.path:
            sys.path.insert(0, sys._MEIPASS)
        if APP_DIR not in sys.path:
            sys.path.insert(0, APP_DIR)

        # Variables d'environnement pour que app.py trouve ses ressources
        os.environ['NAVISUR_APP_DIR'] = APP_DIR

        from app import app
        app.run(host='127.0.0.1', port=port, debug=False,
                use_reloader=False, threaded=True)
    except Exception as e:
        flask_error = str(e)
        import traceback
        try:
            log_file = os.path.join(APP_DIR, 'logs', 'navisur.log')
            with open(log_file, 'a', encoding='utf-8') as lf:
                lf.write(f'\n[FATAL] Launcher Flask error: {e}\n')
                traceback.print_exc(file=lf)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
# VÉRIFICATION WEBVIEW2
# ══════════════════════════════════════════════════════════════
def check_webview2():
    """Vérifie que Microsoft Edge WebView2 Runtime est installé."""
    import winreg
    keys_to_check = [
        r'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
        r'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    ]
    for key_path in keys_to_check:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            winreg.CloseKey(key)
            return True
        except Exception:
            pass
    return False


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    # Instance unique
    if is_already_running():
        # Mettre au premier plan via signal
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, "NAVISUR — CRM Courtage Plaisance")
        if hwnd:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        return
    write_lock()

    # Splash screen
    splash = SplashScreen()
    splash.set_status('Initialisation...')
    splash.update()

    # Trouver un port libre
    try:
        port = find_free_port(5000)
    except Exception as e:
        splash.show_error(f"Impossible de trouver un port disponible.\n{e}")
        splash.root.mainloop()
        return

    global flask_port
    flask_port = port

    # Démarrer Flask en thread
    splash.set_status(f'Démarrage du serveur (port {port})...')
    flask_thread = threading.Thread(target=start_flask, args=(port,), daemon=True)
    flask_thread.start()

    # Attendre que Flask soit prêt (timeout 30s)
    splash.set_status('Chargement de NAVISUR...')
    ready = False
    deadline = time.time() + 60  # 60s timeout (init_db peut prendre du temps)
    attempt = 0
    while time.time() < deadline:
        if flask_error:
            break
        attempt += 1
        try:
            import urllib.request
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=2) as resp:
                # Accepter 200 ET 500 — Flask répond, même si l'appli a une erreur DB
                # La vraie validation est que Flask est UP, pas que la page est parfaite
                ready = True
                break
        except urllib.error.HTTPError as he:
            # 500 = Flask tourne mais l'appli a une erreur — on ouvre quand même
            if he.code == 500:
                ready = True
                break
        except Exception:
            pass
        # Mise à jour du splash toutes les 0.5s
        if attempt % 2 == 0:
            elapsed = int(time.time() - (deadline - 60))
            splash.set_status(f'Initialisation... ({elapsed}s)')
        time.sleep(0.5)
        splash.update()

    if not ready or flask_error:
        msg = flask_error or "NAVISUR n'a pas pu demarrer dans le delai imparti."
        splash.show_error(f"{msg}\nConsultez logs/navisur.log")
        splash.root.mainloop()
        remove_lock()
        return

    splash.set_status('Ouverture de l\'interface...')
    splash.update()

    # Essayer pywebview
    webview_ok = False
    try:
        import webview

        # Vérifier WebView2
        wv2_ok = True
        try:
            wv2_ok = check_webview2()
        except Exception:
            pass  # Pas sur Windows ou vérification impossible

        if not wv2_ok:
            raise ImportError("WebView2 non disponible")

        # Lire la position/taille sauvegardée
        config_path = os.path.join(APP_DIR, 'config', 'window_state.json')
        width, height = 1400, 900
        maximized = True
        try:
            import json
            with open(config_path) as f:
                state = json.load(f)
                width = state.get('width', 1400)
                height = state.get('height', 900)
                maximized = state.get('maximized', True)
        except Exception:
            pass

        # Fermer le splash
        splash.close()

        def on_closed():
            """Appelé quand la fenêtre pywebview est fermée."""
            # Sauvegarder l'état de la fenêtre
            try:
                import json
                w_obj = webview.windows[0] if webview.windows else None
                if w_obj:
                    state = {'width': w_obj.width, 'height': w_obj.height,
                             'maximized': False}
                    with open(config_path, 'w') as f:
                        json.dump(state, f)
            except Exception:
                pass
            # Shutdown Flask
            try:
                import urllib.request
                urllib.request.urlopen(f'http://127.0.0.1:{port}/shutdown', timeout=2)
            except Exception:
                pass
            remove_lock()

        window = webview.create_window(
            title='NAVISUR — CRM Courtage Plaisance',
            url=f'http://127.0.0.1:{port}/',
            width=width,
            height=height,
            min_size=(1024, 700),
            resizable=True,
            text_select=True,
            confirm_close=True,
        )
        window.events.closed += on_closed

        webview.start(
            debug=False,
            http_server=False,
        )

        if maximized:
            try:
                window.maximize()
            except Exception:
                pass

        webview_ok = True

    except Exception as e:
        # Fallback : ouvrir dans Edge en mode app
        try:
            splash.close()
        except Exception:
            pass
        url = f'http://127.0.0.1:{port}/'
        edge_app_cmd = (
            f'"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"'
            f' --app={url} --window-size=1400,900'
        )
        try:
            subprocess.Popen(edge_app_cmd, shell=True)
        except Exception:
            webbrowser.open(url)

        # Attendre que l'utilisateur ferme
        try:
            import tkinter as tk2
            root2 = tk2.Tk()
            root2.withdraw()
            root2.mainloop()
        except Exception:
            while True:
                time.sleep(1)

    if not webview_ok:
        remove_lock()


if __name__ == '__main__':
    # Masquer le terminal sur Windows
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except Exception:
            pass
    main()
