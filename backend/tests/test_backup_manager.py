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
    save_backup_config,
    materialize_full_archive,
    prune_orphan_blobs,
    get_blob_path
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


def test_second_identical_backup_reuses_blobs(mock_schema):
    """
    Second identical backup must have attachment_new_blobs == 0 and attachment_reused_blobs == <n>.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment") as mock_download:

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508": # BOM (2 attachments)
                    return [
                        {"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]},
                        {"id": 2, "Part Number": "20-002", "Image": [{"url": "http://img/2.png", "name": "2.png"}]}
                    ]
                elif table_id == "5770": # Instructions (1 attachment)
                    return [
                        {"id": 10, "Step Order": 1, "Photo": [{"url": "http://img/step1.jpg", "name": "step1.jpg"}]}
                    ]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl
            mock_download.side_effect = lambda url, timeout=15: f"content_for_{url}".encode("utf-8")

            # 1. First backup: all blobs should be new
            manifest1 = create_backup(api_url="http://localhost:7070", token="test_tok", backup_type="manual")
            assert manifest1["metrics"]["attachment_count"] == 3
            assert manifest1["metrics"]["attachment_new_blobs"] == 3
            assert manifest1["metrics"]["attachment_reused_blobs"] == 0
            assert manifest1["storage_format"] == "incremental-v1"

            # 2. Second identical backup: all blobs must be reused, 0 new blobs
            manifest2 = create_backup(api_url="http://localhost:7070", token="test_tok", backup_type="daily")
            assert manifest2["metrics"]["attachment_count"] == 3
            assert manifest2["metrics"]["attachment_new_blobs"] == 0
            assert manifest2["metrics"]["attachment_reused_blobs"] == 3
            assert manifest2["storage_format"] == "incremental-v1"


def test_thin_artifact_size_far_smaller_than_legacy(mock_schema):
    """
    Thin artifact archive_size_bytes must be far smaller than legacy (assert < 5 MB with mocked bodies).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock 3 large attachments: 2 MB each -> 6 MB total
        large_body = b"X" * (2 * 1024 * 1024)

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment", return_value=large_body):

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [
                        {"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/large1.bin", "name": "large1.bin"}]},
                        {"id": 2, "Part Number": "10-002", "Image": [{"url": "http://img/large2.bin", "name": "large2.bin"}]}
                    ]
                elif table_id == "5770":
                    return [
                        {"id": 10, "Step Order": 1, "Photo": [{"url": "http://img/large3.bin", "name": "large3.bin"}]}
                    ]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl

            manifest = create_backup(api_url="http://localhost:7070", token="test_tok")
            thin_zip_size = manifest["metrics"]["archive_size_bytes"]

            # 6 MB of attachments, but thin ZIP should be far below 5 MB (in reality only ~2 KB)
            assert thin_zip_size < 5 * 1024 * 1024
            assert thin_zip_size < 100 * 1024  # Even stricter: thin zip is under 100 KB!

            # Verify thin ZIP contents: no bodies stored inside
            zip_path = os.path.join(tmpdir, manifest["filename"])
            with zipfile.ZipFile(zip_path, "r") as zf:
                namelist = zf.namelist()
                assert "manifest.json" in namelist
                assert "attachments/index.json" in namelist
                # Ensure no raw attachment body entries exist in the thin zip
                assert not any(n.startswith("attachments/") and n != "attachments/index.json" for n in namelist)


