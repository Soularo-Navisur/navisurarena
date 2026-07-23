#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# NAVISUR — Script de déploiement automatique sur VPS IONOS
# Exécuter en root sur un VPS Ubuntu 22.04 / Debian 12
# Usage : bash setup_ionos.sh votredomaine.com
# ══════════════════════════════════════════════════════════════════

set -e
DOMAIN=${1:-"navisur.votredomaine.fr"}
APP_DIR="/opt/navisur"
VENV_DIR="$APP_DIR/venv"
USER="navisur"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NAVISUR — Installation VPS IONOS"
echo "  Domaine : $DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Dépendances système
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# 2. Créer l'utilisateur applicatif
id -u $USER &>/dev/null || useradd -m -s /bin/bash $USER
mkdir -p $APP_DIR
chown $USER:$USER $APP_DIR

# 3. Environnement Python
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip -q
$VENV_DIR/bin/pip install flask gunicorn flask-cors pillow openpyxl -q
echo "  ✅ Python + dépendances OK"

# 4. Dossiers de données
mkdir -p $APP_DIR/{data/documents,logs,backups,config}
chown -R $USER:$USER $APP_DIR

# 5. Service systemd
cat > /etc/systemd/system/navisur.service << SERVICE
[Unit]
Description=NAVISUR CRM Riviera Marine Assurances
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
Environment="NAVISUR_APP_DIR=$APP_DIR"
ExecStart=$VENV_DIR/bin/gunicorn \\
    --workers 2 \\
    --bind 127.0.0.1:5000 \\
    --timeout 120 \\
    --access-logfile $APP_DIR/logs/access.log \\
    --error-logfile $APP_DIR/logs/error.log \\
    app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# 6. Configuration nginx
cat > /etc/nginx/sites-available/navisur << NGINX
server {
    listen 80;
    server_name $DOMAIN;

    # Taille max upload (documents)
    client_max_body_size 50M;

    # NAVISUR app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120;
    }

    # Fichiers statiques servis directement par nginx (plus rapide)
    location /static {
        alias $APP_DIR/static;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX

ln -sf /etc/nginx/sites-available/navisur /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo "  ✅ Nginx configuré"

# 7. HTTPS automatique (Let's Encrypt)
echo "  🔒 Configuration HTTPS..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect
echo "  ✅ HTTPS activé"

# 8. Activer et démarrer le service
systemctl daemon-reload
systemctl enable navisur
systemctl start navisur
echo "  ✅ Service NAVISUR démarré"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ NAVISUR déployé avec succès !"
echo "  🌐 Accès CRM    : https://$DOMAIN"
echo "  👤 Portail client : https://$DOMAIN/portail"
echo ""
echo "  PROCHAINES ÉTAPES :"
echo "  1. Copier vos fichiers NAVISUR dans $APP_DIR/"
echo "     (app.py, core.py, routes/, templates/, static/)"
echo "  2. Copier votre navisur.db dans $APP_DIR/data/"
echo "  3. sudo systemctl restart navisur"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
