#!/usr/bin/env bash
# Build the Burghscape HA Agent add-on for all supported architectures
# Usage: ./build.sh [version]
set -euo pipefail

VERSION="${1:-0.2.0}"
ADDON_DIR="$(cd "$(dirname "$0")" && pwd)"
REGISTRY="${REGISTRY:-localhost}"

echo "=== Building Burghscape Agent v${VERSION} ==="

cd "$ADDON_DIR"

# Build for amd64 (most common for Intel NUC, etc.)
echo "--- Building amd64 ---"
docker build --platform linux/amd64 -t "burghscape/ha-agent:${VERSION}-amd64" .

# Build for aarch64 (Raspberry Pi 4/5, ARM-based NUCs)
echo "--- Building aarch64 ---"
docker build --platform linux/aarch64 -t "burghscape/ha-agent:${VERSION}-aarch64" .

echo "=== Build complete ==="
echo ""
echo "To push to a registry:"
echo "  docker tag burghscape/ha-agent:${VERSION}-amd64 your-registry/ha-agent:${VERSION}-amd64"
echo "  docker push your-registry/ha-agent:${VERSION}-amd64"
echo ""
echo "To install on a client HA:"
echo "  1. Copy this folder to /addons/burghscape_agent/ on the client HA"
echo "  2. In HA: Settings → Add-ons → Add-on Store → Local Add-ons → Install"
echo "  3. Configure: platform_url, subscription_token, instance_name"
echo "  4. Start the add-on — tunnel auto-configures!"
