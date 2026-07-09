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
