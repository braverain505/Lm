# Database Backup and Restore Guide

## Automated Backups

### Setup

1. **Configure environment variables** in `/etc/environment` or backup script:

```bash
export DB_NAME="clearis_prod"
export DB_USER="clearis_prod"
export DB_PASSWORD="your_secure_password"
export DB_HOST="localhost"
export DB_PORT="5432"
export BACKUP_DIR="/var/backups/clearis"
export RETENTION_DAYS="30"

# Optional S3 upload
export S3_BUCKET="your-backup-bucket"
export S3_PREFIX="backups/"
```

2. **Test backup manually**:

```bash
cd /home/clearis/clearis/scripts
./backup-db.sh
```

3. **Schedule with cron** (daily at 2 AM):

```bash
sudo crontab -e -u clearis

# Add this line:
0 2 * * * /home/clearis/clearis/scripts/backup-db.sh >> /var/log/clearis-backup.log 2>&1
```

### Backup with S3 Upload

```bash
./backup-db.sh --upload-s3
```

---

## Manual Backup

```bash
# Simple backup
pg_dump -U clearis_prod -d clearis_prod | gzip > backup_$(date +%Y%m%d).sql.gz

# With custom host
pg_dump -h localhost -p 5432 -U clearis_prod -d clearis_prod | gzip > backup.sql.gz
```

---

## Restore from Backup

### Test Restore (to test database)

```bash
# Create test database
createdb -U clearis_prod clearis_test

# Restore
gunzip -c backup_20260820.sql.gz | psql -U clearis_prod -d clearis_test

# Verify
psql -U clearis_prod -d clearis_test -c "SELECT COUNT(*) FROM school;"
```

### Production Restore

⚠️ **WARNING**: This will overwrite production data!

```bash
# Stop the application first
sudo systemctl stop clearis-api

# Restore using script
./restore-db.sh /var/backups/clearis/clearis_20260820_020000.sql.gz

# Or from S3
./restore-db.sh s3://your-bucket/backups/clearis_20260820_020000.sql.gz --from-s3

# Restart application
sudo systemctl start clearis-api
```

---

## Backup Verification

Always verify backups can be restored:

```bash
# Monthly restore test
./scripts/test-restore.sh
```

---

## Monitoring

Check backup logs:

```bash
tail -f /var/log/clearis-backup.log
```

Check backup disk usage:

```bash
du -sh /var/backups/clearis/
ls -lh /var/backups/clearis/ | tail -10
```

---

## Retention Policy

- Local backups: 30 days (configurable)
- S3 backups: Use lifecycle policies
  - Standard-IA: 30 days
  - Glacier: 90 days
  - Delete: 1 year

---

## Troubleshooting

### Backup fails with "permission denied"

```bash
# Check directory permissions
ls -ld /var/backups/clearis
sudo chown -R clearis:clearis /var/backups/clearis
```

### Large database takes too long

```bash
# Use parallel dump (PostgreSQL 11+)
pg_dump -U clearis_prod -d clearis_prod -j 4 -F d -f backup_dir/
```

### Out of disk space

```bash
# Check space
df -h /var/backups

# Clean old backups manually
find /var/backups/clearis -name "*.sql.gz" -mtime +30 -delete
```

---

## Recovery Point Objective (RPO)

- **Daily backups**: Maximum 24 hours data loss
- **Hourly backups** (recommended for production):

```bash
# Cron for hourly backups
0 * * * * /home/clearis/clearis/scripts/backup-db.sh >> /var/log/clearis-backup.log 2>&1
```

---

## Disaster Recovery Plan

1. **Identify incident**: Data corruption, ransomware, hardware failure
2. **Stop application**: `sudo systemctl stop clearis-api`
3. **Assess damage**: Check database state
4. **Select backup**: Choose most recent uncorrupted backup
5. **Restore**: Use restore script
6. **Verify**: Test critical functions
7. **Resume**: Start application
8. **Document**: Record incident details

Estimated recovery time: 15-30 minutes