def test_read_manifest_list_delete_on_new_artifact(mock_schema):
    """
    read_backup_manifest, list_backups, delete_backup work on a new incremental artifact.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment", return_value=b"test_bytes"):

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [{"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]}]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl

            manifest = create_backup(api_url="http://localhost:7070", token="test_tok", backup_type="manual")
            backup_id = manifest["backup_id"]
            zip_path = os.path.join(tmpdir, manifest["filename"])

            # 1. read_backup_manifest
            read_m = read_backup_manifest(zip_path)
            assert read_m["backup_id"] == backup_id
            assert read_m["storage_format"] == "incremental-v1"
            assert read_m["metrics"]["storage_format"] == "incremental-v1"
            assert read_m["metrics"]["attachment_count"] == 1
            assert read_m["metrics"]["archive_size_bytes"] == os.path.getsize(zip_path)

            # 2. list_backups
            backups = list_backups()
            assert len(backups) == 1
            assert backups[0]["backup_id"] == backup_id
            assert backups[0]["storage_format"] == "incremental-v1"

            # 3. delete_backup
            assert delete_backup(backup_id) is True
            assert not os.path.exists(zip_path)
            assert len(list_backups()) == 0


def test_retention_and_prune_orphan_blobs():
    """
    apply_retention_policy still prunes expired archives and prune_orphan_blobs removes
    only unreferenced blobs (referenced blobs survive).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir):
            now = datetime.datetime.now(datetime.timezone.utc)
            blobs_dir = os.path.join(tmpdir, "_blobs")
            os.makedirs(blobs_dir, exist_ok=True)

            # Define 3 blobs
            hash_kept = "11" + "a" * 62
            hash_expired = "22" + "b" * 62
            hash_orphan = "33" + "c" * 62

            # Write all 3 blobs to disk
            for h in (hash_kept, hash_expired, hash_orphan):
                bpath = os.path.join(blobs_dir, h[:2], h)
                os.makedirs(os.path.dirname(bpath), exist_ok=True)
                with open(bpath, "wb") as bf:
                    bf.write(f"content_{h}".encode("utf-8"))

            # 1. Retained backup (Thursday, 30 days old): references hash_kept
            d_kept = now - datetime.timedelta(days=30)
            while d_kept.weekday() != 3:
                d_kept += datetime.timedelta(days=1)
            z_kept = os.path.join(tmpdir, "backup_thursday_retained.zip")
            with zipfile.ZipFile(z_kept, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d_kept.isoformat(),
                    "is_thursday": True,
                    "storage_format": "incremental-v1"
                }))
                zf.writestr("attachments/index.json", json.dumps([
                    {"safe_key": "BOM_1_img.png", "hash": hash_kept, "size": 20, "name": "img.png", "url": "http://img/1"}
                ]))

            # 2. Expired backup (>14 days old, non-Thursday): references hash_expired
            d_exp = now - datetime.timedelta(days=25)
            while d_exp.weekday() == 3:
                d_exp += datetime.timedelta(days=1)
            z_exp = os.path.join(tmpdir, "backup_daily_expired.zip")
            with zipfile.ZipFile(z_exp, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "timestamp": d_exp.isoformat(),
                    "is_thursday": False,
                    "storage_format": "incremental-v1"
                }))
                zf.writestr("attachments/index.json", json.dumps([
                    {"safe_key": "BOM_2_exp.png", "hash": hash_expired, "size": 20, "name": "exp.png", "url": "http://img/2"}
                ]))

            # Verify all 3 blobs exist before retention
            path_kept = os.path.join(blobs_dir, hash_kept[:2], hash_kept)
            path_exp = os.path.join(blobs_dir, hash_expired[:2], hash_expired)
            path_orphan = os.path.join(blobs_dir, hash_orphan[:2], hash_orphan)
            assert os.path.exists(path_kept)
            assert os.path.exists(path_exp)
            assert os.path.exists(path_orphan)

            # Apply retention policy
            pruned = apply_retention_policy(tmpdir)
            pruned_names = [p["filename"] for p in pruned]
            assert "backup_daily_expired.zip" in pruned_names
            assert "backup_thursday_retained.zip" not in pruned_names

            # Verify backup files on disk
            assert os.path.exists(z_kept)
            assert not os.path.exists(z_exp)

            # Verify blobs:
            # - hash_kept must survive because backup_thursday_retained references it
            # - hash_expired must be deleted because its backup was pruned
            # - hash_orphan must be deleted because no backup references it
            assert os.path.exists(path_kept)
            assert not os.path.exists(path_exp)
            assert not os.path.exists(path_orphan)


