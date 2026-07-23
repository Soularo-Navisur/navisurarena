"""
brevo_service.py — Service d'envoi email centralisé via Brevo
NAVISUR v9.9 — Riviera Marine Assurances

Principe offline-first : si Brevo échoue ou timeout,
bascule silencieuse vers mailto (jamais de crash).
"""
import json
import os
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, datetime

# ── Chemins ─────────────────────────────────────────────────
def _get_app_dir():
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

_CONFIG_FILE = os.path.join(_get_app_dir(), 'config', 'api_keys.json')
_COURTIER_FILE = os.path.join(_get_app_dir(), 'config', 'parametres_courtier.json')
_BREVO_API_URL = 'https://api.brevo.com/v3'
_TIMEOUT = 5  # secondes

# ── Logger minimal (sans dépendance circulaire avec app.py) ──
import logging as _logging
_log = _logging.getLogger('navisur')


def _load_config():
    try:
        with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data):
    try:
        os.makedirs(os.path.dirname(_CONFIG_FILE), exist_ok=True)
        with open(_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def _load_courtier():
    try:
        with open(_COURTIER_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'nom': 'Riviera Marine Assurances',
            'titre': 'Courtier en assurance plaisance',
            'email': 'contact@rivieramarine-assurances.fr',
            'telephone': '',
            'adresse': '',
            'orias': '',
            'site_web': '',
            'signature': (
                'Cordialement,\n\n'
                'Riviera Marine Assurances\n'
                'Courtier en assurance plaisance\n'
                'contact@rivieramarine-assurances.fr'
            )
        }


class BrevoService:
    """Service d'envoi email via API Brevo avec fallback mailto."""

    def __init__(self):
        cfg = _load_config()
        brevo = cfg.get('brevo', {})
        self.api_key = brevo.get('cle', '')
        self.active = brevo.get('active', False) and bool(self.api_key)
        self.expediteur_email = brevo.get('expediteur_email',
                                          'contact@rivieramarine-assurances.fr')
        self.expediteur_nom = brevo.get('expediteur_nom',
                                        'Riviera Marine Assurances')

    def _headers(self):
        return {
            'api-key': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _api_post(self, endpoint, payload):
        """POST vers l'API Brevo. Retourne (code, dict) ou lève une exception."""
        url = f'{_BREVO_API_URL}{endpoint}'
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=self._headers(), method='POST')
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}

    def _api_get(self, endpoint, params=None):
        url = f'{_BREVO_API_URL}{endpoint}'
        if params:
            url += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=self._headers(), method='GET')
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode('utf-8')
            return resp.status, json.loads(body) if body else {}

    # ── Log sécurisé (clé masquée) ──────────────────────────
    def _log_cle(self):
        return self.api_key[:12] + '...' if self.api_key else '(vide)'

    # ────────────────────────────────────────────────────────
    # ENVOI D'EMAIL PRINCIPAL
    # ────────────────────────────────────────────────────────
    def envoyer_email(self,
                      destinataire_email: str,
                      destinataire_nom: str,
                      objet: str,
                      corps_html: str,
                      corps_texte: str = None,
                      pieces_jointes: list = None) -> dict:
        """
        Envoie via Brevo. Si échec → fallback mailto automatique.

        Retourne :
        {
            'succes': bool,
            'message_id': str,   # si succès Brevo
            'erreur': str,       # si échec
            'fallback_mailto': bool,
            'mailto_url': str    # si fallback
        }
        """
        if not self.active:
            return self._fallback_mailto(destinataire_email, objet, corps_texte or corps_html,
                                         raison='Brevo désactivé')

        payload = {
            'sender': {
                'name': self.expediteur_nom,
                'email': self.expediteur_email,
            },
            'to': [{
                'email': destinataire_email,
                'name': destinataire_nom or destinataire_email,
            }],
            'subject': objet,
            'htmlContent': corps_html,
        }
        if corps_texte:
            payload['textContent'] = corps_texte

        if pieces_jointes:
            payload['attachment'] = [
                {
                    'name': pj.get('nom', 'document.pdf'),
                    'content': pj.get('contenu_base64', ''),
                }
                for pj in pieces_jointes
            ]

        try:
            code, resp = self._api_post('/smtp/email', payload)
            message_id = resp.get('messageId', '')
            _log.info(f'Brevo envoi OK → {destinataire_email[:20]}... '
                      f'(clé {self._log_cle()}) messageId={message_id}')
            return {
                'succes': True,
                'message_id': message_id,
                'erreur': None,
                'fallback_mailto': False,
                'mailto_url': '',
            }
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8') if e else ''
            _log.warning(f'Brevo HTTP {e.code} pour {destinataire_email[:20]}... : {detail[:100]}')
            return self._fallback_mailto(destinataire_email, objet, corps_texte or corps_html,
                                         raison=f'HTTP {e.code}')
        except Exception as e:
            _log.warning(f'Brevo erreur pour {destinataire_email[:20]}... : {type(e).__name__}')
            return self._fallback_mailto(destinataire_email, objet, corps_texte or corps_html,
                                         raison=str(e))

    def _fallback_mailto(self, email, objet, corps, raison=''):
        """Construit un lien mailto de fallback."""
        params = urllib.parse.urlencode({'subject': objet, 'body': corps})
        mailto = f'mailto:{urllib.parse.quote(email)}?{params}'
        _log.info(f'Brevo fallback mailto → {email[:20]}... (raison: {raison[:40]})')
        return {
            'succes': False,
            'message_id': '',
            'erreur': raison,
            'fallback_mailto': True,
            'mailto_url': mailto,
        }

    # ────────────────────────────────────────────────────────
    # STATUTS DES EMAILS (ouvertures, clics)
    # ────────────────────────────────────────────────────────
    def verifier_statuts(self, email_client: str, limit: int = 50) -> list:
        """Récupère les événements récents pour un email client."""
        if not self.active:
            return []
        try:
            _, resp = self._api_get('/smtp/statistics/events', {
                'email': email_client,
                'limit': limit,
            })
            events = resp.get('events', [])
            _log.info(f'Brevo statuts : {len(events)} événements pour {email_client[:20]}...')
            return events
        except Exception as e:
            _log.warning(f'Brevo statuts erreur : {e}')
            return []

    # ────────────────────────────────────────────────────────
    # TEST DE CONNEXION
    # ────────────────────────────────────────────────────────
    def tester_connexion(self) -> dict:
        """Envoie un email de test à l'expéditeur."""
        if not self.api_key:
            return {'ok': False, 'message': 'Clé API Brevo non configurée'}
        try:
            result = self.envoyer_email(
                destinataire_email=self.expediteur_email,
                destinataire_nom='Test NAVISUR',
                objet='✅ Test connexion NAVISUR — Brevo opérationnel',
                corps_html=(
                    '<p>Ce message confirme que l\'intégration Brevo dans NAVISUR '
                    'fonctionne correctement.</p>'
                    f'<p>Date : {datetime.now().strftime("%d/%m/%Y à %H:%M")}</p>'
                    '<p>— NAVISUR v9.9</p>'
                ),
            )
            if result['succes']:
                return {'ok': True, 'message': 'Email de test envoyé avec succès ✅'}
            else:
                return {'ok': False, 'message': f'Échec : {result["erreur"]}'}
        except Exception as e:
            return {'ok': False, 'message': str(e)}

    # ────────────────────────────────────────────────────────
    # QUOTA
    # ────────────────────────────────────────────────────────
    def get_quota(self) -> dict:
        """Retourne les informations de quota depuis l'API Brevo."""
        if not self.active:
            return {'aujourd_hui': 0, 'quota_jour': 300,
                    'ce_mois': 0, 'quota_mois': 9000, 'erreur': 'Inactif'}
        try:
            _, resp = self._api_get('/account')
            plan = resp.get('plan', [{}])[0] if resp.get('plan') else {}
            stats = resp.get('statistics', {})
            today_count = stats.get('sentToday', 0)
            month_count = stats.get('sentThisMonth', 0)
            quota_day = plan.get('dailySendingLimit', 300)
            quota_month = plan.get('monthlySendingLimit', 9000)
            _log.info(f'Brevo quota : {today_count}/{quota_day} aujourd\'hui')
            return {
                'aujourd_hui': today_count,
                'quota_jour': quota_day,
                'ce_mois': month_count,
                'quota_mois': quota_month,
                'erreur': None,
            }
        except Exception as e:
            _log.warning(f'Brevo quota erreur : {e}')
            return {'aujourd_hui': 0, 'quota_jour': 300,
                    'ce_mois': 0, 'quota_mois': 9000, 'erreur': str(e)}

    # ────────────────────────────────────────────────────────
    # REMPLACEMENT DE VARIABLES
    # ────────────────────────────────────────────────────────
    def remplacer_variables(self, modele: str, donnees: dict) -> str:
        """
        Remplace les variables {{xxx}} dans un modèle.
        donnees = dict avec clés : client, contrat, devis, sinistre, bateau
        """
        courtier = _load_courtier()

        # Construire le dictionnaire de remplacement
        client = donnees.get('client') or {}
        contrat = donnees.get('contrat') or {}
        devis = donnees.get('devis') or {}
        sinistre = donnees.get('sinistre') or {}
        bateau = donnees.get('bateau') or {}

        civilite = client.get('civilite', '') or ''
        prenom = client.get('prenom', '') or ''
        nom = client.get('nom', '') or ''
        nom_complet = f"{civilite} {prenom} {nom}".strip() if (prenom or nom) else ''

        def fmt_euro(val):
            try:
                return f"{float(val):,.2f} €".replace(',', ' ')
            except Exception:
                return str(val) if val else ''

        def fmt_date(val):
            if not val:
                return ''
            try:
                d = datetime.fromisoformat(str(val)[:10])
                return d.strftime('%d/%m/%Y')
            except Exception:
                return str(val)

        variables = {
            # Client
            '{{civilite}}':      civilite,
            '{{prenom}}':        prenom,
            '{{nom}}':           nom,
            '{{nom_complet}}':   nom_complet,
            '{{email_client}}':  client.get('email', '') or '',
            '{{telephone}}':     client.get('telephone_formate') or client.get('telephone', '') or '',
            # Bateau
            '{{nom_bateau}}':       bateau.get('nom_bateau', '') or '',
            '{{immatriculation}}':  bateau.get('immatriculation', '') or '',
            '{{type_bateau}}':      bateau.get('type_bateau', '') or '',
            # Contrat
            '{{compagnie}}':        contrat.get('compagnie', '') or '',
            '{{n_police}}':         contrat.get('numero', '') or '',
            '{{n_police_cie}}':     contrat.get('numero_police_cie', '') or '',
            '{{prime_ttc}}':        fmt_euro(contrat.get('prime_annuelle')),
            '{{date_effet}}':       fmt_date(contrat.get('date_debut')),
            '{{date_echeance}}':    fmt_date(contrat.get('date_fin')),
            # Devis
            '{{montant_devis}}':    fmt_euro(devis.get('prime_proposee')),
            '{{date_validite}}':    fmt_date(devis.get('date_expiration')),
            '{{compagnie_devis}}':  devis.get('compagnie', '') or '',
            # Sinistre
            '{{n_sinistre}}':       sinistre.get('numero', '') or '',
            '{{n_sinistre_cie}}':   sinistre.get('numero_sinistre_cie', '') or '',
            '{{date_sinistre}}':    fmt_date(sinistre.get('date_sinistre')),
            # Courtier
            '{{courtier_nom}}':     courtier.get('nom', ''),
            '{{courtier_tel}}':     courtier.get('telephone', ''),
            '{{courtier_email}}':   courtier.get('email', ''),
            '{{numero_orias}}':     courtier.get('orias', ''),
            '{{date_du_jour}}':     date.today().strftime('%d/%m/%Y'),
            '{{signature}}':        courtier.get('signature', ''),
            # Compatibilité ancien format {xxx}
            '{prenom}':     prenom,
            '{nom}':        nom,
            '{email}':      client.get('email', '') or '',
            '{telephone}':  client.get('telephone', '') or '',
            '{num_contrat}': contrat.get('numero', '') or '',
            '{type_assurance}': contrat.get('type_assurance', '') or '',
            '{compagnie}':  contrat.get('compagnie', '') or '',
            '{date_echeance}': fmt_date(contrat.get('date_fin')),
            '{prime_annuelle}': fmt_euro(contrat.get('prime_annuelle')),
            '{nom_bateau}': bateau.get('nom_bateau', '') or '',
            '{cabinet_nom}': courtier.get('nom', ''),
            '{cabinet_telephone}': courtier.get('telephone', ''),
            '{cabinet_email}': courtier.get('email', ''),
            '{cabinet_orias}': courtier.get('orias', ''),
        }

        result = modele
        for var, val in variables.items():
            result = result.replace(var, str(val))
        return result


# ── Instance globale (singleton) ─────────────────────────────
_brevo_instance = None

def get_brevo() -> BrevoService:
    """Retourne l'instance singleton de BrevoService."""
    global _brevo_instance
    if _brevo_instance is None:
        _brevo_instance = BrevoService()
    return _brevo_instance

def reload_brevo():
    """Recharge l'instance (après modification de la config)."""
    global _brevo_instance
    _brevo_instance = None
    return get_brevo()
