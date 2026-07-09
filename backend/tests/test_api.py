import json
from unittest.mock import patch

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}

@patch('app.baserow_client.BaserowClient.get_bom_tree')
def test_get_bom_tree_success(mock_get_tree, client):
    mock_tree = [
        {
            "id": 1,
            "part_number": "30-00000",
            "description": "Nova Complete Handle Assembly",
            "quantity_label": "Root",
            "children": [
                {
                    "id": 2,
                    "part_number": "30-00001",
                    "description": "Nova Handle Bottom Plastic Enclosure",
                    "quantity_label": "1 pcs",
                    "children": []
                }
            ]
        }
    ]
    mock_get_tree.return_value = mock_tree

    response = client.get('/api/bom/tree')
    assert response.status_code == 200
    assert response.json == mock_tree
    mock_get_tree.assert_called_once()

@patch('app.baserow_client.BaserowClient.get_bom_tree')
def test_get_bom_tree_error(mock_get_tree, client):
    mock_get_tree.side_effect = Exception("Connection Refused")

    response = client.get('/api/bom/tree')
    assert response.status_code == 500
    assert "Connection Refused" in response.json["error"]
