# SchoolOS Production Deployment Guide

This guide covers deploying SchoolOS to production. Follow ALL steps in order.

---

## Prerequisites

- Ubuntu 20.04+ or similar Linux server
- PostgreSQL 14+
- Python 3.11+
- Node.js 18+ (for frontend)
- Nginx (reverse proxy)
- SSL certificate (Let's Encrypt recommended)
- Domain name configured

---

## 1. Server Setup

### 1.1 Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install Nginx
sudo apt install nginx -y

# Install certbot for SSL
sudo apt install certbot python3-certbot-nginx -y
```

### 1.2 Create Application User

```bash
sudo useradd -m -s /bin/bash schoolos
sudo usermod -aG sudo schoolos
```

---

## 2. Database Setup

### 2.1 Create Production Database

```bash
sudo -u postgres psql

-- In PostgreSQL console:
CREATE USER schoolos_prod WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE schoolos_prod OWNER schoolos_prod;
GRANT ALL PRIVILEGES ON DATABASE schoolos_prod TO schoolos_prod;

-- Enable required extensions
\c schoolos_prod
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
\q
```

### 2.2 Configure PostgreSQL for Production

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
# Connection settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# Performance
random_page_cost = 1.1
checkpoint_completion_target = 0.9

# Logging
log_min_duration_statement = 1000  # Log slow queries (>1s)
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

## 3. Application Deployment

### 3.1 Clone Repository

```bash
sudo su - schoolos
cd /home/schoolos
git clone https://github.com/yourusername/schoolos.git
cd schoolos
```

### 3.2 Backend Setup

```bash
cd apps/api

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev]"

# Copy and configure environment
cp .env.production.example .env
nano .env  # Edit with production values
```

**CRITICAL: Update .env file** (see PRODUCTION_SECURITY.md):
- Generate JWT_SECRET: `openssl rand -hex 32`
- Set DATABASE_URL to production database
- Set COOKIE_SECURE=true
- Set DEBUG=false
- Set DEV_EMAIL=false
- Change all seed passwords

### 3.3 Run Database Migrations

```bash
# Set DATABASE_URL for migrations
export DATABASE_URL="postgresql+psycopg2://schoolos_prod:PASSWORD@localhost:5432/schoolos_prod"

# Run migrations
alembic upgrade head

# Optional: Seed demo data (only if needed)
# python -m app.seed
```

### 3.4 Test Application

```bash
# Test that app starts and config validates
python -c "from app.main import app; print('✓ App configured successfully')"

# Run test suite
pytest -v

# Expected: All 187 tests should pass
```

---

## 4. Process Management with Systemd

### 4.1 Create Systemd Service

Create `/etc/systemd/system/schoolos-api.service`:

```ini
[Unit]
Description=SchoolOS API
After=network.target postgresql.service

[Service]
Type=notify
User=schoolos
Group=schoolos
WorkingDirectory=/home/schoolos/schoolos/apps/api
Environment="PATH=/home/schoolos/schoolos/apps/api/venv/bin"
ExecStart=/home/schoolos/schoolos/apps/api/venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 4 \
    --log-level info \
    --access-log \
    --proxy-headers

# Restart policy
Restart=always
RestartSec=10

# Resource limits
LimitNOFILE=65536

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

### 4.2 Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable schoolos-api
sudo systemctl start schoolos-api

# Check status
sudo systemctl status schoolos-api

# View logs
sudo journalctl -u schoolos-api -f
```

---

## 5. Nginx Configuration

### 5.1 Configure Reverse Proxy

Create `/etc/nginx/sites-available/schoolos`:

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=100r/m;

# Upstream API
upstream schoolos_api {
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # File upload limits
    client_max_body_size 10M;

    # API endpoint
    location /api/ {
        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://schoolos_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Login endpoint - stricter rate limiting
    location /api/auth/login {
        limit_req zone=login_limit burst=2 nodelay;
        
        proxy_pass http://schoolos_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health check
    location /api/health {
        proxy_pass http://schoolos_api;
        access_log off;
    }

    # Frontend (if serving from same domain)
    location / {
        root /home/schoolos/schoolos/apps/web/out;
        try_files $uri $uri/ /index.html;
    }
}
```

### 5.2 Enable Site and Get SSL

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/schoolos /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

---

## 6. Database Backups

### 6.1 Create Backup Script

Create `/home/schoolos/scripts/backup-db.sh`:

```bash
#!/bin/bash
set -e

# Configuration
DB_NAME="schoolos_prod"
DB_USER="schoolos_prod"
BACKUP_DIR="/home/schoolos/backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/schoolos_${DATE}.sql.gz"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U $DB_USER -h localhost $DB_NAME | gzip > $BACKUP_FILE

# Upload to S3 (if configured)
# aws s3 cp $BACKUP_FILE s3://your-backup-bucket/

# Delete old backups
find $BACKUP_DIR -name "schoolos_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "✓ Backup completed: $BACKUP_FILE"
```

### 6.2 Schedule Backup Cron Job

```bash
chmod +x /home/schoolos/scripts/backup-db.sh

# Add to crontab
crontab -e

# Add this line (daily at 2 AM)
0 2 * * * /home/schoolos/scripts/backup-db.sh >> /home/schoolos/logs/backup.log 2>&1
```

### 6.3 Test Backup and Restore