def test_restore_backup_new_and_legacy_artifacts(mock_schema):
    """
    restore_backup restores rows from a NEW incremental artifact AND from a LEGACY artifact.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup") as mock_create_backup, \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post") as mock_post, \
             patch("requests.delete") as mock_del, \
             patch("requests.patch") as mock_patch:

            mock_create_backup.return_value = {"backup_id": "backup_safety_456"}
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": 777}
            mock_patch.return_value.status_code = 200

            # 1. Restore from NEW incremental artifact
            zip_new = os.path.join(tmpdir, "backup_new_incremental.zip")
            with zipfile.ZipFile(zip_new, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "backup_id": "backup_new_incremental",
                    "storage_format": "incremental-v1",
                    "metrics": {"total_rows_count": 1}
                }))
                zf.writestr("attachments/index.json", json.dumps([
                    {"safe_key": "BOM_1_cat.png", "hash": "abc", "size": 10, "name": "cat.png", "url": "http://img/cat"}
                ]))
                zf.writestr("tables/BOM.json", json.dumps({
                    "table_id": "508",
                    "rows": [{"id": 1, "Part Number": "NEW-001"}]
                }))

            res_new = restore_backup("backup_new_incremental", "http://localhost:7070", "token123")
            assert res_new["success"] is True
            assert res_new["restored_backup_id"] == "backup_new_incremental"
            assert res_new["safety_backup"]["backup_id"] == "backup_safety_456"
            assert res_new["restored_counts"]["BOM"] == 1

            # 2. Restore from LEGACY artifact (raw attachment body, no attachments/index.json)
            zip_legacy = os.path.join(tmpdir, "backup_legacy_full.zip")
            with zipfile.ZipFile(zip_legacy, "w") as zf:
                zf.writestr("manifest.json", json.dumps({
                    "backup_id": "backup_legacy_full",
                    "metrics": {"total_rows_count": 1}
                }))
                zf.writestr("attachments/BOM_1_dog.png", b"raw_legacy_dog_image_bytes")
                zf.writestr("tables/BOM.json", json.dumps({
                    "table_id": "508",
                    "rows": [{"id": 2, "Part Number": "LEGACY-002"}]
                }))

            res_legacy = restore_backup("backup_legacy_full", "http://localhost:7070", "token123")
            assert res_legacy["success"] is True
            assert res_legacy["restored_backup_id"] == "backup_legacy_full"
            assert res_legacy["safety_backup"]["backup_id"] == "backup_safety_456"
            assert res_legacy["restored_counts"]["BOM"] == 1


def test_materialize_full_archive_new_and_legacy(mock_schema):
    """
    materialize_full_archive on a new artifact yields a ZIP whose attachment bodies match
    the store and whose bytes equal original bodies; on legacy returns as-is.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment") as mock_download:

            body_img1 = b"unique_image_one_binary_data"
            body_img2 = b"unique_image_two_binary_data"

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [
                        {"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]},
                        {"id": 2, "Part Number": "20-002", "Image": [{"url": "http://img/2.png", "name": "2.png"}]}
                    ]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl
            mock_download.side_effect = lambda url, timeout=15: body_img1 if "1.png" in url else body_img2

            # 1. Create new incremental backup
            manifest = create_backup(api_url="http://localhost:7070", token="test_tok")
            backup_id = manifest["backup_id"]

            # Materialize full archive
            mat_zip_path = materialize_full_archive(backup_id)
            assert os.path.exists(mat_zip_path)

            with zipfile.ZipFile(mat_zip_path, "r") as zf:
                namelist = zf.namelist()
                assert "manifest.json" in namelist
                assert "tables/BOM.json" in namelist
                assert "attachments/BOM_1_1.png" in namelist
                assert "attachments/BOM_2_2.png" in namelist

                # Assert bytes in materialized ZIP match the blob store and original bodies
                assert zf.read("attachments/BOM_1_1.png") == body_img1
                assert zf.read("attachments/BOM_2_2.png") == body_img2
                assert len(zf.read("attachments/BOM_1_1.png")) == len(body_img1)
                assert len(zf.read("attachments/BOM_2_2.png")) == len(body_img2)

            # 2. Legacy backup: materialize_full_archive returns as-is / copies
            legacy_id = "backup_legacy_sample"
            legacy_zip = os.path.join(tmpdir, f"{legacy_id}.zip")
            with zipfile.ZipFile(legacy_zip, "w") as zf:
                zf.writestr("manifest.json", json.dumps({"backup_id": legacy_id, "metrics": {}}))
                zf.writestr("attachments/legacy_sample.png", b"legacy_data")
                zf.writestr("tables/BOM.json", json.dumps({"rows": []}))

            mat_legacy_path = materialize_full_archive(legacy_id)
            assert os.path.exists(mat_legacy_path)
            with zipfile.ZipFile(mat_legacy_path, "r") as zf:
                assert zf.read("attachments/legacy_sample.png") == b"legacy_data"


def test_incrementality_proof(mock_schema):
    """
    Incrementality proof: with a mocked schema of >=3 attachments, create backup A
    then backup B with identical attachment bodies; print and assert
    (bytes_written_for_B) < 1/10 of (bytes_written_for_A).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 3 attachments, 200 KB each = 600 KB payload
        att1_bytes = b"A" * (200 * 1024)
        att2_bytes = b"B" * (200 * 1024)
        att3_bytes = b"C" * (200 * 1024)

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment") as mock_download:

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [
                        {"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/a.png", "name": "a.png"}]},
                        {"id": 2, "Part Number": "20-002", "Image": [{"url": "http://img/b.png", "name": "b.png"}]}
                    ]
                elif table_id == "5770":
                    return [
                        {"id": 10, "Step Order": 1, "Photo": [{"url": "http://img/c.png", "name": "c.png"}]}
                    ]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl

            def mock_dl_impl(url, timeout=15):
                if "a.png" in url:
                    return att1_bytes
                elif "b.png" in url:
                    return att2_bytes
                return att3_bytes

            mock_download.side_effect = mock_dl_impl

            # --- BACKUP A (Initial Backup) ---
            blobs_dir = os.path.join(tmpdir, "_blobs")
            bytes_in_blobs_before_a = 0
            if os.path.exists(blobs_dir):
                bytes_in_blobs_before_a = sum(
                    os.path.getsize(os.path.join(r, f))
                    for r, _, files in os.walk(blobs_dir) if os.path.abspath(r) != os.path.abspath(blobs_dir)
                    for f in files
                )

            manifest_a = create_backup(api_url="http://localhost:7070", token="tokenA", backup_type="manual")
            zip_a_path = os.path.join(tmpdir, manifest_a["filename"])
            zip_a_size = os.path.getsize(zip_a_path)

            bytes_in_blobs_after_a = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, files in os.walk(blobs_dir) if os.path.abspath(r) != os.path.abspath(blobs_dir)
                for f in files
            )
            blobs_written_for_a = bytes_in_blobs_after_a - bytes_in_blobs_before_a
            bytes_written_for_A = blobs_written_for_a + zip_a_size

            # Assert backup A wrote new blobs
            assert manifest_a["metrics"]["attachment_new_blobs"] == 3
            assert manifest_a["metrics"]["attachment_reused_blobs"] == 0

            # --- BACKUP B (Incremental Backup with identical bodies) ---
            bytes_in_blobs_before_b = bytes_in_blobs_after_a

            manifest_b = create_backup(api_url="http://localhost:7070", token="tokenB", backup_type="daily")
            zip_b_path = os.path.join(tmpdir, manifest_b["filename"])
            zip_b_size = os.path.getsize(zip_b_path)

            bytes_in_blobs_after_b = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, files in os.walk(blobs_dir) if os.path.abspath(r) != os.path.abspath(blobs_dir)
                for f in files
            )
            blobs_written_for_b = bytes_in_blobs_after_b - bytes_in_blobs_before_b
            bytes_written_for_B = blobs_written_for_b + zip_b_size

            # Assert backup B reused all blobs and wrote 0 new blobs
            assert blobs_written_for_b == 0
            assert manifest_b["metrics"]["attachment_new_blobs"] == 0
            assert manifest_b["metrics"]["attachment_reused_blobs"] == 3

            # --- PROOF OUTPUT AND ASSERTION ---
            ratio = bytes_written_for_B / bytes_written_for_A
            print(f"\n=======================================================")
            print(f"[INCREMENTALITY PROOF]")
            print(f"Total attachment payload (3 items): {len(att1_bytes) + len(att2_bytes) + len(att3_bytes):,} bytes")
            print(f"Bytes written for Backup A (initial):     {bytes_written_for_A:,} bytes")
            print(f"  - New blobs to blob store:             {blobs_written_for_a:,} bytes")
            print(f"  - Thin ZIP A:                          {zip_a_size:,} bytes")
            print(f"Bytes written for Backup B (incremental): {bytes_written_for_B:,} bytes")
            print(f"  - New blobs to blob store:             {blobs_written_for_b:,} bytes")
            print(f"  - Thin ZIP B:                          {zip_b_size:,} bytes")
            print(f"Ratio (B / A): {ratio:.4%} (< 10.0%)")
            print(f"=======================================================\n")

            assert bytes_written_for_B < (1 / 10) * bytes_written_for_A


def test_download_backup_endpoint_streams_materialized(mock_schema):
    """
    Test that GET /api/backup/download/<backup_id> streams a materialized self-contained archive.
    """
    import io
    from app.main import create_app
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment", return_value=b"streamed_photo_body"):

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [{"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]}]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl

            manifest = create_backup(api_url="http://localhost:7070", token="test_tok")
            backup_id = manifest["backup_id"]

            app = create_app()
            with app.test_client() as client:
                res = client.get(f"/api/backup/download/{backup_id}")
                assert res.status_code == 200
                assert f"filename={backup_id}.zip" in res.headers.get("Content-Disposition", "")

                # Verify downloaded stream is self-contained full archive
                downloaded_bytes = res.data
                with zipfile.ZipFile(io.BytesIO(downloaded_bytes), "r") as zf:
                    assert "manifest.json" in zf.namelist()
                    assert "tables/BOM.json" in zf.namelist()
                    assert "attachments/BOM_1_1.png" in zf.namelist()
                    assert zf.read("attachments/BOM_1_1.png") == b"streamed_photo_body"


def test_attachment_rehash_config(mock_schema):
    """
    When attachment_rehash is True, it always re-downloads to verify hash,
    updating blob index if content changed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        content_version = [b"version_1_bytes"]

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment") as mock_dl:

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [{"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/stable.png", "name": "stable.png"}]}]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl
            mock_dl.side_effect = lambda url, timeout=15: content_version[0]

            # Backup 1: initial
            m1 = create_backup(api_url="http://localhost:7070", token="t1")
            assert m1["metrics"]["attachment_new_blobs"] == 1
            assert m1["metrics"]["attachment_reused_blobs"] == 0

            # Backup 2 with attachment_rehash=False: URL is in index, should not download
            mock_dl.reset_mock()
            m2 = create_backup(api_url="http://localhost:7070", token="t2")
            assert mock_dl.call_count == 0
            assert m2["metrics"]["attachment_new_blobs"] == 0
            assert m2["metrics"]["attachment_reused_blobs"] == 1

            # Backup 3 with attachment_rehash=True and rotated content at same URL:
            content_version[0] = b"version_2_changed_bytes"
            with patch("app.backup_manager.load_backup_config", return_value={"attachment_rehash": True}):
                mock_dl.reset_mock()
                m3 = create_backup(api_url="http://localhost:7070", token="t3")
                assert mock_dl.call_count == 1
                assert m3["metrics"]["attachment_new_blobs"] == 1
                assert m3["metrics"]["attachment_reused_blobs"] == 0



