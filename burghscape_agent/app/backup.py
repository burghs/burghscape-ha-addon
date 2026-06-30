"""Client backup module: generate HA backup and SFTP to Burghscape VM."""
import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone

import aiohttp

from app.config import Config

logger = logging.getLogger("burghscape.agent.backup")


async def generate_ha_backup(config: Config) -> bytes | None:
    """Generate a full HA backup via WebSocket API and return the .tar bytes.

    Uses the HA WebSocket API with the user-provided ha_token (long-lived token).
    Falls back to supervisor API if ha_token is not set.
    """
    ha_url = config.ha_url.rstrip("/")
    token = config.ha_token

    if not token:
        logger.error("No ha_token configured — cannot generate backup")
        return None

    ws_url = ha_url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                # Auth
                auth_msg = await ws.receive_json()
                if auth_msg.get("type") != "auth_required":
                    logger.error("Unexpected WS message: %s", auth_msg)
                    return None

                await ws.send_json({"type": "auth", "access_token": token})

                auth_ok = await ws.receive_json()
                if auth_ok.get("type") != "auth_ok":
                    logger.error("WebSocket auth failed: %s", auth_ok)
                    return None

                # Request full backup
                msg_id = 1
                await ws.send_json({
                    "id": msg_id,
                    "type": "backup/generate",
                })

                # Wait for response (backup can take a while)
                result = None
                while True:
                    msg = await ws.receive_json()
                    if msg.get("id") == msg_id:
                        result = msg
                        break

                if not result or not result.get("success"):
                    logger.error("Backup generation failed: %s", result)
                    return None

                logger.info("Backup generated successfully via WebSocket")

                # Now download the backup file
                # Get backup info to find filename
                msg_id = 2
                await ws.send_json({
                    "id": msg_id,
                    "type": "backup/info",
                })

                info_result = None
                while True:
                    msg = await ws.receive_json()
                    if msg.get("id") == msg_id:
                        info_result = msg
                        break

                if not info_result or not info_result.get("success"):
                    logger.error("Failed to get backup info: %s", info_result)
                    return None

                backups = info_result.get("data", {}).get("backups", [])
                if not backups:
                    logger.error("No backups found after generation")
                    return None

                # Get the most recent backup (the one we just created)
                latest = backups[0]
                slug = latest.get('slug', '')
                if not slug:
                    logger.error("No slug in latest backup: %s", latest)
                    return None

                # Download via REST API
                download_url = f"{ha_url}/api/backup/download/{slug}"
                async with session.get(
                    download_url,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        logger.info("Downloaded backup: %d bytes", len(data))
                        return data
                    else:
                        body = await resp.text()
                        logger.error("Backup download failed: HTTP %d %s", resp.status, body[:200])
                        return None

    except asyncio.TimeoutError:
        logger.error("Timeout during backup generation/download")
        return None
    except Exception as e:
        logger.error("Backup generation error: %s", e, exc_info=True)
        return None


async def generate_ha_backup_via_supervisor(config: Config) -> bytes | None:
    """Fallback: generate backup via supervisor REST API (no ha_token needed)."""
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not supervisor_token:
        token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
        if os.path.isfile(token_path):
            with open(token_path) as f:
                supervisor_token = f.read().strip()

    if not supervisor_token:
        logger.error("No supervisor token available for backup")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            # Generate backup
            for base in ["http://supervisor", "http://172.30.32.2"]:
                try:
                    async with session.post(
                        f"{base}/backup/full",
                        headers={"Authorization": f"Bearer {supervisor_token}"},
                        timeout=aiohttp.ClientTimeout(total=300),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            logger.info("Supervisor backup generated: %d bytes", len(data))
                            return data
                except Exception:
                    continue

            logger.error("Supervisor backup failed on all endpoints")
            return None
    except Exception as e:
        logger.error("Supervisor backup error: %s", e, exc_info=True)
        return None


def upload_sftp(
    data: bytes,
    remote_host: str,
    remote_user: str,
    remote_path: str,
    ssh_key_path: str,
    filename: str,
) -> bool:
    """Upload backup bytes to remote server via SFTP (synchronous — run in thread)."""
    try:
        import paramiko
    except ImportError:
        logger.error("paramiko not installed — cannot SFTP upload")
        return False

    try:
        key = paramiko.Ed25519Key.from_private_key_file(ssh_key_path)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=remote_host,
            username=remote_user,
            pkey=key,
            timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )

        sftp = ssh.open_sftp()

        # Ensure remote directory exists
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            # Create directory recursively
            try:
                sftp.mkdir(remote_path)
            except IOError:
                # Parent might not exist — try with ssh exec
                ssh.exec_command(f"mkdir -p {remote_path}")

        remote_file = f"{remote_path}/{filename}"
        with sftp.file(remote_file, "wb") as f:
            f.write(data)

        sftp.close()
        ssh.close()

        logger.info("SFTP upload complete: %s (%d bytes)", remote_file, len(data))
        return True

    except Exception as e:
        logger.error("SFTP upload failed: %s", e, exc_info=True)
        return False


async def run_backup(config: Config) -> dict:
    """Generate and upload a backup. Returns status dict."""
    result = {
        "success": False,
        "timestamp": None,
        "size_bytes": 0,
        "error": None,
    }
    instance_slug = config.instance_name.lower().replace(" ", "-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{instance_slug}_{timestamp}.tar"

    # Generate backup
    data = await generate_ha_backup(config)
    if not data:
        logger.info("Trying supervisor fallback for backup...")
        data = await generate_ha_backup_via_supervisor(config)

    if not data:
        logger.error("All backup methods failed")
        result["error"] = "All backup generation methods failed"
        return result

    # Get SFTP config
    remote_host = config.backup_sftp_host
    remote_user = config.backup_sftp_user
    remote_base = config.backup_sftp_path
    ssh_key_path = config.backup_ssh_key_path

    if not remote_host:
        logger.warning("BACKUP_SFTP_HOST not set — skipping upload")
        # Still save locally as fallback
        local_path = f"/config/burghscape/backups/{filename}"
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        logger.info("Backup saved locally: %s", local_path)
        result["success"] = True
        result["timestamp"] = timestamp
        result["size_bytes"] = len(data)
        return result

    remote_path = f"{remote_base}/{instance_slug}"

    # Run SFTP upload in thread (paramiko is blocking)
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(
        None,
        upload_sftp,
        data,
        remote_host,
        remote_user,
        remote_path,
        ssh_key_path,
        filename,
    )

    if success:
        # Enforce retention: keep only last N backups
        await loop.run_in_executor(
            None,
            cleanup_old_backups,
            remote_path,
            instance_slug,
            config.backup_keep_count,
            ssh_key_path,
            remote_host,
            remote_user,
        )

    result["success"] = success
    result["timestamp"] = timestamp
    result["size_bytes"] = len(data)
    if not success:
        result["error"] = "SFTP upload failed"
    return result


def cleanup_old_backups(
    remote_path: str,
    instance_slug: str,
    keep_count: int,
    ssh_key_path: str,
    remote_host: str,
    remote_user: str,
):
    """Delete old backups on remote server, keeping only the last N."""
    try:
        import paramiko
    except ImportError:
        return

    try:
        key = paramiko.Ed25519Key.from_private_key_file(ssh_key_path)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=remote_host,
            username=remote_user,
            pkey=key,
            timeout=30,
            look_for_keys=False,
            allow_agent=False,
        )

        sftp = ssh.open_sftp()
        files = sftp.listdir(remote_path)

        # Filter to this instance's backup files
        backup_files = sorted(
            [f for f in files if f.startswith(instance_slug) and f.endswith(".tar")]
        )

        # Delete oldest if we have more than keep_count
        if len(backup_files) > keep_count:
            to_delete = backup_files[:len(backup_files) - keep_count]
            for old_file in to_delete:
                old_path = f"{remote_path}/{old_file}"
                try:
                    sftp.remove(old_path)
                    logger.info("Deleted old backup: %s", old_path)
                except Exception:
                    pass

        sftp.close()
        ssh.close()
        logger.info("Retention cleanup done: kept %d, deleted %d", keep_count, len(backup_files) - keep_count if len(backup_files) > keep_count else 0)
    except Exception as e:
        logger.error("Retention cleanup error: %s", e)
