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
                "Measurement": None,
                "PCB Symbol": "N/A"
            }
        ],
        "next": None
    }

    # Both fetches happen concurrently - mock returns same response for any GET
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
    # get_item now:
    # 1. Concurrently fetches the item row + 2 filtered assembly requests (as_parent, as_child)
    # 2. Then fetches each unique neighbour BOM row individually
    mock_item_resp = MagicMock()
    mock_item_resp.status_code = 200
    mock_item_resp.json.return_value = {"id": 1, "Item description": "Test item", "Part Number": "10-00001"}

    # Filtered assembly: as parent (no edges), as child (no edges)
    mock_edges_empty = MagicMock()
    mock_edges_empty.status_code = 200
    mock_edges_empty.json.return_value = {"results": [], "next": None}

    # Return item for GET /items/1, then two empty edge pages
    mock_get.side_effect = [mock_item_resp, mock_edges_empty, mock_edges_empty]

    client = BaserowClient()
    client.scanner.status = "completed"
    client.scanner.problems = {1: ["Problem 1"]}

    item = client.get_item(1)
    assert item["id"] == 1
    assert item["problems"] == ["Problem 1"]
    assert "contained_items" in item
    assert "containing_items" in item

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


def test_normalize_uploaded_file_webp_to_png():
    import io
    from PIL import Image
    from app.baserow_client import normalize_uploaded_file

    # Create dummy WebP image
    im = Image.new("RGB", (64, 64), color="red")
    webp_io = io.BytesIO()
    im.save(webp_io, format="WEBP")
    webp_bytes = webp_io.getvalue()

    filename, content, content_type = normalize_uploaded_file("manufacturer_logo.webp", webp_bytes, "image/webp")
    assert filename == "manufacturer_logo.png"
    assert content_type == "image/png"

    # Verify converted content is a valid PNG
    res_im = Image.open(io.BytesIO(content))
    assert res_im.format == "PNG"
    assert res_im.size == (64, 64)


def test_normalize_uploaded_file_preserves_pdf():
    from app.baserow_client import normalize_uploaded_file

    pdf_bytes = b"%PDF-1.4 dummy content"
    filename, content, content_type = normalize_uploaded_file("datasheet.pdf", pdf_bytes, "application/pdf")
    assert filename == "datasheet.pdf"
    assert content == pdf_bytes
    assert content_type == "application/pdf"


@patch('app.baserow_client.requests.post')
def test_upload_file_client_converts_logo(mock_post):
    import io
    from PIL import Image
    im = Image.new("RGBA", (50, 50), color=(0, 255, 0, 128))
    img_io = io.BytesIO()
    im.save(img_io, format="WEBP")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"name": "mfg_logo.png"}
    mock_post.return_value = mock_resp

    client = BaserowClient()
    res = client.upload_file("mfg_logo.webp", img_io.getvalue(), "image/webp")
    assert res["name"] == "mfg_logo.png"

    # Verify that the post was called with normalized filename and image/png
    call_kwargs = mock_post.call_args[1]
    files = call_kwargs["files"]["file"]
    assert files[0] == "mfg_logo.png"
    assert files[2] == "image/png"

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
    # Mock item row fetch
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"id": 1, "Item description": "Test item", "Part Number": "10-00001"}

    # Edges returned by the filtered assembly query (as_parent filter: item 1 is parent)
    mock_edges_as_parent = MagicMock()
    mock_edges_as_parent.status_code = 200
    mock_edges_as_parent.json.return_value = {
        "results": [
            # Edge with empty contains list - should be skipped
            {"id": 102, "Item": [{"id": 1}], "Contains": [], "Measurement": ""},
            # Edge with string Amount of Times and string Length - should be processed
            {"id": 103, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": "5.5", "Measurement": "100.2"}
        ],
        "next": None
    }

    # Edges returned by the filtered assembly query (as_child filter: item 1 is child)
    mock_edges_as_child = MagicMock()
    mock_edges_as_child.status_code = 200
    mock_edges_as_child.json.return_value = {
        "results": [
            # Edge with empty items list - should be skipped
            {"id": 101, "Item": [], "Contains": [{"id": 1}], "Amount of Times": "not-a-number"}
        ],
        "next": None
    }

    # Individual BOM row for neighbour item 2 (child of item 1)
    mock_bom_row_2 = MagicMock()
    mock_bom_row_2.status_code = 200
    mock_bom_row_2.json.return_value = {"id": 2, "Part Number": "10-00002", "Item description": "Child Part"}

    mock_get.side_effect = [mock_resp1, mock_edges_as_parent, mock_edges_as_child, mock_bom_row_2]

    client = BaserowClient()
    item = client.get_item(1)

    assert item["id"] == 1
    # Only edge 103 should result in a contained item (edge 102 has empty Contains)
    assert len(item["contained_items"]) == 1
    assert item["contained_items"][0]["edge_id"] == 103
    assert item["contained_items"][0]["amount_label"] == "5 x 100.2mm"

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
    client._instructions_fields_checked = True
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


@patch('app.baserow_client.requests.get')
def test_get_instruction_set_details_non_blackbox_no_instructions_explodes(mock_get):
    """When a sub-assembly item has NO instructions of its own and Blackbox is False,
    it should explode into its constituent parts rather than showing up as itself."""
    mock_instructions = MagicMock()
    mock_instructions.json.return_value = {
        "results": [
            {
                "id": 101,
                "Parent Item": [{"id": 10}],
                "Set Index": 1,
                "Step Order": 1,
                "Action": "Assemble",
                "Quantity": 10,
                "Child Item": [{"id": 30}]
            }
        ],
        "next": None
    }

    mock_bom = MagicMock()
    mock_bom.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "10-00010", "Item description": "Parent Unit", "Blackbox": False},
            {"id": 20, "Part Number": "20-00020", "Item description": "Child Kit (No Instructions)", "Blackbox": False},
            {"id": 30, "Part Number": "30-00030", "Item description": "Kit Part Component", "Blackbox": False}
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
    client._instructions_fields_checked = True
    details = client.get_instruction_set_details(10, 1)

    comp_map = {c["item_id"]: c for c in details["comparison"]}
    # Intermediate kit 20 must NOT be in required comparison
    assert 20 not in comp_map
    # Component 30 must be in comparison with required_qty = 2 * 5 = 10
    assert 30 in comp_map
    assert comp_map[30]["required_qty"] == 10
    assert comp_map[30]["instructed_qty"] == 10
    assert comp_map[30]["discrepancy"] == "OK"


