"""
NAVISUR — Lanceur Bureau
========================
Ouvre le CRM dans une fenêtre native sans navigateur visible.
Compatible Python 3.8 à 3.14+ — aucune dépendance externe requise.
"""

import sys
import os
import threading
import time
import socket
import subprocess
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

PORT  = 5000
HOST  = '127.0.0.1'
TITRE = 'NAVISUR — Riviera Marine Assurances'


def find_free_port(start=5000):
    for p in range(start, start + 20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((HOST, p))
                return p
        except OSError:
            continue
    return start


def wait_for_server(port, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.2)
    return False


def run_flask(port):
    """Lance Flask sans aucune variable d'environnement werkzeug."""
    # Nettoyer les variables qui causent WERKZEUG_SERVER_FD
    for var in ['WERKZEUG_RUN_MAIN', 'WERKZEUG_SERVER_FD']:
        os.environ.pop(var, None)

    import logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('flask').setLevel(logging.ERROR)

    from app import app, init_db
    init_db()

    # use_reloader=False et threaded=True évitent le double process
    app.run(
        host=HOST,
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True,
    )


def find_browser_windows():
    candidates = [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe'),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def launch_app_window(url):
    profile_dir = os.path.join(BASE_DIR, '.navisur_profile')

    if sys.platform == 'win32':
        browser = find_browser_windows()
        if browser:
            args = [
                browser,
                f'--app={url}',
                '--window-size=1440,900',
                '--window-position=50,30',
                f'--user-data-dir={profile_dir}',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-background-networking',
            ]
            print(f'  ✅ Navigateur : {os.path.basename(browser)}')
            print('  🪟 Ouverture en mode application...')
            try:
                return subprocess.Popen(args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f'  ⚠️  Erreur : {e}')

        print('  ℹ️  Edge/Chrome non trouvé — ouverture navigateur par défaut')
        webbrowser.open(url)
        return None

    elif sys.platform == 'darwin':
        for app_path in [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
            '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        ]:
            if os.path.isfile(app_path):
                return subprocess.Popen(
                    [app_path, f'--app={url}', '--window-size=1440,900',
                     f'--user-data-dir={profile_dir}'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        webbrowser.open(url)
        return None

    else:
        for cmd in ['google-chrome', 'chromium-browser', 'chromium', 'microsoft-edge']:
            try:
                return subprocess.Popen(
                    [cmd, f'--app={url}', '--window-size=1440,900'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                continue
        webbrowser.open(url)
        return None


def main():
    port = find_free_port(PORT)
    url  = f'http://{HOST}:{port}'

    print()
    print('=' * 52)
    print(f'  ⚓  {TITRE}')
    print('=' * 52)
    print(f'  Démarrage du serveur (port {port})...')

    flask_thread = threading.Thread(target=run_flask, args=(port,), daemon=True)
    flask_thread.start()

    # Attendre que Flask soit prêt
    print('  Chargement en cours...')
    ready = wait_for_server(port, timeout=25)

    if not ready:
        print()
        print('  ❌ Le serveur n\'a pas démarré.')
        print(f'  → Vérifiez que le port {port} est libre.')
        print(f'  → URL manuelle : {url}')
        # Ouvrir quand même le navigateur — Flask tourne peut-être
        webbrowser.open(url)
        input('\n  Appuyez sur Entrée pour quitter...')
        return

    print(f'  ✅ Serveur prêt !')

    browser_proc = launch_app_window(url)

    print(f'  🌐 URL : {url}')
    print('  Fermez la fenêtre NAVISUR pour quitter (ou Ctrl+C).')
    print('=' * 52)
    print()

    try:
        if browser_proc:
            browser_proc.wait()
            print('\n  Fenêtre fermée — arrêt du serveur.')
        else:
            while flask_thread.is_alive():
                time.sleep(1)
    except KeyboardInterrupt:
        print('\n  Arrêt demandé (Ctrl+C).')

    if browser_proc:
        try:
            browser_proc.terminate()
        except Exception:
            pass

    print('  Au revoir !\n')


if __name__ == '__main__':
    main()
