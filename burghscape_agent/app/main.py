"""Main agent loop for Burghscape Agent add-on."""
import asyncio
import aiohttp
import hashlib
import logging
import os
import shutil
import tempfile
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
ONBOARDING_STATE_PATH = "/data/onboarding_state.json"
REQUIRED_PROXIES = {"127.0.0.1", "::1", "172.30.32.0/23"}
onboarding_status = "starting"
onboarding_error = None


class TaggedYamlValue:
    def __init__(self, tag: str, value):
        self.tag = tag
        self.value = value


class HomeAssistantConfigLoader:
    pass


class HomeAssistantConfigDumper:
    pass


def load_ha_yaml_module():
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    class Dumper(yaml.SafeDumper):
        pass

    def construct_unknown(loader, tag_suffix, node):
        tag = "!" + tag_suffix
        if isinstance(node, yaml.ScalarNode):
            value = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node)
        elif isinstance(node, yaml.MappingNode):
            value = loader.construct_mapping(node)
        else:
            value = None
        return TaggedYamlValue(tag, value)

    def represent_tagged(dumper, data):
        if isinstance(data.value, dict):
            return dumper.represent_mapping(data.tag, data.value)
        if isinstance(data.value, list):
            return dumper.represent_sequence(data.tag, data.value)
        return dumper.represent_scalar(data.tag, str(data.value))

    Loader.add_multi_constructor("!", construct_unknown)
    Dumper.add_representer(TaggedYamlValue, represent_tagged)
    return yaml, Loader, Dumper


def load_ha_config_file(path: str = HA_CONFIG_PATH) -> dict:
    yaml, Loader, _ = load_ha_yaml_module()
    with open(path, "r") as f:
        loaded = yaml.load(f, Loader=Loader) or {}
    if not isinstance(loaded, dict):
        raise ValueError("configuration root is not a mapping")
    return loaded


def write_candidate_config(path: str, ha_config: dict) -> str:
    yaml, _, Dumper = load_ha_yaml_module()
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix=".configuration.", suffix=".yaml.tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(ha_config, f, Dumper=Dumper, default_flow_style=False, sort_keys=False)
        return temp_path
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def backup_ha_config(path: str = HA_CONFIG_PATH) -> str:
    backup_path = f"{path}.burghscape.bak"
    shutil.copy2(path, backup_path)
    return backup_path



def sanitize_response_body(body: str, limit: int = 300) -> str:
    sanitized = " ".join((body or "").split())
    return sanitized[:limit]


def find_top_level_key_count(path: str, key: str) -> int:
    count = 0
    try:
        with open(path, "r") as f:
            for line in f:
                stripped = line.strip()
                if not line.startswith((" ", "\t")) and stripped.startswith(f"{key}:"):
                    count += 1
    except Exception as e:
        logger.warning("Could not inspect %s for duplicate %s blocks: %s", path, key, e)
    return count


def log_effective_ha_proxy_config(hostname: str):
    try:
        ha_config = load_ha_config_file()
        http_config = ha_config.get("http", {})
        homeassistant_config = ha_config.get("homeassistant", {})
        logger.info(
            "Effective HA proxy config from %s: http_type=%s use_x_forwarded_for=%s trusted_proxies=%s homeassistant_type=%s external_url_matches=%s top_level_http_blocks=%s top_level_homeassistant_blocks=%s",
            HA_CONFIG_PATH,
            type(http_config).__name__,
            http_config.get("use_x_forwarded_for") if isinstance(http_config, dict) else None,
            http_config.get("trusted_proxies") if isinstance(http_config, dict) else None,
            type(homeassistant_config).__name__,
            homeassistant_config.get("external_url") == f"https://{hostname}" if isinstance(homeassistant_config, dict) else False,
            find_top_level_key_count(HA_CONFIG_PATH, "http"),
            find_top_level_key_count(HA_CONFIG_PATH, "homeassistant"),
        )
    except Exception as e:
        logger.warning("Could not log effective HA proxy config: %s", e)


def set_onboarding_status(status: str, error: str | None = None):
    global onboarding_status, onboarding_error
    onboarding_status = status
    onboarding_error = error
    if error:
        logger.warning("Onboarding status: %s (%s)", status, error)
    else:
        logger.info("Onboarding status: %s", status)


