#!/bin/bash
#
# SchoolOS Database Backup Script
# Performs automated PostgreSQL backup with compression and optional S3 upload
#
# Usage: ./backup-db.sh [--upload-s3]
#

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Database credentials (override via environment variables)
DB_NAME="${DB_NAME:-schoolos_prod}"
DB_USER="${DB_USER:-schoolos_prod}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Backup settings
BACKUP_DIR="${BACKUP_DIR:-/var/backups/schoolos}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/schoolos_${DATE}.sql.gz"

# S3 settings (optional)
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-backups/}"

# ============================================================================
# FUNCTIONS
# ============================================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
    exit 1
}

check_dependencies() {
    if ! command -v pg_dump &> /dev/null; then
        error "pg_dump not found. Install PostgreSQL client tools."
    fi

    if ! command -v gzip &> /dev/null; then
        error "gzip not found. Install gzip."
    fi

    if [[ "$1" == "--upload-s3" ]] && ! command -v aws &> /dev/null; then
        error "aws CLI not found. Install AWS CLI for S3 uploads."
    fi
}

create_backup_dir() {
    mkdir -p "$BACKUP_DIR" || error "Failed to create backup directory: $BACKUP_DIR"
}

perform_backup() {
    log "Starting database backup..."
    log "Database: $DB_NAME"
    log "Output: $BACKUP_FILE"

    # Perform backup with pg_dump and compress with gzip
    if PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists \
        | gzip > "$BACKUP_FILE"; then

        local size=$(du -h "$BACKUP_FILE" | cut -f1)
        log "✓ Backup completed successfully: $BACKUP_FILE ($size)"
    else
        error "Backup failed"
    fi
}

upload_to_s3() {
    if [[ -z "$S3_BUCKET" ]]; then
        log "⊘ S3 upload skipped (S3_BUCKET not configured)"
        return 0
    fi

    log "Uploading to S3: s3://$S3_BUCKET/$S3_PREFIX"

    if aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/$S3_PREFIX" --storage-class STANDARD_IA; then
        log "✓ Uploaded to S3 successfully"
    else
        log "⚠ S3 upload failed (backup still available locally)"
    fi
}

cleanup_old_backups() {
    log "Cleaning up backups older than $RETENTION_DAYS days..."

    local count=$(find "$BACKUP_DIR" -name "schoolos_*.sql.gz" -mtime +"$RETENTION_DAYS" | wc -l)

    if [[ $count -gt 0 ]]; then
        find "$BACKUP_DIR" -name "schoolos_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
        log "✓ Removed $count old backup(s)"
    else
        log "✓ No old backups to remove"
    fi
}

verify_backup() {
    log "Verifying backup integrity..."

    if gzip -t "$BACKUP_FILE"; then
        log "✓ Backup file integrity verified"
    else
        error "Backup file is corrupted!"
    fi
}

show_summary() {
    log "==================================="
    log "Backup Summary"
    log "==================================="
    log "File: $BACKUP_FILE"
    log "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
    log "Backups in $BACKUP_DIR: $(ls -1 "$BACKUP_DIR"/schoolos_*.sql.gz 2>/dev/null | wc -l)"
    log "==================================="
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    log "SchoolOS Database Backup Script"
    log "==================================="

    # Check for required tools
    check_dependencies "$@"

    # Create backup directory
    create_backup_dir

    # Perform backup
    perform_backup

    # Verify backup
    verify_backup

    # Upload to S3 if requested
    if [[ "$1" == "--upload-s3" ]]; then
        upload_to_s3
    fi

    # Cleanup old backups
    cleanup_old_backups

    # Show summary
    show_summary

    log "✓ Backup process completed successfully"
}

# Run main function
main "$@"
