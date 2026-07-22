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
            {"id": 3, "Part Number": "40-00049", "Item description": "100pF Capacitor", "Search helper": "40 49", "State": {"value": "Engineering Use"}, "Source URL": "https://digikey.com"}
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
    assert root1["state"] == "Production Use"
    
    assert len(root1["children"]) == 1
    child = root1["children"][0]
    assert child["id"] == 2
    assert child["problems_count"] == 0
    assert child["state"] == "Engineering Use"
    
    root2 = tree[1]
    assert root2["id"] == 3
    assert root2["problems_count"] == 1
    assert root2["state"] == "Engineering Use"

@patch('app.baserow_client.requests.get')
def test_get_item(mock_get):
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {"id": 1, "Item description": "Test item", "Part Number": "10-00001"}
    
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {"results": []}
    
    mock_resp3 = MagicMock()
    mock_resp3.json.return_value = {"results": [{"id": 1, "Item description": "Test item", "Part Number": "10-00001"}]}
    
    mock_get.side_effect = [mock_resp1, mock_resp2, mock_resp3]
    
    client = BaserowClient()
    client.scanner.status = "completed"
    client.scanner.problems = {1: ["Problem 1"]}
    
    item = client.get_item(1)
    assert item["id"] == 1
    assert item["problems"] == ["Problem 1"]
    assert "contained_items" in item
    assert "containing_items" in item
    assert mock_get.call_count == 3

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
    assert tag["color"] == "#ff0000"

    # Test get_pn_tag using linked PN Category data
    item_data = {"PN Category": [{"id": 101, "value": "Raw Material"}]}
    linked_tag = client.get_pn_tag("10-00001", item_data)
    assert linked_tag["name"] == "Raw Material"

    tag_unknown = client.get_pn_tag("00-00000")
    assert tag_unknown["name"] == "Unknown"
    assert tag_unknown["color"] == "#8e9095"

    custom_rules = {
        "10": { "name": "Custom Raw", "color": "#00ff00" }
    }
    with patch.object(client, '_request') as mock_req:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"id": 1, "Prefix": "10", "Name": "Custom Raw", "Color": "#00ff00"}]}
        mock_req.return_value = mock_resp

        success = client.save_rules(custom_rules)
        assert success is True
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

@patch('app.baserow_client.requests.get')
def test_get_items_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": 1, "Part Number": "10-00001"}], "next": None}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    res = client.get_items()
    assert len(res) == 1
    assert res[0]["Part Number"] == "10-00001"
    mock_get.assert_called_once()

@patch('app.baserow_client.requests.get')
def test_get_item_relations_safety(mock_get):
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {"id": 1, "Item description": "Test item", "Part Number": "10-00001"}
    
    # Return edges with invalid types, empty links, etc.
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "results": [
            # Edge with empty items list (which would crash parent_link[0])
            {"id": 101, "Item": [], "Contains": [{"id": 2}], "Amount of Times": "not-a-number"},
            # Edge with empty contains list
            {"id": 102, "Item": [{"id": 1}], "Contains": [], "Length (mm)": ""},
            # Edge with string Amount of Times and string Length
            {"id": 103, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": "5.5", "Length (mm)": "100.2"}
        ]
    }
    
    mock_resp3 = MagicMock()
    mock_resp3.json.return_value = {
        "results": [
            {"id": 1, "Part Number": "10-00001", "Item description": "Parent Part"},
            {"id": 2, "Part Number": "10-00002", "Item description": "Child Part"}
        ]
    }
    
    mock_get.side_effect = [mock_resp1, mock_resp2, mock_resp3]
    
    client = BaserowClient()
    item = client.get_item(1)
    
    assert item["id"] == 1
    # Only the last valid/successfully converted edge should be processed
    assert len(item["contained_items"]) == 1
    assert item["contained_items"][0]["edge_id"] == 103
    assert item["contained_items"][0]["amount_label"] == "5 x 100mm"

