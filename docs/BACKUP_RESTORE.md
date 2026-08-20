# Database Backup and Restore Guide

## Automated Backups

### Setup

1. **Configure environment variables** in `/etc/environment` or backup script:

```bash
export DB_NAME="schoolos_prod"
export DB_USER="schoolos_prod"
export DB_PASSWORD="your_secure_password"
export DB_HOST="localhost"
export DB_PORT="5432"
export BACKUP_DIR="/var/backups/schoolos"
export RETENTION_DAYS="30"

# Optional S3 upload
export S3_BUCKET="your-backup-bucket"
export S3_PREFIX="backups/"
```

2. **Test backup manually**:

```bash
cd /home/schoolos/schoolos/scripts
./backup-db.sh
```

3. **Schedule with cron** (daily at 2 AM):

```bash
sudo crontab -e -u schoolos

# Add this line:
0 2 * * * /home/schoolos/schoolos/scripts/backup-db.sh >> /var/log/schoolos-backup.log 2>&1
```

### Backup with S3 Upload

```bash
./backup-db.sh --upload-s3
```

---

## Manual Backup

```bash
# Simple backup
pg_dump -U schoolos_prod -d schoolos_prod | gzip > backup_$(date +%Y%m%d).sql.gz

# With custom host
pg_dump -h localhost -p 5432 -U schoolos_prod -d schoolos_prod | gzip > backup.sql.gz
```

---

## Restore from Backup

### Test Restore (to test database)

```bash
# Create test database
createdb -U schoolos_prod schoolos_test

# Restore
gunzip -c backup_20260820.sql.gz | psql -U schoolos_prod -d schoolos_test

# Verify
psql -U schoolos_prod -d schoolos_test -c "SELECT COUNT(*) FROM school;"
```

### Production Restore

⚠️ **WARNING**: This will overwrite production data!

```bash
# Stop the application first
sudo systemctl stop schoolos-api

# Restore using script
./restore-db.sh /var/backups/schoolos/schoolos_20260820_020000.sql.gz

# Or from S3
./restore-db.sh s3://your-bucket/backups/schoolos_20260820_020000.sql.gz --from-s3

# Restart application
sudo systemctl start schoolos-api
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
tail -f /var/log/schoolos-backup.log
```

Check backup disk usage:

```bash
du -sh /var/backups/schoolos/
ls -lh /var/backups/schoolos/ | tail -10
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
ls -ld /var/backups/schoolos
sudo chown -R schoolos:schoolos /var/backups/schoolos
```

### Large database takes too long

```bash
# Use parallel dump (PostgreSQL 11+)
pg_dump -U schoolos_prod -d schoolos_prod -j 4 -F d -f backup_dir/
```

### Out of disk space

```bash
# Check space
df -h /var/backups

# Clean old backups manually
find /var/backups/schoolos -name "*.sql.gz" -mtime +30 -delete
```

---

## Recovery Point Objective (RPO)

- **Daily backups**: Maximum 24 hours data loss
- **Hourly backups** (recommended for production):

```bash
# Cron for hourly backups
0 * * * * /home/schoolos/schoolos/scripts/backup-db.sh >> /var/log/schoolos-backup.log 2>&1
```

---

## Disaster Recovery Plan

1. **Identify incident**: Data corruption, ransomware, hardware failure
2. **Stop application**: `sudo systemctl stop schoolos-api`
3. **Assess damage**: Check database state
4. **Select backup**: Choose most recent uncorrupted backup
5. **Restore**: Use restore script
6. **Verify**: Test critical functions
7. **Resume**: Start application
8. **Document**: Record incident details

Estimated recovery time: 15-30 minutes