```bash
# Test backup
/home/schoolos/scripts/backup-db.sh

# Test restore (to a test database)
gunzip -c /home/schoolos/backups/schoolos_YYYYMMDD_HHMMSS.sql.gz | psql -U schoolos_prod -d schoolos_test
```

---

## 7. Monitoring Setup

### 7.1 Sentry (Error Tracking)

```bash
# Add to .env
SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
SENTRY_ENVIRONMENT=production

# Install Sentry SDK (already in dependencies)
pip install sentry-sdk
```

### 7.2 System Monitoring

Set up monitoring for:
- Server CPU/RAM/Disk usage
- Database connections and query performance
- API response times
- Error rates
- Health check endpoint

Recommended tools:
- **Uptime monitoring:** UptimeRobot, Pingdom
- **APM:** Datadog, New Relic
- **Logs:** CloudWatch, Papertrail

---

## 8. Security Hardening

### 8.1 Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct database access from outside
sudo ufw deny 5432/tcp

# Enable firewall
sudo ufw enable
```

### 8.2 Fail2Ban (Brute Force Protection)

```bash
sudo apt install fail2ban -y

# Configure Nginx jail
sudo nano /etc/fail2ban/jail.d/nginx.conf
```

Add:
```ini
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
```

```bash
sudo systemctl restart fail2ban
```

### 8.3 Automatic Security Updates

```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 9. Post-Deployment Checklist

### Critical Checks
- [ ] Application starts without errors
- [ ] All 187 tests pass
- [ ] Health check returns 200: `curl https://yourdomain.com/api/health`
- [ ] Database connectivity verified
- [ ] SSL certificate valid and auto-renewal configured
- [ ] Backups running and tested
- [ ] Monitoring/alerts configured
- [ ] Logs accessible and rotating
- [ ] Firewall rules in place
- [ ] Strong passwords set for all accounts

### Security Verification
- [ ] JWT_SECRET is 32+ bytes (not default)
- [ ] COOKIE_SECURE=true
- [ ] DEBUG=false
- [ ] DEV_EMAIL=false
- [ ] CORS_ORIGINS restricted to production domains
- [ ] API docs disabled in production (/api/docs returns 404)
- [ ] Rate limiting working on /api/auth/login
- [ ] Security headers present (check with securityheaders.com)

### Performance Testing
- [ ] Load test with expected traffic
- [ ] Database query performance reviewed
- [ ] Connection pool sized appropriately
- [ ] Response times acceptable (<200ms for most endpoints)

---

## 10. Common Issues & Troubleshooting

### Application won't start

```bash
# Check logs
sudo journalctl -u schoolos-api -n 100

# Common fixes:
# - Verify DATABASE_URL is correct
# - Check JWT_SECRET length (must be 32+ bytes)
# - Ensure all required env vars are set
# - Verify database is running: sudo systemctl status postgresql
```

### Database connection errors

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection manually
psql -U schoolos_prod -h localhost -d schoolos_prod

# Check connection limits
sudo -u postgres psql -c "SHOW max_connections;"
```

### 502 Bad Gateway

```bash
# Check if API is running
sudo systemctl status schoolos-api

# Check nginx error logs
sudo tail -f /var/log/nginx/error.log

# Verify upstream connection
curl http://127.0.0.1:8000/api/health
```

### High memory usage

```bash
# Check worker count (reduce if needed)
sudo nano /etc/systemd/system/schoolos-api.service
# Change --workers 4 to --workers 2

# Restart service
sudo systemctl daemon-reload
sudo systemctl restart schoolos-api
```

---

## 11. Rollback Procedure

If deployment fails:

```bash
# 1. Stop the service
sudo systemctl stop schoolos-api

# 2. Restore database from backup
gunzip -c /home/schoolos/backups/schoolos_LATEST.sql.gz | psql -U schoolos_prod -d schoolos_prod

# 3. Checkout previous working version
cd /home/schoolos/schoolos
git checkout PREVIOUS_TAG

# 4. Rollback database migrations (if needed)
cd apps/api
source venv/bin/activate
alembic downgrade -1  # Or specific revision

# 5. Restart service
sudo systemctl start schoolos-api
```

---

## 12. Maintenance

### Regular Tasks

**Daily:**
- Monitor error rates in Sentry
- Check disk space: `df -h`
- Review backup logs

**Weekly:**
- Review slow query logs
- Check security advisories
- Update dependencies (test in staging first)

**Monthly:**
- Review access logs for suspicious activity
- Database vacuum and analyze: `VACUUM ANALYZE;`
- Test backup restore procedure
- Security audit review

### Updating the Application

```bash
# 1. Backup database first
/home/schoolos/scripts/backup-db.sh

# 2. Pull latest code
cd /home/schoolos/schoolos
git pull origin main

# 3. Update dependencies
cd apps/api
source venv/bin/activate
pip install -e ".[dev]" --upgrade

# 4. Run migrations
alembic upgrade head

# 5. Restart service
sudo systemctl restart schoolos-api

# 6. Verify health
curl https://yourdomain.com/api/health
```

---

## Support

For deployment issues:
- Documentation: `/docs/PRODUCTION_SECURITY.md`
- GitHub Issues: https://github.com/yourusername/schoolos/issues
- Email: support@yourdomain.com

---

**Last Updated:** 2026-08-19