@patch('app.baserow_client.requests.patch')
@patch('app.baserow_client.requests.post')
@patch('app.baserow_client.requests.get')
def test_recategorize_item_client(mock_get, mock_post, mock_patch):
    # Mock responses for:
    # 1. GET src_item (42)
    mock_resp_src = MagicMock()
    mock_resp_src.json.return_value = {
        "id": 42,
        "Part Number": "10-00042",
        "Item description": "Nova Part",
        "State": {"value": "Finish Stock (Use Up)"},
        "Part of a set": [{"id": 99}]
    }

    # 2. GET all flat items (to find next number)
    mock_resp_items = MagicMock()
    mock_resp_items.json.return_value = {
        "results": [
            {"id": 42, "Part Number": "10-00042"},
            {"id": 50, "Part Number": "20-00002"}
        ],
        "next": None
    }

    # 3. GET all assembly rows
    mock_resp_assembly = MagicMock()
    mock_resp_assembly.json.return_value = {
        "results": [
            {
                "id": 301,
                "Item": [{"id": 42}],
                "Contains": [{"id": 55}]
            }
        ],
        "next": None
    }

    mock_get.side_effect = [mock_resp_src, mock_resp_items, mock_resp_assembly]

    # POST response for create new item
    mock_resp_create = MagicMock()
    mock_resp_create.json.return_value = {
        "id": 100,
        "Part Number": "20-00003"
    }
    mock_post.return_value = mock_resp_create

    # PATCH response
    mock_resp_patch = MagicMock()
    mock_patch.return_value = mock_resp_patch

    client = BaserowClient()
    new_item = client.recategorize_item(42, "20")

    # Assert new item properties returned
    assert new_item["id"] == 100
    assert new_item["Part Number"] == "20-00003"

    # Verify POST request payload to table_bom
    mock_post.assert_called_once()
    post_args, post_kwargs = mock_post.call_args
    post_payload = post_kwargs.get("json")
    assert post_payload["Part Number"] == "20-00003"
    assert post_payload["State"] == "Finish Stock (Use Up)"

    # Verify PATCH request to update assembly links
    # and PATCH request to mark old as EOL
    assert mock_patch.call_count == 2


@patch('app.baserow_client.requests.get')
def test_get_instruction_set_details_blackbox(mock_get):
    # Mock table_instructions, table_bom, table_assembly responses
    mock_instructions = MagicMock()
    mock_instructions.json.return_value = {
        "results": [
            {
                "id": 101,
                "Parent Item": [{"id": 10}],
                "Set Index": 1,
                "Step Order": 1,
                "Action": "Assemble",
                "Quantity": 2,
                "Child Item": [{"id": 20}]
            }
        ],
        "next": None
    }

    mock_bom = MagicMock()
    mock_bom.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "10-00010", "Item description": "Parent Unit", "Blackbox": False},
            {"id": 20, "Part Number": "20-00020", "Item description": "Child Sub-assembly", "Blackbox": True},
            {"id": 30, "Part Number": "30-00030", "Item description": "Sub-child component", "Blackbox": False}
        ],
        "next": None
    }

    mock_assembly = MagicMock()
    mock_assembly.json.return_value = {
        "results": [
            {"id": 1, "Item": [{"id": 10}], "Contains": [{"id": 20}], "Amount of Times": 2},
            {"id": 2, "Item": [{"id": 20}], "Contains": [{"id": 30}], "Amount of Times": 5}
        ],
        "next": None
    }

    mock_get.side_effect = [mock_instructions, mock_bom, mock_assembly]

    client = BaserowClient()
    details = client.get_instruction_set_details(10, 1)

    assert len(details["steps"]) == 1
    assert details["steps"][0]["id"] == 101

    # Item 20 is marked Blackbox, so hierarchy traversal stops at 20 and does NOT expand 30!
    comp_map = {c["item_id"]: c for c in details["comparison"]}
    assert 20 in comp_map
    assert comp_map[20]["required_qty"] == 2
    assert comp_map[20]["instructed_qty"] == 2
    assert comp_map[20]["discrepancy"] == "OK"
    assert 30 not in comp_map  # Traversal stopped at Blackbox item 20!


def test_get_next_revision_str():
    from app.baserow_client import get_next_revision_str
    assert get_next_revision_str("") == "A"
    assert get_next_revision_str("A") == "B"
    assert get_next_revision_str("B") == "C"
    assert get_next_revision_str("Y") == "Z"
    assert get_next_revision_str("Z") == "AA"
    assert get_next_revision_str("AA") == "AB"
    assert get_next_revision_str("AZ") == "BA"
    assert get_next_revision_str("ZZ") == "AAA"
    assert get_next_revision_str("123") == "A"


