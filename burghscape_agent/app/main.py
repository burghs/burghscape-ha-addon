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
import uuid

from app.config import Config
from app.ha_client import HAClient
from app.platform_client import PlatformClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("burghscape.agent")

config = Config()
cloudflared_process = None
HA_CONFIG_PATH = "/config/configuration.yaml"
ONBOARDING_STATE_PATH = "/data/onboarding_state.json"
MANUAL_BACKUP_ONCE_STATE_PATH = "/data/managed-backup/manual-once-state.json"
REQUIRED_PROXIES = {"127.0.0.1", "::1", "172.30.32.0/23"}
onboarding_status = "starting"
onboarding_error = None
attempted_onboarding_keys = set()
active_backup_operation_ids = set()


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


def _hash_secret(value: str) -> str:
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()


def addon_config_hash() -> str:
    payload = {
        "ha_url": config.ha_url,
        "ha_token_hash": _hash_secret(config.ha_token),
        "platform_url": config.platform_url,
        "subscription_token_hash": _hash_secret(config.subscription_token),
        "instance_name": config.instance_name,
        "heartbeat_interval": config.heartbeat_interval,
        "monitor_entities": config.monitor_entities,
        "monitor_disk": config.monitor_disk,
        "monitor_automations": config.monitor_automations,
        "monitor_updates": config.monitor_updates,
        "monitor_backups": config.monitor_backups,
        "monitor_frigate": config.monitor_frigate,
        "backup_enabled": config.backup_enabled,
        "backup_interval_hours": config.backup_interval_hours,
        "backup_max_part_size_mb": config.backup_max_part_size_mb,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def onboarding_attempt_key(config_hash: str, tunnel_config: dict) -> str:
    payload = {
        "config_hash": config_hash,
        "addon_config_hash": addon_config_hash(),
        "hostname": tunnel_config.get("hostname", ""),
        "tunnel_id": tunnel_config.get("id", ""),
        "tunnel_token_hash": _hash_secret(tunnel_config.get("token", "")),
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


def valid_public_redirect(hostname: str, location: str) -> bool:
    if not location:
        return False
    return (
        location.startswith("/")
        or location.startswith(f"https://{hostname}/")
        or location.startswith(f"http://{hostname}/")
    )


async def public_tunnel_is_active(hostname: str, attempts: int = 12, delay_seconds: int = 5) -> bool:
    url = f"https://{hostname}/"
    last_error = "no verification attempts completed"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, attempts + 1):
            try:
                async with session.get(url, allow_redirects=False) as resp:
                    body = sanitize_response_body(await resp.text())
                    location_header = resp.headers.get("Location", "")
                    location = sanitize_response_body(location_header, limit=200)
                    logger.info(
                        "Public tunnel verification attempt=%s/%s status=%s location=%s body=%s",
                        attempt,
                        attempts,
                        resp.status,
                        location,
                        body,
                    )
                    if 200 <= resp.status < 300:
                        return True
                    if 300 <= resp.status < 400 and valid_public_redirect(hostname, location_header):
                        return True
                    last_error = f"HTTP {resp.status}: {body}"
            except Exception as e:
                last_error = f"{type(e).__name__}: {sanitize_response_body(str(e), limit=200)}"
                logger.warning(
                    "Public tunnel verification attempt=%s/%s failed: %s",
                    attempt,
                    attempts,
                    last_error,
                )
            if attempt < attempts:
                await asyncio.sleep(delay_seconds)
    set_onboarding_status("verification_failed", f"Public tunnel verification failed for {url}: {last_error}")
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
        try:
            cloudflared_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("cloudflared did not stop cleanly; killing process")
            cloudflared_process.kill()
            cloudflared_process.wait(timeout=5)
        cloudflared_process = None


def is_cloudflared_healthy() -> bool:
    global cloudflared_process
    return cloudflared_process is not None and cloudflared_process.poll() is None


async def setup_tunnel(platform: PlatformClient) -> bool:
    try:
        global cloudflared_process
        tunnel_config = await platform.get_tunnel_config()
        if not tunnel_config or not tunnel_config.get("token"):
            set_onboarding_status("tunnel_config_failed", "No tunnel config received from platform")
            return False
        hostname = tunnel_config["hostname"]
        logger.info(f"Tunnel config received: {hostname}")

        state = load_onboarding_state()
        config_hash = desired_config_hash(hostname)
        attempt_key = onboarding_attempt_key(config_hash, tunnel_config)
        if (
            state.get("status") == "verification_failed"
            and state.get("attempt_key") == attempt_key
            and attempt_key in attempted_onboarding_keys
        ):
            set_onboarding_status("verification_failed", state.get("error") or "Previous public tunnel verification failed")
            logger.warning("Skipping repeated onboarding attempt for unchanged tunnel/configuration")
            return True

        attempted_onboarding_keys.add(attempt_key)
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

        log_effective_ha_proxy_config(hostname)

        process = start_cloudflared(tunnel_config["token"], tunnel_config["id"], hostname)
        cloudflared_process = process
        if process is None:
            error = "cloudflared did not stay running"
            set_onboarding_status("cloudflared_failed", error)
            save_onboarding_state({
                "attempt_key": attempt_key,
                "config_hash": config_hash,
                "status": "verification_failed",
                "error": error,
                "failed_at": time.time(),
                "hostname": hostname,
            })
            return True

        set_onboarding_status("verifying_public_tunnel")
        if not await public_tunnel_is_active(hostname):
            error = onboarding_error or "Public tunnel verification failed"
            save_onboarding_state({
                "attempt_key": attempt_key,
                "config_hash": config_hash,
                "status": "verification_failed",
                "error": error,
                "failed_at": time.time(),
                "hostname": hostname,
            })
            stop_cloudflared()
            return True

        save_onboarding_state({
            "attempt_key": attempt_key,
            "config_hash": config_hash,
            "restart_requested": False,
            "verified": True,
            "verified_at": time.time(),
            "status": "ready",
            "hostname": hostname,
        })
        set_onboarding_status("ready")
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


def utc_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def safe_error_category(exc: Exception) -> str:
    return type(exc).__name__


def load_manual_backup_once_state(path: str = MANUAL_BACKUP_ONCE_STATE_PATH) -> dict:
    try:
        if not os.path.isfile(path):
            return {}
        with open(path, "r") as f:
            loaded = json.load(f) or {}
        if not isinstance(loaded, dict):
            logger.warning("Manual backup one-shot state file is not a mapping; treating as unarmed")
            return {"state_error": "invalid_shape"}
        return loaded
    except Exception as e:
        logger.warning("Could not load manual backup one-shot state: %s", type(e).__name__)
        return {"state_error": type(e).__name__}


def save_manual_backup_once_state(state: dict, path: str = MANUAL_BACKUP_ONCE_STATE_PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        temp_path = f"{path}.tmp"
        with open(temp_path, "w") as f:
            json.dump(state, f, sort_keys=True)
        os.replace(temp_path, path)
    except Exception as e:
        logger.warning("Could not save manual backup one-shot state: %s", type(e).__name__)


def prepare_manual_backup_once(manual_backup_once: bool, path: str = MANUAL_BACKUP_ONCE_STATE_PATH) -> tuple[bool, str | None]:
    state = load_manual_backup_once_state(path)
    previous_trigger = state.get("trigger_state") is True
    attempted = state.get("attempted") is True

    if not manual_backup_once:
        armed_state = {
            "trigger_state": False,
            "attempted": False,
            "result": "armed",
            "updated_at": utc_timestamp(),
        }
        save_manual_backup_once_state(armed_state, path)
        if previous_trigger or attempted:
            logger.info("Manual backup one-shot trigger reset and re-armed")
        else:
            logger.info("Manual backup one-shot trigger armed")
        return False, None

    if previous_trigger and attempted:
        logger.info("Manual backup one-shot trigger already consumed; skipping")
        return False, state.get("operation_id")

    operation_id = uuid.uuid4().hex
    save_manual_backup_once_state({
        "trigger_state": True,
        "attempted": True,
        "operation_id": operation_id,
        "attempted_at": utc_timestamp(),
        "result": "running",
    }, path)
    logger.info("Manual backup one-shot trigger activated operation_id=%s", operation_id)
    return True, operation_id


async def run_manual_backup_once_background(operation_id: str, path: str = MANUAL_BACKUP_ONCE_STATE_PATH):
    logger.info("Manual backup workflow started operation_id=%s", operation_id)
    try:
        from app.manual_backup import run_manual_backup
        result = await run_manual_backup(operation_id)
        safe_result = {
            "trigger_state": True,
            "attempted": True,
            "operation_id": operation_id,
            "attempted_at": load_manual_backup_once_state(path).get("attempted_at"),
            "completed_at": utc_timestamp(),
            "result": "completed",
            "backup_id": result.get("backup_id"),
            "ha_backup_slug": result.get("ha_backup_slug"),
            "size_bytes": result.get("size_bytes"),
            "sha256": result.get("sha256"),
        }
        save_manual_backup_once_state(safe_result, path)
        logger.info("Manual backup workflow completed operation_id=%s backup_id=%s", operation_id, result.get("backup_id"))
    except Exception as e:
        try:
            async with PlatformClient(config) as platform:
                await platform.report_backup_state(operation_id, "failed", error_category=safe_error_category(e))
        except Exception as report_error:
            logger.warning("Could not report backup failure state: %s", type(report_error).__name__)
        save_manual_backup_once_state({
            "trigger_state": True,
            "attempted": True,
            "operation_id": operation_id,
            "failed_at": utc_timestamp(),
            "result": "failed",
            "error_category": safe_error_category(e),
        }, path)
        logger.error("Manual backup workflow failed operation_id=%s error_category=%s", operation_id, safe_error_category(e))



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
    should_run_manual_backup, manual_backup_operation_id = prepare_manual_backup_once(config.manual_backup_once)
    if should_run_manual_backup and manual_backup_operation_id:
        asyncio.create_task(run_manual_backup_once_background(manual_backup_operation_id))

    while True:
        try:
            async with HAClient(config) as ha, PlatformClient(config) as platform:
                if not tunnel_setup_done:
                    tunnel_setup_done = await setup_tunnel(platform)
                report = await run_once(ha, platform)
                command = await platform.get_backup_command()
                operation_id = command.get("operation_id") if command.get("command") == "managed_backup" else None
                if operation_id and operation_id not in active_backup_operation_ids:
                    active_backup_operation_ids.add(operation_id)
                    task = asyncio.create_task(run_manual_backup_once_background(operation_id))
                    task.add_done_callback(lambda _task, op=operation_id: active_backup_operation_ids.discard(op))
                if not report.get("online"):
                    logger.warning("HA appears offline, will retry...")
                if onboarding_status == "ready" and not is_cloudflared_healthy():
                    logger.warning("cloudflared tunnel is down, attempting restart...")
                    tunnel_setup_done = False
                elif onboarding_status != "ready" and not is_cloudflared_healthy():
                    logger.info("cloudflared is not running while onboarding_status=%s", onboarding_status)
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
