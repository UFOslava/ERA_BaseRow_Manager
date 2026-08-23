import os
import io
import json
import time
import zipfile
import logging
import threading
import datetime
import requests
from pathlib import Path
from app.baserow_init import ERA_SCHEMA_DEFINITIONS, discover_baserow_schema, combine_url_and_port

logger = logging.getLogger(__name__)

# Directory where backups are stored in the backend
BACKUPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")
BACKUP_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backup_config.json")

# Default scheduler config: end of workday (8:00 PM – 12:00 AM local time)
DEFAULT_CONFIG = {
    "auto_backup_enabled": True,
    "daily_backup_start_hour_local": 20, # 8:00 PM local time
    "daily_backup_end_hour_local": 24,   # 12:00 AM local time
    "retention_daily_days": 14,
    "retention_thursday_weeks": 52
}


def get_backups_dir() -> str:
    """Ensures and returns the backups storage directory."""
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    return BACKUPS_DIR


def load_backup_config() -> dict:
    """Loads backup configuration or returns default."""
    if os.path.exists(BACKUP_CONFIG_FILE):
        try:
            with open(BACKUP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            logger.warning(f"Failed to load {BACKUP_CONFIG_FILE}: {e}")
    return DEFAULT_CONFIG.copy()


def save_backup_config(config: dict) -> dict:
    """Saves backup configuration."""
    merged = {**DEFAULT_CONFIG, **config}
    try:
        with open(BACKUP_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write {BACKUP_CONFIG_FILE}: {e}")
    return merged


def fetch_all_table_rows(api_url: str, auth_headers: dict, table_id: str) -> list:
    """Fetches all rows from a Baserow table using pagination."""
    rows = []
    page_url = f"{api_url.rstrip('/')}/api/database/rows/table/{table_id}/?user_field_names=true&size=200"
    
    while page_url:
        resp = requests.get(page_url, headers=auth_headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        rows.extend(data.get("results", []))
        page_url = data.get("next")
    
    return rows


def download_attachment(file_url: str, timeout: int = 15) -> bytes:
    """Downloads an attachment file from URL."""
    resp = requests.get(file_url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def create_backup(
    api_url: str = None,
    token: str = None,
    admin_email: str = None,
    admin_password: str = None,
    backup_type: str = "manual",
    custom_note: str = ""
) -> dict:
    """
    Creates a full ZIP archive backup of the Baserow database.
    Archives all 9 tables, downloads all image/file attachments,
    computes metrics, and saves to backend/backups/.
    """
    api_url = (api_url or os.getenv("BASEROW_API_URL", "http://localhost:7070")).rstrip("/")
    token = token or os.getenv("BASEROW_TOKEN", "")
    backups_path = get_backups_dir()

    now_local = datetime.datetime.now().astimezone()
    timestamp_str = now_local.strftime("%Y-%m-%d_%H-%M-%S")
    day_name = now_local.strftime("%A")
    is_thursday = (now_local.weekday() == 3) # 3 is Thursday (Monday=0)

    backup_id = f"backup_{timestamp_str}_{backup_type}"
    zip_filename = f"{backup_id}.zip"
    zip_path = os.path.join(backups_path, zip_filename)

    # Auth headers
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    
    # Discover schema
    schema = discover_baserow_schema(
        api_url=api_url,
        token=token,
        admin_email=admin_email,
        admin_password=admin_password
    )

    tables_data = {}
    table_row_counts = {}
    downloaded_attachments = {}
    attachment_counter = 0

    bom_items_count = 0
    instruction_steps_count = 0

    for table_name, table_info in schema.get("tables", {}).items():
        table_id = table_info.get("id")
        if not table_id:
            continue
        try:
            rows = fetch_all_table_rows(api_url, headers, str(table_id))
            tables_data[table_name] = {
                "table_id": table_id,
                "env_var": table_info.get("env_var"),
                "rows_count": len(rows),
                "rows": rows
            }
            table_row_counts[table_name] = len(rows)

            if table_name == "BOM":
                bom_items_count = len(rows)
            elif table_name == "Assembly Instructions":
                instruction_steps_count = len(rows)

            # Find and download attachments in this table
            for row in rows:
                for col_name, val in row.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict) and item.get("url") and item.get("name"):
                                file_url = item["url"]
                                file_name = item["name"]
                                safe_key = f"{table_name}_{row.get('id', 'r')}_{file_name}"
                                if safe_key not in downloaded_attachments:
                                    try:
                                        file_bytes = download_attachment(file_url)
                                        downloaded_attachments[safe_key] = {
                                            "bytes": file_bytes,
                                            "original_name": file_name,
                                            "original_url": file_url,
                                            "size": len(file_bytes)
                                        }
                                        attachment_counter += 1
                                    except Exception as e:
                                        logger.warning(f"Could not download attachment {file_url}: {e}")
        except Exception as e:
            logger.error(f"Error archiving table '{table_name}' (ID {table_id}): {e}")
            tables_data[table_name] = {
                "table_id": table_id,
                "env_var": table_info.get("env_var"),
                "error": str(e),
                "rows_count": 0,
                "rows": []
            }
            table_row_counts[table_name] = 0

    total_rows = sum(table_row_counts.values())
    retention_tag = "52_weeks_thursday" if is_thursday else "14_days"

    manifest = {
        "backup_id": backup_id,
        "filename": zip_filename,
        "timestamp": now_local.isoformat(),
        "created_at_display": now_local.strftime("%Y-%m-%d %H:%M:%S"),
        "day_of_week": day_name,
        "is_thursday": is_thursday,
        "backup_type": backup_type,
        "retention_policy": retention_tag,
        "note": custom_note,
        "metrics": {
            "bom_items_count": bom_items_count,
            "instruction_steps_count": instruction_steps_count,
            "images_count": attachment_counter,
            "total_tables_count": len(tables_data),
            "total_rows_count": total_rows,
            "table_row_counts": table_row_counts,
            "archive_size_bytes": 0
        },
        "schema_snapshot": schema.get("tables", {})
    }

    # Build ZIP archive
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Write tables JSON
        for tname, tcontent in tables_data.items():
            zip_file.writestr(f"tables/{tname}.json", json.dumps(tcontent, indent=2, ensure_ascii=False))
        
        # 2. Write attachments
        for safe_key, att_data in downloaded_attachments.items():
            zip_file.writestr(f"attachments/{safe_key}", att_data["bytes"])
        
        # 3. Write manifest.json
        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
        zip_file.writestr("manifest.json", manifest_bytes)

    archive_size = os.path.getsize(zip_path)
    manifest["metrics"]["archive_size_bytes"] = archive_size

    logger.info(f"Backup created successfully: {zip_filename} ({archive_size} bytes, {total_rows} rows, {attachment_counter} images)")
    return manifest


def read_backup_manifest(zip_path: str) -> dict:
    """Reads manifest.json from a backup ZIP archive."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            if "manifest.json" in zip_file.namelist():
                content = zip_file.read("manifest.json").decode("utf-8")
                data = json.loads(content)
                if not isinstance(data, dict):
                    data = {}
                if "metrics" not in data or not isinstance(data["metrics"], dict):
                    data["metrics"] = {}
                data["metrics"]["archive_size_bytes"] = os.path.getsize(zip_path)
                return data
    except Exception as e:
        logger.warning(f"Error reading manifest from {zip_path}: {e}")
    
    # Fallback manifest from filename
    fname = os.path.basename(zip_path)
    return {
        "backup_id": fname.replace(".zip", ""),
        "filename": fname,
        "timestamp": datetime.datetime.fromtimestamp(os.path.getmtime(zip_path), datetime.timezone.utc).isoformat(),
        "created_at_display": datetime.datetime.fromtimestamp(os.path.getmtime(zip_path), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "day_of_week": "Unknown",
        "is_thursday": False,
        "backup_type": "manual",
        "retention_policy": "14_days",
        "metrics": {
            "bom_items_count": 0,
            "instruction_steps_count": 0,
            "images_count": 0,
            "total_tables_count": 0,
            "total_rows_count": 0,
            "archive_size_bytes": os.path.getsize(zip_path)
        }
    }


def list_backups() -> list:
    """Returns a list of all backup archives sorted by timestamp newest first."""
    backups_path = get_backups_dir()
    results = []
    
    for fname in os.listdir(backups_path):
        if fname.endswith(".zip"):
            full_path = os.path.join(backups_path, fname)
            manifest = read_backup_manifest(full_path)
            results.append(manifest)
    
    # Sort descending by timestamp
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results


def delete_backup(backup_id: str) -> bool:
    """Deletes a specific backup zip file."""
    backups_path = get_backups_dir()
    zip_path = os.path.join(backups_path, f"{backup_id}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
        logger.info(f"Deleted backup archive: {backup_id}.zip")
        return True
    return False


def apply_retention_policy(backups_path: str = None) -> list:
    """
    Applies retention pruning:
    - Retains Thursday backups for 52 weeks (364 days).
    - Retains all other consecutive daily backups for 14 days.
    Returns list of pruned filenames.
    """
    backups_path = backups_path or get_backups_dir()
    config = load_backup_config()
    daily_retention_days = config.get("retention_daily_days", 14)
    thursday_retention_weeks = config.get("retention_thursday_weeks", 52)
    thursday_retention_days = thursday_retention_weeks * 7

    now = datetime.datetime.now(datetime.timezone.utc)
    pruned = []

    for fname in os.listdir(backups_path):
        if not fname.endswith(".zip"):
            continue
        full_path = os.path.join(backups_path, fname)
        manifest = read_backup_manifest(full_path)
        
        ts_str = manifest.get("timestamp")
        if not ts_str:
            continue
        
        try:
            created_at = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            age_days = (now - created_at).total_seconds() / 86400.0

            is_thursday = manifest.get("is_thursday", False)
            if not is_thursday and created_at.weekday() == 3:
                is_thursday = True

            max_allowed_age = thursday_retention_days if is_thursday else daily_retention_days

            if age_days > max_allowed_age:
                os.remove(full_path)
                pruned.append({
                    "filename": fname,
                    "age_days": round(age_days, 1),
                    "is_thursday": is_thursday,
                    "reason": f"Exceeded {max_allowed_age} days retention"
                })
                logger.info(f"Pruned old backup {fname} (age: {round(age_days, 1)} days, thursday={is_thursday})")
        except Exception as e:
            logger.warning(f"Could not parse timestamp for pruning {fname}: {e}")

    return pruned


def restore_backup(backup_id: str, api_url: str = None, token: str = None) -> dict:
    """
    Safe in-place restore:
    1. Creates a safety backup of existing live data first.
    2. Clears existing rows from Baserow tables.
    3. Recreates rows and cross-table link relations from the archive.
    """
    api_url = (api_url or os.getenv("BASEROW_API_URL", "http://localhost:7070")).rstrip("/")
    token = token or os.getenv("BASEROW_TOKEN", "")
    backups_path = get_backups_dir()
    zip_path = os.path.join(backups_path, f"{backup_id}.zip")

    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Backup archive {backup_id}.zip not found.")

    # 1. Create safety backup first
    logger.info(f"Creating safety pre-restore backup before restoring {backup_id}...")
    safety_manifest = create_backup(
        api_url=api_url,
        token=token,
        backup_type="safety_pre_restore",
        custom_note=f"Automatic safety backup before restoring {backup_id}"
    )

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    # 2. Open ZIP and read contents
    with zipfile.ZipFile(zip_path, "r") as zip_file:
        manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
        
        tables_to_restore = {}
        for item in zip_file.namelist():
            if item.startswith("tables/") and item.endswith(".json"):
                tname = item.replace("tables/", "").replace(".json", "")
                tdata = json.loads(zip_file.read(item).decode("utf-8"))
                tables_to_restore[tname] = tdata

    # Map table names to current live table IDs from environment or discovery
    schema = discover_baserow_schema(api_url=api_url, token=token)
    live_tables = schema.get("tables", {})

    restored_counts = {}

    # 3. For each table, clear existing rows then insert backup rows
    # Link row fields to populate in second pass
    link_fields_second_pass = []

    # Table restoration order (independent lookup tables first, then BOM, then dependent relation tables)
    table_order = [
        "PN Categories",
        "States",
        "Manufacturers",
        "Contacts",
        "Suppliers",
        "WI Templates",
        "BOM",
        "Assembly",
        "Assembly Instructions"
    ]

    sorted_tables = [t for t in table_order if t in tables_to_restore]
    # Add any remaining tables
    for t in tables_to_restore:
        if t not in sorted_tables:
            sorted_tables.append(t)

    # Pass 1: Clear & Create basic row content
    row_id_map = {} # { (table_name, old_id): new_id }

    for tname in sorted_tables:
        tdata = tables_to_restore[tname]
        live_table_info = live_tables.get(tname)
        if not live_table_info or not live_table_info.get("id"):
            logger.warning(f"Skipping restore for '{tname}': live table ID unresolved.")
            continue

        live_table_id = live_table_info["id"]
        rows = tdata.get("rows", [])
        restored_counts[tname] = 0

        # Fetch and delete existing live rows
        try:
            existing_rows = fetch_all_table_rows(api_url, headers, str(live_table_id))
            for erow in existing_rows:
                erow_id = erow.get("id")
                if erow_id:
                    requests.delete(f"{api_url}/api/database/rows/table/{live_table_id}/{erow_id}/", headers=headers, timeout=10)
        except Exception as e:
            logger.warning(f"Error clearing rows in live table '{tname}': {e}")

        # Insert rows from backup
        for row in rows:
            old_id = row.get("id")
            cleaned_row = {}
            second_pass_row = {}

            for col, val in row.items():
                if col in ("id", "order", "Full PN", "Search helper", "Search Helper"):
                    continue # Read-only / auto-calculated
                
                # Check if value is a linked relation list
                if isinstance(val, list) and val and isinstance(val[0], dict) and "id" in val[0] and "value" in val[0]:
                    second_pass_row[col] = val
                else:
                    cleaned_row[col] = val

            try:
                create_resp = requests.post(
                    f"{api_url}/api/database/rows/table/{live_table_id}/?user_field_names=true",
                    headers=headers,
                    json=cleaned_row,
                    timeout=15
                )
                if create_resp.status_code in (200, 201):
                    new_row = create_resp.json()
                    new_id = new_row.get("id")
                    if old_id and new_id:
                        row_id_map[(tname, old_id)] = new_id
                    if second_pass_row and new_id:
                        link_fields_second_pass.append({
                            "table_name": tname,
                            "live_table_id": live_table_id,
                            "new_row_id": new_id,
                            "link_fields": second_pass_row
                        })
                    restored_counts[tname] += 1
                else:
                    logger.warning(f"Failed creating row in '{tname}': {create_resp.text}")
            except Exception as e:
                logger.error(f"Error inserting row into '{tname}': {e}")

    # Pass 2: Resolve linked rows relations with new mapped IDs
    for item in link_fields_second_pass:
        live_table_id = item["live_table_id"]
        new_row_id = item["new_row_id"]
        link_updates = {}

        for col, linked_objs in item["link_fields"].items():
            new_linked_ids = []
            for l_obj in linked_objs:
                old_l_id = l_obj.get("id")
                # Look up in row_id_map
                mapped_id = next((new_id for (tn, oid), new_id in row_id_map.items() if oid == old_l_id), old_l_id)
                if mapped_id:
                    new_linked_ids.append(mapped_id)
            if new_linked_ids:
                link_updates[col] = new_linked_ids

        if link_updates:
            try:
                requests.patch(
                    f"{api_url}/api/database/rows/table/{live_table_id}/{new_row_id}/?user_field_names=true",
                    headers=headers,
                    json=link_updates,
                    timeout=15
                )
            except Exception as e:
                logger.warning(f"Error updating linked relation for row {new_row_id} in table {live_table_id}: {e}")

    logger.info(f"Restore of backup {backup_id} completed successfully. Counts: {restored_counts}")
    return {
        "success": True,
        "restored_backup_id": backup_id,
        "safety_backup": safety_manifest,
        "restored_counts": restored_counts
    }


# Background automated backup scheduler
class BackupSchedulerDaemon:
    def __init__(self, check_interval_seconds: int = 3600):
        self.check_interval = check_interval_seconds
        self._thread = None
        self._stop_event = threading.Event()
        self._last_backup_date = None

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="BackupScheduler")
            self._thread.start()
            logger.info("BackupSchedulerDaemon background thread started.")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
            logger.info("BackupSchedulerDaemon background thread stopped.")

    def _run_loop(self):
        # Initial wait of 10s after startup
        time.sleep(10)
        while not self._stop_event.is_set():
            try:
                config = load_backup_config()
                if config.get("auto_backup_enabled", True):
                    now_local = datetime.datetime.now().astimezone()
                    today_str = now_local.strftime("%Y-%m-%d")
                    start_hour = config.get("daily_backup_start_hour_local", 20) # 8:00 PM local
                    end_hour = config.get("daily_backup_end_hour_local", 24)     # 12:00 AM local

                    # Check existing backups to see if one was already done today
                    existing_today = any(b.get("timestamp", "").startswith(today_str) for b in list_backups())

                    in_window = (start_hour <= now_local.hour < end_hour) if end_hour < 24 else (now_local.hour >= start_hour)
                    if not existing_today and in_window:
                        logger.info(f"Triggering automated end-of-workday backup for {today_str} (local time: {now_local.strftime('%H:%M:%S')})...")
                        create_backup(backup_type="daily", custom_note="Automated scheduled daily backup (end of workday)")
                        self._last_backup_date = today_str
                        # Apply retention pruning
                        apply_retention_policy()
            except Exception as e:
                logger.error(f"Error in BackupScheduler loop: {e}")

            # Sleep in intervals (check every 5 minutes / 300s) to allow quick exit
            sleep_duration = min(self.check_interval, 300)
            for _ in range(sleep_duration // 5):
                if self._stop_event.is_set():
                    break
                time.sleep(5)


# Global scheduler instance
backup_scheduler = BackupSchedulerDaemon()
