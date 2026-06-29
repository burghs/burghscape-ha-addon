#!/bin/bash
# Burghscape Server Restore Script
# Extracts a backup archive and restores all components

set -euo pipefail

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup-archive.tar.gz>"
    echo "Example: ./restore.sh burghscape-backup-20260629_153000.tar.gz"
    exit 1
fi

BACKUP_ARCHIVE="$1"
RESTORE_DIR=$(mktemp -d)
TARGET_DIR="/home/kenny/burghscape"

echo "=== Burghscape Server Restore ==="
echo "Archive: ${BACKUP_ARCHIVE}"
echo "Target: ${TARGET_DIR}"
echo ""

# Extract
echo "[1/6] Extracting backup..."
tar xzf "${BACKUP_ARCHIVE}" -C "${RESTORE_DIR}"
EXTRACTED=$(find "${RESTORE_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)
echo "Extracted to: ${EXTRACTED}"

# 1. Restore platform source
echo "[2/6] Restoring platform source..."
if [ -f "${EXTRACTED}/platform.tar.gz" ]; then
    tar xzf "${EXTRACTED}/platform.tar.gz" -C "${TARGET_DIR}"
    echo "  ✓ Platform source restored"
fi

# 2. Restore docker-compose
echo "[3/6] Restoring docker-compose.yml..."
if [ -f "${EXTRACTED}/docker-compose.yml" ]; then
    cp "${EXTRACTED}/docker-compose.yml" "${TARGET_DIR}/docker-compose.yml"
    echo "  ✓ docker-compose.yml restored"
fi

# 3. Restore .env
echo "[4/6] Restoring .env (secrets)..."
if [ -f "${EXTRACTED}/env" ]; then
    cp "${EXTRACTED}/env" "${TARGET_DIR}/.env"
    echo "  ✓ .env restored"
fi

# 4. Restore cloudflared configs
echo "[5/6] Restoring cloudflare tunnel configs..."
if [ -d "${EXTRACTED}/cloudflared" ]; then
    mkdir -p "${TARGET_DIR}/cloudflared"
    cp "${EXTRACTED}/cloudflared/"*.yaml "${TARGET_DIR}/cloudflared/" 2>/dev/null || true
    echo "  ✓ Cloudflare configs restored"
fi

# 5. Import database
echo "[6/6] Importing PostgreSQL database..."
if [ -f "${EXTRACTED}/db_burghscape.sql" ]; then
    echo "  Starting DB container if needed..."
    cd "${TARGET_DIR}"
    docker compose up -d db
    sleep 5
    docker exec -i mybeacon-db psql -U burghscape -d postgres \
        < "${EXTRACTED}/db_burghscape.sql"
    echo "  ✓ Database restored"
fi

# Cleanup
rm -rf "${RESTORE_DIR}"

echo ""
echo "=== Restore Complete ==="
echo ""
echo "Next steps:"
echo "  1. cd ${TARGET_DIR}"
echo "  2. docker compose up -d"
echo "  3. Verify: docker compose ps"
echo "  4. Test: curl -s http://localhost:8000/health"
echo ""
echo "HA add-on (if repo exists):"
echo "  cd ${TARGET_DIR}/ha-agent-addon"
echo "  git pull origin main"
