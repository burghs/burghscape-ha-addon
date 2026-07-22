#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"
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
git archive HEAD:backend | docker build --build-arg "APP_VERSION=$platform_version" --build-arg "VCS_REF=$platform_commit" -t "burghscape-backend:$platform_commit" -
git archive HEAD:frontend | docker build --build-arg "APP_VERSION=$platform_version" --build-arg "VCS_REF=$platform_commit" -t "burghscape-frontend:$platform_commit" -
docker compose -f "$compose_base" -f "$compose_release" up -d --no-build --force-recreate backend frontend

health=$(curl --fail --silent --show-error http://127.0.0.1:8000/health)
frontend=$(curl --fail --silent --show-error http://127.0.0.1:3000/version.json)
python3 - "$platform_version" "$platform_commit" "$health" "$frontend" <<'PY'
import json,sys
version,commit,health_raw,frontend_raw=sys.argv[1:]
health=json.loads(health_raw);frontend=json.loads(frontend_raw)
assert health["status"]=="healthy"
assert health["version"]==version and health["commit"]==commit, health
assert frontend["version"]==version and frontend["commit"]==commit, frontend
print(json.dumps({"backend":health,"frontend":frontend},indent=2))
PY
docker exec -i mybeacon-db psql -v ON_ERROR_STOP=1 -U burghscape -d burghscape -c "SELECT to_regclass('public.client_onboarding_states') AS onboarding_table;"
echo "Pre-deployment database backup: $backup_file"
