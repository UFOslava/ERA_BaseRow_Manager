import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.baserow_client import BaserowClient
from app.mcp_server import create_mcp_server, run_mcp_stdio, run_mcp_sse, start_mcp_background, _find_item_by_pn_or_id


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.table_bom = "508"
    client.table_assembly = "701"
    client.table_instructions = "5770"
    client.rules = [
        {"prefix": "EL-PCBA", "name": "PCBA", "category": "Electronics"},
        {"prefix": "ME-CHAS", "name": "Chassis", "category": "Mechanical"}
    ]
    client.states_map = {
        "Production Use": 1,
        "Engineering Use": 2,
        "Finish Stock": 3,
        "EOL": 4,
        "Discard": 5
    }

    mock_items = [
        {
            "id": 1,
            "Part Number": "ASY-TOP-001",
            "Full PN": "ASY-TOP-001 Rev.A",
            "Revision": "A",
            "Name": "Top Main Assembly",
            "Description": "Complete top level product assembly",
            "Category": {"value": "Assembly"},
            "Item Lifecycle State": {"value": "Production Use"},
            "Blackbox": False,
            "Purchase Kit": False,
            "Price per unit": "150.00",
            "Lot Size": 1,
            "External PN": "EXT-ASY-1",
            "Manufacturer": "ERA In-House",
            "Supplier": "ERA",
            "Notes": "Primary production unit",
            "Image": [{"url": "http://img.png"}],
            "Datasheet": [{"url": "http://doc.pdf"}]
        },
        {
            "id": 2,
            "Part Number": "EL-PCBA-001",
            "Full PN": "EL-PCBA-001 Rev.1",
            "Revision": "1",
            "Name": "Main Control Board",
            "Description": "SMT MCU board",
            "Category": {"value": "Electronics"},
            "Item Lifecycle State": {"value": "Engineering Use"},
            "Blackbox": True,
            "Purchase Kit": True,
            "Price per unit": "45.00",
            "Lot Size": 10,
            "External PN": "PCB-M1",
            "Manufacturer": "BoardMaker Inc",
            "Supplier": "DigiKey",
            "Notes": "MCU revision B",
            "Image": [{"url": "http://pcb.png"}],
            "Datasheet": [{"url": "http://pcb_spec.pdf"}]
        },
        {
            "id": 3,
            "Part Number": "ME-FAST-001",
            "Full PN": "ME-FAST-001",
            "Name": "M3x8mm Screw",
            "Description": "Stainless steel pan head screw",
            "Category": {"value": "Fasteners"},
            "Item Lifecycle State": {"value": "Production Use"},
            "Blackbox": False,
            "Purchase Kit": False,
            "Price per unit": "0.10",
            "Lot Size": 100,
            "External PN": "SCR-M3-8",
            "Manufacturer": "FastenerCo",
            "Supplier": "McMaster",
            "Notes": "",
            "Image": [],
            "Datasheet": []
        },
        {
            "id": 10,
            "Part Number": "A-001",
            "Full PN": "A-001 Rev.A",
            "Revision": "A",
            "Name": "Sub Sensor Board Rev.A",
            "Description": "Retired revision of sub sensor board",
            "Category": {"value": "Electronics"},
            "Item Lifecycle State": {"value": "Finish Stock"},
            "Blackbox": True,
            "Price per unit": "10.00",
            "Lot Size": 1,
            "External PN": "SEN-A",
            "Manufacturer": "BoardMaker Inc",
            "Supplier": "DigiKey",
            "Notes": "Retired revision",
            "Image": [],
            "Datasheet": []
        },
        {
            "id": 11,
            "Part Number": "A-001",
            "Full PN": "A-001 Rev.B",
            "Revision": "B",
            "Name": "Sub Sensor Board Rev.B",
            "Description": "Active production revision of sub sensor board",
            "Category": {"value": "Electronics"},
            "Item Lifecycle State": {"value": "Production Use"},
            "Blackbox": True,
            "Price per unit": "12.00",
            "Lot Size": 1,
            "External PN": "SEN-B",
            "Manufacturer": "BoardMaker Inc",
            "Supplier": "DigiKey",
            "Notes": "Active revision",
            "Image": [],
            "Datasheet": []
        },
        {
            "id": 20,
            "Part Number": "ASY-REV-001",
            "Full PN": "ASY-REV-001 Rev.A",
            "Revision": "A",
            "Name": "Revision Test Assembly",
            "Description": "Assembly for testing revision resolution",
            "Category": {"value": "Assembly"},
            "Item Lifecycle State": {"value": "Production Use"},
            "Blackbox": False,
            "Price per unit": "100.00",
            "Lot Size": 1,
            "External PN": "EXT-ASY-REV",
            "Manufacturer": "ERA In-House",
            "Supplier": "ERA",
            "Notes": "",
            "Image": [],
            "Datasheet": []
        }
    ]

    client.get_items.return_value = mock_items
    client.get_item.side_effect = lambda iid: next((x for x in mock_items if x["id"] == iid), {"error": "Not found"})
    client.search_items.return_value = [mock_items[0], mock_items[1]]
    client.get_top_level_items.return_value = [mock_items[0]]
    client.get_graph_parents.return_value = [{"id": 1, "part_number": "ASY-TOP-001", "name": "Top Main Assembly"}]
    client.get_graph_children.return_value = [
        {"id": 2, "part_number": "EL-PCBA-001", "name": "Main Control Board", "quantity": 1},
        {"id": 3, "part_number": "ME-FAST-001", "name": "M3x8mm Screw", "quantity": 4}
    ]
    client.get_bom_tree.return_value = [
        {
            "id": 1,
            "part_number": "ASY-TOP-001",
            "name": "Top Main Assembly",
            "children": [
                {"id": 2, "part_number": "EL-PCBA-001", "name": "Main Control Board", "children": []},
                {"id": 3, "part_number": "ME-FAST-001", "name": "M3x8mm Screw", "children": []}
            ]
        }
    ]

    # Assembly edges: Asy 1 contains PCBA 2 (qty 1) and Fastener 3 (qty 4); Asy 20 contains A-001 Rev.B (qty 1)
    client._get_all_rows.side_effect = lambda tbl: (
        mock_items if tbl == "508" else (
            [
                {"id": 101, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 1, "Quantity": 1},
                {"id": 102, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 4, "Quantity": 4},
                {"id": 201, "Item": [{"id": 20}], "Contains": [{"id": 11}], "Amount of Times": 1, "Quantity": 1}
            ] if tbl == "701" else (
                [
                    {
                        "id": 501,
                        "Parent Item": [{"id": 1}],
                        "Step Order": "1",
                        "Step Number": 1,
                        "Action": "Mount Board",
                        "Step Title": "Mount Board",
                        "Description": "Place PCBA on chassis and secure with 4 screws",
                        "Instruction Text": "Place PCBA on chassis and secure with 4 screws",
                        "Set Index": "0",
                        "Instruction Set Index": 0,
                        "Photo": [{"url": "http://step1.png"}],
                        "Toll Map": json.dumps([
                            {"id": 2, "quantity": 1, "toll": True},
                            {"id": 3, "quantity": 4, "toll": True}
                        ])
                    },
                    {
                        "id": 601,
                        "Parent Item": [{"id": 20}],
                        "Step Order": "1",
                        "Step Number": 1,
                        "Action": "Mount Sensor",
                        "Step Title": "Mount Sensor",
                        "Description": "Mount sub sensor board",
                        "Instruction Text": "Mount sub sensor board",
                        "Set Index": "0",
                        "Instruction Set Index": 0,
                        "Photo": [{"url": "http://step_sensor.png"}],
                        "Toll Map": json.dumps([
                            {"edge_id": None, "item_id": 10, "toll": True, "qty": 1.0}
                        ])
                    }
                ] if tbl == "5770" else []
            )
        )
    )

    client.get_instruction_sets_for_item.return_value = [{"set_index": 0, "name": "Standard Assembly", "step_count": 1}]
    client.get_instruction_set_details.return_value = [
        {
            "id": 501,
            "step_order": "1",
            "Step Order": "1",
            "Step Number": 1,
            "action": "Mount Board",
            "Action": "Mount Board",
            "Step Title": "Mount Board",
            "Description": "Place PCBA on chassis and secure with 4 screws",
            "Instruction Text": "Place PCBA on chassis and secure with 4 screws",
            "Photo": [{"url": "http://step1.png"}],
            "Toll Map": json.dumps([{"id": 2, "quantity": 1, "toll": True}, {"id": 3, "quantity": 4, "toll": True}])
        }
    ]

    client.scanner.load_definitions.return_value = [
        {
            "id": "missing_datasheet",
            "name": "Missing Datasheet",
            "severity": "warning",
            "condition": {"field": "Datasheet", "operator": "is_empty", "value": ""}
        }
    ]

    client.get_manufacturers.return_value = [{"id": 1, "Name": "ERA In-House"}, {"id": 2, "Name": "BoardMaker Inc"}]
    client.get_suppliers.return_value = [{"id": 1, "Name": "DigiKey"}, {"id": 2, "Name": "McMaster"}]

    client.create_bom_item.return_value = {"id": 4, "Part Number": "ME-CHAS-001", "Item description": "Alu Chassis"}
    client.create_item.return_value = {"id": 4, "Part Number": "ME-CHAS-001", "Item description": "Alu Chassis"}
    client.update_item.return_value = {"id": 1, "Part Number": "ASY-TOP-001", "Item description": "Updated Name"}
    client.get_state_id.side_effect = lambda state: [1] if state and state != "InvalidState" else []
    client.create_instruction.return_value = {"id": 502, "Step Order": "2", "Step Number": 2, "Description": "Next step", "Instruction Text": "Next step"}
    client.update_instruction.return_value = {"id": 501, "Step Order": "1", "Step Number": 1, "Description": "Updated text", "Instruction Text": "Updated text"}

    return client


