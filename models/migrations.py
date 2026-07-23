"""models/migrations.py — Système de migrations SQLite custom"""
import os, sqlite3
from config import DATABASE, get_path
from utils import nlog

MIGRATIONS_DIR = get_path('migrations')

def get_version():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT version FROM __schema_version WHERE id=1").fetchone()
        return row['version'] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()

def set_version(v):
    conn = sqlite3.connect(DATABASE)
    conn.execute("UPDATE __schema_version SET version=? WHERE id=1", (v,))
    conn.commit(); conn.close()

def list_migrations():
    if not os.path.exists(MIGRATIONS_DIR): return []
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR)
                   if f.endswith('.sql') and f.split('_')[0].isdigit())
    return files

def run_migrations():
    current = get_version()
    files = list_migrations()
    for f in files:
        num = int(f.split('_')[0])
        if num > current:
            path = os.path.join(MIGRATIONS_DIR, f)
            with open(path, 'r', encoding='utf-8') as fh:
                sql = fh.read()
            conn = sqlite3.connect(DATABASE)
            try:
                conn.executescript(sql)
                conn.commit()
                nlog('info', f'Migration {num} appliquée : {f}')
            except Exception as e:
                conn.rollback()
                nlog('error', f'Migration {num} échouée : {e}')
                raise
            finally:
                conn.close()
            set_version(num)
            current = num
    if files:
        nlog('info', f'Schema version = {current}')
