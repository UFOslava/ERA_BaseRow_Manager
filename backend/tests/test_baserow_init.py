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


def test_parse_url_and_port():
    from app.baserow_init import parse_url_and_port
    assert parse_url_and_port("http://localhost:7070") == ("http://localhost", "7070")
    assert parse_url_and_port("https://my-baserow.com:8443") == ("https://my-baserow.com", "8443")
    assert parse_url_and_port("http://localhost") == ("http://localhost", "")
    assert parse_url_and_port("192.168.1.50:8080") == ("http://192.168.1.50", "8080")
    assert parse_url_and_port("") == ("http://localhost", "7070")


def test_combine_url_and_port():
    from app.baserow_init import combine_url_and_port
    assert combine_url_and_port("http://localhost", "7070") == "http://localhost:7070"
    assert combine_url_and_port("http://localhost:7070", "7070") == "http://localhost:7070"
    assert combine_url_and_port("localhost", "7070") == "http://localhost:7070"
    assert combine_url_and_port("https://api.era.com", "") == "https://api.era.com"
    assert combine_url_and_port(None, None) == "http://localhost"


def test_test_baserow_connection_success_and_failure():
    from app.baserow_init import test_baserow_connection
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        res = test_baserow_connection("http://localhost:7070")
        assert res["success"] is True

        mock_get.side_effect = Exception("Connection timed out")
        res_fail = test_baserow_connection("http://localhost:7070")
        assert res_fail["success"] is False
        assert "timed out" in res_fail["message"]


def test_test_token_permissions():
    from app.baserow_init import test_token_permissions
    assert test_token_permissions("http://localhost:7070", "")["valid"] is False

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        res = test_token_permissions("http://localhost:7070", "valid_token")
        assert res["valid"] is True
        assert res["warning"] is None

        mock_get.return_value.status_code = 401
        res_401 = test_token_permissions("http://localhost:7070", "bad_token")
        assert res_401["valid"] is False
        assert "401" in res_401["warning"]

        mock_get.return_value.status_code = 403
        res_403 = test_token_permissions("http://localhost:7070", "restricted_token")
        assert res_403["valid"] is False
        assert "403" in res_403["warning"]


def test_test_jwt_credentials():
    from app.baserow_init import test_jwt_credentials
    res_empty = test_jwt_credentials("http://localhost:7070", None, None)
    assert res_empty["provided"] is False
    assert res_empty["valid"] is False

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"token": "jwt_tok"}
        res = test_jwt_credentials("http://localhost:7070", "admin@era.com", "pass")
        assert res["provided"] is True
        assert res["valid"] is True
        assert res["token"] == "jwt_tok"

        mock_post.return_value.status_code = 400
        res_fail = test_jwt_credentials("http://localhost:7070", "admin@era.com", "wrong")
        assert res_fail["provided"] is True
        assert res_fail["valid"] is False


def test_discover_baserow_schema_complete():
    from app.baserow_init import discover_baserow_schema
    with patch("app.baserow_init.test_baserow_connection", return_value={"success": True, "message": "OK"}), \
         patch("app.baserow_init.test_token_permissions", return_value={"valid": True, "warning": None}), \
         patch("app.baserow_init.test_jwt_credentials", return_value={"provided": False, "valid": False, "token": None, "message": "N/A"}), \
         patch("requests.get") as mock_get:
        
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"id": 101, "name": "Part Number", "type": "text"},
            {"id": 102, "name": "Item description", "type": "text"}
        ]
        mock_get.return_value = mock_resp

        with patch.dict(os.environ, {
            "BASEROW_API_URL": "http://localhost:7070",
            "BASEROW_TOKEN": "valid_token",
            "BASEROW_TABLE_BOM": "508",
            "BASEROW_TABLE_ASSEMBLY": "701",
            "BASEROW_TABLE_INSTRUCTIONS": "5770",
            "BASEROW_TABLE_PN_CATEGORIES": "42471",
            "BASEROW_TABLE_ITEM_STATES": "48537",
            "BASEROW_TABLE_WI_TEMPLATES": "48538",
            "BASEROW_TABLE_MANUFACTURERS": "683",
            "BASEROW_TABLE_SUPPLIERS": "682",
            "BASEROW_TABLE_CONTACTS": "684",
        }, clear=False):
            res = discover_baserow_schema()
            assert res["is_complete"] is True
            assert res["is_connected"] is True
            assert res["token_valid"] is True
            assert "BOM" in res["tables"]
            assert res["tables"]["BOM"]["found"] is True


def test_get_auth_status_summary():
    from app.baserow_init import get_auth_status_summary
    with patch("app.baserow_init.test_baserow_connection", return_value={"success": True, "message": "OK"}), \
         patch("app.baserow_init.test_token_permissions", return_value={"valid": True, "warning": None}):
        with patch.dict(os.environ, {
            "BASEROW_API_URL": "http://localhost:7070",
            "BASEROW_TOKEN": "token123",
            "BASEROW_TABLE_BOM": "508",
            "BASEROW_TABLE_ASSEMBLY": "701",
            "BASEROW_TABLE_INSTRUCTIONS": "5770",
            "BASEROW_TABLE_PN_CATEGORIES": "42471",
            "BASEROW_TABLE_ITEM_STATES": "48537",
            "BASEROW_TABLE_WI_TEMPLATES": "48538",
            "BASEROW_TABLE_MANUFACTURERS": "683",
            "BASEROW_TABLE_SUPPLIERS": "682",
            "BASEROW_TABLE_CONTACTS": "684",
        }, clear=False):
            status = get_auth_status_summary()
            assert status["is_complete"] is True
            assert status["missing"] == []

        with patch.dict(os.environ, {"BASEROW_TOKEN": ""}, clear=False):
            status_missing_tok = get_auth_status_summary()
            assert status_missing_tok["is_complete"] is False
            assert "Baserow API Token" in status_missing_tok["missing"]


def test_save_auth_configuration():
    from app.baserow_init import save_auth_configuration
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("EXISTING_KEY=old\n")

        with patch("app.baserow_init.find_env_files", return_value=[env_file]), \
             patch("app.baserow_init.test_baserow_connection", return_value={"success": True, "message": "OK"}), \
             patch("app.baserow_init.test_token_permissions", return_value={"valid": True, "warning": None}), \
             patch("app.baserow_init.test_jwt_credentials", return_value={"provided": True, "valid": True, "token": "jwt123", "message": "OK"}):
            
            payload = {
                "host": "http://192.168.1.100",
                "port": "8080",
                "token": "saved_token_123",
                "admin_email": "admin@example.com",
                "admin_password": "mypassword",
                "database_id": "5"
            }
            res = save_auth_configuration(payload)
            assert res["success"] is True
            with open(env_file, "r", encoding="utf-8") as f:
                content = f.read()
                assert "BASEROW_API_URL=http://192.168.1.100:8080" in content
                assert "BASEROW_TOKEN=saved_token_123" in content
                assert "BASEROW_ADMIN_EMAIL=admin@example.com" in content
                assert "BASEROW_DATABASE_ID=5" in content