@patch('app.baserow_client.requests.get')
def test_get_instruction_set_details_toll(mock_get):
    # Mock table_instructions, table_bom, table_assembly responses
    mock_instructions = MagicMock()
    mock_instructions.json.return_value = {
        "results": [
            {
                "id": 101,
                "Parent Item": [{"id": 10}],
                "Set Index": 1,
                "Step Order": 1,
                "Action": "Prepare",
                "Quantity": 2,
                "Child Item": [{"id": 20}],
                "Toll": False
            }
        ],
        "next": None
    }

    mock_bom = MagicMock()
    mock_bom.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "10-00010", "Item description": "Parent Unit", "Blackbox": False},
            {"id": 20, "Part Number": "20-00020", "Item description": "Child Sub-assembly", "Blackbox": False}
        ],
        "next": None
    }

    mock_assembly = MagicMock()
    mock_assembly.json.return_value = {
        "results": [
            {"id": 1, "Item": [{"id": 10}], "Contains": [{"id": 20}], "Amount of Times": 2}
        ],
        "next": None
    }

    mock_get.side_effect = [mock_instructions, mock_bom, mock_assembly]

    client = BaserowClient()
    client._instructions_fields_checked = True
    details = client.get_instruction_set_details(10, 1)

    assert len(details["steps"]) == 1
    assert details["steps"][0]["id"] == 101
    assert details["steps"][0]["toll"] is False

    comp_map = {c["item_id"]: c for c in details["comparison"]}
    assert 20 in comp_map
    assert comp_map[20]["required_qty"] == 2
    assert comp_map[20]["instructed_qty"] == 0  # Toll is False, so instructed_qty should be 0!
    assert comp_map[20]["discrepancy"] == "Missing Instruction"


@patch('app.baserow_client.requests.get')
def test_get_instruction_set_details_toll_map_dict_format(mock_get):
    """New dict toll_map format {"id": {"toll": bool, "qty": int}} should be respected."""
    import json as _json
    toll_map_data = {
        "20": {"toll": False, "qty": 3},  # item 20: untolled (should be excluded)
        "21": {"toll": True,  "qty": 2},  # item 21: tolled with qty=2 (override)
    }
    mock_instructions = MagicMock()
    mock_instructions.json.return_value = {
        "results": [
            {
                "id": 101,
                "Parent Item": [{"id": 10}],
                "Set Index": 1,
                "Step Order": 1,
                "Action": "Assemble",
                "Quantity": 5,  # global qty — should be overridden by per-item qty
                "Child Item": [{"id": 20}, {"id": 21}],
                "Toll": True,
                "Toll Map": _json.dumps(toll_map_data)
            }
        ],
        "next": None
    }
    mock_bom = MagicMock()
    mock_bom.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "10-00010", "Item description": "Parent", "Blackbox": False},
            {"id": 20, "Part Number": "20-00020", "Item description": "Widget A", "Blackbox": False},
            {"id": 21, "Part Number": "21-00021", "Item description": "Widget B", "Blackbox": False},
        ],
        "next": None
    }
    mock_assembly = MagicMock()
    mock_assembly.json.return_value = {
        "results": [
            {"id": 1, "Item": [{"id": 10}], "Contains": [{"id": 20}], "Amount of Times": 3},
            {"id": 2, "Item": [{"id": 10}], "Contains": [{"id": 21}], "Amount of Times": 2},
        ],
        "next": None
    }
    mock_get.side_effect = [mock_instructions, mock_bom, mock_assembly]
    client = BaserowClient()
    client._instructions_fields_checked = True
    details = client.get_instruction_set_details(10, 1)
    comp_map = {c["item_id"]: c for c in details["comparison"]}
    # item 20 has toll=False → instructed_qty should be 0
    assert comp_map[20]["instructed_qty"] == 0, "Untolled item must contribute 0 to instructed count"
    assert comp_map[20]["discrepancy"] == "Missing Instruction"
    # item 21 has toll=True and qty=2 override → instructed_qty == 2 (not global 5)
    assert comp_map[21]["instructed_qty"] == 2, "Per-item qty in toll_map must override global step qty"


