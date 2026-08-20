#!/bin/bash
#
# SchoolOS Database Restore Script
# Restores a PostgreSQL backup from compressed archive
#
# Usage: ./restore-db.sh <backup_file.sql.gz> [--from-s3]
#

set -e

# Configuration
DB_NAME="${DB_NAME:-schoolos_prod}"
DB_USER="${DB_USER:-schoolos_prod}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
    exit 1
}

# Check arguments
if [[ -z "$1" ]]; then
    error "Usage: $0 <backup_file.sql.gz> [--from-s3]"
fi

BACKUP_FILE="$1"

# Download from S3 if requested
if [[ "$2" == "--from-s3" ]]; then
    log "Downloading from S3: $BACKUP_FILE"
    LOCAL_FILE="/tmp/$(basename "$BACKUP_FILE")"
    aws s3 cp "$BACKUP_FILE" "$LOCAL_FILE" || error "S3 download failed"
    BACKUP_FILE="$LOCAL_FILE"
fi

# Check if file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file not found: $BACKUP_FILE"
fi

log "==================================="
log "SchoolOS Database Restore"
log "==================================="
log "Backup file: $BACKUP_FILE"
log "Database: $DB_NAME"
log ""
log "WARNING: This will DROP and recreate the database!"
log "Press Ctrl+C within 5 seconds to cancel..."
sleep 5

log "Starting restore..."

# Restore database
if gunzip -c "$BACKUP_FILE" | PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME"; then
    log "✓ Database restored successfully"
else
    error "Restore failed"
fi

log "==================================="
log "Restore completed"
