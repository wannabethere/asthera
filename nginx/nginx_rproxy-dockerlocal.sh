#!/bin/bash

set -e

# === USER CONFIGURATION ===
DOMAIN="ec2-54-161-71-105.compute-1.amazonaws.com"                  # Replace with your domain
EMAIL="admin@flowharmonic.com"             # For Certbot registration
NETWORKS=("app-network" "analytics-network")  # Add more as needed
PROXY_DIR="$HOME/nginx-reverse-proxy"
CERTBOT_MODE="manual"                     # Set to 'manual' or 'auto'

# === DIRECTORY SETUP ===
echo "📁 Creating directory structure..."
mkdir -p "$PROXY_DIR"/{conf.d,certs,html,logs}

# === GENERATE MULTI-SERVICE NGINX CONFIG ===
cat <<EOF > "$PROXY_DIR/conf.d/multi-services.conf"
# HTTP config for multiple services

# Route to app-service (on app-network)
server {
    listen 80;
    server_name unstructured.ec2-54-161-71-105.compute-1.amazonaws.com;

    location / {
        proxy_pass http://ec2-54-161-71-105.compute-1.amazonaws.com:8015;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}

# Route to analytics-service (on analytics-network)
server {
    listen 80;
    server_name analytics.ec2-54-161-71-105.compute-1.amazonaws.com;

    location / {
        proxy_pass http://ec2-54-161-71-105.compute-1.amazonaws.com:8020;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# === CREATE DOCKER COMPOSE FILE ===
echo "🐳 Generating docker-compose.yml..."
cat <<EOF > "$PROXY_DIR/docker-compose.yml"
version: '3.8'

services:
  nginx:
    image: nginx:latest
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./conf.d:/etc/nginx/conf.d
      - ./html:/usr/share/nginx/html
      - ./certs:/etc/letsencrypt
      - ./logs:/var/log/nginx
    restart: always
    networks:
EOF

for net in "${NETWORKS[@]}"; do
  echo "      - $net" >> "$PROXY_DIR/docker-compose.yml"
done

echo "" >> "$PROXY_DIR/docker-compose.yml"
echo "networks:" >> "$PROXY_DIR/docker-compose.yml"

for net in "${NETWORKS[@]}"; do
  echo "  $net:" >> "$PROXY_DIR/docker-compose.yml"
  echo "    external: true" >> "$PROXY_DIR/docker-compose.yml"
done

# === CREATE NETWORKS IF NOT PRESENT ===
for net in "${NETWORKS[@]}"; do
  if ! docker network ls | grep -q "$net"; then
    echo "🔌 Creating Docker network: $net"
    docker network create "$net"
  fi
done

# === CERTBOT SETUP (OPTIONAL) ===
if [ "$CERTBOT_MODE" == "auto" ]; then
    echo "🔐 Installing and running Certbot..."
    sudo apt update
    sudo apt install certbot -y
    sudo certbot certonly --standalone -d "$DOMAIN" --agree-tos -m "$EMAIL" --non-interactive

    echo "📂 Copying certificates to: $PROXY_DIR/certs/"
    cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" "$PROXY_DIR/certs/"
    cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" "$PROXY_DIR/certs/"

    # Overwrite config with HTTPS version
    cat <<EOF > "$PROXY_DIR/conf.d/multi-services.conf"
# HTTPS config for multiple services

server {
    listen 443 ssl;
    server_name app.$DOMAIN;

    ssl_certificate /etc/letsencrypt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/privkey.pem;

    location / {
        proxy_pass http://app-service:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}

server {
    listen 443 ssl;
    server_name analytics.$DOMAIN;

    ssl_certificate /etc/letsencrypt/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/privkey.pem;

    location / {
        proxy_pass http://analytics-service:8020;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
else
    echo "🔐 HTTPS setup skipped (CERTBOT_MODE=$CERTBOT_MODE)."
    echo "⚠️  You can manually run:"
    echo "    sudo certbot certonly --standalone -d $DOMAIN"
    echo "    Then copy certs into: $PROXY_DIR/certs/"
fi

# === START NGINX CONTAINER ===
echo "🚀 Launching NGINX reverse proxy..."
cd "$PROXY_DIR"
docker-compose up -d

echo ""
echo "✅ Setup complete!"
echo "➡️ Point your subdomains:"
echo "   app.$DOMAIN → maps to app-service:8080"
echo "   analytics.$DOMAIN → maps to analytics-service:9000"
echo "🎯 Make sure DNS points to this EC2 instance."