@patch('app.baserow_client.requests.get')
def test_get_instruction_set_details_toll_map_string_qty(mock_get):
    """String quantities in toll_map/tool_map (e.g. {"69": {"toll": true, "qty": "1"}}) should be parsed without TypeError."""
    import json as _json
    toll_map_data = {
        "20": {"toll": True, "qty": "3"},
        "21": {"toll": True, "qty": "2"},
    }
    tool_map_data = [
        {"id": 30, "quantity": "1"}
    ]
    mock_instructions = MagicMock()
    mock_instructions.json.return_value = {
        "results": [
            {
                "id": 101,
                "Parent Item": [{"id": 10}],
                "Set Index": 1,
                "Step Order": 1,
                "Action": "Assemble",
                "Quantity": None,
                "Child Item": [{"id": 20}, {"id": 21}],
                "Toll": None,
                "Toll Map": _json.dumps(toll_map_data),
                "Tool Map": _json.dumps(tool_map_data)
            }
        ],
        "next": None
    }
    mock_bom = MagicMock()
    mock_bom.json.return_value = {
        "results": [
            {"id": 10, "Part Number": "10-00010", "Item description": "Parent", "Blackbox": False},
            {"id": 20, "Part Number": "20-00020", "Item description": "Widget A", "Blackbox": False},
            {"id": 21, "Part Number": "21-00021", "Item description": "Widget B", "Blackbox": False},
            {"id": 30, "Part Number": "90-00030", "Item description": "Wrench", "Blackbox": False},
        ],
        "next": None
    }
    mock_assembly = MagicMock()
    mock_assembly.json.return_value = {
        "results": [
            {"id": 1, "Item": [{"id": 10}], "Contains": [{"id": 20}], "Amount of Times": 3},
            {"id": 2, "Item": [{"id": 10}], "Contains": [{"id": 21}], "Amount of Times": 2},
        ],
        "next": None
    }
    mock_get.side_effect = [mock_instructions, mock_bom, mock_assembly]
    client = BaserowClient()
    client._instructions_fields_checked = True
    details = client.get_instruction_set_details(10, 1)
    
    assert len(details["steps"]) == 1
    step = details["steps"][0]
    assert step["quantity"] == 5
    assert step["part_slots"][0]["quantity"] == 3
    assert step["tool_slots"][0]["quantity"] == 1
    
    comp_map = {c["item_id"]: c for c in details["comparison"]}
    assert comp_map[20]["instructed_qty"] == 3
    assert comp_map[21]["instructed_qty"] == 2
    assert comp_map[20]["discrepancy"] == "OK"
    assert comp_map[21]["discrepancy"] == "OK"


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
        "Notes": "Some notes",
        "Blackbox": True,
        "Price": "12.34",
        "Sourced by": "Supplier"
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
            {"id": 101, "Item": [{"id": 10}], "Contains": [{"id": 50}], "Amount of Times": 2, "Measurement": 0, "PCB Symbol": "C1"},
            # Parent edge (child is 10) -> Should NOT be copied
            {"id": 102, "Item": [{"id": 5}], "Contains": [{"id": 10}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "N/A"}
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
    assert item_payload["Blackbox"] is True
    assert item_payload["Price"] == "12.34"
    assert item_payload["Sourced by"] == "Supplier"

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
    # get_item fetches item row + 2 filtered assembly pages (as_parent, as_child) concurrently
    mock_src_resp = MagicMock()
    mock_src_resp.status_code = 200
    mock_src_resp.json.return_value = {
        "id": 42,
        "Part Number": "10-00042",
        "Item description": "Test Part",
        "PN Category": []
    }

    # No edges found for item 42 as parent or child
    mock_edges_empty = MagicMock()
    mock_edges_empty.status_code = 200
    mock_edges_empty.json.return_value = {"results": [], "next": None}

    # item row, as_parent edges, as_child edges
    mock_get.side_effect = [mock_src_resp, mock_edges_empty, mock_edges_empty]

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

@patch('app.baserow_client.requests.get')
def test_search_items_sends_search_param_and_caps_limit(mock_get):
    """search_items() must send ?search=<query>&size=<capped_limit> in a single request."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "results": [
            {"id": 5, "Part Number": "40-00005", "Item description": "Capacitor 100nF"}
        ],
        "next": None
    }
    mock_get.return_value = mock_resp

    client = BaserowClient()
    results = client.search_items("cap", limit=50)

    assert mock_get.call_count == 1
    call_args = mock_get.call_args
    params = call_args.kwargs.get("params") or call_args[1].get("params", {})
    assert params.get("search") == "cap"
    assert params.get("size") == 50
    assert params.get("user_field_names") == "true"
    assert len(results) == 1
    assert results[0]["id"] == 5

@patch('app.baserow_client.requests.get')
def test_search_items_caps_limit_at_200(mock_get):
    """search_items() must never request more than 200 rows."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [], "next": None}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    client.search_items("xyz", limit=9999)

    params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params", {})
    assert params.get("size") == 200

@patch('app.baserow_client.requests.get')
def test_get_top_level_items(mock_get):
    mock_bom_resp = MagicMock()
    mock_bom_resp.status_code = 200
    mock_bom_resp.json.return_value = {
        "results": [
            {"id": 1, "Part Number": "10-00000", "Revision": "B", "Item description": "Production Item (Root)", "State": {"value": "Production Use"}},
            {"id": 2, "Part Number": "20-00000", "Revision": "A", "Item description": "Engineering Item (Root)", "State": {"value": "Engineering Use"}},
            {"id": 3, "Part Number": "30-00000", "Revision": "A", "Item description": "Production Item (Child)", "State": {"value": "Production Use"}},
        ],
        "next": None
    }
    
    mock_assembly_resp = MagicMock()
    mock_assembly_resp.status_code = 200
    mock_assembly_resp.json.return_value = {
        "results": [
            {
                "id": 101,
                "Item": [{"id": 1, "value": "10-00000"}],
                "Contains": [{"id": 3, "value": "30-00000"}]
            }
        ],
        "next": None
    }
    
    mock_get.side_effect = [mock_bom_resp, mock_assembly_resp]
    
    client = BaserowClient()
    result = client.get_top_level_items(state="Production Use", offset=0, limit=5)
    
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == 1
    assert result["items"][0]["part_number"] == "10-00000"
    assert result["items"][0]["revision"] == "B"
    assert result["items"][0]["state"] == "Production Use"
    assert result["items"][0]["has_children"] is True


@patch('app.baserow_client.requests.get')
def test_get_manufacturer_by_id_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 2, "Name": "Schlegel", "Suppliers": [{"id": 6, "value": "Kahane"}]}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    res = client.get_manufacturer(2)
    assert res["id"] == 2
    assert res["Name"] == "Schlegel"


