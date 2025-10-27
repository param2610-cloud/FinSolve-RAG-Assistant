# EC2 Deployment Guide - FinSolve RAG Assistant

This guide explains how to deploy the FinSolve RAG Assistant on an AWS EC2 instance with HTTPS support.

## Prerequisites

### 1. AWS EC2 Instance
- **Instance Type**: t3.medium or larger (recommended for ML workloads)
- **AMI**: Ubuntu 22.04 LTS
- **Storage**: At least 20GB EBS volume
- **Security Group**: Configure the following inbound rules:
  - SSH (22) - Your IP
  - HTTP (80) - Anywhere
  - HTTPS (443) - Anywhere
  - Custom TCP (5001) - Your IP (for testing)

### 2. Domain Name
- You need a domain name pointing to your EC2 instance's public IP
- Update your domain's DNS A record to point to the EC2 public IP
- Wait for DNS propagation (5-30 minutes)

### 3. Required Information
- Groq API key (get from: https://console.groq.com/)
- Email address (for Let's Encrypt SSL certificate)
- Domain name

## Quick Deployment

### Step 1: Connect to EC2
```bash
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

### Step 2: Clone Repository
```bash
cd /opt
sudo git clone https://github.com/param2610-cloud/FinSolve-RAG-Assistant.git
cd FinSolve-RAG-Assistant
```

### Step 3: Make Script Executable
```bash
sudo chmod +x deploy_ec2.sh
```

### Step 4: Run Deployment Script
```bash
sudo ./deploy_ec2.sh your-domain.com your-email@example.com
```

**Example:**
```bash
sudo ./deploy_ec2.sh finsolve.example.com admin@example.com
```

### Step 5: Update Environment Variables
After deployment, update the `.env` file with your API keys:

```bash
sudo nano /opt/finsolve-rag-assistant/.env
```

Update these values:
```env
GROQ_API_KEY=your_actual_groq_api_key_here
```

Save and exit (Ctrl+X, then Y, then Enter)

### Step 6: Restart Application
```bash
sudo systemctl restart finsolve-rag
```

### Step 7: Verify Deployment
```bash
# Check application status
sudo systemctl status finsolve-rag

# Check logs
sudo journalctl -u finsolve-rag -f

# Test HTTPS
curl -I https://your-domain.com
```

## What the Script Does

1. **System Setup**
   - Updates system packages
   - Installs Python 3.10, Nginx, Certbot, and dependencies
   - Configures UFW firewall

2. **Application Setup**
   - Creates virtual environment
   - Installs Python dependencies
   - Downloads spaCy language model
   - Generates secure secret keys

3. **Gunicorn Configuration**
   - Sets up production WSGI server
   - Configures workers based on CPU cores
   - Sets up logging

4. **Systemd Service**
   - Creates auto-starting service
   - Enables automatic restart on failure
   - Runs as www-data user for security

5. **Nginx Configuration**
   - Reverse proxy on port 5001
   - HTTP to HTTPS redirect
   - Rate limiting and security headers
   - Static file serving

6. **SSL Certificate**
   - Obtains free SSL from Let's Encrypt
   - Configures auto-renewal
   - Enforces HTTPS

## Architecture

```
Internet (HTTPS/443)
         ↓
    Nginx (Reverse Proxy)
         ↓
  Gunicorn (Port 5001)
         ↓
   Flask Application
         ↓
    ChromaDB + Groq LLM
```

## Manual Deployment (Alternative)

If you prefer to deploy step-by-step manually, follow these commands:

### 1. Update System
```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### 2. Install Dependencies
```bash
sudo apt-get install -y python3.10 python3-pip python3.10-venv nginx certbot python3-certbot-nginx
```

### 3. Clone and Setup Application
```bash
cd /opt
sudo git clone https://github.com/param2610-cloud/FinSolve-RAG-Assistant.git
cd FinSolve-RAG-Assistant
sudo python3.10 -m venv venv
sudo venv/bin/pip install -r requirements.txt
sudo venv/bin/pip install gunicorn
sudo venv/bin/python -m spacy download en_core_web_sm
```

### 4. Configure Environment
```bash
sudo nano .env
# Add your configuration (see deploy_ec2.sh for template)
```

### 5. Create Systemd Service
```bash
sudo nano /etc/systemd/system/finsolve-rag.service
# Copy service configuration from deploy_ec2.sh
```

### 6. Configure Nginx
```bash
sudo nano /etc/nginx/sites-available/finsolve-rag
# Copy Nginx configuration from deploy_ec2.sh
sudo ln -s /etc/nginx/sites-available/finsolve-rag /etc/nginx/sites-enabled/
sudo nginx -t
```

### 7. Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable finsolve-rag
sudo systemctl start finsolve-rag
sudo systemctl restart nginx
```

### 8. Obtain SSL Certificate
```bash
sudo certbot --nginx -d your-domain.com --non-interactive --agree-tos --email your@email.com
```

## Useful Commands

### Application Management
```bash
# Start application
sudo systemctl start finsolve-rag

# Stop application
sudo systemctl stop finsolve-rag

# Restart application
sudo systemctl restart finsolve-rag

# Check status
sudo systemctl status finsolve-rag

# View logs (real-time)
sudo journalctl -u finsolve-rag -f

# View Gunicorn logs
sudo tail -f /var/log/finsolve-rag/error.log
sudo tail -f /var/log/finsolve-rag/access.log
```

### Nginx Management
```bash
# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# View logs
sudo tail -f /var/log/nginx/finsolve-access.log
sudo tail -f /var/log/nginx/finsolve-error.log
```

### SSL Certificate Management
```bash
# Check certificate status
sudo certbot certificates

# Renew certificate (manual)
sudo certbot renew

# Test auto-renewal
sudo certbot renew --dry-run
```

### Firewall Management
```bash
# Check firewall status
sudo ufw status

# Allow a port
sudo ufw allow 8080/tcp

# Remove a rule
sudo ufw delete allow 8080/tcp
```

## Troubleshooting

### Application Won't Start
```bash
# Check logs
sudo journalctl -u finsolve-rag -n 100 --no-pager

# Check if port is in use
sudo netstat -tlnp | grep 5001

# Check file permissions
ls -la /opt/finsolve-rag-assistant
```

### SSL Certificate Issues
```bash
# Check Nginx configuration
sudo nginx -t

# Verify DNS
nslookup your-domain.com

# Check certificate
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal
```

### High Memory Usage
```bash
# Check memory
free -h

# Reduce Gunicorn workers
sudo nano /opt/finsolve-rag-assistant/gunicorn_config.py
# Change: workers = 2
sudo systemctl restart finsolve-rag
```

### Can't Access Application
```bash
# Check if service is running
sudo systemctl status finsolve-rag

# Check Nginx status
sudo systemctl status nginx

# Check firewall
sudo ufw status

# Test local connection
curl http://localhost:5001

# Check logs
sudo journalctl -u finsolve-rag -f
```

## Updating the Application

```bash
# Pull latest changes
cd /opt/finsolve-rag-assistant
sudo git pull

# Activate virtual environment
source venv/bin/activate

# Install any new dependencies
sudo venv/bin/pip install -r requirements.txt

# Restart application
sudo systemctl restart finsolve-rag
```

## Performance Tuning

### Gunicorn Workers
Edit `/opt/finsolve-rag-assistant/gunicorn_config.py`:
```python
# For CPU-bound tasks (default)
workers = multiprocessing.cpu_count() * 2 + 1

# For memory-constrained environments
workers = 2

# For high-traffic scenarios
workers = multiprocessing.cpu_count() * 4 + 1
worker_class = 'gevent'  # Install gevent first
```

### Nginx Connection Limits
Edit `/etc/nginx/sites-available/finsolve-rag`:
```nginx
# Increase rate limit
limit_req_zone $binary_remote_addr zone=finsolve_limit:10m rate=20r/s;

# Increase burst
limit_req zone=finsolve_limit burst=50 nodelay;
```

## Security Best Practices

1. **Keep System Updated**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. **Use Strong Secrets**
   - Generate new secrets in `.env`
   - Never commit `.env` to version control

3. **Limit SSH Access**
   - Use key-based authentication only
   - Disable password authentication
   - Use specific IP allowlisting

4. **Monitor Logs**
   ```bash
   # Set up log rotation
   sudo nano /etc/logrotate.d/finsolve-rag
   ```

5. **Regular Backups**
   - Back up `/opt/finsolve-rag-assistant/resources/database/`
   - Back up `.env` file
   - Back up ChromaDB vector store

## Cost Optimization

- **EC2 Instance**: Use t3.medium (~$30/month) or t3.small for light usage
- **Storage**: 20GB EBS is sufficient (~$2/month)
- **Data Transfer**: First 100GB free per month
- **SSL Certificate**: Free with Let's Encrypt

**Estimated Monthly Cost**: $30-50 USD

## Support

For issues or questions:
- Check logs: `sudo journalctl -u finsolve-rag -f`
- GitHub Issues: https://github.com/param2610-cloud/FinSolve-RAG-Assistant/issues
- Review this guide's Troubleshooting section

## License

This deployment configuration is part of the FinSolve RAG Assistant project.
