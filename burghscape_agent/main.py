     1|#!/usr/bin/env python3
     2|"""Main agent loop for Burghscape Agent add-on."""
     3|import asyncio
     4|import logging
     5|import os
     6|import subprocess
     7|import json
     8|import signal
     9|import sys
    10|import time
    11|
    12|from app.config import Config
    13|from app.ha_client import HAClient
    14|from app.platform_client import PlatformClient
    15|
    16|logging.basicConfig(
    17|    level=logging.INFO,
    18|    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    19|)
    20|logger = logging.getLogger("burghscape.agent")
    21|
    22|config = Config()
    23|cloudflared_process = None
    24|
    25|
    26|def get_cloudflared_path() -> str:
    27|    """Find cloudflared binary."""
    28|    for path in ["/usr/local/bin/cloudflared", "/usr/bin/cloudflared", "cloudflared"]:
    29|        if os.path.isfile(path) or subprocess.run(["which", path], capture_output=True).returncode == 0:
    30|            return path
    31|    return "cloudflared"
    32|
    33|
    34|def write_cloudflared_config(tunnel_id: str, hostname: str) -> str:
    logger.debug(f"DEBUG: write_cloudflared_config - tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    35|    """Write cloudflared config file and return path."""
    36|    config_dir = "/config/cloudflared"
    37|    os.makedirs(config_dir, exist_ok=True)
    38|
    39|    import yaml
    40|    cfg = {
    41|        "tunnel": tunnel_id,
    42|        "ingress": [
    43|            {
    44|                "hostname": hostname,
    45|                "service": "http://localhost:8123",
    46|                "originRequest": {
    47|                    "noTLSVerify": True
    48|                }
    49|            },
    50|            {"service": "http_status:404"}
    51|        ]
    52|    }
    53|
    54|    config_path = os.path.join(config_dir, "config.yml")
    55|    with open(config_path, "w") as f:
    56|        yaml.dump(cfg, f)
    57|
    58|    logger.info(f"Cloudflare config written to {config_path}")
    59|    return config_path
    60|
    61|
    62|def start_cloudflared(tunnel_token: str, tunnel_id: str, hostname: str) -> subprocess.Popen:
    logger.debug(f"DEBUG: start_cloudflared - tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    63|    """Start cloudflared tunnel process."""
    64|    global cloudflared_process
    65|
    66|    if cloudflared_process and cloudflared_process.poll() is None:
    67|        logger.info("cloudflared already running")
    68|        return cloudflared_process
    69|
    70|    config_path = write_cloudflared_config(tunnel_id, hostname)
    71|
    72|    # cloudflared tunnel --config <file> run --token <TOKEN> <TUNNEL_ID>
    73|    cf_bin = get_cloudflared_path()
    74|    cmd = [
    75|        cf_bin, "tunnel",
    76|        "--config", config_path,
    77|        "run",
    78|        "--token", tunnel_token,
    79|        tunnel_id,
    80|    ]
    81|
    82|    logger.info(f"Starting cloudflared: tunnel --config ... run --token ... {tunnel_id} (to {hostname})")
    83|
    84|    try:
    85|        log_file = open("/config/cloudflared/cloudflared.log", "a")
    86|        process = subprocess.Popen(
    87|            cmd,
    88|            stdout=log_file,
    89|            stderr=subprocess.STDOUT,
    90|        )
    91|        logger.info(f"cloudflared started (PID {process.pid})")
    92|
    93|        time.sleep(5)
    94|        if process.poll() is not None:
    95|            with open("/config/cloudflared/cloudflared.log", "r") as f:
    96|                last_lines = f.readlines()[-15:]
    97|            logger.error("cloudflared exited immediately! Last log lines:")
    98|            for line in last_lines:
    99|                logger.error(f"  {line.strip()}")
   100|            return None
   101|
   102|        return process
   103|    except FileNotFoundError:
   104|        logger.error("cloudflared not installed!")
   105|        return None
   106|
   107|
   108|def stop_cloudflared():
   109|    """Stop cloudflared tunnel process."""
   110|    global cloudflared_process
   111|    if cloudflared_process and cloudflared_process.poll() is None:
   112|        logger.info("Stopping cloudflared...")
   113|        cloudflared_process.terminate()
   114|        try:
   115|            cloudflared_process.wait(timeout=10)
   116|        except subprocess.TimeoutExpired:
   117|            cloudflared_process.kill()
   118|        cloudflared_process = None
   119|
   120|
   121|def is_cloudflared_healthy() -> bool:
   122|    """Check if cloudflared is running and connected."""
   123|    global cloudflared_process
   124|    if cloudflared_process is None:
   125|        return False
   126|    if cloudflared_process.poll() is not None:
   127|        return False
   128|    return True
   129|
   130|
   131|async def setup_tunnel(platform: PlatformClient) -> bool:
   132|    """Fetch tunnel config from platform and start cloudflared."""
   133|    global cloudflared_process
   134|
   135|    logger.info("Fetching tunnel config from platform...")
    logger.debug(f"DEBUG: setup_tunnel - Before platform.get_tunnel_config: {{platform}}")
   136|    tunnel_cfg = await platform.get_tunnel_config()
    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg received: {{tunnel_cfg}}")
   137|    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg: {tunnel_cfg}")
   138|
   139|    if not tunnel_cfg or not tunnel_cfg.get("tunnel_token"):
   140|        logger.warning("No tunnel config available from platform")
   141|        return False
   142|
   143|    tunnel_token = tunnel_cfg["tunnel_token"]
   144|    tunnel_id = tunnel_cfg.get("tunnel_id", "")
   145|    hostname = tunnel_cfg.get("hostname", "")
    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
   146|    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
   147|
   148|    if not hostname:
        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={{hostname}}")
   149|        hostname = config.instance_name + ".mybeacon.co.za" # Fallback if platform doesn't provide it
   150|        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={hostname}")
   151|
   152|
   153|    logger.info(f"Tunnel config: id={tunnel_id}, hostname={hostname}")
   154|    logger.debug(f"DEBUG: setup_tunnel - About to call start_cloudflared with: tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
   155|
   156|    try:
   157|        cf_bin = get_cloudflared_path()
   158|        result = subprocess.run([cf_bin, "--version"], capture_output=True, text=True)
   159|        logger.info(f"cloudflared: {result.stdout.strip()}")
   160|    except FileNotFoundError:
   161|        logger.error("cloudflared not found in container!")
   162|        return False
   163|
    logger.debug(f"DEBUG: setup_tunnel - About to call start_cloudflared with: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
   164|    cloudflared_process = start_cloudflared(tunnel_token, tunnel_id, hostname)
   165|    return cloudflared_process is not None
   166|
   167|
   168|async def run_once(ha: HAClient, platform: PlatformClient) -> dict:
   169|    """Collect data from HA and send to platform."""
   170|    logger.info("Collecting HA report...")
   171|    report = await ha.get_full_report()
   172|
   173|    report["tunnel_running"] = is_cloudflared_healthy()
   174|
   175|    logger.info(
   176|        "Report: online=%s entities=%s version=%s tunnel=%s",
   177|        report.get("online"),
   178|        report.get("entity_count", "?"),
   179|        report.get("ha_version", "?"),
   180|        report.get("tunnel_running"),
   181|    )
   182|    result = await platform.send_heartbeat(report)
   183|    logger.info("Platform response: %s", result)
   184|    return report
   185|
   186|
   187|async def main_loop():
   188|    """Main loop: collect and report at configured interval."""
   189|    logger.info("Burghscape Agent starting")
   190|    logger.info("Platform: %s", config.platform_url)
   191|    logger.info("Instance: %s", config.instance_name)
   192|    logger.info("Heartbeat: every %ss", config.heartbeat_interval)
   193|
   194|    def handle_signal(sig, frame):
   195|        logger.info("Received signal %s, shutting down...", sig)
   196|        stop_cloudflared()
   197|        sys.exit(0)
   198|
   199|    signal.signal(signal.SIGTERM, handle_signal)
   200|    signal.signal(signal.SIGINT, handle_signal)
   201|
   202|    tunnel_setup_done = False
   203|
   204|    while True:
   205|        try:
   206|            async with HAClient(config) as ha, PlatformClient(config) as platform:
   207|                if not tunnel_setup_done:
   208|                    tunnel_setup_done = await setup_tunnel(platform)
   209|
   210|                report = await run_once(ha, platform)
   211|                if not report.get("online"):\
   212|                    logger.warning("HA appears offline, will retry...")
   213|        except Exception as e:
   214|            logger.error("Error in main loop: %s", e, exc_info=True)
   215|
   216|        if not is_cloudflared_healthy():
   217|            if tunnel_setup_done:
   218|                logger.warning("cloudflared died, will restart on next cycle...")
   219|                tunnel_setup_done = False
   220|
   221|        logger.info("Sleeping %ss until next report...", config.heartbeat_interval)
   222|        await asyncio.sleep(config.heartbeat_interval)
   223|
   224|
   225|if __name__ == "__main__":
   226|    asyncio.run(main_loop())