@patch('app.baserow_client.requests.post')
def test_create_manufacturer_client(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 10, "Name": "NewMfg", "Suppliers": [{"id": 1, "value": "Mouser"}]}
    mock_post.return_value = mock_resp

    client = BaserowClient()
    res = client.create_manufacturer({"Name": "NewMfg", "Suppliers": [1]})
    assert res["id"] == 10
    mock_post.assert_called_once()


@patch('app.baserow_client.requests.patch')
def test_update_manufacturer_client(mock_patch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 10, "Name": "UpdatedMfg"}
    mock_patch.return_value = mock_resp

    client = BaserowClient()
    res = client.update_manufacturer(10, {"Name": "UpdatedMfg", "Website": "https://mfg.com"})
    assert res["Name"] == "UpdatedMfg"
    mock_patch.assert_called_once()


@patch('app.baserow_client.requests.delete')
def test_delete_manufacturer_client(mock_delete):
    mock_resp = MagicMock()
    mock_delete.return_value = mock_resp

    client = BaserowClient()
    res = client.delete_manufacturer(10)
    assert res is True
    mock_delete.assert_called_once()


@patch('app.baserow_client.requests.get')
def test_get_suppliers_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": 1, "Company Name": "Mouser"}], "next": None}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    res = client.get_suppliers()
    assert len(res) == 1
    assert res[0]["Company Name"] == "Mouser"


@patch('app.baserow_client.requests.get')
def test_get_supplier_by_id_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 1, "Company Name": "Mouser", "Online Store": True}
    mock_get.return_value = mock_resp

    client = BaserowClient()
    res = client.get_supplier(1)
    assert res["id"] == 1
    assert res["Company Name"] == "Mouser"


@patch('app.baserow_client.requests.post')
def test_create_supplier_client(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 5, "Company Name": "DigiKey"}
    mock_post.return_value = mock_resp

    client = BaserowClient()
    res = client.create_supplier({"name": "DigiKey", "online_store": True})
    assert res["id"] == 5
    mock_post.assert_called_once()


@patch('app.baserow_client.requests.patch')
def test_update_supplier_client(mock_patch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 5, "Company Name": "DigiKey Corp"}
    mock_patch.return_value = mock_resp

    client = BaserowClient()
    res = client.update_supplier(5, {"Company Name": "DigiKey Corp"})
    assert res["Company Name"] == "DigiKey Corp"
    mock_patch.assert_called_once()


@patch('app.baserow_client.requests.delete')
def test_delete_supplier_client(mock_delete):
    mock_resp = MagicMock()
    mock_delete.return_value = mock_resp

    client = BaserowClient()
    res = client.delete_supplier(5)
    assert res is True
    mock_delete.assert_called_once()


