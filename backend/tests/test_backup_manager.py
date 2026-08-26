import os
import json
import zipfile
import tempfile
import datetime
from unittest.mock import patch, MagicMock
import pytest
from app.backup_manager import (
    create_backup,
    read_backup_manifest,
    list_backups,
    delete_backup,
    apply_retention_policy,
    restore_backup,
    load_backup_config,
    save_backup_config
)


@pytest.fixture
def mock_schema():
    return {
        "tables": {
            "BOM": {"id": "508", "env_var": "BASEROW_TABLE_BOM"},
            "Assembly": {"id": "701", "env_var": "BASEROW_TABLE_ASSEMBLY"},
            "Assembly Instructions": {"id": "5770", "env_var": "BASEROW_TABLE_INSTRUCTIONS"},
            "PN Categories": {"id": "42471", "env_var": "BASEROW_TABLE_PN_CATEGORIES"},
            "States": {"id": "48537", "env_var": "BASEROW_TABLE_ITEM_STATES"},
            "WI Templates": {"id": "48538", "env_var": "BASEROW_TABLE_WI_TEMPLATES"},
            "Manufacturers": {"id": "683", "env_var": "BASEROW_TABLE_MANUFACTURERS"},
            "Suppliers": {"id": "682", "env_var": "BASEROW_TABLE_SUPPLIERS"},
            "Contacts": {"id": "684", "env_var": "BASEROW_TABLE_CONTACTS"}
        }
    }


def test_create_backup_archive_and_metrics(mock_schema):
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment", return_value=b"fake_image_bytes"):
            
            # Mock table rows
            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508": # BOM
                    return [
                        {"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]},
                        {"id": 2, "Part Number": "20-002", "Image": []}
                    ]
                elif table_id == "5770": # Instructions
                    return [
                        {"id": 10, "Step Order": 1, "Photo": [{"url": "http://img/step1.jpg", "name": "step1.jpg"}]},
                        {"id": 11, "Step Order": 2, "Photo": []},
                        {"id": 12, "Step Order": 3, "Photo": []}
                    ]
                return [{"id": 99, "Name": "Sample"}]

            mock_fetch_rows.side_effect = mock_rows_impl

            manifest = create_backup(
                api_url="http://localhost:7070",
                token="test_tok",
                backup_type="manual",
                custom_note="Test note"
            )

            assert manifest["backup_type"] == "manual"
            assert manifest["metrics"]["bom_items_count"] == 2
            assert manifest["metrics"]["instruction_steps_count"] == 3
            assert manifest["metrics"]["images_count"] == 2
            assert manifest["metrics"]["total_tables_count"] == 9
            assert manifest["metrics"]["archive_size_bytes"] > 0

            # Verify zip file on disk
            zip_path = os.path.join(tmpdir, manifest["filename"])
            assert os.path.exists(zip_path)

            with zipfile.ZipFile(zip_path, "r") as zf:
                namelist = zf.namelist()
                assert "manifest.json" in namelist
                assert "tables/BOM.json" in namelist
                assert "tables/Assembly Instructions.json" in namelist
                assert any("attachments/" in n for n in namelist)


def test_list_and_delete_backups():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir):
            # Create two dummy zip archives
            zip1_path = os.path.join(tmpdir, "backup_2026-08-20_00-00-00_manual.zip")
            zip2_path = os.path.join(tmpdir, "backup_2026-08-22_00-00-00_daily.zip")

            m1 = {
                "backup_id": "backup_2026-08-20_00-00-00_manual",
                "filename": "backup_2026-08-20_00-00-00_manual.zip",
                "timestamp": "2026-08-20T00:00:00+00:00",
                "day_of_week": "Thursday",
                "is_thursday": True,
                "backup_type": "manual",
                "retention_policy": "52_weeks_thursday",
                "metrics": {"bom_items_count": 10}
            }
            m2 = {
                "backup_id": "backup_2026-08-22_00-00-00_daily",
                "filename": "backup_2026-08-22_00-00-00_daily.zip",
                "timestamp": "2026-08-22T00:00:00+00:00",
                "day_of_week": "Saturday",
                "is_thursday": False,
                "backup_type": "daily",
                "retention_policy": "14_days",
                "metrics": {"bom_items_count": 15}
            }

            with zipfile.ZipFile(zip1_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(m1))
            with zipfile.ZipFile(zip2_path, "w") as zf:
                zf.writestr("manifest.json", json.dumps(m2))

            backups = list_backups()
            assert len(backups) == 2
            assert backups[0]["backup_id"] == "backup_2026-08-22_00-00-00_daily"

            deleted = delete_backup("backup_2026-08-20_00-00-00_manual")
            assert deleted is True
            assert not os.path.exists(zip1_path)
            assert len(list_backups()) == 1