def test_download_endpoint_cleans_up_materialized_tempfile(mock_schema):
    """
    The download route materializes a self-contained ZIP into a temp file for
    incremental archives; that temp file must not leak after the response is sent.
    """
    import io
    import os as _os
    from app.main import create_app

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.fetch_all_table_rows") as mock_fetch_rows, \
             patch("app.backup_manager.download_attachment", return_value=b"photo_body"):

            def mock_rows_impl(api_url, headers, table_id):
                if table_id == "508":
                    return [{"id": 1, "Part Number": "10-001", "Image": [{"url": "http://img/1.png", "name": "1.png"}]}]
                return []

            mock_fetch_rows.side_effect = mock_rows_impl

            manifest = create_backup(api_url="http://localhost:7070", token="t")
            backup_id = manifest["backup_id"]

            created = []
            real_mkstemp = tempfile.mkstemp

            def spy_mkstemp(*a, **k):
                fd, p = real_mkstemp(*a, **k)
                created.append(p)
                return fd, p

            app = create_app()
            with patch("app.backup_manager.tempfile.mkstemp", side_effect=spy_mkstemp):
                with app.test_client() as client:
                    res = client.get(f"/api/backup/download/{backup_id}")
                    assert res.status_code == 200
                    # The streamed download is still a complete self-contained archive.
                    with zipfile.ZipFile(io.BytesIO(res.data), "r") as zf:
                        assert zf.read("attachments/BOM_1_1.png") == b"photo_body"
                    assert len(created) == 1, "expected exactly one materialized temp file"

            # ...and it is gone once the request has completed.
            assert all(not _os.path.exists(p) for p in created), created


