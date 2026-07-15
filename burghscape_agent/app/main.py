"""Main agent loop for Burghscape Agent add-on."""
import asyncio
import logging
import os
import subprocess
import json
import signal
import sys
import time

from app.config import Config
from app.ha_client import HAClient
from app.platform_client import PlatformClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("burghscape.agent")

config = Config()
cloudflared_process = None
HA_CONFIG_PATH = "/config/configuration.yaml"


def get_cloudflared_path() -> str:
    for path in ["/usr/local/bin/cloudflared", "/usr/bin/cloudflared", "cloudflared"]:
        if os.path.isfile(path) or subprocess.run(["which", path], capture_output=True).returncode == 0:
            return path
    return "cloudflared"


def write_cloudflared_config(tunnel_id: str, hostname: str) -> str:
    config_dir = "/config/cloudflared"
    os.makedirs(config_dir, exist_ok=True)
    import yaml
    cfg = {"tunnel": tunnel_id, "ingress": [{"hostname": hostname, "service": "http://localhost:8123", "originRequest": {"noTLSVerify": True}}, {"service": "http_status:404"}]}
    config_path = os.path.join(config_dir, "config.yml")
    with open(config_path, "w") as f:
        yaml.dump(cfg, f)
    logger.info(f"Cloudflare config written to {config_path}")
    return config_path


def ensure_ha_config(hostname: str):
    if not os.path.isfile(HA_CONFIG_PATH):
        logger.warning("HA config not found at %s", HA_CONFIG_PATH)
        return

    try:
        import yaml
        with open(HA_CONFIG_PATH, "r") as f:
            ha_config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("Could not parse %s: %s. Skipping modifications.", HA_CONFIG_PATH, e)
        return

    made_changes = False

    http_config = ha_config.get("http", {})
    if not isinstance(http_config, dict):
        http_config = {}

    if http_config.get("use_x_forwarded_for") is not True:
        http_config["use_x_forwarded_for"] = True
        made_changes = True

    existing_proxies = http_config.get("trusted_proxies", [])
    if isinstance(existing_proxies, str):
        current_proxies = {existing_proxies}
    elif isinstance(existing_proxies, list):
        current_proxies = set(existing_proxies)
    else:
        current_proxies = set()

    required_proxies = {"127.0.0.1", "::1", "172.30.32.0/23"}
    updated_proxies = current_proxies | required_proxies
    if updated_proxies != current_proxies:
        http_config["trusted_proxies"] = sorted(updated_proxies)
        made_changes = True

    if made_changes or ha_config.get("http") != http_config:
        ha_config["http"] = http_config

    external_url = f"https://{hostname}"
    homeassistant_config = ha_config.get("homeassistant", {})
    if not isinstance(homeassistant_config, dict):
        homeassistant_config = {}
    if homeassistant_config.get("external_url") != external_url:
        logger.info("Setting Home Assistant external_url to %s", external_url)
        homeassistant_config["external_url"] = external_url
        ha_config["homeassistant"] = homeassistant_config
        made_changes = True

    if made_changes:
        logger.info("Writing updated Home Assistant proxy configuration to %s", HA_CONFIG_PATH)
        try:
            with open(HA_CONFIG_PATH, "w") as f:
                yaml.dump(ha_config, f, default_flow_style=False, sort_keys=False)
            logger.info("Home Assistant configuration updated. A Home Assistant restart may be required.")
        except Exception as e:
            logger.error("Failed to write %s: %s", HA_CONFIG_PATH, e)
    else:
        logger.info("Home Assistant proxy configuration is already correct.")


def start_cloudflared(tunnel_token: str, tunnel_id: str, hostname: str):
    global cloudflared_process
    if cloudflared_process and cloudflared_process.poll() is None:
        logger.info("cloudflared already running")
        return cloudflared_process
    config_path = write_cloudflared_config(tunnel_id, hostname)
    cf_bin = get_cloudflared_path()
    cmd = [cf_bin, "tunnel", "--config", config_path, "run", "--token", tunnel_token, tunnel_id]
    logger.info(f"Starting cloudflared: tunnel --config ... run --token ... {tunnel_id} (to {hostname})")
    try:
        log_file = open("/config/cloudflared/cloudflared.log", "a")
        process = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT)
        logger.info(f"cloudflared started (PID {process.pid})")
        time.sleep(5)
        if process.poll() is not None:
            with open("/config/cloudflared/cloudflared.log", "r") as f:
                last_lines = f.readlines()[-15:]
            logger.error("cloudflared exited immediately! Last log lines:")
            for line in last_lines:
                logger.error(f"  {line.strip()}")
            return None
    except Exception:
        logger.error("Failed to start cloudflared", exc_info=True)
        return None
    return process


def stop_cloudflared():
    global cloudflared_process
    if cloudflared_process and cloudflared_process.poll() is None:
        logger.info("Stopping cloudflared...")
        cloudflared_process.terminate()
        cloudflared_process = None


def is_cloudflared_healthy() -> bool:
    global cloudflared_process
    return cloudflared_process is not None and cloudflared_process.poll() is None


async def setup_tunnel(platform: PlatformClient) -> bool:
    try:
        tunnel_config = await platform.get_tunnel_config()
        if not tunnel_config or not tunnel_config.get("token"):
            logger.warning("No tunnel config received from platform")
            return False
        hostname = tunnel_config["hostname"]
        logger.info(f"Tunnel config received: {hostname}")
        ensure_ha_config(hostname)
        global cloudflared_process
        process = start_cloudflared(tunnel_config["token"], tunnel_config["id"], hostname)
        cloudflared_process = process
        return process is not None
    except Exception as e:
        logger.error(f"Failed to setup tunnel: {e}")
        return False


async def run_once(ha: HAClient, platform: PlatformClient) -> dict:
    logger.info("Collecting HA report...")
    report = await ha.get_full_report()
    report["tunnel_running"] = is_cloudflared_healthy()
    logger.info("Report: online=%s entities=%s version=%s tunnel=%s",
        report.get("online"), report.get("entities_count", "?"), report.get("ha_version", "?"),
        report.get("tunnel_running"))
    result = await platform.send_heartbeat(report)
    logger.info("Platform response: %s", result)
    return report


async def main_loop():
    logger.info("Burghscape Agent starting")
    logger.info("Platform: %s", config.platform_url)
    logger.info("Instance: %s", config.instance_name)
    logger.info("Heartbeat: every %ss", config.heartbeat_interval)

    def handle_signal(sig, frame):
        logger.info("Received signal %s, shutting down...", sig)
        stop_cloudflared()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    tunnel_setup_done = False

    while True:
        try:
            async with HAClient(config) as ha, PlatformClient(config) as platform:
                if not tunnel_setup_done:
                    tunnel_setup_done = await setup_tunnel(platform)
                report = await run_once(ha, platform)
                if not report.get("online"):
                    logger.warning("HA appears offline, will retry...")
                if not is_cloudflared_healthy():
                    logger.warning("cloudflared tunnel is down, attempting restart...")
                    tunnel_setup_done = False
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        logger.info("Sleeping %ss until next report...", config.heartbeat_interval)
        await asyncio.sleep(config.heartbeat_interval)


def main():
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        stop_cloudflared()


if __name__ == "__main__":
    main()
