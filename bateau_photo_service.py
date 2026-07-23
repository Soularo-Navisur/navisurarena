"""
bateau_photo_service.py — NAVISUR v9.9
Recherche de photos de bateaux via Wikipedia/Wikimedia (gratuit, sans clé API).
Cascade de 5 étapes, timeout 3s par étape, cache en mémoire.
"""

import urllib.request
import urllib.parse
import json
import re

# ── Cache session (réinitialisé à chaque redémarrage) ─────────────────
_cache = {}

# ── Emojis par type ────────────────────────────────────────────────────
_EMOJIS = {
    'voilier':      '⛵',
    'Voilier':      '⛵',
    'yacht':        '⛵',
    'Yacht à moteur': '🚤',
    'moteur':       '🚤',
    'semi-rigide':  '🚤',
    'Semi-rigide':  '🚤',
    'catamaran':    '⛵',
    'Catamaran':    '⛵',
    'trimaran':     '⛵',
    'jet ski':      '🏄',
    'Jet Ski':      '🏄',
    'peniche':      '🚢',
    'Péniche':      '🚢',
    'fluvial':      '🚢',
    'pro':          '⚓',
    'charter':      '⚓',
}

TIMEOUT = 3  # secondes par requête


def _get_emoji(type_bateau):
    if not type_bateau:
        return '⛵'
    tb = type_bateau.lower()
    for k, v in _EMOJIS.items():
        if k.lower() in tb:
            return v
    return '⛵'


def _fetch_json(url, timeout=TIMEOUT):
    """Fetch JSON avec timeout, retourne None si erreur."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'NAVISUR/9.9 (bateau photo service)'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        return None


def _clean_query(s):
    """Nettoie une chaîne pour une URL de recherche."""
    return re.sub(r'[^\w\s\-\.]', '', s or '').strip()


def _etape1_wikipedia_fr(marque, modele):
    """Étape 1 : Résumé Wikipedia FR pour 'Marque Modele'."""
    query = f"{marque} {modele}".strip()
    slug = urllib.parse.quote(query.replace(' ', '_'))
    url = f"https://fr.wikipedia.org/api/rest_v1/page/summary/{slug}"
    data = _fetch_json(url)
    if data and data.get('originalimage', {}).get('source'):
        return {
            'succes': True,
            'image_url': data['originalimage']['source'],
            'source': 'Wikipédia FR',
            'titre': data.get('title', query),
            'description': data.get('extract', '')[:200],
            'etape_trouvee': 1,
            'images': [data['originalimage']['source']],
        }
    # Essayer aussi thumbnail
    if data and data.get('thumbnail', {}).get('source'):
        return {
            'succes': True,
            'image_url': data['thumbnail']['source'],
            'source': 'Wikipédia FR',
            'titre': data.get('title', query),
            'description': data.get('extract', '')[:200],
            'etape_trouvee': 1,
            'images': [data['thumbnail']['source']],
        }
    return None


def _etape2_commons(marque, modele):
    """Étape 2 : Wikimedia Commons — recherche images."""
    query = f"{marque} {modele} bateau"
    params = urllib.parse.urlencode({
        'action': 'query',
        'list': 'search',
        'srsearch': query,
        'srnamespace': '6',
        'srlimit': '5',
        'format': 'json',
    })
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    data = _fetch_json(url)
    results = (data or {}).get('query', {}).get('search', [])
    images = []
    for item in results:
        title = item.get('title', '')
        if title.startswith('File:'):
            fname = urllib.parse.quote(title[5:].replace(' ', '_'))
            # Construire l'URL Wikimedia
            img_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{fname}?width=600"
            images.append(img_url)
    if images:
        return {
            'succes': True,
            'image_url': images[0],
            'source': 'Wikimedia Commons',
            'titre': f"{marque} {modele}",
            'description': '',
            'etape_trouvee': 2,
            'images': images,
        }
    return None


def _etape3_wikipedia_en(marque, modele):
    """Étape 3 : Résumé Wikipedia EN."""
    query = f"{marque} {modele}"
    slug = urllib.parse.quote(query.replace(' ', '_'))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    data = _fetch_json(url)
    for key in ('originalimage', 'thumbnail'):
        if data and data.get(key, {}).get('source'):
            return {
                'succes': True,
                'image_url': data[key]['source'],
                'source': 'Wikipedia EN',
                'titre': data.get('title', query),
                'description': data.get('extract', '')[:200],
                'etape_trouvee': 3,
                'images': [data[key]['source']],
            }
    return None


def _etape4_marque_generique(marque, type_bateau):
    """Étape 4 : Recherche générique par marque."""
    terme = type_bateau or 'bateau'
    for lang, base in [('fr', 'fr.wikipedia.org'), ('en', 'en.wikipedia.org')]:
        query = f"{marque} {terme}"
        slug = urllib.parse.quote(query.replace(' ', '_'))
        url = f"https://{base}/api/rest_v1/page/summary/{slug}"
        data = _fetch_json(url)
        for key in ('originalimage', 'thumbnail'):
            if data and data.get(key, {}).get('source'):
                return {
                    'succes': True,
                    'image_url': data[key]['source'],
                    'source': f'Wikipédia ({lang.upper()})',
                    'titre': data.get('title', query),
                    'description': data.get('extract', '')[:200],
                    'etape_trouvee': 4,
                    'images': [data[key]['source']],
                }
    return None


def chercher_photo(marque, modele, type_bateau='bateau'):
    """
    Cherche une photo de référence pour un bateau.
    Retourne un dict avec succes, image_url, source, titre, description.
    """
    marque = _clean_query(marque)
    modele = _clean_query(modele)

    # Clé de cache
    cle = f"{marque}_{modele}".lower().strip()
    if cle in _cache:
        return _cache[cle]

    # Cascade des étapes
    etapes = []
    if marque and modele:
        etapes += [
            lambda: _etape1_wikipedia_fr(marque, modele),
            lambda: _etape2_commons(marque, modele),
            lambda: _etape3_wikipedia_en(marque, modele),
        ]
    if marque:
        etapes.append(lambda: _etape4_marque_generique(marque, type_bateau))

    for fn in etapes:
        try:
            result = fn()
            if result:
                _cache[cle] = result
                return result
        except Exception:
            continue

    # Fallback emoji
    fallback = {
        'succes': False,
        'fallback_emoji': _get_emoji(type_bateau),
        'message': f"Aucune photo trouvée pour {marque} {modele}",
    }
    _cache[cle] = fallback
    return fallback
