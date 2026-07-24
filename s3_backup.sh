#!/bin/bash
set -euo pipefail

# ==========================================================
# WhatsApp Summary - Shift-wise S3 Backup
# ==========================================================

BASE_DIR="$HOME/whatsapp-summary"

DISABLE_SCRIPT="$BASE_DIR/disable_services.sh"
ENABLE_SCRIPT="$BASE_DIR/enable_services.sh"

BUCKET="cq-openclaw-backups"

DB_PATH="$BASE_DIR/data/messages.db"
MEDIA_PATH="$HOME/.openclaw/media"

# ==========================================================
# Date / Shift (Server Time: UTC)
# ==========================================================

YEAR=$(date +%Y)
MONTH=$(date +%m)
DAY=$(date +%d)
HOUR=$(date +%H)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

#
# Backup Schedule (UTC / IST)
#
# Backups are taken at the END of each shift.
#
# 00:40 UTC (06:10 IST) -> Backup C Shift (22:10–06:10 IST)
# 08:40 UTC (14:10 IST) -> Backup A Shift (06:10–14:10 IST)
# 16:40 UTC (22:10 IST) -> Backup B Shift (14:10–22:10 IST)
#

case "$HOUR" in
    00)
        SHIFT="C"
        ;;
    08)
        SHIFT="A"
        ;;
    16)
        SHIFT="B"
        ;;
    *)
        echo "Backup should only be executed by the scheduled cron jobs."
        echo "Current UTC Time: $(date)"
        exit 1
        ;;
esac

BACKUP_PREFIX="${YEAR}/${MONTH}/${DAY}/${SHIFT}"

echo "======================================================"
echo "Backup Started : $(date)"
echo "Shift          : ${SHIFT}"
echo "S3 Bucket      : ${BUCKET}"
echo "S3 Location    : s3://${BUCKET}/${BACKUP_PREFIX}"
echo "======================================================"

# ==========================================================
# Stop Services
# ==========================================================

echo "Stopping services..."

bash "$DISABLE_SCRIPT"

cleanup() {
    echo "Starting services..."
    bash "$ENABLE_SCRIPT"
}

trap cleanup EXIT

# ==========================================================
# Backup Database
# ==========================================================

if [ -f "$DB_PATH" ]; then

    echo "Uploading database..."

    aws s3 cp \
        "$DB_PATH" \
        "s3://${BUCKET}/${BACKUP_PREFIX}/messages_${TIMESTAMP}.db"

    echo "Database uploaded successfully."

    echo "Removing local database..."

    rm -f "$DB_PATH"

else
    echo "Database not found: $DB_PATH"
fi

# ==========================================================
# Backup Media
# ==========================================================

if [ -d "$MEDIA_PATH" ]; then

    echo "Uploading media..."

    aws s3 sync \
        "$MEDIA_PATH" \
        "s3://${BUCKET}/${BACKUP_PREFIX}/media/"

    echo "Media uploaded successfully."

    echo "Removing local media..."

    find "$MEDIA_PATH" -type f -delete

else
    echo "Media directory not found: $MEDIA_PATH"
fi

# ==========================================================
# Complete
# ==========================================================

echo "======================================================"
echo "Backup completed successfully."
echo "Shift : ${SHIFT}"
echo "Time  : $(date)"
echo "======================================================"