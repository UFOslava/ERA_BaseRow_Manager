import pytest
from unittest.mock import patch, MagicMock
from app.baserow_client import BaserowClient

@patch('app.baserow_client.requests.get')
def test_baserow_client_get_bom_tree(mock_get):
    mock_bom_resp = MagicMock()
    mock_bom_resp.json.return_value = {
        "results": [
            {"id": 1, "Part Number": "30-00000", "Item description": "Nova Complete Handle Assembly", "Search helper": "30 0"},
            {"id": 2, "Part Number": "30-00001", "Item description": "Nova Handle Bottom Plastic Enclosure", "Search helper": "30 1"},
            {"id": 3, "Part Number": "40-00049", "Item description": "100pF Capacitor", "Search helper": "40 49"}
        ],
        "next": None
    }
    
    mock_assembly_resp = MagicMock()
    mock_assembly_resp.json.return_value = {
        "results": [
            {
                "id": 10,
                "Item": [{"id": 1, "value": "30-00000 Rev.A"}],
                "Contains": [{"id": 2, "value": "30-00001 Rev.A"}],
                "Amount of Times": 1,
                "Length (mm)": None,
                "PCB Symbol": "N/A"
            },
            {
                "id": 11,
                "Item": [{"id": 2, "value": "30-00001 Rev.A"}],
                "Contains": [{"id": 3, "value": "40-00049 Rev.A"}],
                "Amount of Times": None,
                "Length (mm)": 150,
                "PCB Symbol": "C1"
            }
        ],
        "next": None
    }

    mock_get.side_effect = [mock_bom_resp, mock_assembly_resp]

    client = BaserowClient()
    tree = client.get_bom_tree()

    assert len(tree) == 1
    root = tree[0]
    assert root["id"] == 1
    assert root["part_number"] == "30-00000"
    assert root["quantity_label"] == "Root"
    
    assert len(root["children"]) == 1
    child = root["children"][0]
    assert child["id"] == 2
    assert child["part_number"] == "30-00001"
    assert child["quantity_label"] == "1 pcs"
    
    assert len(child["children"]) == 1
    grandchild = child["children"][0]
    assert grandchild["id"] == 3
    assert grandchild["part_number"] == "40-00049"
    assert grandchild["quantity_label"] == "150 mm"
    assert grandchild["pcb_symbol"] == "C1"

@patch('app.baserow_client.requests.get')
def test_baserow_client_circular_reference(mock_get):
    mock_bom_resp = MagicMock()
    mock_bom_resp.json.return_value = {
        "results": [
            {"id": 1, "Part Number": "A", "Item description": "Part A"},
            {"id": 2, "Part Number": "B", "Item description": "Part B"}
        ],
        "next": None
    }
    
    mock_assembly_resp = MagicMock()
    mock_assembly_resp.json.return_value = {
        "results": [
            {
                "id": 10,
                "Item": [{"id": 1}],
                "Contains": [{"id": 2}],
                "Amount of Times": 1,
                "Length (mm)": None
            },
            {
                "id": 11,
                "Item": [{"id": 2}],
                "Contains": [{"id": 1}],
                "Amount of Times": 1,
                "Length (mm)": None
            }
        ],
        "next": None
    }

    mock_get.side_effect = [mock_bom_resp, mock_assembly_resp]

    client = BaserowClient()
    tree = client.get_bom_tree()

    assert len(tree) == 0
