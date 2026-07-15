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
        "Image": []
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
            "Image": []
        }]
        mock_instance.get_items.assert_called_once()
