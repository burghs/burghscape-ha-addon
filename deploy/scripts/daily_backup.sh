#!/bin/bash
# Burghscape Daily Backup Cron Job
# Runs via: crontab -e -> 0 3 * * * /home/kenny/burghscape/backup/scripts/daily_backup.sh
# Backs up to local /home/kenny/backups/ with 30-day retention

set -euo pipefail

BACKUP_DIR="/home/kenny/backups"
SOURCE_DIR="/home/kenny/burghscape"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TMP_DIR="/tmp/burghscape-daily-${TIMESTAMP}"

mkdir -p "${TMP_DIR}" "${BACKUP_DIR}"

# DB dump
docker exec mybeacon-db pg_dump -U burghscape burghscape \
    --clean --if-exists --no-owner --no-privileges \
    > "${TMP_DIR}/db.sql"

# Configs
cp "${SOURCE_DIR}/.env" "${TMP_DIR}/env"
cp "${SOURCE_DIR}/docker-compose.yml" "${TMP_DIR}/"
mkdir -p "${TMP_DIR}/cloudflared"
cp "${SOURCE_DIR}/cloudflared/"*.yaml "${TMP_DIR}/cloudflared/" 2>/dev/null || true

# Platform source (git archive if available, else tar)
cd "${SOURCE_DIR}/platform"
if [ -d .git ]; then
    git archive --format=tar.gz -o "${TMP_DIR}/platform.tar.gz" HEAD
else
    tar czf "${TMP_DIR}/platform.tar.gz" -C "${SOURCE_DIR}" platform/
fi

# HA add-on
cd "${SOURCE_DIR}/ha-agent-addon"
if [ -d .git ]; then
    git archive --format=tar.gz -o "${TMP_DIR}/ha-addon.tar.gz" HEAD
else
    tar czf "${TMP_DIR}/ha-addon.tar.gz" -C "${SOURCE_DIR}" ha-agent-addon/
fi

# Package
ARCHIVE="${BACKUP_DIR}/burghscape-backup-${TIMESTAMP}.tar.gz"
tar czf "${ARCHIVE}" -C /tmp "burghscape-daily-${TIMESTAMP}"
rm -rf "${TMP_DIR}"

# Retention: keep last 30 daily backups
cd "${BACKUP_DIR}"
ls -t burghscape-backup-*.tar.gz 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null || true

# Log
echo "[$(date)] Backup complete: ${ARCHIVE} ($(du -h ${ARCHIVE} | cut -f1))"
echo "[$(date)] Backup complete: ${ARCHIVE} ($(du -h ${ARCHIVE} | cut -f1))" >> "${BACKUP_DIR}/backup.log"
