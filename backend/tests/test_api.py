import json
from unittest.mock import patch, MagicMock
from app.main import create_app

def test_health():
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/health')
        assert response.status_code == 200
        assert response.json == {"status": "healthy"}

@patch('app.main.BaserowClient')
def test_get_bom_tree_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_tree = [{"id": 1, "part_number": "30-00000", "description": "Nova Complete Handle Assembly", "problems_count": 0, "children": []}]
    mock_instance.get_bom_tree.return_value = mock_tree

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/tree')
        assert response.status_code == 200
        assert response.json == mock_tree
        mock_instance.get_bom_tree.assert_called_once()

@patch('app.main.BaserowClient')
def test_get_item_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_item = {"id": 1, "Part Number": "30-00000", "Item description": "Nova Complete Handle Assembly", "problems": []}
    mock_instance.get_item.return_value = mock_item

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/items/1')
        assert response.status_code == 200
        assert response.json == mock_item
        mock_instance.get_item.assert_called_once_with(1)

@patch('app.main.BaserowClient')
def test_update_item_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_item = {"id": 1, "Item description": "Updated"}
    mock_instance.update_item.return_value = mock_item

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.patch('/api/bom/items/1', json={"Item description": "Updated"})
        assert response.status_code == 200
        assert response.json == mock_item
        mock_instance.update_item.assert_called_once_with(1, {"Item description": "Updated"})

