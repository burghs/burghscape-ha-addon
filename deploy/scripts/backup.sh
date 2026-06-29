#!/bin/bash
# Burghscape Full Server Backup Script
# Run on the VM via: ./backup.sh
# Backs up: DB dump, .env, cloudflared configs, docker-compose, platform source

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/burghscape-backup-${TIMESTAMP}"
SOURCE_DIR="/home/kenny/burghscape"

echo "=== Burghscape Server Backup v1.0 ==="
echo "Timestamp: ${TIMESTAMP}"

# Create temp backup dir
mkdir -p "${BACKUP_DIR}"

# 1. PostgreSQL Database dump
echo "[1/6] Dumping PostgreSQL database..."
docker exec mybeacon-db pg_dump -U burghscape burghscape \
    --clean --if-exists --no-owner --no-privileges \
    > "${BACKUP_DIR}/db_burghscape.sql"

# 2. .env file
echo "[2/6] Copying .env..."
cp "${SOURCE_DIR}/.env" "${BACKUP_DIR}/env"

# 3. Docker Compose
echo "[3/6] Copying docker-compose.yml..."
cp "${SOURCE_DIR}/docker-compose.yml" "${BACKUP_DIR}/docker-compose.yml"

# 4. Cloudflare tunnel configs
echo "[4/6] Copying cloudflared configs..."
mkdir -p "${BACKUP_DIR}/cloudflared"
cp "${SOURCE_DIR}/cloudflared/"*.yaml "${BACKUP_DIR}/cloudflared/" 2>/dev/null || true

# 5. Platform source code (frontend + backend)
echo "[5/6] Archiving platform source..."
tar czf "${BACKUP_DIR}/platform.tar.gz" -C "${SOURCE_DIR}" platform/

# 6. HA Add-on source
echo "[6/6] Archiving HA add-on source..."
cd "${SOURCE_DIR}/ha-agent-addon"
if [ -d .git ]; then
    git archive --format=tar.gz -o "${BACKUP_DIR}/ha-addon.tar.gz" HEAD
else
    tar czf "${BACKUP_DIR}/ha-addon.tar.gz" -C "${SOURCE_DIR}" ha-agent-addon/
fi

# Create manifest
cat > "${BACKUP_DIR}/MANIFEST.json" <<MANIFEST
{
  "backup_version": "1.0",
  "timestamp": "${TIMESTAMP}",
  "hostname": "$(hostname)",
  "files": {
    "db_burghscape.sql": "PostgreSQL database dump",
    "env": "Environment variables (secrets)",
    "docker-compose.yml": "Docker service definitions",
    "cloudflared/": "Cloudflare tunnel configs",
    "platform.tar.gz": "Frontend + Backend source code",
    "ha-addon.tar.gz": "HA add-on source code"
  }
}
MANIFEST

# Create single archive
FINAL_ARCHIVE="/home/kenny/backups/burghscape-backup-${TIMESTAMP}.tar.gz"
mkdir -p /home/kenny/backups
tar czf "${FINAL_ARCHIVE}" -C /tmp "burghscape-backup-${TIMESTAMP}"

# Cleanup temp dir
rm -rf "${BACKUP_DIR}"

echo ""
echo "=== Backup Complete ==="
echo "Archive: ${FINAL_ARCHIVE}"
echo "Size: $(du -h ${FINAL_ARCHIVE} | cut -f1)"
echo ""
echo "To upload to OneDrive manually:"
echo "  rclone copy ${FINAL_ARCHIVE} onedrive:/Backups/infra/"
echo ""
echo "To restore, extract and see restore_instructions.sh"
