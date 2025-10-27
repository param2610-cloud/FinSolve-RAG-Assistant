#!/bin/bash

################################################################################
# FinSolve RAG Assistant - EC2 Deployment Script
# This script sets up the application on an EC2 instance with HTTPS support
################################################################################

set -e  # Exit on any error

# Configuration
APP_PORT=5001  # Odd port for Flask app
APP_NAME="finsolve-rag"
APP_DIR="/opt/finsolve-rag-assistant"
DOMAIN_NAME="${1:-your-domain.com}"  # Pass domain as first argument
EMAIL="${2:-admin@your-domain.com}"  # Pass email as second argument

echo "=========================================="
echo "FinSolve RAG Assistant - EC2 Deployment"
echo "=========================================="
echo "Domain: $DOMAIN_NAME"
echo "App Port: $APP_PORT"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Step 1: Update system packages
print_status "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Step 2: Install required system packages
print_status "Installing required system packages..."
apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    nginx \
    certbot \
    python3-certbot-nginx \
    git \
    curl \
    supervisor \
    ufw

# Step 3: Configure firewall
print_status "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw allow $APP_PORT/tcp  # Flask app (for testing)
print_status "Firewall configured"

# Step 4: Create application directory
print_status "Setting up application directory..."
mkdir -p $APP_DIR
cd $APP_DIR

# If this script is being run from the repo, copy files
if [ -f "../app/main.py" ]; then
    print_status "Copying application files..."
    cp -r ../app .
    cp -r ../resources .
    cp ../requirements.txt .
    cp ../.env.example .env || touch .env
else
    print_warning "Application files not found. Please clone/copy your repo to $APP_DIR"
fi

# Step 5: Create Python virtual environment
print_status "Creating Python virtual environment..."
python3.10 -m venv venv
source venv/bin/activate

# Step 6: Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Production WSGI server

# Step 7: Download spaCy model
print_status "Downloading spaCy language model..."
python -m spacy download en_core_web_sm

# Step 8: Set up environment variables
print_status "Setting up environment variables..."
cat > .env << EOF
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=$(openssl rand -hex 32)

# JWT Configuration
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Groq API Key (UPDATE THIS!)
GROQ_API_KEY=your_groq_api_key_here

# Vector Store
VECTOR_DB_PATH=resources/database/vector_store
COLLECTION_NAME=company_docs

# Server
HOST=0.0.0.0
PORT=$APP_PORT
EOF

print_warning "Please update .env file with your actual API keys!"
print_warning "Edit: nano $APP_DIR/.env"

# Step 9: Create Gunicorn configuration
print_status "Creating Gunicorn configuration..."
cat > gunicorn_config.py << 'EOF'
import multiprocessing

# Server socket
bind = "127.0.0.1:5001"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = '/var/log/finsolve-rag/access.log'
errorlog = '/var/log/finsolve-rag/error.log'
loglevel = 'info'
capture_output = True

# Process naming
proc_name = 'finsolve-rag'

# Server mechanics
daemon = False
pidfile = '/var/run/finsolve-rag.pid'
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
EOF

# Step 10: Create log directory
print_status "Creating log directory..."
mkdir -p /var/log/finsolve-rag
chown -R www-data:www-data /var/log/finsolve-rag

# Step 11: Create systemd service
print_status "Creating systemd service..."
cat > /etc/systemd/system/finsolve-rag.service << EOF
[Unit]
Description=FinSolve RAG Assistant Gunicorn Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn -c gunicorn_config.py app.main:app
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Step 12: Configure Nginx
print_status "Configuring Nginx..."
cat > /etc/nginx/sites-available/$APP_NAME << EOF
# Rate limiting
limit_req_zone \$binary_remote_addr zone=finsolve_limit:10m rate=10r/s;

# Upstream application server
upstream finsolve_app {
    server 127.0.0.1:$APP_PORT fail_timeout=0;
}

# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN_NAME;

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    # Redirect all HTTP to HTTPS
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN_NAME;

    # SSL certificates (will be added by certbot)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem;

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Client upload size
    client_max_body_size 16M;

    # Logging
    access_log /var/log/nginx/finsolve-access.log;
    error_log /var/log/nginx/finsolve-error.log;

    # Rate limiting
    limit_req zone=finsolve_limit burst=20 nodelay;

    # Proxy to Flask app
    location / {
        proxy_pass http://finsolve_app;
        proxy_redirect off;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }

    # Static files (if served by Nginx)
    location /static {
        alias $APP_DIR/resources/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Step 13: Set permissions
print_status "Setting file permissions..."
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

# Step 14: Start services
print_status "Starting services..."
systemctl daemon-reload
systemctl enable finsolve-rag
systemctl start finsolve-rag
systemctl restart nginx

# Step 15: Obtain SSL certificate
print_status "Obtaining SSL certificate from Let's Encrypt..."
print_warning "Make sure your domain $DOMAIN_NAME points to this server's IP!"
read -p "Press Enter to continue with SSL certificate generation, or Ctrl+C to cancel..."

certbot --nginx -d $DOMAIN_NAME --non-interactive --agree-tos --email $EMAIL --redirect

# Step 16: Set up auto-renewal
print_status "Setting up SSL certificate auto-renewal..."
systemctl enable certbot.timer
systemctl start certbot.timer

# Step 17: Display status
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
systemctl status finsolve-rag --no-pager
echo ""
print_status "Application Status:"
echo "  - Application URL: https://$DOMAIN_NAME"
echo "  - Direct app port: http://$(hostname -I | awk '{print $1}'):$APP_PORT (for testing)"
echo "  - Logs: /var/log/finsolve-rag/"
echo "  - Nginx logs: /var/log/nginx/"
echo ""
print_status "Useful Commands:"
echo "  - View logs: journalctl -u finsolve-rag -f"
echo "  - Restart app: sudo systemctl restart finsolve-rag"
echo "  - Restart Nginx: sudo systemctl restart nginx"
echo "  - Check status: sudo systemctl status finsolve-rag"
echo "  - Update .env: sudo nano $APP_DIR/.env"
echo ""
print_warning "Next Steps:"
echo "  1. Update API keys in: $APP_DIR/.env"
echo "  2. Restart application: sudo systemctl restart finsolve-rag"
echo "  3. Test your app at: https://$DOMAIN_NAME"
echo ""
print_status "SSL certificate will auto-renew. Check with: sudo certbot renew --dry-run"
echo ""