def test_retention_policy_thursday_vs_daily():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir):
            now = datetime.datetime.now(datetime.timezone.utc)

            # 1. Recent backup (5 days old) -> Keep
            d1 = now - datetime.timedelta(days=5)
            z1 = os.path.join(tmpdir, "backup_recent.zip")
            with zipfile.ZipFile(z1, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d1.isoformat(),
                    "is_thursday": False
                }))

            # 2. Old non-Thursday backup (>14 days old) -> Prune
            d2_days = 20
            while (now - datetime.timedelta(days=d2_days)).weekday() == 3:
                d2_days += 1
            d2 = now - datetime.timedelta(days=d2_days)
            z2 = os.path.join(tmpdir, "backup_old_regular.zip")
            with zipfile.ZipFile(z2, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d2.isoformat(),
                    "is_thursday": False
                }))

            # 3. Thursday backup (<52 weeks old) -> Keep
            d3_days = 30
            while (now - datetime.timedelta(days=d3_days)).weekday() != 3:
                d3_days += 1
            d3 = now - datetime.timedelta(days=d3_days)
            z3 = os.path.join(tmpdir, "backup_thursday_retained.zip")
            with zipfile.ZipFile(z3, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d3.isoformat(),
                    "is_thursday": True
                }))

            # 4. Very old Thursday backup (>364 days old) -> Prune
            d4_days = 400
            while (now - datetime.timedelta(days=d4_days)).weekday() != 3:
                d4_days += 1
            d4 = now - datetime.timedelta(days=d4_days)
            z4 = os.path.join(tmpdir, "backup_thursday_expired.zip")
            with zipfile.ZipFile(z4, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d4.isoformat(),
                    "is_thursday": True
                }))

            pruned = apply_retention_policy(tmpdir)
            pruned_names = [p["filename"] for p in pruned]

            assert "backup_old_regular.zip" in pruned_names
            assert "backup_thursday_expired.zip" in pruned_names
            assert "backup_recent.zip" not in pruned_names
            assert "backup_thursday_retained.zip" not in pruned_names

            assert os.path.exists(z1)
            assert not os.path.exists(z2)
            assert os.path.exists(z3)
            assert not os.path.exists(z4)


def test_restore_backup_creates_safety_and_restores_rows(mock_schema):
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup") as mock_create_backup, \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post") as mock_post, \
             patch("requests.delete") as mock_del, \
             patch("requests.patch") as mock_patch:
            
            mock_create_backup.return_value = {"backup_id": "backup_safety_123"}
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": 555}
            mock_patch.return_value.status_code = 200

            # Create a backup zip to restore
            zip_path = os.path.join(tmpdir, "backup_to_restore.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                manifest = {
                    "backup_id": "backup_to_restore",
                    "metrics": {"total_rows_count": 2}
                }
                zf.writestr("manifest.json", json.dumps(manifest))
                bom_table = {
                    "table_id": "508",
                    "rows": [
                        {"id": 101, "Part Number": "10-001", "Manufacturer": [{"id": 99, "value": "VendorA"}]}
                    ]
                }
                zf.writestr("tables/BOM.json", json.dumps(bom_table))

            result = restore_backup("backup_to_restore", "http://localhost:7070", "token123")
            assert result["success"] is True
            assert result["safety_backup"]["backup_id"] == "backup_safety_123"
            assert result["restored_counts"]["BOM"] == 1