def load_onboarding_state() -> dict:
    try:
        if not os.path.isfile(ONBOARDING_STATE_PATH):
            return {}
        with open(ONBOARDING_STATE_PATH, "r") as f:
            return json.load(f) or {}
    except Exception as e:
        logger.warning("Could not load onboarding state: %s", e)
        return {}


def save_onboarding_state(state: dict):
    try:
        os.makedirs(os.path.dirname(ONBOARDING_STATE_PATH), exist_ok=True)
        with open(ONBOARDING_STATE_PATH, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning("Could not save onboarding state: %s", e)


def desired_config_hash(hostname: str) -> str:
    payload = {
        "hostname": hostname,
        "use_x_forwarded_for": True,
        "trusted_proxies": sorted(REQUIRED_PROXIES),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate_ha_config_file(hostname: str, path: str = HA_CONFIG_PATH) -> bool:
    try:
        ha_config = load_ha_config_file(path)
    except Exception as e:
        logger.error("Could not validate %s: %s", path, e)
        return False

    http_config = ha_config.get("http", {})
    homeassistant_config = ha_config.get("homeassistant", {})
    if not isinstance(http_config, dict) or not isinstance(homeassistant_config, dict):
        logger.error("Home Assistant config validation failed: http or homeassistant block is not a mapping")
        return False
    if http_config.get("use_x_forwarded_for") is not True:
        logger.error("Home Assistant config validation failed: use_x_forwarded_for is not true")
        return False
    proxies = http_config.get("trusted_proxies", [])
    if isinstance(proxies, str):
        proxies = [proxies]
    if not isinstance(proxies, list) or not REQUIRED_PROXIES.issubset(set(proxies)):
        logger.error("Home Assistant config validation failed: required trusted_proxies are missing")
        return False
    if homeassistant_config.get("external_url") != f"https://{hostname}":
        logger.error("Home Assistant config validation failed: external_url does not match platform hostname")
        return False
    return True


def get_supervisor_token() -> str:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if token:
        return token
    token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
    try:
        if os.path.isfile(token_path):
            with open(token_path) as f:
                return f.read().strip()
    except Exception as e:
        logger.warning("Could not read Supervisor token: %s", e)
    return ""


async def request_core_restart() -> bool:
    token = get_supervisor_token()
    if not token:
        set_onboarding_status("restart_failed", "Supervisor token unavailable")
        return False

    urls = [
        "http://supervisor/core/restart",
        "http://172.30.32.2/core/restart",
    ]
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as session:
        for url in urls:
            try:
                async with session.post(url) as resp:
                    body = await resp.text()
                    if resp.status in (200, 202):
                        logger.warning("Requested Home Assistant Core restart via Supervisor API")
                        return True
                    logger.warning("Supervisor restart endpoint %s returned HTTP %s: %s", url, resp.status, body[:200])
            except Exception as e:
                logger.warning("Supervisor restart endpoint %s failed: %s", url, e)
    set_onboarding_status("restart_failed", "Supervisor Core restart request failed")
    return False


async def core_is_reachable() -> bool:
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get("http://localhost:8123/api/") as resp:
                return resp.status < 500
    except Exception:
        return False


async def wait_for_core_restart(timeout_seconds: int = 180) -> bool:
    down_deadline = time.time() + 60
    saw_down = False
    while time.time() < down_deadline:
        if not await core_is_reachable():
            saw_down = True
            logger.info("Home Assistant Core restart is in progress")
            break
        await asyncio.sleep(2)

    if not saw_down:
        logger.warning("Did not observe Home Assistant Core stop after restart request; continuing verification")

    up_deadline = time.time() + timeout_seconds
    while time.time() < up_deadline:
        if await core_is_reachable():
            logger.info("Home Assistant Core is reachable after restart")
            return True
        await asyncio.sleep(5)

    set_onboarding_status("verification_failed", "Home Assistant Core did not become reachable after restart")
    return False


async def reverse_proxy_config_is_active(hostname: str) -> bool:
    log_effective_ha_proxy_config(hostname)
    headers = {
        "Host": hostname,
        "X-Forwarded-For": "203.0.113.10",
        "X-Forwarded-Proto": "https",
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get("http://localhost:8123/", headers=headers, allow_redirects=False) as resp:
                body = await resp.text()
                sanitized_body = sanitize_response_body(body)
                logger.info(
                    "Home Assistant reverse-proxy verification status=%s body=%s",
                    resp.status,
                    sanitized_body,
                )
                if 200 <= resp.status < 400:
                    return True
                set_onboarding_status(
                    "verification_failed",
                    f"Reverse-proxy verification returned HTTP {resp.status}: {sanitized_body}",
                )
                return False
    except Exception as e:
        set_onboarding_status("verification_failed", f"Reverse-proxy verification failed: {e}")
        return False

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


def ensure_ha_config(hostname: str) -> tuple[bool, str | None]:
    if not os.path.isfile(HA_CONFIG_PATH):
        error = f"HA config not found at {HA_CONFIG_PATH}"
        logger.warning(error)
        return False, error

    try:
        ha_config = load_ha_config_file()
    except Exception as e:
        error = f"Could not parse {HA_CONFIG_PATH}: {e}"
        logger.error("%s. Skipping modifications.", error)
        return False, error

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

    updated_proxies = current_proxies | REQUIRED_PROXIES
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
        temp_path = None
        try:
            temp_path = write_candidate_config(HA_CONFIG_PATH, ha_config)
            if not validate_ha_config_file(hostname, temp_path):
                return False, "Candidate Home Assistant configuration failed validation"
            backup_path = backup_ha_config()
            os.replace(temp_path, HA_CONFIG_PATH)
            temp_path = None
            logger.info("Backed up Home Assistant configuration to %s", backup_path)
        except Exception as e:
            error = f"Failed to safely write {HA_CONFIG_PATH}: {e}"
            logger.error(error)
            return False, error
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        if not validate_ha_config_file(hostname):
            return False, "Written Home Assistant configuration failed validation"
        logger.warning("Home Assistant configuration updated and validated. Core restart is required to apply reverse-proxy settings.")
        return True, None

    logger.info("Home Assistant proxy configuration is already correct.")
    return False, None

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
            set_onboarding_status("tunnel_config_failed", "No tunnel config received from platform")
            return False
        hostname = tunnel_config["hostname"]
        logger.info(f"Tunnel config received: {hostname}")

        state = load_onboarding_state()
        config_hash = desired_config_hash(hostname)
        config_changed, config_error = ensure_ha_config(hostname)
        if config_error:
            set_onboarding_status("config_failed", config_error)
            return False

        restart_already_requested = (
            state.get("config_hash") == config_hash
            and state.get("restart_requested") is True
        )
        if config_changed:
            if restart_already_requested:
                set_onboarding_status("restart_pending", "Core restart was already requested for this configuration")
            else:
                state = {
                    "config_hash": config_hash,
                    "restart_requested": True,
                    "restart_requested_at": time.time(),
                    "hostname": hostname,
                }
                save_onboarding_state(state)
                set_onboarding_status("restart_requested")
                if not await request_core_restart():
                    return False
            if not await wait_for_core_restart():
                return False

        if not await reverse_proxy_config_is_active(hostname):
            return False

        save_onboarding_state({
            "config_hash": config_hash,
            "restart_requested": False,
            "verified": True,
            "verified_at": time.time(),
            "hostname": hostname,
        })
        set_onboarding_status("ready")

        global cloudflared_process
        process = start_cloudflared(tunnel_config["token"], tunnel_config["id"], hostname)
        cloudflared_process = process
        if process is None:
            set_onboarding_status("cloudflared_failed", "cloudflared did not stay running")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to setup tunnel: {e}")
        set_onboarding_status("error", str(e))
        return False

async def run_once(ha: HAClient, platform: PlatformClient) -> dict:
    logger.info("Collecting HA report...")
    report = await ha.get_full_report()
    report["tunnel_running"] = is_cloudflared_healthy()
    report["onboarding_status"] = onboarding_status
    if onboarding_error:
        report["onboarding_error"] = onboarding_error
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