def test_mcp_server_registration(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]

        expected_tools = [
            "search_items",
            "get_item_details",
            "create_item",
            "update_item",
            "get_bom_tree",
            "get_where_used",
            "audit_bom_balance",
            "scan_bom_duplicates",
            "get_work_instructions",
            "create_or_update_wi_step",
            "get_inventory_summary",
            "list_pn_categories",
            "list_item_lifecycle_states",
            "list_manufacturers_and_suppliers"
        ]
        for exp in expected_tools:
            assert exp in tool_names, f"Expected tool {exp} not registered"
        assert "run_quality_scan" not in tool_names, "run_quality_scan should not be registered"

        templates = await server.list_resource_templates()
        template_uris = [t.uri_template for t in templates]
        assert "era://items/{part_number}" in template_uris
        assert "era://bom/{part_number}" in template_uris
        assert "era://wi/{part_number}" in template_uris
        assert "era://inventory/{part_number}" in template_uris

        prompts = await server.list_prompts()
        prompt_names = [p.name for p in prompts]
        assert "audit_bom_balance" in prompt_names
        assert "create_assembly_wi" in prompt_names
        assert "hardware_problem_scan" not in prompt_names

    asyncio.run(_test())


def test_search_items_tool(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        
        # 1. Broad search
        res = await server.call_tool("search_items", {"query": "ASY", "limit": 10})
        data = json.loads(res.content[0].text)
        assert data["count"] > 0
        assert data["items"][0]["part_number"] == "ASY-TOP-001"

        # 2. Filter by category
        res_cat = await server.call_tool("search_items", {"category": "Electronics"})
        data_cat = json.loads(res_cat.content[0].text)
        assert any(i["part_number"] == "EL-PCBA-001" for i in data_cat["items"])

        # 3. Filter by lifecycle state
        res_state = await server.call_tool("search_items", {"lifecycle_state": "Engineering Use"})
        data_state = json.loads(res_state.content[0].text)
        assert all(i["lifecycle_state"] == "Engineering Use" for i in data_state["items"])

    asyncio.run(_test())


def test_get_item_details_tool(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # By PN
        res = await server.call_tool("get_item_details", {"part_number_or_id": "ASY-TOP-001"})
        data = json.loads(res.content[0].text)
        assert data["part_number"] == "ASY-TOP-001"
        assert data["child_components_count"] == 2
        assert data["has_photos"] is True

        # By Numeric ID
        res_id = await server.call_tool("get_item_details", {"part_number_or_id": "2"})
        data_id = json.loads(res_id.content[0].text)
        assert data_id["part_number"] == "EL-PCBA-001"
        assert data_id["blackbox"] is True

        # Not found
        res_err = await server.call_tool("get_item_details", {"part_number_or_id": "NON-EXISTENT"})
        data_err = json.loads(res_err.content[0].text)
        assert "error" in data_err

    asyncio.run(_test())


def test_create_and_update_item_tools(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Create item
        res_create = await server.call_tool("create_item", {
            "part_number": "ME-CHAS-001",
            "name": "Alu Chassis",
            "category": "Mechanical",
            "price_per_unit": 25.50,
            "blackbox": False
        })
        data_create = json.loads(res_create.content[0].text)
        assert "Successfully created" in data_create["message"]
        mock_client.create_bom_item.assert_called_once()
        payload = mock_client.create_bom_item.call_args[0][0]
        assert payload["Part Number"] == "ME-CHAS-001"
        assert payload["Item description"] == "Alu Chassis"
        assert payload["Price per unit"] == 25.50
        assert "Name" not in payload
        assert "Description" not in payload
        assert "Item Lifecycle State" not in payload

        # Update item
        res_upd = await server.call_tool("update_item", {
            "part_number_or_id": "ASY-TOP-001",
            "name": "Updated Top Assembly",
            "price_per_unit": 160.0
        })
        data_upd = json.loads(res_upd.content[0].text)
        assert "Successfully updated" in data_upd["message"]
        assert "Item description" in data_upd["updated_fields"]
        assert "Name" not in data_upd["updated_fields"]

    asyncio.run(_test())


def test_create_item_validation(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Invalid lifecycle state rejected
        res_state = await server.call_tool("create_item", {
            "part_number": "40-00099",
            "name": "Bad State Item",
            "lifecycle_state": "InvalidState"
        })
        data_state = json.loads(res_state.content[0].text)
        assert "error" in data_state
        assert "Invalid lifecycle_state" in data_state["error"]

        # Unresolvable manufacturer rejected with error naming link_row
        res_mfg = await server.call_tool("create_item", {
            "part_number": "40-00099",
            "name": "Bad Mfg Item",
            "manufacturer": "NonexistentMfgXYZ"
        })
        data_mfg = json.loads(res_mfg.content[0].text)
        assert "error" in data_mfg
        assert "link_row" in data_mfg["error"]

    asyncio.run(_test())


def test_bom_tree_and_where_used(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Whole tree
        res_tree = await server.call_tool("get_bom_tree", {})
        data_tree = json.loads(res_tree.content[0].text)
        assert "bom_tree" in data_tree

        # Subtree by PN
        res_sub = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001"})
        data_sub = json.loads(res_sub.content[0].text)
        assert data_sub["part_number"] == "ASY-TOP-001"

        # Where used
        res_wu = await server.call_tool("get_where_used", {"part_number_or_id": "EL-PCBA-001"})
        data_wu = json.loads(res_wu.content[0].text)
        assert data_wu["used_in_count"] >= 1
        assert data_wu["parent_assemblies"][0]["part_number"] == "ASY-TOP-001"

    asyncio.run(_test())


def test_audit_bom_balance_tool(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Top assembly has 1 PCBA + 4 Screws, and Step 1 tolls 1 PCBA + 4 Screws -> Equilibrium Balanced
        res = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-TOP-001"})
        data = json.loads(res.content[0].text)
        assert data["bom_equilibrium_balanced"] is True
        assert data["discrepancies"] == []
        assert len(data["sets"]) == 1
        assert data["sets"][0]["is_balanced"] is True
        assert len(data["sets"][0]["discrepancies"]) == 0
        assert data["sets"][0]["steps"][0]["step_number"] == 1
        assert data["sets"][0]["steps"][0]["title"] == "Mount Board"

    asyncio.run(_test())


def test_audit_bom_balance_unambiguous_boolean_and_reason(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # 1. No instruction sets -> bom_equilibrium_balanced = False, reason = "no_instruction_sets"
        orig_side_effect = mock_client._get_all_rows.side_effect
        mock_client._get_all_rows.side_effect = lambda tbl: (
            orig_side_effect("508") if tbl == "508" else (
                orig_side_effect("701") if tbl == "701" else []
            )
        )
        res_no_sets = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-TOP-001"})
        data_no_sets = json.loads(res_no_sets.content[0].text)
        assert data_no_sets["bom_equilibrium_balanced"] is False
        assert data_no_sets["reason"] == "no_instruction_sets"
        assert data_no_sets["instruction_sets_count"] == 0

        # 2. Unbalanced instruction set -> bom_equilibrium_balanced = False, reason = "unbalanced_instruction_sets"
        mock_client._get_all_rows.side_effect = lambda tbl: (
            orig_side_effect("508") if tbl == "508" else (
                orig_side_effect("701") if tbl == "701" else (
                    [
                        {
                            "id": 501,
                            "Parent Item": [{"id": 1}],
                            "Step Order": "1",
                            "Action": "Mount Board",
                            "Set Index": "0",
                            "Toll Map": json.dumps([
                                {"id": 2, "quantity": 1, "toll": True},
                                {"id": 3, "quantity": 1, "toll": True}
                            ])
                        }
                    ] if tbl == "5770" else []
                )
            )
        )
        res_unbalanced = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-TOP-001"})
        data_unbalanced = json.loads(res_unbalanced.content[0].text)
        assert data_unbalanced["bom_equilibrium_balanced"] is False
        assert data_unbalanced["reason"] == "unbalanced_instruction_sets"
        assert len(data_unbalanced["discrepancies"]) > 0

        mock_client._get_all_rows.side_effect = orig_side_effect

    asyncio.run(_test())


def test_find_item_revision_preference(mock_client):
    # 1. Two revisions of one PN (A-001 Rev.A and Rev.B as separate rows, different states).
    # Bare Part Number returns the current revision (Production Use preferred over Finish Stock).
    item_bare = _find_item_by_pn_or_id(mock_client, "A-001")
    assert item_bare is not None
    assert item_bare["id"] == 11
    assert item_bare["Full PN"] == "A-001 Rev.B"
    assert item_bare["Revision"] == "B"
    assert "_ambiguous_matches" in item_bare

    # Exact Full PN match returns the exact revision requested.
    item_rev_a = _find_item_by_pn_or_id(mock_client, "A-001 Rev.A")
    assert item_rev_a is not None
    assert item_rev_a["id"] == 10
    assert item_rev_a["Full PN"] == "A-001 Rev.A"
    assert item_rev_a["Revision"] == "A"

    item_rev_b = _find_item_by_pn_or_id(mock_client, "A-001 Rev.B")
    assert item_rev_b is not None
    assert item_rev_b["id"] == 11
    assert item_rev_b["Full PN"] == "A-001 Rev.B"
    assert item_rev_b["Revision"] == "B"


def test_audit_bom_balance_stale_revision_resolution(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # 2. Stale-revision toll: parent ASY-REV-001 has BOM child Rev.B (id 11, qty 1.0);
        # the WI toll map references Rev.A (id 10, edge_id: None) at the same quantity 1.0.
        res = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-REV-001"})
        data = json.loads(res.content[0].text)

        assert data["bom_equilibrium_balanced"] is True
        assert data["discrepancies"] == []
        assert len(data["stale_revision_references"]) == 1

        stale = data["stale_revision_references"][0]
        assert stale["parent"] == "ASY-REV-001 Rev.A"
        assert stale["bom_child"] == "A-001 Rev.B"
        assert stale["tolled_row"] == "A-001 Rev.A"
        assert stale["part_number"] == "A-001"
        assert stale["quantity"] == 1.0
        assert stale["step_number"] == 1

        assert len(data["sets"]) == 1
        assert data["sets"][0]["is_balanced"] is True
        assert data["sets"][0]["discrepancies"] == []
        assert len(data["sets"][0]["stale_revision_references"]) == 1

    asyncio.run(_test())


def test_audit_bom_balance_genuine_mismatch_and_orphan(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        orig_side_effect = mock_client._get_all_rows.side_effect

        # 3a. Toll quantity differs (required 1.0 vs tolled 2.0)
        mock_client._get_all_rows.side_effect = lambda tbl: (
            orig_side_effect("508") if tbl == "508" else (
                orig_side_effect("701") if tbl == "701" else (
                    [
                        {
                            "id": 601,
                            "Parent Item": [{"id": 20}],
                            "Step Order": "1",
                            "Action": "Mount Sensor",
                            "Set Index": "0",
                            "Photo": [{"url": "http://photo.png"}],
                            "Toll Map": json.dumps([
                                {"edge_id": None, "item_id": 10, "toll": True, "qty": 2.0}
                            ])
                        }
                    ] if tbl == "5770" else []
                )
            )
        )
        res_qty = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-REV-001"})
        data_qty = json.loads(res_qty.content[0].text)
        assert data_qty["bom_equilibrium_balanced"] is False
        assert len(data_qty["discrepancies"]) == 1
        disc = data_qty["discrepancies"][0]
        assert disc["part_id"] == 11
        assert disc["part_number"] == "A-001"
        assert disc["revision"] == "B"
        assert disc["full_pn"] == "A-001 Rev.B"
        assert disc["required_bom_qty"] == 1.0
        assert disc["tolled_wi_qty"] == 2.0
        assert disc["variance"] == 1.0
        assert disc["status"] == "OVER_TOLLED"
        assert len(data_qty["stale_revision_references"]) == 1

        # 3b. Tolled PN is absent from the BOM -> orphan_toll_entry
        mock_client._get_all_rows.side_effect = lambda tbl: (
            orig_side_effect("508") if tbl == "508" else (
                orig_side_effect("701") if tbl == "701" else (
                    [
                        {
                            "id": 601,
                            "Parent Item": [{"id": 20}],
                            "Step Order": "1",
                            "Action": "Mount Sensor",
                            "Set Index": "0",
                            "Photo": [{"url": "http://photo.png"}],
                            "Toll Map": json.dumps([
                                {"edge_id": None, "item_id": 10, "toll": True, "qty": 1.0},
                                {"edge_id": None, "item_id": 999, "toll": True, "qty": 3.0}
                            ])
                        }
                    ] if tbl == "5770" else []
                )
            )
        )
        res_orphan = await server.call_tool("audit_bom_balance", {"part_number_or_id": "ASY-REV-001"})
        data_orphan = json.loads(res_orphan.content[0].text)
        assert data_orphan["bom_equilibrium_balanced"] is False
        orphan_disc = next((d for d in data_orphan["discrepancies"] if d.get("part_id") == 999), None)
        assert orphan_disc is not None
        assert orphan_disc["reason"] == "orphan_toll_entry"
        assert orphan_disc["status"] == "OVER_TOLLED"
        assert orphan_disc["required_bom_qty"] == 0
        assert orphan_disc["tolled_wi_qty"] == 3.0

        mock_client._get_all_rows.side_effect = orig_side_effect

    asyncio.run(_test())


def test_work_instructions_tools(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Get WI
        res_wi = await server.call_tool("get_work_instructions", {"part_number_or_id": "ASY-TOP-001"})
        data_wi = json.loads(res_wi.content[0].text)
        assert len(data_wi["steps"]) == 1
        assert data_wi["steps"][0]["Step Title"] == "Mount Board"

        # Update WI Step
        res_step = await server.call_tool("create_or_update_wi_step", {
            "assembly_pn_or_id": "ASY-TOP-001",
            "step_number": 1,
            "instruction_text": "Updated step instructions",
            "step_title": "Mount PCBA"
        })
        data_step = json.loads(res_step.content[0].text)
        assert "Updated Step #1" in data_step["message"]
        mock_client.update_instruction.assert_called_once()

    asyncio.run(_test())


def test_inventory_summary_tool(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Inventory explosion for 2 units of ASY-TOP-001
        res = await server.call_tool("get_inventory_summary", {
            "part_number_or_id": "ASY-TOP-001",
            "target_build_qty": 2.0
        })
        data = json.loads(res.content[0].text)
        assert data["assembly"]["target_build_qty"] == 2.0
        assert data["total_unique_terminal_parts"] == 2  # 1 blackbox PCBA + 1 screw fastener
        # 2 units * (1 PCBA @ 45 + 4 screws @ 0.10) = 2 * (45 + 0.40) = 90.80
        assert data["total_estimated_unit_bom_cost"] == 90.80

    asyncio.run(_test())


def test_metadata_tools(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Categories
        res_cat = await server.call_tool("list_pn_categories", {})
        data_cat = json.loads(res_cat.content[0].text)
        assert len(data_cat["categories"]) == 2

        # Lifecycle states
        res_states = await server.call_tool("list_item_lifecycle_states", {})
        data_states = json.loads(res_states.content[0].text)
        assert "Production Use" in data_states["lifecycle_states"]

        # Manufacturers and suppliers
        res_mfgs = await server.call_tool("list_manufacturers_and_suppliers", {})
        data_mfgs = json.loads(res_mfgs.content[0].text)
        assert data_mfgs["manufacturers_count"] == 2
        assert data_mfgs["suppliers_count"] == 2

    asyncio.run(_test())


def test_mcp_resources_and_prompts(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Read item resource
        item_res = await server.read_resource("era://items/ASY-TOP-001")
        assert item_res is not None
        item_data = json.loads(item_res[0].content)
        assert item_data["part_number"] == "ASY-TOP-001"

        # Read BOM resource
        bom_res = await server.read_resource("era://bom/ASY-TOP-001")
        bom_data = json.loads(bom_res[0].content)
        assert bom_data["part_number"] == "ASY-TOP-001"

        # Read Categories resource
        cat_res = await server.read_resource("era://categories")
        cat_data = json.loads(cat_res[0].content)
        assert len(cat_data["categories"]) == 2

        # Get prompt
        prompt_res = await server.get_prompt("audit_bom_balance", {"part_number": "ASY-TOP-001"})
        assert prompt_res is not None
        assert "ASY-TOP-001" in prompt_res.messages[0].content.text

    asyncio.run(_test())


def test_start_mcp_background(mock_client):
    with patch("app.mcp_server.run_mcp_sse") as mock_run_sse:
        thread = start_mcp_background(host="127.0.0.1", port=9999, client=mock_client)
        assert thread.name == "ERA-MCP-Server-Thread"


def test_run_cli_mcp_stdio():
    import run
    with patch("sys.argv", ["run.py", "--mcp"]), \
         patch("app.mcp_server.run_mcp_stdio") as mock_stdio:
        run.main()
        mock_stdio.assert_called_once()


def test_run_cli_mcp_sse():
    import run
    from unittest.mock import ANY
    with patch("sys.argv", ["run.py", "--mcp-sse", "--mcp-port", "8888"]), \
         patch("app.mcp_server.run_mcp_sse") as mock_sse:
        run.main()
        mock_sse.assert_called_once_with(host="127.0.0.1", port=8888, auth_token=ANY)


def test_run_cli_default_with_mcp():
    import run
    from unittest.mock import ANY
    mock_app = MagicMock()
    with patch("sys.argv", ["run.py", "--port", "5005"]), \
         patch("app.mcp_server.start_mcp_background") as mock_bg, \
         patch("app.main.create_app", return_value=mock_app):
        run.main()
        mock_bg.assert_called_once_with(host="127.0.0.1", port=8001, auth_token=ANY)
        mock_app.run.assert_called_once()


def test_run_cli_no_mcp_flag():
    import run
    mock_app = MagicMock()
    with patch("sys.argv", ["run.py", "--NoMCP", "--port", "5005"]), \
         patch("app.mcp_server.start_mcp_background") as mock_bg, \
         patch("app.main.create_app", return_value=mock_app):
        run.main()
        mock_bg.assert_not_called()
        mock_app.run.assert_called_once()


def test_metadata_extraction_with_baserow_field_conventions():
    client = MagicMock()
    client.get_items.return_value = [
        {
            "id": 532,
            "Part Number": "55-00013",
            "Full PN": "55-00013 Rev.A",
            "Item description": "Nova Populated Chassis with Screen",
            "Category": "Assemblies & Kits",
            "State": [{"id": 3, "value": "Production Use"}],
            "Price per unit": "0.00",
        }
    ]
    client.get_item.return_value = client.get_items.return_value[0]
    client.search_items.return_value = client.get_items.return_value
    client.get_graph_parents.return_value = []
    client.get_graph_children.return_value = []

    server = create_mcp_server(client)

    async def _test():
        res = await server.call_tool("get_item_details", {"part_number_or_id": "55-00013"})
        data = json.loads(res.content[0].text)
        assert data["part_number"] == "55-00013"
        assert data["name"] == "Nova Populated Chassis with Screen"
        assert data["description"] == "Nova Populated Chassis with Screen"
        assert data["category"] == "Assemblies & Kits"
        assert data["lifecycle_state"] == "Production Use"

        # Search fallback by Item description
        res_search = await server.call_tool("search_items", {"query": "Screen"})
        data_search = json.loads(res_search.content[0].text)
        assert data_search["count"] == 1
        assert data_search["items"][0]["lifecycle_state"] == "Production Use"

    asyncio.run(_test())


def test_mcp_auth_middleware():
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import PlainTextResponse, JSONResponse
    from starlette.testclient import TestClient
    from app.mcp_server import MCPAuthMiddleware

    async def sse_endpoint(request):
        return PlainTextResponse("sse-content")

    async def health_endpoint(request):
        return JSONResponse({"status": "healthy"})

    # 1. Test with auth token enabled
    app = Starlette(routes=[
        Route("/sse", sse_endpoint),
        Route("/health", health_endpoint)
    ])
    app.add_middleware(MCPAuthMiddleware, token="test-secret-token")
    client = TestClient(app)

    # Health is public
    assert client.get("/health").status_code == 200

    # SSE requires token
    assert client.get("/sse").status_code == 401
    assert client.get("/sse", headers={"Authorization": "Bearer wrong-token"}).status_code == 401
    assert client.get("/sse", headers={"X-API-Key": "wrong-token"}).status_code == 401
    assert client.get("/sse?token=wrong-token").status_code == 401

    # Bearer header
    res_bearer = client.get("/sse", headers={"Authorization": "Bearer test-secret-token"})
    assert res_bearer.status_code == 200
    assert res_bearer.text == "sse-content"

    # X-API-Key header
    res_api_key = client.get("/sse", headers={"X-API-Key": "test-secret-token"})
    assert res_api_key.status_code == 200

    # Query param ?token=...
    res_query_token = client.get("/sse?token=test-secret-token")
    assert res_query_token.status_code == 200

    # Query param ?api_key=...
    res_query_api_key = client.get("/sse?api_key=test-secret-token")
    assert res_query_api_key.status_code == 200

    # 2. Test without token (open local mode)
    app_open = Starlette(routes=[Route("/sse", sse_endpoint)])
    app_open.add_middleware(MCPAuthMiddleware, token="")
    client_open = TestClient(app_open)
    assert client_open.get("/sse").status_code == 200


def test_create_mcp_sse_app_with_auth(mock_client):
    from app.mcp_server import create_mcp_sse_app
    server = create_mcp_server(mock_client)
    app = create_mcp_sse_app(server, host="127.0.0.1", auth_token="my-token")
    assert app is not None


def test_run_cli_default_with_mcp_token():
    import run
    mock_app = MagicMock()
    with patch("sys.argv", ["run.py", "--port", "5005", "--mcp-token", "custom-token"]), \
         patch("app.mcp_server.start_mcp_background") as mock_bg, \
         patch("app.main.create_app", return_value=mock_app):
        run.main()
        mock_bg.assert_called_once_with(host="127.0.0.1", port=8001, auth_token="custom-token")
        mock_app.run.assert_called_once()


def test_get_bom_tree_enrichment(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        res = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001"})
        data = json.loads(res.content[0].text)

        # Root node
        assert data["part_number"] == "ASY-TOP-001"
        assert data["blackbox"] is False
        assert data["purchase_kit"] is False
        assert data["has_children"] is True
        assert data["has_instructions"] is True

        # Children
        children = data["children"]
        assert len(children) == 2

        pcba = next(c for c in children if c["part_number"] == "EL-PCBA-001")
        assert pcba["blackbox"] is True
        assert pcba["purchase_kit"] is True
        assert pcba["has_children"] is False
        assert pcba["has_instructions"] is False

        screw = next(c for c in children if c["part_number"] == "ME-FAST-001")
        assert screw["blackbox"] is False
        assert screw["purchase_kit"] is False
        assert screw["has_children"] is False
        assert screw["has_instructions"] is False

    asyncio.run(_test())


def test_get_bom_tree_compact_projection(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        res = await server.call_tool("get_bom_tree", {
            "part_number_or_id": "ASY-TOP-001",
            "compact": True
        })
        data = json.loads(res.content[0].text)

        # Core fields must be present
        expected_keys = {
            "id", "part_number", "name", "description", "state",
            "quantity", "blackbox", "purchase_kit", "has_children", "has_instructions", "children"
        }
        for k in expected_keys:
            assert k in data, f"Key '{k}' missing from compact node"

        # Heavy metadata must NOT be present
        forbidden_keys = {"edge_id", "uom_id", "search_helper", "pcb_symbol", "parent_id", "external_pn", "notes"}
        for k in forbidden_keys:
            assert k not in data, f"Heavy key '{k}' unexpectedly present in compact node"

        # Check child node
        child = data["children"][0]
        for k in expected_keys:
            assert k in child
        for k in forbidden_keys:
            assert k not in child

    asyncio.run(_test())


def test_get_bom_tree_max_nodes_capping(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # 1. max_nodes = 1: Capped to root only
        res_cap1 = await server.call_tool("get_bom_tree", {
            "part_number_or_id": "ASY-TOP-001",
            "max_nodes": 1
        })
        data_cap1 = json.loads(res_cap1.content[0].text)
        assert data_cap1["truncated"] is True
        assert data_cap1["node_count"] == 1
        assert len(data_cap1["children"]) == 0
        assert data_cap1["has_children"] is True  # still knows it has children!

        # 2. max_nodes = 2: Root + 1 child
        res_cap2 = await server.call_tool("get_bom_tree", {
            "part_number_or_id": "ASY-TOP-001",
            "max_nodes": 2
        })
        data_cap2 = json.loads(res_cap2.content[0].text)
        assert data_cap2["truncated"] is True
        assert data_cap2["node_count"] == 2
        assert len(data_cap2["children"]) == 1

        # 3. max_nodes = 10: Not truncated (tree has 3 nodes)
        res_cap10 = await server.call_tool("get_bom_tree", {
            "part_number_or_id": "ASY-TOP-001",
            "max_nodes": 10
        })
        data_cap10 = json.loads(res_cap10.content[0].text)
        assert data_cap10["truncated"] is False
        assert data_cap10["node_count"] == 3
        assert len(data_cap10["children"]) == 2

        # 4. max_nodes = 0: Backwards compatible, no truncated/node_count keys
        res_default = await server.call_tool("get_bom_tree", {
            "part_number_or_id": "ASY-TOP-001",
            "max_nodes": 0
        })
        data_default = json.loads(res_default.content[0].text)
        assert "truncated" not in data_default
        assert "node_count" not in data_default

    asyncio.run(_test())


def test_find_assemblies_missing_instructions_empty_when_all_covered(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # In standard mock_client: ASY-TOP-001 has instructions, PCBA is blackbox, Screw has no children
        res = await server.call_tool("find_assemblies_missing_instructions", {
            "part_number_or_id": "ASY-TOP-001"
        })
        data = json.loads(res.content[0].text)
        assert data["count"] == 0
        assert data["assemblies"] == []

    asyncio.run(_test())


def test_find_assemblies_missing_instructions_multitier():
    async def _test():
        client = MagicMock()
        client.table_bom = "508"
        client.table_assembly = "701"
        client.table_instructions = "5770"

        # Tree structure:
        # 80-00000 (id 100, has instructions, non-blackbox)
        #   ├── 55-00003 (id 101, NO instructions, non-blackbox) -> MATCH! depth 1
        #   │     ├── 20-00001 (id 201, leaf part)
        #   │     └── 50-00005 (id 102, NO instructions, non-blackbox) -> MATCH! depth 2
        #   │           └── 10-00001 (id 202, leaf part)
        #   ├── 55-00015 (id 103, HAS instructions, non-blackbox)
        #   │     └── 55-00016 (id 104, NO instructions, non-blackbox) -> MATCH! depth 2
        #   │           └── 20-00002 (id 203, leaf part)
        #   ├── 55-00020 (id 105, blackbox=True, has children) -> EXCLUDED, subtree NOT traversed!
        #   │     └── 20-00099 (id 204, leaf part)
        #   └── 20-00010 (id 205, leaf part)
        mock_tree = [
            {
                "id": 100,
                "part_number": "80-00000",
                "name": "Nova Main Console",
                "revision": "A",
                "children": [
                    {
                        "id": 101,
                        "part_number": "55-00003",
                        "name": "Nova Logo Light Fixture Assembly",
                        "revision": "B",
                        "children": [
                            {"id": 201, "part_number": "20-00001", "name": "Screw M2", "children": []},
                            {
                                "id": 102,
                                "part_number": "50-00005",
                                "name": "Light Cable Subassembly",
                                "revision": "1",
                                "children": [
                                    {"id": 202, "part_number": "10-00001", "name": "Wire red", "children": []}
                                ]
                            }
                        ]
                    },
                    {
                        "id": 103,
                        "part_number": "55-00015",
                        "name": "Umbilical Cord Assembly",
                        "revision": "A",
                        "children": [
                            {
                                "id": 104,
                                "part_number": "55-00016",
                                "name": "Umbilical Inner Core",
                                "revision": "C",
                                "children": [
                                    {"id": 203, "part_number": "20-00002", "name": "Connector 12p", "children": []}
                                ]
                            }
                        ]
                    },
                    {
                        "id": 105,
                        "part_number": "55-00020",
                        "name": "Sealed Power Supply Unit",
                        "revision": "1",
                        "children": [
                            {"id": 204, "part_number": "20-00099", "name": "Internal Cap", "children": []}
                        ]
                    },
                    {"id": 205, "part_number": "20-00010", "name": "Chassis Bumper", "children": []}
                ]
            }
        ]

        bom_items = [
            {"id": 100, "Part Number": "80-00000", "Name": "Nova Main Console", "Revision": "A", "Blackbox": False},
            {"id": 101, "Part Number": "55-00003", "Name": "Nova Logo Light Fixture Assembly", "Revision": "B", "Blackbox": False},
            {"id": 102, "Part Number": "50-00005", "Name": "Light Cable Subassembly", "Revision": "1", "Blackbox": False},
            {"id": 103, "Part Number": "55-00015", "Name": "Umbilical Cord Assembly", "Revision": "A", "Blackbox": False},
            {"id": 104, "Part Number": "55-00016", "Name": "Umbilical Inner Core", "Revision": "C", "Blackbox": False},
            {"id": 105, "Part Number": "55-00020", "Name": "Sealed Power Supply Unit", "Revision": "1", "Blackbox": True},
            {"id": 201, "Part Number": "20-00001", "Name": "Screw M2", "Blackbox": False},
            {"id": 202, "Part Number": "10-00001", "Name": "Wire red", "Blackbox": False},
            {"id": 203, "Part Number": "20-00002", "Name": "Connector 12p", "Blackbox": False},
            {"id": 204, "Part Number": "20-00099", "Name": "Internal Cap", "Blackbox": False},
            {"id": 205, "Part Number": "20-00010", "Name": "Chassis Bumper", "Blackbox": False},
        ]

        # Only 100 and 103 have instructions
        instruction_rows = [
            {"id": 1, "Parent Item": [{"id": 100}]},
            {"id": 2, "Parent Item": [{"id": 103}]}
        ]

        client.get_bom_tree.return_value = mock_tree
        client.get_items.return_value = bom_items
        client.get_item.side_effect = lambda iid: next((x for x in bom_items if x["id"] == iid), None)
        client._get_all_rows.side_effect = lambda tbl: (
            bom_items if tbl == "508" else (
                instruction_rows if tbl == "5770" else []
            )
        )

        server = create_mcp_server(client)

        res = await server.call_tool("find_assemblies_missing_instructions", {
            "part_number_or_id": "80-00000",
            "max_depth": 10
        })
        data = json.loads(res.content[0].text)
        assert data["count"] == 3

        pns = [a["part_number"] for a in data["assemblies"]]
        assert pns == ["55-00003", "50-00005", "55-00016"]

        # Check fields on each result
        a1 = next(a for a in data["assemblies"] if a["part_number"] == "55-00003")
        assert a1["name"] == "Nova Logo Light Fixture Assembly"
        assert a1["revision"] == "B"
        assert a1["id"] == 101
        assert a1["depth"] == 1

        a2 = next(a for a in data["assemblies"] if a["part_number"] == "50-00005")
        assert a2["depth"] == 2
        assert a2["revision"] == "1"

        a3 = next(a for a in data["assemblies"] if a["part_number"] == "55-00016")
        assert a3["depth"] == 2
        assert a3["revision"] == "C"

        # Verify blackbox item 105 and its child 204 are excluded
        assert "55-00020" not in pns
        assert "20-00099" not in pns

        # Test error for unknown PN
        res_err = await server.call_tool("find_assemblies_missing_instructions", {
            "part_number_or_id": "DOES-NOT-EXIST"
        })
        data_err = json.loads(res_err.content[0].text)
        assert "error" in data_err

    asyncio.run(_test())


def test_get_item_details_child_components_description(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        res = await server.call_tool("get_item_details", {"part_number_or_id": "ASY-TOP-001"})
        data = json.loads(res.content[0].text)
        assert data["child_components_count"] == 2
        assert "child_components_description" in data
        assert "Raw count of direct assembly table edges" in data["child_components_description"]

    asyncio.run(_test())


def test_get_bom_tree_problems_count_null(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Full mode: problems_count must be null (None), not false 0
        res_full = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001", "compact": False})
        data_full = json.loads(res_full.content[0].text)
        assert data_full.get("problems_count") is None

        # Compact mode: problems_count must be dropped
        res_compact = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001", "compact": True})
        data_compact = json.loads(res_compact.content[0].text)
        assert "problems_count" not in data_compact

    asyncio.run(_test())


def test_create_or_update_wi_step_step_order_matching(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Step Order in existing steps is string "1"
        mock_client.get_instruction_set_details.return_value = {
            "steps": [
                {
                    "id": 501,
                    "step_order": "1",
                    "action": "Mount Board",
                    "description": "Old text"
                }
            ]
        }

        res = await server.call_tool("create_or_update_wi_step", {
            "assembly_pn_or_id": "ASY-TOP-001",
            "step_number": 1,
            "instruction_text": "Updated step text",
            "step_title": "Mount Board"
        })
        data = json.loads(res.content[0].text)
        assert "Updated Step #1" in data["message"]
        mock_client.update_instruction.assert_called_once()
        args, kwargs = mock_client.update_instruction.call_args
        assert args[0] == 501
        assert args[1]["Step Order"] == 1
        assert args[1]["Description"] == "Updated step text"
        assert args[1]["Action"] == "Mount Board"

    asyncio.run(_test())


def test_get_bom_tree_duplicate_edge_combining():
    from unittest.mock import patch
    from app.baserow_client import BaserowClient

    mock_bom = [
        {"id": 1, "Part Number": "55-00014", "Description": "Housing Assy"},
        {"id": 2, "Part Number": "20-00027", "Description": "Magnet", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 3, "Part Number": "10-00023", "Description": "Wire", "Consumption UoM": [{"id": 4, "value": "Millimeter"}]},
        {"id": 4, "Part Number": "40-00001", "Description": "Single Part", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
    ]
    mock_assembly = [
        # 55-00014 -> 20-00027 (2 count edges: 14 + 14)
        {"id": 149, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 152, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        # 55-00014 -> 10-00023 (2 dimensional edges: 40mm and 400mm)
        {"id": 758, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 1, "Measurement": 40.0, "PCB Symbol": ""},
        {"id": 759, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 1, "Measurement": 400.0, "PCB Symbol": ""},
        # 55-00014 -> 40-00001 (single count edge: 1 pcs)
        {"id": 800, "Item": [{"id": 1}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R1"},
    ]

    with patch.object(BaserowClient, "_get_all_rows") as mock_rows:
        mock_rows.side_effect = lambda tbl, *args, **kwargs: mock_bom if str(tbl) in ("508", "mock_bom") else (mock_assembly if str(tbl) in ("701", "mock_assembly") else [])
        client = BaserowClient()
        client.table_bom = "508"
        client.table_assembly = "701"
        tree = client.get_bom_tree()

        assert len(tree) == 1
        root = tree[0]
        children = root["children"]
        assert len(children) == 4

        # Combined count-measured node for 20-00027
        magnet = next(c for c in children if c["part_number"] == "20-00027")
        assert magnet["quantity"] == 28
        assert magnet["quantity_label"] == "28 pcs"
        assert magnet["edge_id"] == 149
        assert magnet["edge_ids"] == [149, 152]

        # Kept separate dimensional nodes for 10-00023
        wires = [c for c in children if c["part_number"] == "10-00023"]
        assert len(wires) == 2
        assert wires[0]["length"] == 40.0
        assert wires[0]["edge_id"] == 758
        assert "edge_ids" not in wires[0]
        assert wires[1]["length"] == 400.0
        assert wires[1]["edge_id"] == 759
        assert "edge_ids" not in wires[1]

        # Single count edge for 40-00001
        single = next(c for c in children if c["part_number"] == "40-00001")
        assert single["quantity"] == 1
        assert single["edge_id"] == 800
        assert "edge_ids" not in single


def test_scan_bom_duplicates_classification():
    from unittest.mock import MagicMock
    from app.mcp_server import create_mcp_server

    mock_client = MagicMock()
    mock_client.table_bom = "508"
    mock_client.table_assembly = "701"

    mock_bom = [
        {"id": 1, "Part Number": "55-00014", "Description": "Housing Assy"},
        {"id": 2, "Part Number": "20-00027", "Description": "Magnet", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 3, "Part Number": "50-00007", "Description": "Board Assy"},
        {"id": 4, "Part Number": "40-00097", "Description": "Resistor", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 5, "Part Number": "50-00027", "Description": "Cable Assy"},
        {"id": 6, "Part Number": "10-00023", "Description": "Wire", "Consumption UoM": [{"id": 4, "value": "Millimeter"}]},
        {"id": 7, "Part Number": "40-00001", "Description": "Single Part", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
    ]
    mock_assembly = [
        # 1 -> 2: true_duplicate (2 count edges, no designators, 14 + 14 = 28)
        {"id": 149, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 152, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        # 3 -> 4: placement_split (2 edges, designators R5, R6)
        {"id": 100, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R5"},
        {"id": 101, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R6"},
        # 5 -> 6: distinct_measure (2 edges: 40mm and 400mm)
        {"id": 758, "Item": [{"id": 5}], "Contains": [{"id": 6}], "Amount of Times": 1, "Measurement": 40.0, "PCB Symbol": ""},
        {"id": 759, "Item": [{"id": 5}], "Contains": [{"id": 6}], "Amount of Times": 1, "Measurement": 400.0, "PCB Symbol": ""},
        # 1 -> 7: single-edge child (should be ignored by duplicate scanner)
        {"id": 800, "Item": [{"id": 1}], "Contains": [{"id": 7}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": ""},
    ]

    mock_client._get_all_rows.side_effect = lambda tbl: mock_bom if str(tbl) in ("508", "mock_bom") else (mock_assembly if str(tbl) in ("701", "mock_assembly") else [])

    async def _test():
        server = create_mcp_server(mock_client)
        res = await server.call_tool("scan_bom_duplicates", {"apply": False})
        data = json.loads(res.content[0].text)

        assert data["totals"]["true_duplicate"] == 1
        assert data["totals"]["placement_split"] == 1
        assert data["totals"]["distinct_measure"] == 1
        assert data["totals"]["total"] == 3

        groups = data["groups"]
        assert len(groups) == 3

        # Group 1: 50-00007 -> 40-00097 (placement_split)
        g_split = next(g for g in groups if g["parent_pn"] == "50-00007" and g["child_pn"] == "40-00097")
        assert g_split["classification"] == "placement_split"
        assert g_split["action"] == "merge"
        assert g_split["sum_qty"] == 2
        assert g_split["designators"] == ["R5", "R6"]
        assert len(g_split["edges"]) == 2

        # Group 2: 50-00027 -> 10-00023 (distinct_measure)
        g_measure = next(g for g in groups if g["parent_pn"] == "50-00027" and g["child_pn"] == "10-00023")
        assert g_measure["classification"] == "distinct_measure"
        assert g_measure["action"] == "keep_separate"
        assert g_measure["sum_qty"] == 2
        assert len(g_measure["edges"]) == 2

        # Group 3: 55-00014 -> 20-00027 (true_duplicate)
        g_dup = next(g for g in groups if g["parent_pn"] == "55-00014" and g["child_pn"] == "20-00027")
        assert g_dup["classification"] == "true_duplicate"
        assert g_dup["action"] == "merge"
        assert g_dup["sum_qty"] == 28
        assert g_dup["designators"] == []
        assert len(g_dup["edges"]) == 2

        # Verify single edge 40-00001 was ignored
        assert not any(g["child_pn"] == "40-00001" for g in groups)

    asyncio.run(_test())


def test_scan_bom_duplicates_subtree_filter():
    from unittest.mock import MagicMock
    from app.mcp_server import create_mcp_server

    mock_client = MagicMock()
    mock_client.table_bom = "508"
    mock_client.table_assembly = "701"

    mock_bom = [
        {"id": 1, "Part Number": "55-00014", "Description": "Housing Assy"},
        {"id": 2, "Part Number": "20-00027", "Description": "Magnet", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 3, "Part Number": "50-00007", "Description": "Board Assy"},
        {"id": 4, "Part Number": "40-00097", "Description": "Resistor", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
    ]
    mock_assembly = [
        {"id": 149, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 152, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 100, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R5"},
        {"id": 101, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R6"},
    ]

    mock_client._get_all_rows.side_effect = lambda tbl: mock_bom if str(tbl) in ("508", "mock_bom") else (mock_assembly if str(tbl) in ("701", "mock_assembly") else [])

    async def _test():
        server = create_mcp_server(mock_client)
        res = await server.call_tool("scan_bom_duplicates", {"part_number_or_id": "55-00014", "apply": False})
        data = json.loads(res.content[0].text)

        assert data["totals"]["total"] == 1
        assert data["totals"]["true_duplicate"] == 1
        assert data["totals"]["placement_split"] == 0
        assert len(data["groups"]) == 1
        assert data["groups"][0]["parent_pn"] == "55-00014"
        assert data["groups"][0]["child_pn"] == "20-00027"

    asyncio.run(_test())


def test_scan_bom_duplicates_apply():
    from unittest.mock import MagicMock
    from app.mcp_server import create_mcp_server

    mock_client = MagicMock()
    mock_client.table_bom = "508"
    mock_client.table_assembly = "701"

    mock_bom = [
        {"id": 1, "Part Number": "55-00014", "Description": "Housing Assy"},
        {"id": 2, "Part Number": "20-00027", "Description": "Magnet", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 3, "Part Number": "50-00007", "Description": "Board Assy"},
        {"id": 4, "Part Number": "40-00097", "Description": "Resistor", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
        {"id": 5, "Part Number": "50-00027", "Description": "Cable Assy"},
        {"id": 6, "Part Number": "10-00023", "Description": "Wire", "Consumption UoM": [{"id": 4, "value": "Millimeter"}]},
    ]

    table_assembly_state = [
        # True duplicate (149, 152) -> lowest 149, sum 28
        {"id": 149, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 152, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        # Placement split (100, 101) -> lowest 100, sum 2, designators "R5, R6"
        {"id": 100, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R5"},
        {"id": 101, "Item": [{"id": 3}], "Contains": [{"id": 4}], "Amount of Times": 1, "Measurement": 0, "PCB Symbol": "R6"},
        # Distinct measure (758, 759) -> MUST NOT BE TOUCHED
        {"id": 758, "Item": [{"id": 5}], "Contains": [{"id": 6}], "Amount of Times": 1, "Measurement": 40.0, "PCB Symbol": ""},
        {"id": 759, "Item": [{"id": 5}], "Contains": [{"id": 6}], "Amount of Times": 1, "Measurement": 400.0, "PCB Symbol": ""},
    ]

    mock_client._get_all_rows.side_effect = lambda tbl: mock_bom if str(tbl) in ("508", "mock_bom") else list(table_assembly_state)

    def mock_update_assembly(edge_id, quantity=None, pcb_symbol=None, **kwargs):
        for row in table_assembly_state:
            if row["id"] == edge_id:
                if quantity is not None:
                    row["Amount of Times"] = quantity
                if pcb_symbol is not None:
                    row["PCB Symbol"] = pcb_symbol
                return row
        return {}

    def mock_delete_assembly(edge_id):
        nonlocal table_assembly_state
        table_assembly_state = [r for r in table_assembly_state if r["id"] != edge_id]

    mock_client.update_assembly.side_effect = mock_update_assembly
    mock_client.delete_assembly.side_effect = mock_delete_assembly

    async def _test():
        server = create_mcp_server(mock_client)
        res = await server.call_tool("scan_bom_duplicates", {"apply": True})
        data = json.loads(res.content[0].text)

        assert "verified" in data
        verified = data["verified"]
        assert len(verified) == 2

        v1 = next(v for v in verified if v["parent_pn"] == "55-00014" and v["child_pn"] == "20-00027")
        assert v1["status"] == "verified"
        assert v1["surviving_edge_id"] == 149
        assert v1["deleted_edge_ids"] == [152]
        assert v1["pre_sum_qty"] == 28
        assert v1["post_sum_qty"] == 28
        assert v1["merged_group_gone"] is True
        assert v1["quantity_unchanged"] is True

        v2 = next(v for v in verified if v["parent_pn"] == "50-00007" and v["child_pn"] == "40-00097")
        assert v2["status"] == "verified"
        assert v2["surviving_edge_id"] == 100
        assert v2["deleted_edge_ids"] == [101]
        assert v2["pre_sum_qty"] == 2
        assert v2["post_sum_qty"] == 2
        assert v2["merged_group_gone"] is True
        assert v2["quantity_unchanged"] is True

        # Distinct measure group (758, 759) must NOT be modified or deleted
        assert not any(v["parent_pn"] == "50-00027" for v in verified)
        remaining_ids = [r["id"] for r in table_assembly_state]
        assert 758 in remaining_ids
        assert 759 in remaining_ids

        # Surviving edges check in state
        surviving_149 = next(r for r in table_assembly_state if r["id"] == 149)
        assert surviving_149["Amount of Times"] == 28
        assert surviving_149["PCB Symbol"] == "N/A"

        surviving_100 = next(r for r in table_assembly_state if r["id"] == 100)
        assert surviving_100["Amount of Times"] == 2
        assert surviving_100["PCB Symbol"] == "R5, R6"

        assert 152 not in remaining_ids
        assert 101 not in remaining_ids

    asyncio.run(_test())


def test_scan_bom_duplicates_apply_fail_closed():
    from unittest.mock import MagicMock
    from app.mcp_server import create_mcp_server

    mock_client = MagicMock()
    mock_client.table_bom = "508"
    mock_client.table_assembly = "701"

    mock_bom = [
        {"id": 1, "Part Number": "55-00014", "Description": "Housing Assy"},
        {"id": 2, "Part Number": "20-00027", "Description": "Magnet", "Consumption UoM": [{"id": 3, "value": "Piece"}]},
    ]
    mock_assembly = [
        {"id": 149, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
        {"id": 152, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 14, "Measurement": 0, "PCB Symbol": ""},
    ]

    mock_client._get_all_rows.side_effect = lambda tbl: mock_bom if str(tbl) in ("508", "mock_bom") else list(mock_assembly)
    mock_client.update_assembly.side_effect = RuntimeError("Baserow connection error")

    async def _test():
        server = create_mcp_server(mock_client)
        res = await server.call_tool("scan_bom_duplicates", {"apply": True})
        data = json.loads(res.content[0].text)

        assert "verified" in data
        assert len(data["verified"]) == 1
        assert data["verified"][0]["status"] == "failed"
        assert "Baserow connection error" in data["verified"][0]["error"]

    asyncio.run(_test())


def test_get_bom_tree_converted_dimensional_grouping():
    from unittest.mock import patch
    from app.baserow_client import BaserowClient

    mock_bom = [
        {"id": 1, "Part Number": "50-00027", "Description": "Cable Assy"},
        {"id": 2, "Part Number": "10-00000", "Description": "Equal Length Wire", "Consumption UoM": [{"id": 4, "value": "Millimeter"}]},
        {"id": 3, "Part Number": "10-00023", "Description": "Different Length Wire", "Consumption UoM": [{"id": 4, "value": "Millimeter"}]},
    ]
    mock_assembly = [
        # 50-00027 -> 10-00000: edge 1 is 100 cm (mult 10 -> 1000mm), edge 2 is 1 m (mult 1000 -> 1000mm)
        {"id": 101, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 1, "Measurement": 100.0, "Measurement UoM": [{"id": 5, "value": "Centimeter"}], "PCB Symbol": ""},
        {"id": 102, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 2, "Measurement": 1.0, "Measurement UoM": [{"id": 6, "value": "Meter"}], "PCB Symbol": ""},
        # 50-00027 -> 10-00023: differing lengths 40 mm and 400 mm
        {"id": 758, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 1, "Measurement": 40.0, "Measurement UoM": [{"id": 4, "value": "Millimeter"}], "PCB Symbol": ""},
        {"id": 759, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 1, "Measurement": 400.0, "Measurement UoM": [{"id": 4, "value": "Millimeter"}], "PCB Symbol": ""},
    ]

    with patch.object(BaserowClient, "_get_all_rows") as mock_rows:
        mock_rows.side_effect = lambda tbl, *args, **kwargs: mock_bom if str(tbl) in ("508", "mock_bom") else (mock_assembly if str(tbl) in ("701", "mock_assembly") else [])
        client = BaserowClient()
        client.table_bom = "508"
        client.table_assembly = "701"
        tree = client.get_bom_tree()

        assert len(tree) == 1
        root = tree[0]
        children = root["children"]
        assert len(children) == 3

        # Combined dimensional node for 10-00000: 100 cm == 1 m == 1000 mm, qty 1 + 2 = 3
        wire_eq = next(c for c in children if c["part_number"] == "10-00000")
        assert wire_eq["quantity"] == 3
        assert wire_eq["length"] == 1000.0
        assert wire_eq["uom"] == "mm"
        assert wire_eq["quantity_label"] == "3 x 1000mm"
        assert wire_eq["edge_id"] == 101
        assert wire_eq["edge_ids"] == [101, 102]

        # Separate dimensional nodes for 10-00023: 40 mm and 400 mm
        wires_diff = [c for c in children if c["part_number"] == "10-00023"]
        assert len(wires_diff) == 2
        assert wires_diff[0]["length"] == 40.0
        assert wires_diff[0]["edge_id"] == 758
        assert "edge_ids" not in wires_diff[0]
        assert "pcb_symbols" not in wires_diff[0]

        assert wires_diff[1]["length"] == 400.0
        assert wires_diff[1]["edge_id"] == 759
        assert "edge_ids" not in wires_diff[1]
        assert "pcb_symbols" not in wires_diff[1]


def test_inventory_summary_collapsed_revisions(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        orig_side_effect = mock_client._get_all_rows.side_effect

        # Assembly 20 contains:
        # - A-001 Rev.B (id 11, Production Use, $12) with qty 3
        # - A-001 Rev.A (id 10, Finish Stock, $10) with qty 2
        # - ME-FAST-001 (id 3, $0.10) with qty 5
        mock_client._get_all_rows.side_effect = lambda tbl: (
            orig_side_effect("508") if tbl == "508" else (
                [
                    {"id": 201, "Item": [{"id": 20}], "Contains": [{"id": 11}], "Amount of Times": 3, "Quantity": 3},
                    {"id": 202, "Item": [{"id": 20}], "Contains": [{"id": 10}], "Amount of Times": 2, "Quantity": 2},
                    {"id": 203, "Item": [{"id": 20}], "Contains": [{"id": 3}], "Amount of Times": 5, "Quantity": 5},
                ] if tbl == "701" else orig_side_effect(tbl)
            )
        )

        res = await server.call_tool("get_inventory_summary", {
            "part_number_or_id": "ASY-REV-001",
            "target_build_qty": 1.0
        })
        data = json.loads(res.content[0].text)

        # Total unique PNs should be 2: A-001 and ME-FAST-001
        assert data["total_unique_terminal_parts"] == 2
        parts = data["required_parts"]
        assert len(parts) == 2

        # A-001 must be collapsed into 1 line, choosing current revision (Rev.B, id 11)
        a001_line = next(p for p in parts if p["part_number"] == "A-001")
        assert a001_line["part_id"] == 11
        assert a001_line["required_quantity"] == 5.0  # 3 + 2
        assert a001_line["unit_price"] == 12.0
        assert a001_line["subtotal_cost"] == 60.0
        assert a001_line["collapsed_revisions"] == ["A-001 Rev.B", "A-001 Rev.A"]

        # Fastener line must NOT have collapsed_revisions
        fast_line = next(p for p in parts if p["part_number"] == "ME-FAST-001")
        assert fast_line["part_id"] == 3
        assert fast_line["required_quantity"] == 5.0
        assert fast_line["unit_price"] == 0.10
        assert fast_line["subtotal_cost"] == 0.50
        assert "collapsed_revisions" not in fast_line

        # Total cost computed from collapsed lines: 60.0 + 0.50 = 60.50
        assert data["total_estimated_unit_bom_cost"] == 60.50

        mock_client._get_all_rows.side_effect = orig_side_effect

    asyncio.run(_test())


def test_problem_scanner_stale_revision_rule(monkeypatch):
    from app.baserow_client import ProblemScanner, BaserowClient, evaluate_condition
    import time

    # 1. Test evaluate_condition with has_stale_revision and aliases
    row = {"id": 1, "Part Number": "TEST-01"}
    for alias in ("has_stale_revision", "Has Stale Revision", "has_stale_revision_refs", "stale_revision"):
        cond = {"field": alias, "operator": "equals", "value": "true"}
        assert evaluate_condition(row, cond, has_children=True, has_stale_revision=True) is True
        assert evaluate_condition(row, cond, has_children=True, has_stale_revision=False) is False
        assert evaluate_condition(row, cond, has_children=False, has_stale_revision=False) is False

    # 2. Test ProblemScanner scan with real definition
    client = BaserowClient()
    orig_sleep = time.sleep
    monkeypatch.setattr("app.baserow_client.time.sleep", lambda x: None)

    # 3 assemblies:
    # - 100: Clean top assembly (contains subassembly 200, which has instructions)
    # - 200: Subassembly with stale WI toll (BOM child is A-001 Rev.B (id 11), toll is A-001 Rev.A (id 10))
    # - 300: Subassembly with stale BOM edge (BOM child is A-001 Rev.A (id 10))
    # Terminal items:
    # - 10: A-001 Rev.A (Finish Stock)
    # - 11: A-001 Rev.B (Production Use -> current)
    # - 2: PCBA-001 (Production Use)
    bom_rows = [
        {"id": 100, "Part Number": "ASY-TOP", "Full PN": "ASY-TOP Rev.A", "State": {"value": "Production Use"}},
        {"id": 200, "Part Number": "ASY-STALE-TOLL", "Full PN": "ASY-STALE-TOLL Rev.A", "State": {"value": "Production Use"}},
        {"id": 300, "Part Number": "ASY-STALE-EDGE", "Full PN": "ASY-STALE-EDGE Rev.A", "State": {"value": "Production Use"}},
        {"id": 10, "Part Number": "A-001", "Revision": "A", "Full PN": "A-001 Rev.A", "State": {"value": "Finish Stock"}},
        {"id": 11, "Part Number": "A-001", "Revision": "B", "Full PN": "A-001 Rev.B", "State": {"value": "Production Use"}},
        {"id": 2, "Part Number": "PCBA-001", "Revision": "1", "Full PN": "PCBA-001 Rev.1", "State": {"value": "Production Use"}},
    ]

    assembly_rows = [
        # 100 contains 200 (qty 1) and 2 (qty 1)
        {"id": 1, "Item": [{"id": 100}], "Contains": [{"id": 200}], "Amount of Times": 1},
        {"id": 2, "Item": [{"id": 100}], "Contains": [{"id": 2}], "Amount of Times": 1},
        # 200 contains 11 (qty 1)
        {"id": 3, "Item": [{"id": 200}], "Contains": [{"id": 11}], "Amount of Times": 1},
        # 300 contains 10 (qty 1) -> Stale BOM edge (10 is Rev.A, current is Rev.B)
        {"id": 4, "Item": [{"id": 300}], "Contains": [{"id": 10}], "Amount of Times": 1},
    ]

    instruction_rows = [
        # 100 instructions: clean toll to 200 and 2
        {
            "id": 1001,
            "Parent Item": [{"id": 100}],
            "Set Index": 1,
            "Photo": [{"url": "http://photo.png"}],
            "Toll Map": json.dumps([
                {"edge_id": 1, "item_id": 200, "toll": True, "qty": 1.0},
                {"edge_id": 2, "item_id": 2, "toll": True, "qty": 1.0},
            ])
        },
        # 200 instructions: stale toll to 10 (Rev.A) while BOM requires 11 (Rev.B)
        {
            "id": 2001,
            "Parent Item": [{"id": 200}],
            "Set Index": 1,
            "Photo": [{"url": "http://photo.png"}],
            "Toll Map": json.dumps([
                {"edge_id": None, "item_id": 10, "toll": True, "qty": 1.0}
            ])
        },
        # 300 instructions: toll to 10
        {
            "id": 3001,
            "Parent Item": [{"id": 300}],
            "Set Index": 1,
            "Photo": [{"url": "http://photo.png"}],
            "Toll Map": json.dumps([
                {"edge_id": 4, "item_id": 10, "toll": True, "qty": 1.0}
            ])
        }
    ]

    def mock_get_all_rows(table_id, params=None):
        if str(table_id) == str(client.table_bom):
            return bom_rows
        elif str(table_id) == str(client.table_assembly):
            return assembly_rows
        elif str(table_id) == str(client.table_instructions):
            return instruction_rows
        return []

    monkeypatch.setattr(client, "_get_all_rows", mock_get_all_rows)

    scanner = ProblemScanner()
    defs = [
        {
            "id": "stale_revision_reference",
            "name": "Stale Revision Reference",
            "rule": {"field": "has_stale_revision", "operator": "equals", "value": "true"}
        }
    ]
    monkeypatch.setattr(scanner, "load_definitions", lambda: defs)
    scanner.start_scan(client)
    if scanner.thread:
        scanner.thread.join(timeout=5.0)

    assert scanner.status == "completed"

    # ASY-STALE-TOLL (id 200) has stale WI toll -> Stale Revision Reference
    assert "Stale Revision Reference" in scanner.problems.get(200, [])

    # ASY-STALE-EDGE (id 300) has stale BOM edge -> Stale Revision Reference
    assert "Stale Revision Reference" in scanner.problems.get(300, [])

    # ASY-TOP (id 100) is clean in its assembly scope -> NO Stale Revision Reference
    assert "Stale Revision Reference" not in scanner.problems.get(100, [])


def test_purchase_kit_surface(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # 1. get_item_details
        res_kit = await server.call_tool("get_item_details", {"part_number_or_id": "EL-PCBA-001"})
        data_kit = json.loads(res_kit.content[0].text)
        assert data_kit["purchase_kit"] is True

        res_non_kit = await server.call_tool("get_item_details", {"part_number_or_id": "ASY-TOP-001"})
        data_non_kit = json.loads(res_non_kit.content[0].text)
        assert data_non_kit["purchase_kit"] is False

        # 2. get_bom_tree (root + at least one child)
        # Root ASY-TOP-001 (not kit) with child EL-PCBA-001 (kit) and ME-FAST-001 (not kit)
        res_tree = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001"})
        data_tree = json.loads(res_tree.content[0].text)
        assert data_tree["purchase_kit"] is False
        assert len(data_tree["children"]) >= 2
        child_kit = next(c for c in data_tree["children"] if c["part_number"] == "EL-PCBA-001")
        assert child_kit["purchase_kit"] is True
        child_non_kit = next(c for c in data_tree["children"] if c["part_number"] == "ME-FAST-001")
        assert child_non_kit["purchase_kit"] is False

        # Root as a purchase kit
        res_tree_root_kit = await server.call_tool("get_bom_tree", {"part_number_or_id": "EL-PCBA-001"})
        data_tree_root_kit = json.loads(res_tree_root_kit.content[0].text)
        assert data_tree_root_kit["purchase_kit"] is True

        # Compact mode
        res_tree_compact = await server.call_tool("get_bom_tree", {"part_number_or_id": "ASY-TOP-001", "compact": True})
        data_tree_compact = json.loads(res_tree_compact.content[0].text)
        assert data_tree_compact["purchase_kit"] is False
        compact_child_kit = next(c for c in data_tree_compact["children"] if c["part_number"] == "EL-PCBA-001")
        assert compact_child_kit["purchase_kit"] is True

        # 3. search_items
        res_search_kit = await server.call_tool("search_items", {"query": "PCBA"})
        data_search_kit = json.loads(res_search_kit.content[0].text)
        assert data_search_kit["count"] > 0
        search_kit_item = next(i for i in data_search_kit["items"] if i["part_number"] == "EL-PCBA-001")
        assert search_kit_item["purchase_kit"] is True

        res_search_non_kit = await server.call_tool("search_items", {"query": "ASY"})
        data_search_non_kit = json.loads(res_search_non_kit.content[0].text)
        assert data_search_non_kit["count"] > 0
        search_non_kit_item = next(i for i in data_search_non_kit["items"] if i["part_number"] == "ASY-TOP-001")
        assert search_non_kit_item["purchase_kit"] is False

    asyncio.run(_test())







# ---------------------------------------------------------------------------
# Regression tests for identifier resolution, search limits, inventory qty,
# and BOM-tree root reporting.
# ---------------------------------------------------------------------------

def test_find_item_by_pn_or_id_exact_only_no_fuzzy_fallback():
    """A partial/truncated identifier must NOT silently resolve to a different part."""
    client = MagicMock()
    rows = [
        {"id": 1, "Part Number": "55-00020", "Full PN": "55-00020 Rev.A", "Revision": "A",
         "Item description": "Enclosure Kit", "Item Lifecycle State": {"value": "Production Use"}},
        {"id": 2, "Part Number": "55-00021", "Full PN": "55-00021 Rev.A", "Revision": "A",
         "Item description": "XLR sub-assembly", "Item Lifecycle State": {"value": "Production Use"}},
    ]
    client.get_items.return_value = rows
    client.get_item.side_effect = lambda iid: next(
        (x for x in rows if x["id"] == iid), {"error": "Not found"})

    # Exact Part Number / Full PN / numeric ID still resolve.
    assert _find_item_by_pn_or_id(client, "55-00021")["id"] == 2
    assert _find_item_by_pn_or_id(client, "55-00020 Rev.A")["id"] == 1
    assert _find_item_by_pn_or_id(client, "2")["id"] == 2

    # A truncated identifier that is a substring of a real PN must NOT match it.
    assert _find_item_by_pn_or_id(client, "55-0002") is None
    # Unknown identifiers stay unresolved.
    assert _find_item_by_pn_or_id(client, "NOPE-99999") is None


def test_find_item_by_pn_or_id_prefers_current_revision_and_pins_full_pn():
    """Bare PN -> most current revision (+ ambiguity annotation); Full PN -> exact row."""
    client = MagicMock()
    rows = [
        {"id": 10, "Part Number": "A-001", "Full PN": "A-001 Rev.A", "Revision": "A",
         "Item description": "Rev A", "Item Lifecycle State": {"value": "Finish Stock"}},
        {"id": 11, "Part Number": "A-001", "Full PN": "A-001 Rev.B", "Revision": "B",
         "Item description": "Rev B", "Item Lifecycle State": {"value": "Production Use"}},
    ]
    client.get_items.return_value = rows
    client.get_item.side_effect = lambda iid: next(
        (x for x in rows if x["id"] == iid), {"error": "Not found"})

    got = _find_item_by_pn_or_id(client, "A-001")
    assert got["id"] == 11  # current (Production Use), not the retired Rev.A
    assert set(got["_ambiguous_matches"]) == {"A-001 Rev.A", "A-001 Rev.B"}

    # An exact Full PN pins the exact revision.
    assert _find_item_by_pn_or_id(client, "A-001 Rev.A")["id"] == 10


def test_search_items_non_positive_limit_returns_empty(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        for lim in (0, -1):
            res = await server.call_tool("search_items", {"limit": lim})
            data = json.loads(res.content[0].text)
            assert data["count"] == 0
            assert data["items"] == []

    asyncio.run(_test())


def test_inventory_summary_non_positive_qty_rejected(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)
        for q in (0, -5):
            res = await server.call_tool("get_inventory_summary", {
                "part_number_or_id": "ASY-TOP-001", "target_build_qty": q})
            data = json.loads(res.content[0].text)
            assert "error" in data
            assert "required_parts" not in data

    asyncio.run(_test())


def test_bom_tree_returns_all_roots_and_reports_truncation():
    """Every root is returned; deliberate capping is announced, never silent."""
    client = MagicMock()
    client.table_bom = "508"
    client.table_assembly = "701"
    client.table_instructions = "5770"
    client.get_bom_tree.return_value = [
        {"id": 1000 + i, "part_number": f"80-{i:05d}", "name": f"Root {i}", "children": []}
        for i in range(12)
    ]
    client._get_all_rows.side_effect = lambda tbl, *a, **k: []
    client.get_instruction_sets_for_item.return_value = []

    server = create_mcp_server(client)

    async def _test():
        res = await server.call_tool("get_bom_tree", {})
        data = json.loads(res.content[0].text)
        assert data["root_count"] == 12
        assert len(data["bom_tree"]) == 12          # nothing silently dropped
        assert "truncated" not in data
        assert data["roots_returned"] == 12

        res_cap = await server.call_tool("get_bom_tree", {"max_nodes": 5})
        data_cap = json.loads(res_cap.content[0].text)
        assert data_cap["truncated"] is True        # explicit cap is announced
        assert len(data_cap["bom_tree"]) == 5

    asyncio.run(_test())


def test_search_items_filter_uses_full_candidate_pool(mock_client):
    """A category filter must not be starved by a small `limit`.

    The tool fetches candidates, then filters locally, so when a filter is present it
    must widen the fetch to the page cap instead of the user's `limit`.
    """
    async def _test():
        server = create_mcp_server(mock_client)
        mock_client.search_items.reset_mock()
        res = await server.call_tool("search_items", {
            "query": "Connector", "category": "Electrical COTS", "limit": 5})
        data = json.loads(res.content[0].text)
        assert "error" not in data
        # Candidate pool widened beyond the user limit (Baserow page cap).
        called_limit = mock_client.search_items.call_args.kwargs.get("limit")
        assert called_limit is not None and called_limit > 5

        # With no filter, the user's limit is passed straight through.
        mock_client.search_items.reset_mock()
        await server.call_tool("search_items", {"query": "Connector", "limit": 5})
        assert mock_client.search_items.call_args.kwargs.get("limit") == 5

    asyncio.run(_test())
