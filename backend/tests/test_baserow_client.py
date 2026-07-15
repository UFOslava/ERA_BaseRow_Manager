import pytest
from unittest.mock import patch, MagicMock
from app.baserow_client import BaserowClient

@patch('app.baserow_client.requests.get')
def test_baserow_client_get_bom_tree(mock_get):
    mock_bom_resp = MagicMock()
    mock_bom_resp.json.return_value = {
        "results": [
            {"id": 1, "Part Number": "30-00000", "Item description": "Nova Complete Handle Assembly", "Search helper": "30 0", "State": {"value": "Production Use"}},
            {"id": 2, "Part Number": "30-00001", "Item description": "Nova Handle Bottom Plastic Enclosure", "Search helper": "30 1", "State": {"value": "Engineering Use"}},
            {"id": 3, "Part Number": "40-00049", "Item description": "100pF Capacitor", "Search helper": "40 49", "State": {"value": "Engineering Use"}, "Source": "https://digikey.com"}
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
            }
        ],
        "next": None
    }

    mock_get.side_effect = [mock_bom_resp, mock_assembly_resp]

    client = BaserowClient()
    
    client.scanner.status = "completed"
    client.scanner.problems = {
        1: ["Production item not belonging in any assembly"],
        2: [],
        3: ["Source link is not an Octopart link"]
    }
    
    tree = client.get_bom_tree()

    assert len(tree) == 2
    root1 = tree[0]
    assert root1["id"] == 1
    assert root1["problems_count"] == 1
    
    assert len(root1["children"]) == 1
    child = root1["children"][0]
    assert child["id"] == 2
    assert child["problems_count"] == 0
    
    root2 = tree[1]
    assert root2["id"] == 3
    assert root2["problems_count"] == 1

@patch('app.baserow_client.requests.get')
def test_get_item(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 1, "Item description": "Test item"}
    mock_get.return_value = mock_resp
    
    client = BaserowClient()
    client.scanner.status = "completed"
    client.scanner.problems = {1: ["Problem 1"]}
    
    item = client.get_item(1)
    assert item["id"] == 1
    assert item["problems"] == ["Problem 1"]
    mock_get.assert_called_once()

@patch('app.baserow_client.requests.patch')
def test_update_item(mock_patch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 1, "Item description": "Updated description"}
    mock_patch.return_value = mock_resp
    
    client = BaserowClient()
    client.scanner.status = "completed"
    
    item = client.update_item(1, {"Item description": "Updated description"})
    assert item["Item description"] == "Updated description"
    assert client.scanner.status == "pending"
    mock_patch.assert_called_once()

def test_baserow_client_rules():
    client = BaserowClient()
    tag = client.get_pn_tag("10-00001")
    assert tag["name"] == "Raw Material"
    assert tag["color"] == "#10b981"

    tag_unknown = client.get_pn_tag("00-00000")
    assert tag_unknown["name"] == "Unknown"
    assert tag_unknown["color"] == "#8e9095"

    custom_rules = {
        "10": { "name": "Custom Raw", "color": "#00ff00" }
    }
    with patch('builtins.open', MagicMock()):
        success = client.save_rules(custom_rules)
        assert success is True
        assert client.rules == custom_rules
        assert client.get_pn_tag("10-00001")["name"] == "Custom Raw"

@patch('app.baserow_client.requests.get')
def test_get_manufacturers_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": 1, "Name": "Nostrali"}], "next": None}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    res = client.get_manufacturers()
    assert len(res) == 1
    assert res[0]["Name"] == "Nostrali"
    mock_get.assert_called_once()

@patch('app.baserow_client.requests.post')
def test_upload_file_client(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"name": "test.pdf"}
    mock_post.return_value = mock_resp

    client = BaserowClient()
    res = client.upload_file("test.pdf", b"abc", "application/pdf")
    assert res["name"] == "test.pdf"
    mock_post.assert_called_once()
