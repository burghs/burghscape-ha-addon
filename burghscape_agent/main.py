#!/usr/bin/env python3
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("burghscape.agent")

config = Config()
cloudflared_process = None


def get_cloudflared_path() -> str:
    """Find cloudflared binary."""
    for path in ["/usr/local/bin/cloudflared", "/usr/bin/cloudflared", "cloudflared"]:
        if os.path.isfile(path) or subprocess.run(["which", path], capture_output=True).returncode == 0:
            return path
    return "cloudflared"


def write_cloudflared_config(tunnel_id: str, hostname: str) -> str:
    logger.debug(f"DEBUG: write_cloudflared_config - tunnel_id={tunnel_id}, hostname={hostname}")
    """Write cloudflared config file and return path."""
    config_dir = "/config/cloudflared"
    os.makedirs(config_dir, exist_ok=True)

    import yaml
    cfg = {
        "tunnel": tunnel_id,
        "ingress": [
            {
                "hostname": hostname,
                "service": "http://localhost:8123",
                "originRequest": {
                    "noTLSVerify": True
                }
            },
            {"service": "http_status:404"}
        ]
    }

    config_path = os.path.join(config_dir, "config.yml")
    with open(config_path, "w") as f:
        yaml.dump(cfg, f)

    logger.info(f"Cloudflare config written to {config_path}")
    return config_path


def start_cloudflared(tunnel_token: str, tunnel_id: str, hostname: str) -> subprocess.Popen:
    logger.debug(f"DEBUG: start_cloudflared - tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
    """Start cloudflared tunnel process."""
    global cloudflared_process

    if cloudflared_process and cloudflared_process.poll() is None:
        logger.info("cloudflared already running")
        return cloudflared_process

    config_path = write_cloudflared_config(tunnel_id, hostname)

    # cloudflared tunnel --config <file> run --token <TOKEN> <TUNNEL_ID>
    cf_bin = get_cloudflared_path()
    cmd = [
        cf_bin, "tunnel",
        "--config", config_path,
        "run",
        "--token", tunnel_token,
        tunnel_id,
    ]

    logger.info(f"Starting cloudflared: tunnel --config ... run --token ... {tunnel_id} (to {hostname})")

    try:
        log_file = open("/config/cloudflared/cloudflared.log", "a")
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        logger.info(f"cloudflared started (PID {process.pid})")

        time.sleep(5)
        if process.poll() is not None:
            with open("/config/cloudflared/cloudflared.log", "r") as f:
                last_lines = f.readlines()[-15:]
            logger.error("cloudflared exited immediately! Last log lines:")
            for line in last_lines:
                logger.error(f"  {line.strip()}")
            return None

        return process
    except FileNotFoundError:
        logger.error("cloudflared not installed!")
        return None


def stop_cloudflared():
    """Stop cloudflared tunnel process."""
    global cloudflared_process
    if cloudflared_process and cloudflared_process.poll() is None:
        logger.info("Stopping cloudflared...")
        cloudflared_process.terminate()
        try:
            cloudflared_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cloudflared_process.kill()
        cloudflared_process = None


def is_cloudflared_healthy() -> bool:
    """Check if cloudflared is running and connected."""
    global cloudflared_process
    if cloudflared_process is None:
        return False
    if cloudflared_process.poll() is not None:
        return False
    return True


async def setup_tunnel(platform: PlatformClient) -> bool:
    """Fetch tunnel config from platform and start cloudflared."""
    global cloudflared_process

    logger.info("Fetching tunnel config from platform...")
    logger.debug(f"DEBUG: setup_tunnel - Before platform.get_tunnel_config: {platform}")
    tunnel_cfg = await platform.get_tunnel_config()
    logger.debug(f"DEBUG: setup_tunnel - After platform.get_tunnel_config: {tunnel_cfg}")
    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg received: {tunnel_cfg}")

    if not tunnel_cfg or not tunnel_cfg.get("tunnel_token"):
        logger.warning("No tunnel config available from platform")
        return False

    tunnel_token = tunnel_cfg["tunnel_token"]
    tunnel_id = tunnel_cfg.get("tunnel_id", "")
    hostname = tunnel_cfg.get("hostname", "")
    logger.debug(f"DEBUG: setup_tunnel - After hostname assignment from tunnel_cfg: hostname={hostname}")
    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
    if not hostname:
        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={hostname}")
        hostname = config.instance_name + ".mybeacon.co.za" # Fallback if platform doesnt provide it
