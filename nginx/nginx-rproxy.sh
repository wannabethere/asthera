#!/bin/bash

set -e

# === CONFIGURATION ===
DOMAIN="ec2-54-161-71-105.compute-1.amazonaws.com"  # EC2 public DNS
SERVICES=( "8020 analytics" "8015 unstructured" )                # Format: "PORT SUBDOMAIN"
PROXY_DIR="$HOME/nginx-reverse-proxy"
CERTBOT_MODE="manual"                               # Change to 'auto' to install certs

# === Resolve host IP (AWS Linux compatible) ===
HOST_IP=$(ip route get 1 | awk '{print $NF; exit}')
echo "🌐 Detected host IP: $HOST_IP"

# === Set up proxy directory ===
echo "📁 Setting up directory: $PROXY_DIR"
mkdir -p "$PROXY_DIR"/{conf.d,certs,html,logs}

# === Write Docker Compose ===
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
      - ./certs:/etc/letsencrypt
      - ./logs:/var/log/nginx
      - ./html:/usr/share/nginx/html
    restart: always
EOF

# === Write NGINX config ===
CONF_FILE="$PROXY_DIR/conf.d/multi-services.conf"
echo "# Auto-generated NGINX reverse proxy config" > "$CONF_FILE"

for SERVICE in "${SERVICES[@]}"; do
  PORT=$(echo $SERVICE | awk '{print $1}')
  NAME=$(echo $SERVICE | awk '{print $2}')
cat <<EOF >> "$CONF_FILE"

server {
    listen 80;
    server_name $NAME.$DOMAIN;

    location / {
        proxy_pass http://$HOST_IP:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
done

# === Certbot manual notice ===
if [ "$CERTBOT_MODE" == "manual" ]; then
  echo "🔐 HTTPS not auto-configured (CERTBOT_MODE=manual)."
  echo "👉 To enable certs: sudo certbot certonly --standalone -d $DOMAIN"
  echo "🔁 Then copy certs to $PROXY_DIR/certs/"
fi

# === Start container ===
cd "$PROXY_DIR"
docker-compose up -d --force-recreate

echo ""
echo "✅ NGINX reverse proxy running at http://$DOMAIN"
for SERVICE in "${SERVICES[@]}"; do
  PORT=$(echo $SERVICE | awk '{print $1}')
  NAME=$(echo $SERVICE | awk '{print $2}')
  echo "   http://$NAME.$DOMAIN → $HOST_IP:$PORT"
done