@patch('app.baserow_client.requests.post')
@patch('app.baserow_client.requests.get')
def test_add_revision_client(mock_get, mock_post):
    from app.baserow_client import BaserowClient

    # 1. GET src_item (10)
    mock_src_item = MagicMock()
    mock_src_item.json.return_value = {
        "id": 10,
        "Part Number": "40-00127",
        "Revision": "A",
        "Item description": "Nova Handle",
        "State": {"value": "Engineerig Use"},
        "Notes": "Some notes"
    }

    # 2. GET all flat items (to check existing revisions for PN 40-00127)
    mock_all_items = MagicMock()
    mock_all_items.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "40-00127", "Revision": "A"}
        ],
        "next": None
    }

    # 3. GET all assembly rows (item 10 has a child 50, and a parent 5)
    mock_assembly_rows = MagicMock()
    mock_assembly_rows.json.return_value = {
        "results": [
            # Child edge (parent is 10) -> Should be copied
            {"id": 101, "Item": [{"id": 10}], "Contains": [{"id": 50}], "Amount of Times": 2, "Length (mm)": 0, "PCB Symbol": "C1"},
            # Parent edge (child is 10) -> Should NOT be copied
            {"id": 102, "Item": [{"id": 5}], "Contains": [{"id": 10}], "Amount of Times": 1, "Length (mm)": 0, "PCB Symbol": "N/A"}
        ],
        "next": None
    }

    mock_get.side_effect = [mock_src_item, mock_all_items, mock_assembly_rows]

    # POST responses:
    # First POST creates new BOM item
    mock_post_create_item = MagicMock()
    mock_post_create_item.json.return_value = {"id": 11, "Part Number": "40-00127", "Revision": "B"}
    # Second POST creates assembly edge for child 50
    mock_post_create_assembly = MagicMock()
    mock_post_create_assembly.json.return_value = {"id": 201, "Item": [{"id": 11}], "Contains": [{"id": 50}]}

    mock_post.side_effect = [mock_post_create_item, mock_post_create_assembly]

    client = BaserowClient()
    new_item = client.add_revision(10)

    assert new_item["id"] == 11
    assert new_item["Revision"] == "B"

    # Verify 2 POST calls: 1 to create item with Rev B, 1 to create child edge
    assert mock_post.call_count == 2

    # Verify first POST call (item creation)
    first_call_kwargs = mock_post.call_args_list[0][1]
    item_payload = first_call_kwargs.get("json")
    assert item_payload["Part Number"] == "40-00127"
    assert item_payload["Revision"] == "B"
    assert item_payload["Item description"] == "Nova Handle"

    # Verify second POST call (assembly child creation)
    second_call_kwargs = mock_post.call_args_list[1][1]
    assembly_payload = second_call_kwargs.get("json")
    assert assembly_payload["Item"] == [11]
    assert assembly_payload["Contains"] == [50]
    assert assembly_payload["Amount of Times"] == 2
    assert assembly_payload["PCB Symbol"] == "C1"


import requests

@patch('app.baserow_client.requests.get')
@patch('time.sleep')
def test_request_retry_on_502(mock_sleep, mock_get):
    mock_502 = MagicMock()
    mock_502.status_code = 502

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"success": True}

    mock_get.side_effect = [mock_502, mock_200]

    client = BaserowClient()
    res = client._request("GET", "http://localhost:7070/test", backoff_factor=0.01)

    assert res.status_code == 200
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1

@patch('app.baserow_client.requests.get')
@patch('time.sleep')
def test_request_retry_on_connection_error(mock_sleep, mock_get):
    mock_200 = MagicMock()
    mock_200.status_code = 200

    mock_get.side_effect = [requests.exceptions.ConnectionError("Connection refused"), mock_200]

    client = BaserowClient()
    res = client._request("GET", "http://localhost:7070/test", backoff_factor=0.01)

    assert res.status_code == 200
    assert mock_get.call_count == 2
    assert mock_sleep.call_count == 1

@patch('app.baserow_client.requests.get')
@patch('app.baserow_client.requests.patch')
def test_get_item_autofills_blank_category(mock_patch, mock_get):
    mock_src_resp = MagicMock()
    mock_src_resp.json.return_value = {
        "id": 42,
        "Part Number": "10-00042",
        "Item description": "Test Part",
        "PN Category": []
    }

    mock_assembly_resp = MagicMock()
    mock_assembly_resp.json.return_value = {"results": [], "next": None}

    mock_bom_resp = MagicMock()
    mock_bom_resp.json.return_value = {"results": [], "next": None}

    mock_get.side_effect = [mock_src_resp, mock_assembly_resp, mock_bom_resp]

    mock_patch_resp = MagicMock()
    mock_patch_resp.status_code = 200
    mock_patch.return_value = mock_patch_resp

    client = BaserowClient()
    client.rules = {
        "10": {"id": 101, "name": "Raw Material"}
    }

    item = client.get_item(42)

    mock_patch.assert_called_once()
    patch_args, patch_kwargs = mock_patch.call_args
    patch_payload = patch_kwargs.get("json")
    assert patch_payload["PN Category"] == [101]
    assert item["PN Category"] == [{"id": 101, "value": "10"}]
