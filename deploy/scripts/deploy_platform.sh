#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
deployment_env=/home/kenny/burghscape/.env
test -f "$deployment_env"
TOTP_ENCRYPTION_KEY=$(sed -n 's/^TOTP_ENCRYPTION_KEY=//p' "$deployment_env" | tail -n 1)
export TOTP_ENCRYPTION_KEY
: "${TOTP_ENCRYPTION_KEY:?TOTP_ENCRYPTION_KEY must be configured persistently in $deployment_env}"
python3 - <<'PYKEY'
import base64, os
from cryptography.fernet import Fernet
value = os.environ["TOTP_ENCRYPTION_KEY"].encode()
assert len(base64.urlsafe_b64decode(value)) == 32
Fernet(value)
PYKEY
test "$(git branch --show-current)" = "master"
platform_commit=$(git rev-parse HEAD)
platform_version=$(PYTHONDONTWRITEBYTECODE=1 python3 -c 'import sys;sys.path.insert(0,"backend/app");from config import get_settings;print(get_settings().APP_VERSION)')
export PLATFORM_IMAGE_TAG="$platform_commit"
compose_base=/home/kenny/burghscape/docker-compose.yml
compose_release="$repo_root/deploy/releases/docker-compose.platform.yml"
backup_file="/home/kenny/backups/platform-predeploy-${platform_commit:0:12}-$(date -u +%Y%m%dT%H%M%SZ).sql"

echo "Deploying Platform $platform_version at $platform_commit"
docker exec mybeacon-db pg_dump -U burghscape -d burghscape > "$backup_file"
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape < "$repo_root/backend/migrations/20260722_add_versioned_onboarding.sql"
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape < "$repo_root/backend/migrations/20260722_clear_pre_overlay_popup_impressions.sql"
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape < "$repo_root/backend/migrations/20260722_campaign_notification_lifecycle.sql"
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape < "$repo_root/backend/migrations/20260723_add_client_totp.sql"
git archive HEAD:backend | docker build --build-arg "APP_VERSION=$platform_version" --build-arg "VCS_REF=$platform_commit" -t "burghscape-backend:$platform_commit" -
git archive HEAD:frontend | docker build --build-arg "APP_VERSION=$platform_version" --build-arg "VCS_REF=$platform_commit" -t "burghscape-frontend:$platform_commit" -
docker compose -f "$compose_base" -f "$compose_release" up -d --no-build --force-recreate backend frontend

fetch_with_retry() {
  local url=$1
  local value
  for _attempt in $(seq 1 30); do
    if value=$(curl --fail --silent --show-error "$url" 2>/dev/null); then
      printf '%s' "$value"
      return 0
    fi
    sleep 2
  done
  echo "Timed out waiting for $url" >&2
  return 1
}
health=$(fetch_with_retry http://127.0.0.1:8000/health)
frontend=$(fetch_with_retry http://127.0.0.1:3000/version.json)
python3 - "$platform_version" "$platform_commit" "$health" "$frontend" <<'PY'
import json,sys
version,commit,health_raw,frontend_raw=sys.argv[1:]
health=json.loads(health_raw);frontend=json.loads(frontend_raw)
assert health["status"]=="healthy"
assert health["version"]==version and health["commit"]==commit, health
assert frontend["version"]==version and frontend["commit"]==commit, frontend
print(json.dumps({"backend":health,"frontend":frontend},indent=2))
PY
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape -c "SELECT to_regclass('public.client_onboarding_states') AS onboarding_table, to_regclass('public.two_factor_challenges') AS two_factor_table;"
echo "Pre-deployment database backup: $backup_file"
