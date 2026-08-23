import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from app.baserow_init import (
    ERA_SCHEMA_DEFINITIONS,
    DEFAULT_PN_CATEGORIES,
    DEFAULT_STATES,
    DEFAULT_QUICK_ACTION_TEMPLATES,
    format_detailed_error,
    get_jwt_token,
    discover_baserow_tables,
    update_env_files,
    seed_default_data,
    init_baserow_schema
)

def test_format_detailed_error():
    err = format_detailed_error("Test Action", "Sample error details", ["Action 1", "Action 2"])
    assert "Test Action" in err
    assert "Sample error details" in err
    assert "Action 1" in err
    assert "Action 2" in err
    assert "BASEROW DATABASE INITIALIZATION / SCHEMA NOTICE" in err


def test_format_detailed_error_default_schema_dump():
    err = format_detailed_error("Create Tables", "Permission denied")
    assert "Table 'BOM'" in err
    assert "Table 'Assembly'" in err
    assert "Table 'PN Categories'" in err


def test_get_jwt_token_success():
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"token": "jwt-token-123"}
        token = get_jwt_token("http://localhost:7070", "admin@era.com", "secret")
        assert token == "jwt-token-123"


def test_get_jwt_token_failure_or_missing_credentials():
    assert get_jwt_token("http://localhost:7070", None, None) is None

    with patch("requests.post", side_effect=Exception("Network error")):
        assert get_jwt_token("http://localhost:7070", "admin@era.com", "secret") is None


def test_update_env_files_modifies_and_appends():
    with tempfile.TemporaryDirectory() as tmpdir:
        env1 = os.path.join(tmpdir, ".env")
        env2 = os.path.join(tmpdir, "backend.env")

        with open(env1, "w", encoding="utf-8") as f:
            f.write("EXISTING_KEY=old_val\nBASEROW_TABLE_BOM=100\n")

        with open(env2, "w", encoding="utf-8") as f:
            f.write("EXISTING_KEY=old_val\n")

        with patch("app.baserow_init.find_env_files", return_value=[env1, env2]):
            update_env_files({
                "BASEROW_TABLE_BOM": "508",
                "BASEROW_TABLE_ASSEMBLY": "701"
            })

        with open(env1, "r", encoding="utf-8") as f:
            content1 = f.read()
            assert "BASEROW_TABLE_BOM=508" in content1
            assert "BASEROW_TABLE_ASSEMBLY=701" in content1
            assert "EXISTING_KEY=old_val" in content1

        with open(env2, "r", encoding="utf-8") as f:
            content2 = f.read()
            assert "BASEROW_TABLE_BOM=508" in content2
            assert "BASEROW_TABLE_ASSEMBLY=701" in content2


def test_discover_baserow_tables_via_applications():
    mock_apps = [{"id": 1, "type": "database", "name": "ERA DB"}]
    mock_tables = [
        {"id": 508, "name": "BOM"},
        {"id": 701, "name": "Assembly"},
        {"id": 5770, "name": "Assembly Instructions"},
        {"id": 42471, "name": "PN Categories"},
        {"id": 48537, "name": "States"},
        {"id": 48538, "name": "WI Templates"},
        {"id": 683, "name": "Manufacturers"},
        {"id": 682, "name": "Suppliers"},
        {"id": 684, "name": "Contacts"}
    ]

    with patch("requests.get") as mock_get:
        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "/api/applications/" in url:
                resp.status_code = 200
                resp.json.return_value = mock_apps
            elif "/api/database/tables/database/1/" in url:
                resp.status_code = 200
                resp.json.return_value = mock_tables
            else:
                resp.status_code = 404
            return resp

        mock_get.side_effect = side_effect

        discovered = discover_baserow_tables(
            api_url="http://localhost:7070",
            token="token123",
            admin_email=None,
            admin_password=None
        )

        assert discovered["BASEROW_TABLE_BOM"] == "508"
        assert discovered["BASEROW_TABLE_ASSEMBLY"] == "701"
        assert discovered["BASEROW_TABLE_INSTRUCTIONS"] == "5770"
        assert discovered["BASEROW_TABLE_PN_CATEGORIES"] == "42471"
        assert discovered["BASEROW_TABLE_ITEM_STATES"] == "48537"


def test_discover_baserow_tables_fallback_direct_query():
    with patch("requests.get") as mock_get:
        def side_effect(url, **kwargs):
            resp = MagicMock()
            if "/api/applications/" in url:
                resp.status_code = 403  # Token not permitted for applications
            elif "/api/database/rows/table/" in url:
                resp.status_code = 200
                resp.json.return_value = {"results": []}
            else:
                resp.status_code = 404
            return resp

        mock_get.side_effect = side_effect

        with patch.dict(os.environ, {"BASEROW_TABLE_BOM": "508"}, clear=False):
            discovered = discover_baserow_tables(
                api_url="http://localhost:7070",
                token="token123"
            )
            assert discovered["BASEROW_TABLE_BOM"] == "508"


def test_seed_default_data_pn_categories_and_states():
    table_ids = {
        "BASEROW_TABLE_PN_CATEGORIES": "42471",
        "BASEROW_TABLE_ITEM_STATES": "48537"
    }

    posted_rows = []

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Existing rows empty
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"results": []}

        mock_post.return_value.status_code = 200

        seeded = seed_default_data("http://localhost:7070", {"Authorization": "Token t"}, table_ids)
        assert len(seeded) > 0
        assert any("PN Category 10" in s for s in seeded)
        assert any("Item State: Production Use" in s for s in seeded)
        assert any("Problem Definitions initialized to empty []" in s for s in seeded)


def test_init_baserow_schema_missing_tables_token_only():
    with patch("requests.get") as mock_get, patch("app.baserow_init.discover_baserow_tables", return_value={}):
        mock_get.return_value.status_code = 200
        with patch("app.baserow_init.get_jwt_token", return_value=None):
            with patch("app.baserow_init.update_env_files") as mock_update:
                success = init_baserow_schema(auto_update_env=False)
                assert success is True


def test_init_baserow_schema_unreachable_api():
    with patch("requests.get", side_effect=Exception("Connection refused")):
        success = init_baserow_schema(auto_update_env=False)
        assert success is False
