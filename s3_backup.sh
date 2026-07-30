#!/bin/bash
set -euo pipefail

# ==========================================================
# WhatsApp Summary - Shift-wise S3 Backup
# ==========================================================
#
# Server Time Zone : Asia/Kolkata (IST)
#
# Shift Schedule:
#   A Shift : 06:10 IST → 14:10 IST
#   B Shift : 14:10 IST → 22:10 IST
#   C Shift : 22:10 IST → 06:10 IST (Next Day)
#
# Backups are taken at the END of each shift.
#
# Folder Structure:
#
#   YYYY/MM/DD/A/
#   YYYY/MM/DD/B/
#   YYYY/MM/DD/C/
#
# The folder date represents the SHIFT START DATE.
#
# Example:
#   A Shift : 25 Jul 06:10 → 25 Jul 14:10
#       -> 2026/07/25/A/
#
#   B Shift : 25 Jul 14:10 → 25 Jul 22:10
#       -> 2026/07/25/B/
#
#   C Shift : 25 Jul 22:10 → 26 Jul 06:10
#       -> 2026/07/25/C/
#
# This ensures that all three shifts belonging to the same
# production day are stored under the same folder.
#
# ==========================================================

BASE_DIR="$HOME/whatsapp-summary"

DISABLE_SCRIPT="$BASE_DIR/disable_services.sh"
ENABLE_SCRIPT="$BASE_DIR/enable_services.sh"

BUCKET="cq-openclaw-backups"

DB_PATH="$BASE_DIR/data/messages.db"
MEDIA_PATH="$HOME/.openclaw/media"

# ==========================================================
# Determine Shift and Production Date
# ==========================================================

HOUR=$(date +%H)
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

case "$HOUR" in

    06)
        # End of C Shift
        SHIFT="C"
        SHIFT_DATE=$(date -d "yesterday" +%Y/%m/%d)
        ;;

    14)
        # End of A Shift
        SHIFT="A"
        SHIFT_DATE=$(date +%Y/%m/%d)
        ;;

    22)
        # End of B Shift
        SHIFT="B"
        SHIFT_DATE=$(date +%Y/%m/%d)
        ;;

    *)
        echo "Backup should only be executed by the scheduled cron jobs."
        echo "Current Time : $(date)"
        exit 1
        ;;

esac

BACKUP_PREFIX="${SHIFT_DATE}/${SHIFT}"

echo "======================================================"
echo "Backup Started : $(date)"
echo "Shift          : ${SHIFT}"
echo "Shift Date     : ${SHIFT_DATE}"
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
        "s3://${BUCKET}/${BACKUP_PREFIX}/messages.db"

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

    MEDIA_COUNT=$(find "$MEDIA_PATH" -type f | wc -l)

    echo "Media files found : ${MEDIA_COUNT}"

    if [ "$MEDIA_COUNT" -gt 0 ]; then

        echo "Uploading media..."

        aws s3 sync \
            "$MEDIA_PATH" \
            "s3://${BUCKET}/${BACKUP_PREFIX}/media/"

        echo "Media uploaded successfully."
        echo "Media files uploaded : ${MEDIA_COUNT}"

        echo "Removing local media..."

        find "$MEDIA_PATH" -type f -delete

    else

        echo "No media files found to upload."

    fi

else

    echo "Media directory not found: $MEDIA_PATH"

fi

# ==========================================================
# Complete
# ==========================================================

echo "======================================================"
echo "Backup completed successfully."
echo "Shift          : ${SHIFT}"
echo "Shift Date     : ${SHIFT_DATE}"
echo "Completed Time : $(date)"
echo "======================================================"