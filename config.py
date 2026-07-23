"""config.py — Chemins, app Flask, constantes"""
import os, sys
from flask import Flask

# ── Chemins ──
def get_base_dir():
    env = os.environ.get('NAVISUR_APP_DIR')
    if env: return env
    if getattr(sys, 'frozen', False): return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_dir():
    if getattr(sys, 'frozen', False): return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR     = get_base_dir()
RESOURCE_DIR = get_resource_dir()

def get_path(*parts):     return os.path.join(BASE_DIR, *parts)
def get_resource(*parts):  return os.path.join(RESOURCE_DIR, *parts)

# Dossiers données
for _d in ['data', os.path.join('data','documents'), 'logs', 'backups', 'config', 'migrations']:
    os.makedirs(get_path(_d), exist_ok=True)

DATABASE      = get_path('data', 'navisur.db')
UPLOAD_FOLDER = get_path('data', 'documents')
BACKUP_DIR    = get_path('backups')
LOG_FILE      = get_path('logs', 'navisur.log')
CONFIG_DIR    = get_path('config')

# ── Flask app ──
app = Flask(__name__,
    template_folder=get_resource('templates'),
    static_folder=get_resource('static'))

# Secret key (surchargé par security_bootstrap)
app.secret_key = 'riviera-marine-courtage-plaisance-2024'
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

# ── Constantes métier ──
ALLOWED_EXTENSIONS = {'pdf','png','jpg','jpeg','gif','webp','doc','docx','xls','xlsx','csv',
                      'txt','odt','ods','zip','msg','eml'}

PRODUITS_PLAISANCE = [
    'Assurance Plaisance','Assurance Yacht & Grande Plaisance','Assurance Fluvial',
    'Assurance Jet Ski','Assurance Pro — Concession','Assurance Pro — Broker',
    'Assurance Pro — Réparateur','Assurance Pro — Charter',
    'Assurance Multicoques','Autre',
]

TYPES_DOCUMENTS = [
    "CNI / Passeport","RIB / Coordonnées bancaires","Permis mer (côtier)",
    "Permis hauturier","Permis fluvial","Acte de francisation",
    "Certificat d'immatriculation","Carte de circulation","Contrat d'assurance",
    "Avenant","Devis","Attestation d'assurance","Bordereau de commission",
    "Facture","Justificatif de domicile","Kbis / Extrait SIREN",
    "Rapport d'expertise","Constat amiable","Relevé de sinistralité",
    "Mandat / Procuration","Autre document",
]

STATUTS_CONTRAT = [
    ('en_cours','En cours','badge-en_cours'),
    ('devis_envoye','Devis envoyé','badge-devis'),
    ('attente_pieces','En attente de pièces','badge-attente'),
    ('transmis_cie','Transmis à la compagnie','badge-attendu'),
    ('accepte_cie','Accepté — attente police','badge-accepte_cie'),
    ('a_renouveler','À renouveler','badge-renouveler'),
    ('suspendu','Suspendu / Impayé','badge-suspendu'),
    ('renouvele','Renouvelé','badge-inactif'),
    ('resilie_client','Résilié (client)','badge-resilie'),
    ('resilie_cie','Résilié (compagnie)','badge-resilie'),
    ('echu','Échu','badge-echu'),
]

TRANSITIONS_CONTRAT = {
    'devis_envoye':   ['attente_pieces','transmis_cie','en_cours','echu'],
    'attente_pieces': ['transmis_cie','en_cours','echu'],
    'transmis_cie':   ['accepte_cie','attente_pieces','echu'],
    'accepte_cie':    ['en_cours'],
    'en_cours':       ['suspendu','a_renouveler','transmis_cie','resilie_client','resilie_cie','echu','renouvele'],
    'suspendu':       ['en_cours','resilie_cie','echu'],
    'a_renouveler':   ['en_cours','renouvele','echu'],
}

STATUTS_DEVIS = [
    ('en_attente','⏳ En attente de réponse','badge-attendu'),
    ('accepte','✅ Accepté','badge-clos'),
    ('refuse','❌ Refusé','badge-resilie'),
    ('sans_suite','⛔ Sans suite','badge-inactif'),
    ('expire','⏰ Expiré','badge-echu'),
]

STATUTS_COMMISSION = [
    ('attendue','⏳ Attendue'),('releve_recu','📄 Relevé reçu'),
    ('encaissee','✅ Encaissée'),('retard','⚠️ En retard'),
    ('contestee','❌ Contestée'),('annulee','🚫 Annulée'),
]

NATURES_RECETTE = [
    ('commission_apport','Commission d\'apport (nouveau contrat)'),
    ('commission_renouvellement','Commission de renouvellement'),
    ('surcommission','Surcommission / Bonus volume'),
    ('frais_courtage','Frais de courtage'),
    ('honoraire_conseil','Honoraire de conseil'),('autre','Autre'),
]

MODES_REGLEMENT = ['virement','cheque','especes','prelevement','autre']
