#!/bin/bash

set -e

# === CONFIGURATION ===
DOMAIN="ec2-54-161-71-105.compute-1.amazonaws.com"  # Use EC2 public DNS or your own domain
CERT_DIR="$HOME/nginx-reverse-proxy/certs"
DAYS_VALID=365

# === Create certs directory if needed ===
mkdir -p "$CERT_DIR"

echo "🔐 Generating self-signed certificate for $DOMAIN..."

# === Generate self-signed cert + key ===
openssl req -x509 -nodes -days "$DAYS_VALID" -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=$DOMAIN"

echo "✅ Self-signed certificate created:"
echo "   - $CERT_DIR/fullchain.pem"
echo "   - $CERT_DIR/privkey.pem"

# === Example nginx block (for reference) ===
cat <<EOF

📄 Add this block to your nginx conf (e.g., conf.d/selfsigned.conf):

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/privkey.pem;

    location / {
        proxy_pass http://<your-service-host>:<port>;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}

⚠️ Browsers will show a warning for self-signed certs. Use Let's Encrypt for trusted certs.
EOF
