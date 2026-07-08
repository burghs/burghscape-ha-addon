     1|     1|#!/usr/bin/env python3
     2|     2|"""Main agent loop for Burghscape Agent add-on."""
     3|     3|import asyncio
     4|     4|import logging
     5|     5|import os
     6|     6|import subprocess
     7|     7|import json
     8|     8|import signal
     9|     9|import sys
    10|    10|import time
    11|    11|
    12|    12|from app.config import Config
    13|    13|from app.ha_client import HAClient
    14|    14|from app.platform_client import PlatformClient
    15|    15|
    16|    16|logging.basicConfig(
    17|    17|    level=logging.INFO,
    18|    18|    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    19|    19|)
    20|    20|logger = logging.getLogger("burghscape.agent")
    21|    21|
    22|    22|config = Config()
    23|    23|cloudflared_process = None
    24|    24|
    25|    25|
    26|    26|def get_cloudflared_path() -> str:
    27|    27|    """Find cloudflared binary."""
    28|    28|    for path in ["/usr/local/bin/cloudflared", "/usr/bin/cloudflared", "cloudflared"]:
    29|    29|        if os.path.isfile(path) or subprocess.run(["which", path], capture_output=True).returncode == 0:
    30|    30|            return path
    31|    31|    return "cloudflared"
    32|    32|
    33|    33|
    34|    34|def write_cloudflared_config(tunnel_id: str, hostname: str) -> str:
    logger.debug(f"DEBUG: write_cloudflared_config - tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    35|    logger.debug(f"DEBUG: write_cloudflared_config - tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    36|    35|    """Write cloudflared config file and return path."""
    37|    36|    config_dir = "/config/cloudflared"
    38|    37|    os.makedirs(config_dir, exist_ok=True)
    39|    38|
    40|    39|    import yaml
    41|    40|    cfg = {
    42|    41|        "tunnel": tunnel_id,
    43|    42|        "ingress": [
    44|    43|            {
    45|    44|                "hostname": hostname,
    46|    45|                "service": "http://localhost:8123",
    47|    46|                "originRequest": {
    48|    47|                    "noTLSVerify": True
    49|    48|                }
    50|    49|            },
    51|    50|            {"service": "http_status:404"}
    52|    51|        ]
    53|    52|    }
    54|    53|
    55|    54|    config_path = os.path.join(config_dir, "config.yml")
    56|    55|    with open(config_path, "w") as f:
    57|    56|        yaml.dump(cfg, f)
    58|    57|
    59|    58|    logger.info(f"Cloudflare config written to {config_path}")
    60|    59|    return config_path
    61|    60|
    62|    61|
    63|    62|def start_cloudflared(tunnel_token: str, tunnel_id: str, hostname: str) -> subprocess.Popen:
    logger.debug(f"DEBUG: start_cloudflared - tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    64|    logger.debug(f"DEBUG: start_cloudflared - tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    65|    63|    """Start cloudflared tunnel process."""
    66|    64|    global cloudflared_process
    67|    65|
    68|    66|    if cloudflared_process and cloudflared_process.poll() is None:
    69|    67|        logger.info("cloudflared already running")
    70|    68|        return cloudflared_process
    71|    69|
    72|    70|    config_path = write_cloudflared_config(tunnel_id, hostname)
    73|    71|
    74|    72|    # cloudflared tunnel --config <file> run --token <TOKEN> <TUNNEL_ID>
    75|    73|    cf_bin = get_cloudflared_path()
    76|    74|    cmd = [
    77|    75|        cf_bin, "tunnel",
    78|    76|        "--config", config_path,
    79|    77|        "run",
    80|    78|        "--token", tunnel_token,
    81|    79|        tunnel_id,
    82|    80|    ]
    83|    81|
    84|    82|    logger.info(f"Starting cloudflared: tunnel --config ... run --token ... {tunnel_id} (to {hostname})")
    85|    83|
    86|    84|    try:
    87|    85|        log_file = open("/config/cloudflared/cloudflared.log", "a")
    88|    86|        process = subprocess.Popen(
    89|    87|            cmd,
    90|    88|            stdout=log_file,
    91|    89|            stderr=subprocess.STDOUT,
    92|    90|        )
    93|    91|        logger.info(f"cloudflared started (PID {process.pid})")
    94|    92|
    95|    93|        time.sleep(5)
    96|    94|        if process.poll() is not None:
    97|    95|            with open("/config/cloudflared/cloudflared.log", "r") as f:
    98|    96|                last_lines = f.readlines()[-15:]
    99|    97|            logger.error("cloudflared exited immediately! Last log lines:")
   100|    98|            for line in last_lines:
   101|    99|                logger.error(f"  {line.strip()}")
   102|   100|            return None
   103|   101|
   104|   102|        return process
   105|   103|    except FileNotFoundError:
   106|   104|        logger.error("cloudflared not installed!")
   107|   105|        return None
   108|   106|
   109|   107|
   110|   108|def stop_cloudflared():
   111|   109|    """Stop cloudflared tunnel process."""
   112|   110|    global cloudflared_process
   113|   111|    if cloudflared_process and cloudflared_process.poll() is None:
   114|   112|        logger.info("Stopping cloudflared...")
   115|   113|        cloudflared_process.terminate()
   116|   114|        try:
   117|   115|            cloudflared_process.wait(timeout=10)
   118|   116|        except subprocess.TimeoutExpired:
   119|   117|            cloudflared_process.kill()
   120|   118|        cloudflared_process = None
   121|   119|
   122|   120|
   123|   121|def is_cloudflared_healthy() -> bool:
   124|   122|    """Check if cloudflared is running and connected."""
   125|   123|    global cloudflared_process
   126|   124|    if cloudflared_process is None:
   127|   125|        return False
   128|   126|    if cloudflared_process.poll() is not None:
   129|   127|        return False
   130|   128|    return True
   131|   129|
   132|   130|
   133|   131|async def setup_tunnel(platform: PlatformClient) -> bool:
   134|   132|    """Fetch tunnel config from platform and start cloudflared."""
   135|   133|    global cloudflared_process
   136|   134|
   137|   135|    logger.info("Fetching tunnel config from platform...")
    logger.debug(f"DEBUG: setup_tunnel - Before platform.get_tunnel_config: {{platform}}")
   138|    logger.debug(f"DEBUG: setup_tunnel - Before platform.get_tunnel_config: {{platform}}")
   139|   136|    tunnel_cfg = await platform.get_tunnel_config()
    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg received: {{tunnel_cfg}}")
   140|    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg received: {{tunnel_cfg}}")
   141|   137|    logger.debug(f"DEBUG: setup_tunnel - tunnel_cfg: {tunnel_cfg}")
   142|   138|
   143|   139|    if not tunnel_cfg or not tunnel_cfg.get("tunnel_token"):
   144|   140|        logger.warning("No tunnel config available from platform")
   145|   141|        return False
   146|   142|
   147|   143|    tunnel_token = tunnel_cfg["tunnel_token"]
   148|   144|    tunnel_id = tunnel_cfg.get("tunnel_id", "")
   149|   145|    hostname = tunnel_cfg.get("hostname", "")
    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
   150|    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
   151|   146|    logger.debug(f"DEBUG: setup_tunnel - Before hostname fallback: tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
   152|   147|
   153|   148|    if not hostname:
        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={{hostname}}")
   154|        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={{hostname}}")
   155|   149|        hostname = config.instance_name + ".mybeacon.co.za" # Fallback if platform doesn't provide it
   156|   150|        logger.debug(f"DEBUG: setup_tunnel - After hostname fallback: hostname={hostname}")
   157|   151|
   158|   152|
   159|   153|    logger.info(f"Tunnel config: id={tunnel_id}, hostname={hostname}")
   160|   154|    logger.debug(f"DEBUG: setup_tunnel - About to call start_cloudflared with: tunnel_token={tunnel_token}, tunnel_id={tunnel_id}, hostname={hostname}")
   161|   155|
   162|   156|    try:
   163|   157|        cf_bin = get_cloudflared_path()
   164|   158|        result = subprocess.run([cf_bin, "--version"], capture_output=True, text=True)
   165|   159|        logger.info(f"cloudflared: {result.stdout.strip()}")
   166|   160|    except FileNotFoundError:
   167|   161|        logger.error("cloudflared not found in container!")
   168|   162|        return False
   169|   163|
   170|    logger.debug(f"DEBUG: setup_tunnel - About to call start_cloudflared with: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
    logger.debug(f"DEBUG: setup_tunnel - About to call start_cloudflared with: tunnel_token={{tunnel_token}}, tunnel_id={{tunnel_id}}, hostname={{hostname}}")
   171|   164|    cloudflared_process = start_cloudflared(tunnel_token, tunnel_id, hostname)
   172|   165|    return cloudflared_process is not None
   173|   166|
   174|   167|
   175|   168|async def run_once(ha: HAClient, platform: PlatformClient) -> dict:
   176|   169|    """Collect data from HA and send to platform."""
   177|   170|    logger.info("Collecting HA report...")
   178|   171|    report = await ha.get_full_report()
   179|   172|
   180|   173|    report["tunnel_running"] = is_cloudflared_healthy()
   181|   174|
   182|   175|    logger.info(
   183|   176|        "Report: online=%s entities=%s version=%s tunnel=%s",
   184|   177|        report.get("online"),
   185|   178|        report.get("entity_count", "?"),
   186|   179|        report.get("ha_version", "?"),
   187|   180|        report.get("tunnel_running"),
   188|   181|    )
   189|   182|    result = await platform.send_heartbeat(report)
   190|   183|    logger.info("Platform response: %s", result)
   191|   184|    return report
   192|   185|
   193|   186|
   194|   187|async def main_loop():
   195|   188|    """Main loop: collect and report at configured interval."""
   196|   189|    logger.info("Burghscape Agent starting")
   197|   190|    logger.info("Platform: %s", config.platform_url)
   198|   191|    logger.info("Instance: %s", config.instance_name)
   199|   192|    logger.info("Heartbeat: every %ss", config.heartbeat_interval)
   200|   193|
   201|   194|    def handle_signal(sig, frame):
   202|   195|        logger.info("Received signal %s, shutting down...", sig)
   203|   196|        stop_cloudflared()
   204|   197|        sys.exit(0)
   205|   198|
   206|   199|    signal.signal(signal.SIGTERM, handle_signal)
   207|   200|    signal.signal(signal.SIGINT, handle_signal)
   208|   201|
   209|   202|    tunnel_setup_done = False
   210|   203|
   211|   204|    while True:
   212|   205|        try:
   213|   206|            async with HAClient(config) as ha, PlatformClient(config) as platform:
   214|   207|                if not tunnel_setup_done:
   215|   208|                    tunnel_setup_done = await setup_tunnel(platform)
   216|   209|
   217|   210|                report = await run_once(ha, platform)
   218|   211|                if not report.get("online"):\
   219|   212|                    logger.warning("HA appears offline, will retry...")
   220|   213|        except Exception as e:
   221|   214|            logger.error("Error in main loop: %s", e, exc_info=True)
   222|   215|
   223|   216|        if not is_cloudflared_healthy():
   224|   217|            if tunnel_setup_done:
   225|   218|                logger.warning("cloudflared died, will restart on next cycle...")
   226|   219|                tunnel_setup_done = False
   227|   220|
   228|   221|        logger.info("Sleeping %ss until next report...", config.heartbeat_interval)
   229|   222|        await asyncio.sleep(config.heartbeat_interval)
   230|   223|
   231|   224|
   232|   225|if __name__ == "__main__":
   233|   226|    asyncio.run(main_loop())