def test_two_subsequent_backups_capture_additions_and_removals(mock_schema):
    """
    Two subsequent backups across a live mutation (one row REMOVED, one row ADDED):
      - each backup stores the FULL current row set, not an incremental delta;
      - attachments are deduped (unchanged body reuses its blob, new body adds one);
      - restore of the later backup reproduces exactly that point-in-time state, so a
        row deleted between the two backups comes back at restore (delete-then-insert).
    """
    import re
    import hashlib

    version = {"rows": []}

    def fetch_rows(api_url, headers, table_id):
        if table_id == "508":
            return [dict(r) for r in version["rows"]]
        return []

    def hashes_of(rows):
        out = set()
        for r in rows:
            for v in r.values():
                if isinstance(v, list):
                    for it in v:
                        if isinstance(it, dict) and it.get("url"):
                            out.add(item_hash(it["url"]))
        return out

    def item_hash(url):
        return hashlib.sha256(f"body::{url}".encode()).hexdigest()

    with tempfile.TemporaryDirectory() as tmpdir:
        common = dict(
            get_backups_dir=patch("app.backup_manager.get_backups_dir", return_value=tmpdir),
            schema=patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema),
            fetch=patch("app.backup_manager.fetch_all_table_rows", side_effect=fetch_rows),
            dl=patch("app.backup_manager.download_attachment",
                     side_effect=lambda url, timeout=15: f"body::{url}".encode()),
        )
        with common["get_backups_dir"], common["schema"], common["fetch"], common["dl"]:
            # --- Backup A: rows {10-001, 10-002}, two distinct attachments ---
            version["rows"] = [
                {"id": 1, "Part Number": "10-001",
                 "Image": [{"url": "http://img/a.png", "name": "a.png"}]},
                {"id": 2, "Part Number": "10-002",
                 "Image": [{"url": "http://img/b.png", "name": "b.png"}]},
            ]
            A = create_backup(api_url="http://localhost:7070", token="tok", backup_type="manual")
            assert A["metrics"]["attachment_count"] == 2
            assert A["metrics"]["attachment_new_blobs"] == 2

            # --- Live mutation between backups: drop 10-002, add 10-003 ---
            version["rows"] = [
                {"id": 1, "Part Number": "10-001",
                 "Image": [{"url": "http://img/a.png", "name": "a.png"}]},
                {"id": 3, "Part Number": "10-003",
                 "Image": [{"url": "http://img/c.png", "name": "c.png"}]},
            ]
            B = create_backup(api_url="http://localhost:7070", token="tok", backup_type="daily")
            assert B["metrics"]["attachment_count"] == 2
            assert B["metrics"]["attachment_new_blobs"] == 1      # only c.png is new
            assert B["metrics"]["attachment_reused_blobs"] == 1   # a.png reused from blob store

        # --- B carries the FULL live row set: addition present, removal gone ---
        with zipfile.ZipFile(os.path.join(tmpdir, B["filename"])) as zf:
            rows_b = json.loads(zf.read("tables/BOM.json"))["rows"]
        assert sorted(r["Part Number"] for r in rows_b) == ["10-001", "10-003"]
        # It is a snapshot, not a delta: 10-003 has no "added"/"removed" wrapper — it is just a row.
        assert all("Part Number" in r for r in rows_b)

        # --- The removed row's attachment blob survives: backup A still references it ---
        b_hash = item_hash("http://img/b.png")
        assert os.path.exists(get_blob_path(b_hash, tmpdir)), "removed row's blob must not be pruned while A exists"

        # --- Restore B over a live store that currently holds A's rows ---
        live = {"BOM": {1: {"Part Number": "10-001"}, 2: {"Part Number": "10-002"}}}
        next_id = [900]

        def live_fetch(api_url, headers, table_id):
            if table_id == "508":
                return [dict(id=i, **r) for i, r in live["BOM"].items()]
            return []

        def tname_for(table_id):
            return next(t for t, i in mock_schema["tables"].items() if str(i["id"]) == str(table_id))

        def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
            if "/upload-file/" in url:
                m = MagicMock(); m.status_code = 200
                m.json.return_value = {"name": "uploaded", "url": "http://img/restored"}
                return m
            tid = re.search(r"/table/(\d+)/", url).group(1)
            new_id = next_id[0]; next_id[0] += 1
            row = dict(json or {}); row["id"] = new_id
            live.setdefault(tname_for(tid), {})[new_id] = row
            m = MagicMock(); m.status_code = 200; m.json.return_value = {"id": new_id}; m.text = ""
            return m

        def fake_delete(url, headers=None, timeout=None):
            m2 = re.search(r"/table/(\d+)/(\d+)/", url)
            live.get(tname_for(m2.group(1)), {}).pop(int(m2.group(2)), None)
            m = MagicMock(); m.status_code = 204
            return m

        def fake_patch(url, headers=None, json=None, timeout=None):
            m = MagicMock(); m.status_code = 200
            return m

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup", return_value={"backup_id": "backup_safety_x"}), \
             patch("app.backup_manager.fetch_all_table_rows", side_effect=live_fetch), \
             patch("app.backup_manager.requests.post", side_effect=fake_post), \
             patch("app.backup_manager.requests.delete", side_effect=fake_delete), \
             patch("app.backup_manager.requests.patch", side_effect=fake_patch):
            res = restore_backup(B["backup_id"], "http://localhost:7070", "tok")
        assert res["success"] is True
        assert res["restored_counts"]["BOM"] == 2
        assert res["attachments_restored"] == 2
        live_pns = sorted(r["Part Number"] for r in live["BOM"].values())
        assert live_pns == ["10-001", "10-003"], live_pns  # addition restored, removal NOT resurrected

        # --- Only after A is gone does the removed row's blob become prunable ---
        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir):
            assert delete_backup(A["backup_id"]) is True
        pruned = prune_orphan_blobs(tmpdir)
        assert not os.path.exists(get_blob_path(b_hash, tmpdir))
        assert any(b_hash in p for p in pruned), pruned