@patch('app.baserow_client.requests.get')
def test_get_contacts_filtered_client(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"id": 1, "Name": "Alice", "Suppliers": [{"id": 1, "value": "Mouser"}]},
            {"id": 2, "Name": "Bob", "Suppliers": [{"id": 2, "value": "DigiKey"}]}
        ],
        "next": None
    }
    mock_get.return_value = mock_resp

    client = BaserowClient()
    all_contacts = client.get_contacts()
    assert len(all_contacts) == 2

    filtered = client.get_contacts(supplier_id=1)
    assert len(filtered) == 1
    assert filtered[0]["Name"] == "Alice"


@patch('app.baserow_client.requests.post')
def test_create_contact_client(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 10, "Name": "Charlie", "Email": "charlie@supplier.com"}
    mock_post.return_value = mock_resp

    client = BaserowClient()
    res = client.create_contact({"name": "Charlie", "email": "charlie@supplier.com", "suppliers": [1]})
    assert res["id"] == 10
    mock_post.assert_called_once()


@patch('app.baserow_client.requests.patch')
def test_update_contact_client(mock_patch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 10, "Name": "Charlie Updated"}
    mock_patch.return_value = mock_resp

    client = BaserowClient()
    res = client.update_contact(10, {"Name": "Charlie Updated"})
    assert res["Name"] == "Charlie Updated"
    mock_patch.assert_called_once()


@patch('app.baserow_client.requests.delete')
def test_delete_contact_client(mock_delete):
    mock_resp = MagicMock()
    mock_delete.return_value = mock_resp

    client = BaserowClient()
    res = client.delete_contact(10)
    assert res is True
    mock_delete.assert_called_once()


