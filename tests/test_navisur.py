import pytest
import os
import sys

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
from core import app as flask_app, get_db, init_db, check_db_integrity
from security_bootstrap import init_auth_db

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    init_db()
    init_auth_db()
    with flask_app.test_client() as client:
        yield client

def test_db_integrity(client):
    init_db()
    ok, msg = check_db_integrity()
    assert ok is True

def test_login_and_dashboard(client):
    res = client.post('/login', data={
        'email': 'admin@navisur.local',
        'password': 'admin123'
    }, follow_redirects=True)
    assert res.status_code == 200

def test_clients_page(client):
    client.post('/login', data={
        'email': 'admin@navisur.local',
        'password': 'admin123'
    }, follow_redirects=True)
    res = client.get('/clients')
    assert res.status_code == 200

def test_contrats_page(client):
    client.post('/login', data={
        'email': 'admin@navisur.local',
        'password': 'admin123'
    }, follow_redirects=True)
    res = client.get('/contrats')
    assert res.status_code == 200