def test_restore_backup_incremental_attachment_restoration(mock_schema):
    """
    Incremental-v1 restore:
    A row with an attachment whose blob exists in _blobs/:
      (a) the blob bytes were POSTed to /api/user-files/upload-file/ (field 'file')
      (b) the row was PATCHed with the uploaded file object for that column
      (c) attachments_restored == 1
      (d) no dangling old URL was written to initial row POST
    """
    import hashlib
    with tempfile.TemporaryDirectory() as tmpdir:
        blob_bytes = b"real_binary_image_data_incremental"
        blob_hash = hashlib.sha256(blob_bytes).hexdigest()

        # Write blob to _blobs/
        blob_path = get_blob_path(blob_hash, tmpdir)
        os.makedirs(os.path.dirname(blob_path), exist_ok=True)
        with open(blob_path, "wb") as bf:
            bf.write(blob_bytes)

        # Write thin ZIP
        zip_path = os.path.join(tmpdir, "backup_inc_att.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "backup_id": "backup_inc_att",
                "storage_format": "incremental-v1",
                "metrics": {"total_rows_count": 1}
            }))
            zf.writestr("attachments/index.json", json.dumps([
                {
                    "safe_key": "BOM_1_circuit.png",
                    "name": "circuit.png",
                    "url": "http://img.internal/circuit.png",
                    "hash": blob_hash,
                    "size": len(blob_bytes)
                }
            ]))
            bom_table = {
                "table_id": "508",
                "rows": [
                    {
                        "id": 1,
                        "Part Number": "10-999",
                        "Image": [{"url": "http://img.internal/circuit.png", "name": "circuit.png"}]
                    }
                ]
            }
            zf.writestr("tables/BOM.json", json.dumps(bom_table))

        post_calls = []
        def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
            call_info = {"url": url, "headers": headers, "json": json, "files": files}
            post_calls.append(call_info)
            m = MagicMock()
            m.status_code = 200
            if "/upload-file/" in url:
                m.json.return_value = {
                    "size": len(blob_bytes),
                    "mime_type": "image/png",
                    "is_image": True,
                    "url": "http://baserow/media/user_files/new_circuit.png",
                    "name": "new_circuit.png",
                    "original_name": "circuit.png"
                }
            else:
                m.json.return_value = {"id": 777}
            return m

        patch_calls = []
        def fake_patch(url, headers=None, json=None, timeout=None, **kwargs):
            patch_calls.append({"url": url, "headers": headers, "json": json})
            m = MagicMock()
            m.status_code = 200
            return m

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup", return_value={"backup_id": "backup_safety_inc"}), \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post", side_effect=fake_post), \
             patch("requests.delete") as mock_del, \
             patch("requests.patch", side_effect=fake_patch):
            
            res = restore_backup("backup_inc_att", "http://localhost:7070", "test_tok")

        # Verify response
        assert res["success"] is True
        # (c) attachments_restored == 1
        assert res["attachments_restored"] == 1
        assert res["restored_counts"]["BOM"] == 1
        assert res["attachments_by_table"]["BOM"] == 1

        # (a) the blob bytes were POSTed to /api/user-files/upload-file/ (field 'file')
        upload_calls = [c for c in post_calls if "/api/user-files/upload-file/" in c["url"]]
        assert len(upload_calls) == 1
        assert "file" in upload_calls[0]["files"]
        filename, uploaded_bytes = upload_calls[0]["files"]["file"]
        assert filename == "circuit.png"
        assert uploaded_bytes == blob_bytes

        # (b) the row was PATCHed with the uploaded file object for that column
        row_patch_calls = [c for c in patch_calls if "/api/database/rows/table/508/777/" in c["url"]]
        assert len(row_patch_calls) == 1
        assert "Image" in row_patch_calls[0]["json"]
        assert row_patch_calls[0]["json"]["Image"] == [{
            "size": len(blob_bytes),
            "mime_type": "image/png",
            "is_image": True,
            "url": "http://baserow/media/user_files/new_circuit.png",
            "name": "new_circuit.png",
            "original_name": "circuit.png"
        }]

        # (d) no dangling old URL was written
        create_row_calls = [c for c in post_calls if "/api/database/rows/table/508/" in c["url"]]
        assert len(create_row_calls) == 1
        assert "Image" not in create_row_calls[0]["json"]
        assert "http://img.internal/circuit.png" not in json.dumps(create_row_calls[0]["json"])