@patch.object(BaserowClient, '_ensure_item_category', side_effect=lambda item_id, item: item)
@patch.object(BaserowClient, '_get_all_rows')
@patch.object(BaserowClient, 'get_items')
@patch.object(BaserowClient, '_request')
def test_duplicate_item_client(mock_request, mock_get_items, mock_get_all_rows, mock_ensure_cat):
    client = BaserowClient()
    client.rules = {"40": {"id": 6, "name": "Electrical COTS"}}

    # Mock source item fetch
    source_item = {
        "id": 57,
        "Part Number": "40-00000",
        "Revision": "A",
        "Item description": "Silver pushbutton with illuminated ring",
        "External Part Number": "RRJTLR",
        "Manufacturer": [{"id": 2, "value": "Schlegel Electrokontakt GMBH"}],
        "System": {"id": 2963, "value": "DC Power Supply"},
        "Price per unit": "12.50",
        "Source URL": "https://kahane.co.il",
        "Notes": "https://www.schlegel.biz/en/rrjtlr/rrjtlr",
        "Sourced By": {"id": 3000, "value": "TBD"},
        "Blackbox": False,
        "State": [{"id": 5, "value": "Unknown"}],
        "Image": [{"name": "photo1.jpg", "url": "http://test/photo1.jpg"}],
        "Datasheet": [{"name": "spec.pdf", "url": "http://test/spec.pdf"}]
    }

    def mock_request_side_effect(method, url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if method == "GET" and f"/api/database/rows/table/{client.table_bom}/57/" in url:
            resp.json.return_value = source_item
            return resp
        elif method == "POST" and f"/api/database/rows/table/{client.table_bom}/" in url:
            payload = kwargs.get("json", {})
            created = dict(payload)
            created["id"] = 199
            resp.json.return_value = created
            return resp
        resp.json.return_value = {}
        return resp

    mock_request.side_effect = mock_request_side_effect
    mock_get_items.return_value = [{"Part Number": "40-00000"}]
    mock_get_all_rows.return_value = []

    res = client.duplicate_item(
        source_id=57,
        new_prefix="40",
        new_description="Silver pushbutton copy",
        duplicate_parents=False,
        duplicate_children=False,
        duplicate_instructions=False,
        duplicate_photos=True
    )

    assert res["id"] == 199
    assert res["Part Number"] == "40-00001"
    assert res["Item description"] == "Silver pushbutton copy"
    assert res["External Part Number"] == "RRJTLR"
    assert res["Manufacturer"] == [2]
    assert res["System"] == 2963
    assert res["Price per unit"] == "12.50"
    assert res["Source URL"] == "https://kahane.co.il"
    assert res["Notes"] == "https://www.schlegel.biz/en/rrjtlr/rrjtlr"
    assert res["Sourced By"] == 3000
    assert res["State"] == [5]
    assert res["Image"] == [{"name": "photo1.jpg"}]
    # Ensure Datasheet is NEVER copied
    assert "Datasheet" not in res

def test_evaluate_condition_hooks_and_fields():
    from app.baserow_client import evaluate_condition

    row = {
        "id": 1,
        "Part Number": "10-00001",
        "Item description": "Steel Screw M3",
        "External PN": "EXT-9988",
        "State": {"value": "Production Use"},
        "Sourced By": {"value": "Purchased by ERA"},
        "Source URL": "https://octopart.com/search?q=123"
    }

    # Test External PN equals, contains, not_equals
    assert evaluate_condition(row, {"field": "External PN", "operator": "equals", "value": "EXT-9988"})
    assert evaluate_condition(row, {"field": "External PN", "operator": "contains", "value": "9988"})
    assert evaluate_condition(row, {"field": "External PN", "operator": "not_equals", "value": "EXT-0000"})
    assert evaluate_condition(row, {"field": "External Part Number", "operator": "equals", "value": "ext-9988"})
    assert not evaluate_condition(row, {"field": "External PN", "operator": "is_empty", "value": ""})
    assert evaluate_condition(row, {"field": "External PN", "operator": "is_not_empty", "value": ""})

    # Test is_in_assembly hook
    assert evaluate_condition(row, {"field": "is_in_assembly", "operator": "equals", "value": "true"}, is_in_assembly=True)
    assert not evaluate_condition(row, {"field": "is_in_assembly", "operator": "equals", "value": "true"}, is_in_assembly=False)
    assert evaluate_condition(row, {"field": "is_in_assembly", "operator": "equals", "value": "false"}, is_in_assembly=False)

    # Test has_children hook
    assert evaluate_condition(row, {"field": "has_children", "operator": "equals", "value": "true"}, has_children=True)
    assert not evaluate_condition(row, {"field": "has_children", "operator": "equals", "value": "true"}, has_children=False)
    assert evaluate_condition(row, {"field": "has_children", "operator": "equals", "value": "false"}, has_children=False)

    # Test State and Sourced By
    assert evaluate_condition(row, {"field": "State", "operator": "equals", "value": "Production Use"})
    assert evaluate_condition(row, {"field": "Sourced By", "operator": "equals", "value": "Purchased by ERA"})
    assert not evaluate_condition(row, {"field": "State", "operator": "equals", "value": "EOL"})

    # Test Blackbox hook
    row_bb = dict(row, Blackbox=True)
    row_non_bb = dict(row, Blackbox=False)
    assert evaluate_condition(row_bb, {"field": "Blackbox", "operator": "equals", "value": "true"})
    assert not evaluate_condition(row_non_bb, {"field": "Blackbox", "operator": "equals", "value": "true"})
    assert evaluate_condition(row_non_bb, {"field": "Blackbox", "operator": "equals", "value": "false"})

    # Test has_photos hook
    row_photos = dict(row, Image=[{"name": "test.png", "url": "http://img"}])
    row_no_photos = dict(row, Image=[])
    assert evaluate_condition(row_photos, {"field": "has_photos", "operator": "equals", "value": "true"})
    assert not evaluate_condition(row_no_photos, {"field": "has_photos", "operator": "equals", "value": "true"})
    assert evaluate_condition(row_no_photos, {"field": "has_photos", "operator": "equals", "value": "false"})
    assert evaluate_condition(row_photos, {"field": "Has photos", "operator": "equals", "value": "true"})

    # Test bom_equilibrium hook
    assert evaluate_condition(row, {"field": "bom_equilibrium", "operator": "equals", "value": "true"}, bom_equilibrium=True)
    assert not evaluate_condition(row, {"field": "bom_equilibrium", "operator": "equals", "value": "true"}, bom_equilibrium=False)
    assert evaluate_condition(row, {"field": "bom_equilibrium", "operator": "equals", "value": "false"}, bom_equilibrium=False)
    assert evaluate_condition(row, {"field": "BOM equilibrium (balance)", "operator": "equals", "value": "true"}, bom_equilibrium=True)

    # Test has_all_images hook
    assert evaluate_condition(row, {"field": "has_all_images", "operator": "equals", "value": "true"}, has_all_images=True)
    assert not evaluate_condition(row, {"field": "has_all_images", "operator": "equals", "value": "true"}, has_all_images=False)
    assert evaluate_condition(row, {"field": "has_all_images", "operator": "equals", "value": "false"}, has_all_images=False)
    assert evaluate_condition(row, {"field": "Has all images", "operator": "equals", "value": "true"}, has_all_images=True)

    # Test Price hook and numeric comparisons
    row_price = dict(row, **{"Price per unit": "25.50"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "equals", "value": "25.50"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "equals", "value": "25.5"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "greater_than", "value": "20.00"})
    assert not evaluate_condition(row_price, {"field": "Price per unit", "operator": "greater_than", "value": "30.00"})
    assert evaluate_condition(row_price, {"field": "Price", "operator": "less_than", "value": "30.00"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "greater_than_or_equal", "value": "25.50"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "less_than_or_equal", "value": "25.50"})
    assert evaluate_condition(row_price, {"field": "Price per unit", "operator": "is_not_empty", "value": ""})
    assert not evaluate_condition(row_price, {"field": "Price per unit", "operator": "is_empty", "value": ""})

    row_no_price = dict(row, **{"Price per unit": None})
    assert evaluate_condition(row_no_price, {"field": "Price per unit", "operator": "is_empty", "value": ""})
    assert not evaluate_condition(row_no_price, {"field": "Price per unit", "operator": "is_not_empty", "value": ""})

    # Test nested group
    group_rule = {
        "type": "AND",
        "conditions": [
            {"field": "has_children", "operator": "equals", "value": "true"},
            {"field": "State", "operator": "equals", "value": "Production Use"},
            {"field": "Price per unit", "operator": "greater_than", "value": "20"}
        ]
    }
    assert evaluate_condition(row_price, group_rule, has_children=True)
    assert not evaluate_condition(row, group_rule, has_children=True) # row has no price


def test_problem_scanner_instruction_sets_multi_set_or_logic(monkeypatch):
    import time
    from unittest.mock import MagicMock
    from app.baserow_client import ProblemScanner, BaserowClient

    client = BaserowClient()
    scanner = ProblemScanner()

    # Mock definitions: flag problem when bom_equilibrium is false OR has_all_images is false
    defs = [
        {
            "id": 1,
            "name": "BOM Not Balanced",
            "rule": {"field": "bom_equilibrium", "operator": "equals", "value": "false"}
        },
        {
            "id": 2,
            "name": "Missing Step Images",
            "rule": {"field": "has_all_images", "operator": "equals", "value": "false"}
        }
    ]
    monkeypatch.setattr(scanner, "load_definitions", lambda: defs)
    # Eliminate sleep delay in scanner thread
    monkeypatch.setattr(time, "sleep", lambda x: None)

    bom_rows = [
        {"id": 100, "Part Number": "10-00100"}, # 0 sets -> Should be True for both (0 problems)
        {"id": 200, "Part Number": "10-00200"}, # 1 set: balanced, all images (0 problems)
        {"id": 300, "Part Number": "10-00300"}, # 1 set: imbalanced, missing image (2 problems)
        {"id": 400, "Part Number": "10-00400"}, # 2 sets: Set 1 imbalanced & missing image, Set 2 balanced & all images -> OR = True for both (0 problems)
        {"id": 500, "Part Number": "10-00500"}, # 2 sets: both imbalanced & both missing images -> (2 problems)
    ]

    # Assembly relationships
    # 200 contains 100 (qty 1)
    # 300 contains 100 (qty 2)
    # 400 contains 100 (qty 1)
    # 500 contains 100 (qty 2)
    assembly_rows = [
        {"id": 1, "Item": [{"id": 200}], "Contains": [{"id": 100}], "Amount of Times": 1},
        {"id": 2, "Item": [{"id": 300}], "Contains": [{"id": 100}], "Amount of Times": 2},
        {"id": 3, "Item": [{"id": 400}], "Contains": [{"id": 100}], "Amount of Times": 1},
        {"id": 4, "Item": [{"id": 500}], "Contains": [{"id": 100}], "Amount of Times": 2},
    ]

    instruction_rows = [
        # For 200: Set 1 (instructs 100 qty 1, with photo) -> Balanced, All images
        {
            "id": 10,
            "Parent Item": [{"id": 200}],
            "Set Index": 1,
            "Child Item": [{"id": 100}],
            "Quantity": 1,
            "Toll": True,
            "Photo": [{"url": "http://img.png"}]
        },
        # For 300: Set 1 (instructs 100 qty 1 instead of 2, without photo) -> Imbalanced, Missing images
        {
            "id": 20,
            "Parent Item": [{"id": 300}],
            "Set Index": 1,
            "Child Item": [{"id": 100}],
            "Quantity": 1,
            "Toll": True,
            "Photo": []
        },
        # For 400: Set 1 (imbalanced, no photo)
        {
            "id": 30,
            "Parent Item": [{"id": 400}],
            "Set Index": 1,
            "Child Item": [{"id": 100}],
            "Quantity": 5, # wrong qty
            "Toll": True,
            "Photo": []
        },
        # For 400: Set 2 (balanced qty 1, with photo) -> Makes 400 True by OR logic
        {
            "id": 31,
            "Parent Item": [{"id": 400}],
            "Set Index": 2,
            "Child Item": [{"id": 100}],
            "Quantity": 1,
            "Toll": True,
            "Photo": [{"url": "http://photo.jpg"}]
        },
        # For 500: Set 1 (imbalanced, no photo)
        {
            "id": 40,
            "Parent Item": [{"id": 500}],
            "Set Index": 1,
            "Child Item": [{"id": 100}],
            "Quantity": 10,
            "Toll": True,
            "Photo": []
        },
        # For 500: Set 2 (also imbalanced, also no photo)
        {
            "id": 41,
            "Parent Item": [{"id": 500}],
            "Set Index": 2,
            "Child Item": [{"id": 100}],
            "Quantity": 99,
            "Toll": True,
            "Photo": []
        },
    ]

    def mock_get_all_rows(table_id, params=None):
        if table_id == client.table_bom:
            return bom_rows
        elif table_id == client.table_assembly:
            return assembly_rows
        elif table_id == client.table_instructions:
            return instruction_rows
        return []

    monkeypatch.setattr(client, "_get_all_rows", mock_get_all_rows)

    scanner.start_scan(client)
    # Wait for scanner thread to complete
    for _ in range(50):
        if scanner.status == "completed":
            break
        time.sleep(0.05)

    assert scanner.status == "completed"
    probs = scanner.problems

    # 100 has 0 sets -> 0 problems
    assert probs.get(100) == []

    # 200 has 1 set (balanced, all images) -> 0 problems
    assert probs.get(200) == []

    # 300 has 1 set (imbalanced, missing image) -> 2 problems
    assert "BOM Not Balanced" in probs.get(300)
    assert "Missing Step Images" in probs.get(300)

    # 400 has 2 sets (Set 2 is balanced & has photos) -> OR resolves to True for both -> 0 problems
    assert probs.get(400) == []

    # 500 has 2 sets (neither balanced, neither has photos) -> 2 problems
    assert "BOM Not Balanced" in probs.get(500)
    assert "Missing Step Images" in probs.get(500)


def test_get_instruction_sets_for_item_balanced_and_unbalanced(monkeypatch):
    import json
    from app.baserow_client import BaserowClient
    client = BaserowClient()
    client._instructions_fields_checked = True

    bom_rows = [
        {"id": 10, "Part Number": "10-00010", "Item description": "Parent Unit", "Blackbox": False},
        {"id": 20, "Part Number": "20-00020", "Item description": "Child Item", "Blackbox": False},
        {"id": 30, "Part Number": "30-00030", "Item description": "Another Child", "Blackbox": False}
    ]

    # Item 10 contains Item 20 (qty 2) and Item 30 (qty 1)
    assembly_rows = [
        {"id": 1, "Item": [{"id": 10}], "Contains": [{"id": 20}], "Amount of Times": 2},
        {"id": 2, "Item": [{"id": 10}], "Contains": [{"id": 30}], "Amount of Times": 1}
    ]

    # Set 1: instructs 20 (qty 2) and 30 (qty 1) -> BALANCED
    # Set 2: instructs 20 (qty 1) -> UNBALANCED (missing 30 and 1 of 20)
    instruction_rows = [
        {"id": 101, "Parent Item": [{"id": 10}], "Set Index": 1, "Toll Map": json.dumps([{"id": 20, "quantity": 2, "toll": True}])},
        {"id": 102, "Parent Item": [{"id": 10}], "Set Index": 1, "Toll Map": json.dumps([{"id": 30, "quantity": 1, "toll": True}])},
        {"id": 103, "Parent Item": [{"id": 10}], "Set Index": 2, "Toll Map": json.dumps([{"id": 20, "quantity": 1, "toll": True}])}
    ]

    def mock_get_all_rows(table_id):
        if table_id == client.table_bom:
            return bom_rows
        elif table_id == client.table_assembly:
            return assembly_rows
        elif table_id == client.table_instructions:
            return instruction_rows
        return []

    monkeypatch.setattr(client, "_get_all_rows", mock_get_all_rows)

    sets = client.get_instruction_sets_for_item(10)
    assert len(sets) == 2
    assert sets[0]["set_index"] == 1
    assert sets[0]["step_count"] == 2
    assert sets[0]["is_balanced"] is True

    assert sets[1]["set_index"] == 2
    assert sets[1]["step_count"] == 1
    assert sets[1]["is_balanced"] is False

    # Test with new canonical per-edge format
    instruction_rows_canonical = [
        {"id": 101, "Parent Item": [{"id": 10}], "Set Index": 1, "Toll Map": json.dumps([{"edge_id": 501, "item_id": 20, "qty": 2, "toll": True, "length": 0}])},
        {"id": 102, "Parent Item": [{"id": 10}], "Set Index": 1, "Toll Map": json.dumps([{"edge_id": 502, "item_id": 30, "qty": 1, "toll": True, "length": 0}])}
    ]
    def mock_get_all_rows_canonical(table_id):
        if table_id == client.table_instructions:
            return instruction_rows_canonical
        return mock_get_all_rows(table_id)
    monkeypatch.setattr(client, "_get_all_rows", mock_get_all_rows_canonical)

    sets_canonical = client.get_instruction_sets_for_item(10)
    assert len(sets_canonical) == 1
    assert sets_canonical[0]["is_balanced"] is True

    # For an item with no instruction sets:
    empty_sets = client.get_instruction_sets_for_item(999)
    assert empty_sets == []


def test_format_relation_amount():
    from app.baserow_client import format_relation_amount
    assert format_relation_amount(1, 10, "cm") == "1 x 10cm"
    assert format_relation_amount(5, 100.2, "mm") == "5 x 100.2mm"
    assert format_relation_amount(2, 0, "pcs") == "2 pcs"
    assert format_relation_amount(1, 0, "pcs") == "1 pcs"
    assert format_relation_amount("1", "2700", "mm") == "1 x 2700mm"
    assert format_relation_amount(None, 50, "m") == "50m"
    assert format_relation_amount(3, None, None) == "3 pcs"
    assert format_relation_amount(1, 250, "ml") == "1 x 250ml"