@patch('app.main.BaserowClient')
def test_get_scan_status(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.scanner.status = "completed"

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/scan-status')
        assert response.status_code == 200
        assert response.json == {"status": "completed"}

@patch('app.main.BaserowClient')
def test_get_rules_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_rules = {"10": {"name": "Raw", "color": "#123456"}}
    mock_instance.rules = mock_rules

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/rules')
        assert response.status_code == 200
        assert response.json == mock_rules

@patch('app.main.BaserowClient')
def test_get_states_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_states = {"Production Use": {"id": 1, "name": "Production Use", "color": "#00FF00"}}
    mock_instance.states_map = mock_states

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/states')
        assert response.status_code == 200
        assert response.json == mock_states
        mock_instance.load_states.assert_called_once()

@patch('app.main.BaserowClient')
def test_update_rules_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_rules = {"10": {"name": "Updated", "color": "#123456"}}
    mock_instance.save_rules.return_value = True
    mock_instance.rules = mock_rules

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/rules', json=mock_rules)
        assert response.status_code == 200
        assert response.json == {"status": "success", "rules": mock_rules}
        mock_instance.save_rules.assert_called_once_with(mock_rules)

@patch('app.main.BaserowClient')
def test_get_problem_definitions_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_defs = [{"id": "rule_1", "name": "Rule 1", "rule": {}}]
    mock_instance.scanner.load_definitions.return_value = mock_defs

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/problem-definitions')
        assert response.status_code == 200
        assert response.json == mock_defs

@patch('app.main.BaserowClient')
def test_update_problem_definitions_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_defs = [{"id": "rule_1", "name": "Rule 1", "rule": {}}]
    mock_instance.scanner.save_definitions.return_value = True
    mock_instance.scanner.load_definitions.return_value = mock_defs

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/problem-definitions', json=mock_defs)
        assert response.status_code == 200
        assert response.json == {"status": "success", "definitions": mock_defs}
        mock_instance.scanner.save_definitions.assert_called_once_with(mock_defs)
        mock_instance.scanner.reset.assert_called_once()
        mock_instance.scanner.start_scan.assert_called_once_with(mock_instance)

@patch('app.main.BaserowClient')
def test_get_definition_count_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.scanner.get_problem_count.return_value = (5, "completed")

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/problem-definitions/rule_1/count')
        assert response.status_code == 200
        assert response.json == {"id": "rule_1", "count": 5, "status": "completed"}
        mock_instance.scanner.get_problem_count.assert_called_once_with("rule_1")

@patch('app.main.BaserowClient')
def test_get_definition_count_not_found(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.scanner.get_problem_count.return_value = (None, "not_found")

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/problem-definitions/rule_nonexistent/count')
        assert response.status_code == 404
        assert response.json == {"id": "rule_nonexistent", "count": None, "status": "unsaved"}
        mock_instance.scanner.get_problem_count.assert_called_once_with("rule_nonexistent")

@patch('app.main.BaserowClient')
def test_trigger_rescan_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/scan/rescan')
        assert response.status_code == 200
        assert response.json == {"status": "running"}
        mock_instance.scanner.reset.assert_called_once()
        mock_instance.scanner.start_scan.assert_called_once_with(mock_instance)

@patch('app.main.BaserowClient')
def test_get_manufacturers_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_manufacturers.return_value = [{"id": 1, "Name": "Nostrali"}]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/manufacturers')
        assert response.status_code == 200
        assert response.json == [{"id": 1, "name": "Nostrali"}]
        mock_instance.get_manufacturers.assert_called_once()

@patch('app.main.BaserowClient')
def test_upload_file_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.upload_file.return_value = {"name": "test.pdf", "url": "http://localhost/test.pdf"}

    app = create_app()
    with app.test_client() as test_client:
        import io
        data = {'file': (io.BytesIO(b"abcdef"), 'test.pdf')}
        response = test_client.post('/api/bom/upload-file', data=data, content_type='multipart/form-data')
        assert response.status_code == 200
        assert response.json == {"name": "test.pdf", "url": "http://localhost/test.pdf"}
        mock_instance.upload_file.assert_called_once()

@patch('app.main.BaserowClient')
def test_get_items_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_items.return_value = [{
        "id": 1,
        "Part Number": "10-00001",
        "Revision": "A",
        "Item description": "Sample Component",
        "Image": [],
        "External PN": "EXT-100",
        "Notes": "Notes value",
        "Search helper": "Search helper value",
        "Manufacturer": [{"id": 1, "value": "Nostrali"}],
        "State": {"id": 1, "value": "Production Use"},
        "Full PN": "10-00001 Rev.A"
    }]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/items')
        assert response.status_code == 200
        assert response.json == [{
            "id": 1,
            "Part Number": "10-00001",
            "Revision": "A",
            "Item description": "Sample Component",
            "Image": [],
            "External PN": "EXT-100",
            "Notes": "Notes value",
            "Search helper": "Search helper value",
            "Manufacturer": [{"id": 1, "value": "Nostrali"}],
            "State": {"id": 1, "value": "Production Use"},
            "Full PN": "10-00001 Rev.A"
        }]
        mock_instance.get_items.assert_called_once()

@patch('app.main.BaserowClient')
def test_get_items_search_query(mock_baserow_client):
    """When ?search=<>=3chars, route delegates to search_items()."""
    mock_instance = mock_baserow_client.return_value
    mock_instance.search_items.return_value = [{
        "id": 2,
        "Part Number": "40-00001",
        "Revision": "A",
        "Item description": "Capacitor",
        "Image": [],
        "External PN": None,
        "Notes": None,
        "Search helper": None,
        "Manufacturer": [],
        "State": None,
        "Full PN": None
    }]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/items?search=cap&limit=50')
        assert response.status_code == 200
        result = response.json
        assert len(result) == 1
        assert result[0]["id"] == 2
        mock_instance.search_items.assert_called_once_with('cap', 50)
        mock_instance.get_items.assert_not_called()

@patch('app.main.BaserowClient')
def test_get_items_short_search_falls_back_to_get_items(mock_baserow_client):
    """When ?search= has fewer than 3 chars, route falls back to get_items()."""
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_items.return_value = []

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/items?search=ab')
        assert response.status_code == 200
        mock_instance.get_items.assert_called_once()
        mock_instance.search_items.assert_not_called()

@patch('app.main.BaserowClient')
def test_create_assembly_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.create_assembly.return_value = {"id": 10, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 3, "Length (mm)": 150}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/assembly', json={"parent_id": 1, "child_id": 2, "quantity": 3, "length": 150, "pcb_symbol": "C1"})
        assert response.status_code == 200
        assert response.json == {"id": 10, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 3, "Length (mm)": 150}
        mock_instance.create_assembly.assert_called_once_with(1, 2, 3, 150, "C1")

@patch('app.main.BaserowClient')
def test_update_assembly_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.update_assembly.return_value = {"id": 10, "Amount of Times": 5, "Length (mm)": 200}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.patch('/api/bom/assembly/10', json={"quantity": 5, "length": 200, "pcb_symbol": "C2", "parent_id": 1, "child_id": 2})
        assert response.status_code == 200
        assert response.json == {"id": 10, "Amount of Times": 5, "Length (mm)": 200}
        mock_instance.update_assembly.assert_called_once_with(10, 5, 200, "C2", 1, 2)

@patch('app.main.BaserowClient')
def test_delete_assembly_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.delete('/api/bom/assembly/10')
        assert response.status_code == 200
        assert response.json == {"status": "success"}
        mock_instance.delete_assembly.assert_called_once_with(10)

@patch('app.main.BaserowClient')
def test_create_item_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.create_item.return_value = {"id": 99, "Part Number": "10-00005", "Item description": "New Component"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/items', json={"prefix": "10", "description": "New Component"})
        assert response.status_code == 200
        assert response.json == {"id": 99, "Part Number": "10-00005", "Item description": "New Component"}
        mock_instance.create_item.assert_called_once_with("10", "New Component")

@patch('app.main.BaserowClient')
def test_recategorize_item_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.recategorize_item.return_value = {"id": 200, "Part Number": "20-00003"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/items/42/recategorize', json={"new_prefix": "20"})
        assert response.status_code == 200
        assert response.json == {"id": 200, "Part Number": "20-00003"}
        mock_instance.recategorize_item.assert_called_once_with(42, "20")

@patch('app.main.BaserowClient')
def test_recategorize_item_missing_prefix(mock_baserow_client):
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/items/42/recategorize', json={})
        assert response.status_code == 400
        assert "Missing new_prefix" in response.json["error"]

@patch('app.main.BaserowClient')
def test_recategorize_item_error(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.recategorize_item.side_effect = Exception("Baserow error")

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/items/42/recategorize', json={"new_prefix": "30"})
        assert response.status_code == 500
        assert "error" in response.json

@patch('app.main.BaserowClient')
def test_add_item_revision_success(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.add_revision.return_value = {"id": 11, "Part Number": "40-00127", "Revision": "B"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/bom/items/10/revision')
        assert response.status_code == 200
        assert response.json == {"id": 11, "Part Number": "40-00127", "Revision": "B"}
        mock_instance.add_revision.assert_called_once_with(10)

@patch('app.main.BaserowClient')
def test_get_top_level_items_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_data = {
        "total": 1,
        "items": [{"id": 1, "part_number": "10-00000", "state": "Production Use"}]
    }
    mock_instance.get_top_level_items.return_value = mock_data

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/top-level?state=Production%20Use&offset=0&limit=50')
        assert response.status_code == 200
        assert response.json == mock_data
        mock_instance.get_top_level_items.assert_called_once_with(
            state="Production Use",
            offset=0,
            limit=50
        )

@patch('app.main.BaserowClient')
def test_export_item_excel_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_item.return_value = {
        "id": 1,
        "Part Number": "10-00000",
        "Revision": "A",
        "contained_items": [
            {
                "id": 2,
                "part_number": "20-00000",
                "description": "Child Component",
                "revision": "B",
                "quantity": 2,
                "length": None,
                "pcb_symbol": "R1, R2",
                "price": 1.25,
                "Image": []
            }
        ]
    }

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/items/1/export')
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        # Validate header download name format
        assert "attachment" in response.headers["Content-Disposition"]
        assert "filename=BOM_Export_10-00000_Rev_A.xlsx" in response.headers["Content-Disposition"]

@patch('app.main.BaserowClient')
def test_duplicate_item_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_new_item = {"id": 100, "Part Number": "10-00001", "Item description": "Nova Handle - copy"}
    mock_instance.duplicate_item.return_value = mock_new_item

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post(
            '/api/bom/items/1/duplicate',
            json={"prefix": "10", "description": "Nova Handle - copy"}
        )
        assert response.status_code == 200
        assert response.json == mock_new_item
        mock_instance.duplicate_item.assert_called_once_with(
            1, "10", "Nova Handle - copy",
            duplicate_parents=True,
            duplicate_children=True,
            duplicate_instructions=True,
            duplicate_photos=True
        )


@patch('app.main.BaserowClient')
def test_get_manufacturers_detailed(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_manufacturers.return_value = [{"id": 1, "Name": "Nostrali", "Notes": "Mfg notes"}]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/manufacturers?detailed=true')
        assert response.status_code == 200
        assert response.json == [{"id": 1, "Name": "Nostrali", "Notes": "Mfg notes"}]


@patch('app.main.BaserowClient')
def test_get_manufacturer_by_id(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_manufacturer.return_value = {"id": 1, "Name": "Nostrali", "Website": "https://nostrali.com"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/manufacturers/1')
        assert response.status_code == 200
        assert response.json["Name"] == "Nostrali"


@patch('app.main.BaserowClient')
def test_create_manufacturer_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.create_manufacturer.return_value = {"id": 2, "Name": "Schurter"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/manufacturers', json={"Name": "Schurter"})
        assert response.status_code == 201
        assert response.json["id"] == 2


@patch('app.main.BaserowClient')
def test_update_manufacturer_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.update_manufacturer.return_value = {"id": 2, "Name": "Schurter Updated"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.patch('/api/manufacturers/2', json={"Name": "Schurter Updated"})
        assert response.status_code == 200
        assert response.json["Name"] == "Schurter Updated"


@patch('app.main.BaserowClient')
def test_delete_manufacturer_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.delete_manufacturer.return_value = True

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.delete('/api/manufacturers/2')
        assert response.status_code == 200
        assert response.json == {"status": "deleted"}


@patch('app.main.BaserowClient')
def test_get_suppliers_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_suppliers.return_value = [{"id": 1, "Company Name": "Mouser"}]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/suppliers')
        assert response.status_code == 200
        assert response.json == [{"id": 1, "Company Name": "Mouser"}]


@patch('app.main.BaserowClient')
def test_get_supplier_by_id_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_supplier.return_value = {"id": 1, "Company Name": "Mouser", "Online Store": True}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/suppliers/1')
        assert response.status_code == 200
        assert response.json["Company Name"] == "Mouser"


@patch('app.main.BaserowClient')
def test_create_supplier_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.create_supplier.return_value = {"id": 3, "Company Name": "Farnell"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/suppliers', json={"Company Name": "Farnell"})
        assert response.status_code == 201
        assert response.json["id"] == 3


@patch('app.main.BaserowClient')
def test_update_supplier_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.update_supplier.return_value = {"id": 3, "Company Name": "Farnell UK"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.patch('/api/suppliers/3', json={"Company Name": "Farnell UK"})
        assert response.status_code == 200
        assert response.json["Company Name"] == "Farnell UK"


@patch('app.main.BaserowClient')
def test_delete_supplier_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.delete_supplier.return_value = True

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.delete('/api/suppliers/3')
        assert response.status_code == 200
        assert response.json == {"status": "deleted"}


@patch('app.main.BaserowClient')
def test_get_contacts_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_contacts.return_value = [{"id": 1, "Name": "John Doe"}]

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/contacts')
        assert response.status_code == 200
        assert response.json == [{"id": 1, "Name": "John Doe"}]


@patch('app.main.BaserowClient')
def test_get_contact_by_id_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.get_contact.return_value = {"id": 1, "Name": "John Doe", "Email": "john@test.com"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/contacts/1')
        assert response.status_code == 200
        assert response.json["Email"] == "john@test.com"


@patch('app.main.BaserowClient')
def test_create_contact_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.create_contact.return_value = {"id": 5, "Name": "Jane"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/contacts', json={"Name": "Jane", "Email": "jane@test.com"})
        assert response.status_code == 201
        assert response.json["id"] == 5


@patch('app.main.BaserowClient')
def test_update_contact_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.update_contact.return_value = {"id": 5, "Name": "Jane Updated"}

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.patch('/api/contacts/5', json={"Name": "Jane Updated"})
        assert response.status_code == 200
        assert response.json["Name"] == "Jane Updated"


@patch('app.main.BaserowClient')
def test_delete_contact_api(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.delete_contact.return_value = True

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.delete('/api/contacts/5')
        assert response.status_code == 200
        assert response.json == {"status": "deleted"}


@patch('app.main.get_auth_status_summary')
def test_get_auth_status_endpoint(mock_get_status):
    mock_get_status.return_value = {"is_complete": True, "token_valid": True, "missing": []}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/auth/status')
        assert response.status_code == 200
        assert response.json["is_complete"] is True


@patch('app.main.discover_baserow_schema')
def test_get_auth_config_endpoint(mock_discover):
    mock_discover.return_value = {"is_complete": True, "tables": {}}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/auth/config')
        assert response.status_code == 200
        assert response.json["is_complete"] is True


@patch('app.main.discover_baserow_schema')
def test_test_auth_endpoint(mock_discover):
    mock_discover.return_value = {"is_complete": True, "is_connected": True}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/auth/test', json={"host": "http://localhost", "port": "7070", "token": "test"})
        assert response.status_code == 200
        assert response.json["is_connected"] is True


@patch('app.main.save_auth_configuration')
def test_save_auth_endpoint(mock_save):
    mock_save.return_value = {"success": True, "schema": {}, "status": {"is_complete": True}}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/auth/save', json={"host": "http://localhost", "port": "7070", "token": "test"})
        assert response.status_code == 200
        assert response.json["success"] is True


@patch('app.main.BaserowClient')
def test_bom_tree_guarded_when_incomplete(mock_baserow_client):
    mock_instance = mock_baserow_client.return_value
    mock_instance.token = ""
    mock_instance.table_bom = "508"

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/tree')
        assert response.status_code == 503
        assert response.json.get("auth_incomplete") is True


@patch('app.backup_manager.list_backups')
def test_get_backups_endpoint(mock_list):
    mock_list.return_value = [{"backup_id": "b1", "metrics": {"bom_items_count": 5}}]
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/backup/list')
        assert response.status_code == 200
        assert len(response.json) == 1
        assert response.json[0]["backup_id"] == "b1"


@patch('app.backup_manager.create_backup')
def test_create_backup_endpoint(mock_create):
    mock_create.return_value = {"backup_id": "b_new", "metrics": {}}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/backup/create', json={"type": "manual", "note": "test"})
        assert response.status_code == 200
        assert response.json["backup_id"] == "b_new"


@patch('app.backup_manager.restore_backup')
def test_restore_backup_endpoint(mock_restore):
    mock_restore.return_value = {"success": True, "restored_backup_id": "b_target"}
    app = create_app()
    with app.test_client() as test_client:
        response = test_client.post('/api/backup/restore', json={"backup_id": "b_target"})
        assert response.status_code == 200
        assert response.json["success"] is True


@patch('app.backup_manager.load_backup_config')
@patch('app.backup_manager.save_backup_config')
def test_backup_config_endpoints(mock_save, mock_load):
    mock_load.return_value = {"auto_backup_enabled": True}
    mock_save.return_value = {"auto_backup_enabled": False}
    app = create_app()
    with app.test_client() as test_client:
        res_get = test_client.get('/api/backup/config')
        assert res_get.status_code == 200
        assert res_get.json["auto_backup_enabled"] is True

        res_post = test_client.post('/api/backup/config', json={"auto_backup_enabled": False})
        assert res_post.status_code == 200
        assert res_post.json["auto_backup_enabled"] is False







