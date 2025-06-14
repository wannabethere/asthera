#!/bin/bash

set -e

# === CONFIG ===
DOMAIN="ec2-54-161-71-105.compute-1.amazonaws.com"  # Use your actual DNS/domain
EMAIL="admin@example.com"                           # Your email for Let's Encrypt
PROXY_DIR="$HOME/nginx-reverse-proxy"
CERT_DIR="$PROXY_DIR/certs"
NGINX_CONTAINER="nginx-proxy"
SERVICE_NAME="app1"                                 # For example
SERVICE_PORT=8015

# === Stop NGINX container to free port 80 ===
echo "🛑 Stopping NGINX container to allow certbot to bind to port 80..."
docker stop "$NGINX_CONTAINER" || true

# === Install certbot on Amazon Linux ===
if ! command -v certbot &>/dev/null; then
  echo "🔧 Installing Certbot..."
  sudo yum install -y certbot
fi

# === Generate certificate ===
echo "🔐 Requesting Let's Encrypt certificate for $DOMAIN..."
sudo certbot certonly --standalone --non-interactive --agree-tos \
  -m "$EMAIL" -d "$DOMAIN"

# === Copy certs into Docker volume path ===
mkdir -p "$CERT_DIR"
cp /etc/letsencrypt/live/"$DOMAIN"/fullchain.pem "$CERT_DIR/fullchain.pem"
cp /etc/letsencrypt/live/"$DOMAIN"/privkey.pem "$CERT_DIR/privkey.pem"

echo "📂 Certificates copied to $CERT_DIR"

# === Generate HTTPS NGINX config ===
CONF="$PROXY_DIR/conf.d/$SERVICE_NAME-ssl.conf"
cat <<EOF > "$CONF"
server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/privkey.pem;

    location / {
        proxy_pass http://localhost:$SERVICE_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# === Restart NGINX container ===
echo "🚀 Restarting NGINX with HTTPS config..."
cd "$PROXY_DIR"
docker-compose up -d

echo "✅ HTTPS is now enabled for: https://$DOMAIN"