def test_restore_backup_legacy_attachment_restoration(mock_schema):
    """
    Legacy FAT ZIP restore:
    Attachment body bytes come from the embedded attachments/<safe_key> entry.
      (a) the bytes were POSTed to /api/user-files/upload-file/ (field 'file')
      (b) the row was PATCHed with the uploaded file object for that column
      (c) attachments_restored == 1
      (d) no dangling old URL was written to initial row POST
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        legacy_bytes = b"legacy_fat_zip_photo_bytes_999"

        # Write legacy FAT ZIP (bodies inside zip under attachments/<safe_key>)
        zip_path = os.path.join(tmpdir, "backup_legacy_att.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "backup_id": "backup_legacy_att",
                "storage_format": "legacy",
                "metrics": {"total_rows_count": 1}
            }))
            # safe_key: <table_name>_<old_row_id>_<file_name>
            zf.writestr("attachments/BOM_42_part_photo.jpg", legacy_bytes)
            bom_table = {
                "table_id": "508",
                "rows": [
                    {
                        "id": 42,
                        "Part Number": "10-042",
                        "Image": [{"url": "http://legacy.baserow/media/part_photo.jpg", "name": "part_photo.jpg"}]
                    }
                ]
            }
            zf.writestr("tables/BOM.json", json.dumps(bom_table))

        post_calls = []
        def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
            call_info = {"url": url, "headers": headers, "json": json, "files": files}
            post_calls.append(call_info)
            m = MagicMock()
            m.status_code = 200
            if "/upload-file/" in url:
                m.json.return_value = {
                    "size": len(legacy_bytes),
                    "name": "new_part_photo.jpg",
                    "url": "http://baserow/media/user_files/new_part_photo.jpg"
                }
            else:
                m.json.return_value = {"id": 842}
            return m

        patch_calls = []
        def fake_patch(url, headers=None, json=None, timeout=None, **kwargs):
            patch_calls.append({"url": url, "headers": headers, "json": json})
            m = MagicMock()
            m.status_code = 200
            return m

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup", return_value={"backup_id": "backup_safety_leg"}), \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post", side_effect=fake_post), \
             patch("requests.delete") as mock_del, \
             patch("requests.patch", side_effect=fake_patch):
            
            res = restore_backup("backup_legacy_att", "http://localhost:7070", "test_tok")

        assert res["success"] is True
        assert res["attachments_restored"] == 1
        assert res["restored_counts"]["BOM"] == 1
        assert res["attachments_by_table"]["BOM"] == 1

        upload_calls = [c for c in post_calls if "/api/user-files/upload-file/" in c["url"]]
        assert len(upload_calls) == 1
        assert "file" in upload_calls[0]["files"]
        filename, uploaded_bytes = upload_calls[0]["files"]["file"]
        assert filename == "part_photo.jpg"
        assert uploaded_bytes == legacy_bytes

        row_patch_calls = [c for c in patch_calls if "/api/database/rows/table/508/842/" in c["url"]]
        assert len(row_patch_calls) == 1
        assert "Image" in row_patch_calls[0]["json"]
        assert row_patch_calls[0]["json"]["Image"][0]["name"] == "new_part_photo.jpg"

        create_row_calls = [c for c in post_calls if "/api/database/rows/table/508/" in c["url"]]
        assert len(create_row_calls) == 1
        assert "Image" not in create_row_calls[0]["json"]
        assert "http://legacy.baserow/media/part_photo.jpg" not in json.dumps(create_row_calls[0]["json"])


def test_restore_backup_link_relations_and_attachments_coexist(mock_schema):
    """
    Assert link-relation second pass still works and row counts unchanged
    when both link relations and attachments are present.
    """
    import hashlib
    import re
    with tempfile.TemporaryDirectory() as tmpdir:
        blob_bytes = b"blob_data_for_bom_image"
        blob_hash = hashlib.sha256(blob_bytes).hexdigest()

        blob_path = get_blob_path(blob_hash, tmpdir)
        os.makedirs(os.path.dirname(blob_path), exist_ok=True)
        with open(blob_path, "wb") as bf:
            bf.write(blob_bytes)

        zip_path = os.path.join(tmpdir, "backup_links_and_att.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "backup_id": "backup_links_and_att",
                "storage_format": "incremental-v1",
                "metrics": {"total_rows_count": 2}
            }))
            zf.writestr("attachments/index.json", json.dumps([
                {
                    "safe_key": "BOM_101_schematic.png",
                    "name": "schematic.png",
                    "url": "http://img.internal/schematic.png",
                    "hash": blob_hash,
                    "size": len(blob_bytes)
                }
            ]))
            mfg_table = {
                "table_id": "683",
                "rows": [{"id": 50, "Name": "VendorAlpha"}]
            }
            bom_table = {
                "table_id": "508",
                "rows": [
                    {
                        "id": 101,
                        "Part Number": "10-101",
                        "Manufacturer": [{"id": 50, "value": "VendorAlpha"}],
                        "Image": [{"url": "http://img.internal/schematic.png", "name": "schematic.png"}]
                    }
                ]
            }
            zf.writestr("tables/Manufacturers.json", json.dumps(mfg_table))
            zf.writestr("tables/BOM.json", json.dumps(bom_table))

        new_ids = {"683": 3001, "508": 4001}
        post_calls = []
        def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
            post_calls.append({"url": url, "json": json, "files": files})
            m = MagicMock(); m.status_code = 200
            if "/upload-file/" in url:
                m.json.return_value = {"name": "restored_schematic.png", "url": "http://baserow/media/restored.png"}
            else:
                tid = re.search(r"/table/(\d+)/", url).group(1)
                m.json.return_value = {"id": new_ids[tid]}
            return m

        patch_calls = []
        def fake_patch(url, headers=None, json=None, timeout=None, **kwargs):
            patch_calls.append({"url": url, "json": json})
            m = MagicMock(); m.status_code = 200
            return m

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup", return_value={"backup_id": "backup_safety_link"}), \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post", side_effect=fake_post), \
             patch("requests.delete") as mock_del, \
             patch("requests.patch", side_effect=fake_patch):
            
            res = restore_backup("backup_links_and_att", "http://localhost:7070", "test_tok")

        assert res["success"] is True
        assert res["restored_counts"]["Manufacturers"] == 1
        assert res["restored_counts"]["BOM"] == 1
        assert res["attachments_restored"] == 1

        # Check Pass 2: Manufacturer link relation was remapped to new ID 3001
        link_patches = [c for c in patch_calls if "/api/database/rows/table/508/4001/" in c["url"] and "Manufacturer" in c["json"]]
        assert len(link_patches) == 1
        assert link_patches[0]["json"]["Manufacturer"] == [3001]

        # Check Pass 3: Attachment was restored
        att_patches = [c for c in patch_calls if "/api/database/rows/table/508/4001/" in c["url"] and "Image" in c["json"]]
        assert len(att_patches) == 1
        assert att_patches[0]["json"]["Image"][0]["name"] == "restored_schematic.png"


def test_restore_backup_missing_blob_warns_and_succeeds(mock_schema, caplog):
    """
    Negative case: missing blob -> warning logged + attachments_restored not incremented
    + restore still succeeds.
    """
    import logging
    with tempfile.TemporaryDirectory() as tmpdir:
        # Incremental backup referencing a blob hash that DOES NOT exist in _blobs/
        missing_hash = "0000000000000000000000000000000000000000000000000000000000000000"

        zip_path = os.path.join(tmpdir, "backup_missing_blob.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({
                "backup_id": "backup_missing_blob",
                "storage_format": "incremental-v1",
                "metrics": {"total_rows_count": 1}
            }))
            zf.writestr("attachments/index.json", json.dumps([
                {
                    "safe_key": "BOM_1_missing.png",
                    "name": "missing.png",
                    "url": "http://img.internal/missing.png",
                    "hash": missing_hash,
                    "size": 500
                }
            ]))
            bom_table = {
                "table_id": "508",
                "rows": [
                    {
                        "id": 1,
                        "Part Number": "10-MISSING",
                        "Image": [{"url": "http://img.internal/missing.png", "name": "missing.png"}]
                    }
                ]
            }
            zf.writestr("tables/BOM.json", json.dumps(bom_table))

        post_calls = []
        def fake_post(url, headers=None, json=None, files=None, timeout=None, **kwargs):
            post_calls.append({"url": url, "json": json, "files": files})
            m = MagicMock(); m.status_code = 200
            m.json.return_value = {"id": 999}
            return m

        with patch("app.backup_manager.get_backups_dir", return_value=tmpdir), \
             patch("app.backup_manager.discover_baserow_schema", return_value=mock_schema), \
             patch("app.backup_manager.create_backup", return_value={"backup_id": "backup_safety_miss"}), \
             patch("app.backup_manager.fetch_all_table_rows", return_value=[]), \
             patch("requests.post", side_effect=fake_post), \
             patch("requests.delete") as mock_del, \
             patch("requests.patch") as mock_patch:
            
            with caplog.at_level(logging.WARNING):
                res = restore_backup("backup_missing_blob", "http://localhost:7070", "test_tok")

        assert res["success"] is True
        assert res["restored_counts"]["BOM"] == 1
        assert res["attachments_restored"] == 0

        # Upload should NEVER have been called since blob was missing
        upload_calls = [c for c in post_calls if "/api/user-files/upload-file/" in c["url"]]
        assert len(upload_calls) == 0

        # PATCH for attachment should not have been called
        mock_patch.assert_not_called()

        # Warning logged about missing blob
        assert any("Blob file missing" in record.message for record in caplog.records)
