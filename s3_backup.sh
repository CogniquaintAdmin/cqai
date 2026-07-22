#!/bin/bash
set -euo pipefail

# ==========================
# Configuration
# ==========================
BASE_DIR="$HOME/whatsapp-summary"

DISABLE_SCRIPT="$BASE_DIR/disable_services.sh"
ENABLE_SCRIPT="$BASE_DIR/enable_services.sh"

BUCKET="cq-openclaw-backups"
DB_PATH="$BASE_DIR/data/messages.db"
MEDIA_PATH="$HOME/.openclaw/media"

YEAR=$(date +%Y)
MONTH=$(date +%m)
DAY=$(date +%d)

BACKUP_PREFIX="${YEAR}/${MONTH}/${DAY}"

echo "[$(date)] Stopping services..."

# Disable services before backup
bash "$DISABLE_SCRIPT"

cleanup() {
    echo "[$(date)] Starting services..."
    bash "$ENABLE_SCRIPT"
}

trap cleanup EXIT

echo "[$(date)] Starting backup..."

# ==========================
# Backup SQLite database
# ==========================
if [ -f "$DB_PATH" ]; then

    aws s3 cp \
        "$DB_PATH" \
        "s3://${BUCKET}/${BACKUP_PREFIX}/messages.db"

    echo "Database uploaded successfully. Removing local database..."

    rm -f "$DB_PATH"

else
    echo "Database not found: $DB_PATH"
fi


# ==========================
# Backup media
# ==========================
if [ -d "$MEDIA_PATH" ]; then

    aws s3 sync \
        "$MEDIA_PATH" \
        "s3://${BUCKET}/${BACKUP_PREFIX}/media/"

    echo "Media uploaded successfully. Removing local media..."

    find "$MEDIA_PATH" -type f -delete

else
    echo "Media directory not found: $MEDIA_PATH"
fi


echo "[$(date)] Backup completed successfully."
