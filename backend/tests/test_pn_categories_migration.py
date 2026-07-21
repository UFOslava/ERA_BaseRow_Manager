import pytest
from unittest.mock import patch, MagicMock
from app.migrate_pn_categories import get_jwt_token, run_migration

@patch('app.migrate_pn_categories.requests.post')
def test_get_jwt_token_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"token": "fake_jwt_token"}
    mock_post.return_value = mock_resp

    token = get_jwt_token("http://localhost:7070", "admin@test.com", "pass")
    assert token == "fake_jwt_token"
    mock_post.assert_called_once_with("http://localhost:7070/api/user/token-auth/", json={"username": "admin@test.com", "password": "pass"})

@patch('app.migrate_pn_categories.requests.get')
@patch('app.migrate_pn_categories.requests.post')
@patch('app.migrate_pn_categories.requests.patch')
@patch('app.migrate_pn_categories.get_jwt_token')
def test_run_migration_success(mock_get_jwt, mock_patch, mock_post, mock_get):
    mock_get_jwt.return_value = "fake_jwt_token"

    # GET mock responses:
    # 1. /api/applications/
    mock_apps = MagicMock()
    mock_apps.status_code = 200
    mock_apps.json.return_value = [{"id": 129, "type": "database"}]

    # 2. /api/database/tables/database/129/ (BOM check)
    mock_tables_check = MagicMock()
    mock_tables_check.status_code = 200
    mock_tables_check.json.return_value = [{"id": 508, "name": "BOM"}]

    # 3. /api/database/tables/database/129/ (PN Categories check)
    mock_pn_tables_check = MagicMock()
    mock_pn_tables_check.status_code = 200
    mock_pn_tables_check.json.return_value = [{"id": 508, "name": "BOM"}, {"id": 42471, "name": "PN Categories"}]

    # 4. /api/database/fields/table/42471/
    mock_fields_cat = MagicMock()
    mock_fields_cat.status_code = 200
    mock_fields_cat.json.return_value = [
        {"id": 1, "name": "Prefix", "primary": True},
        {"id": 2, "name": "Name", "primary": False},
        {"id": 3, "name": "Color", "primary": False}
    ]

    # 5. /api/database/rows/table/42471/ (check existing)
    mock_rows_cat = MagicMock()
    mock_rows_cat.status_code = 200
    mock_rows_cat.json.return_value = {"results": [{"id": 10, "Prefix": "10", "Name": "Raw Material", "Color": "#ff0000"}]}

    # 6. /api/database/fields/table/508/ (check link field)
    mock_fields_bom = MagicMock()
    mock_fields_bom.status_code = 200
    mock_fields_bom.json.return_value = [{"id": 99, "name": "PN Category"}]

    # 7. /api/database/rows/table/508/ (fetch items to backfill)
    mock_rows_bom = MagicMock()
    mock_rows_bom.status_code = 200
    mock_rows_bom.json.return_value = {
        "results": [{"id": 1, "Part Number": "10-00001", "PN Category": []}],
        "next": None
    }

    mock_get.side_effect = [
        mock_apps, mock_tables_check, mock_pn_tables_check,
        mock_fields_cat, mock_rows_cat, mock_rows_cat,
        mock_fields_bom, mock_rows_bom
    ]

    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200
    mock_patch.return_value = mock_patch_resp

    with patch.dict('os.environ', {'BASEROW_ADMIN_EMAIL': 'admin@test.com', 'BASEROW_ADMIN_PASSWORD': 'pass'}):
        res = run_migration()
        assert res["pn_cat_table_id"] == 42471
        assert res["backfilled_count"] == 1
