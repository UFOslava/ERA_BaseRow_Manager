import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.mcp_server import create_mcp_server, run_mcp_stdio, run_mcp_sse, start_mcp_background


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
            "Price per unit": "0.10",
            "Lot Size": 100,
            "External PN": "SCR-M3-8",
            "Manufacturer": "FastenerCo",
            "Supplier": "McMaster",
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

    # Assembly edges: Asy 1 contains PCBA 2 (qty 1) and Fastener 3 (qty 4)
    client._get_all_rows.side_effect = lambda tbl: (
        mock_items if tbl == "508" else (
            [
                {"id": 101, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Quantity": 1},
                {"id": 102, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Quantity": 4}
            ] if tbl == "701" else (
                [
                    {
                        "id": 501,
                        "Parent Item": [{"id": 1}],
                        "Step Number": 1,
                        "Step Title": "Mount Board",
                        "Instruction Text": "Place PCBA on chassis and secure with 4 screws",
                        "Instruction Set Index": 0,
                        "Photo": [{"url": "http://step1.png"}],
                        "Toll Map": json.dumps([
                            {"id": 2, "quantity": 1, "toll": True},
                            {"id": 3, "quantity": 4, "toll": True}
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
            "Step Number": 1,
            "Step Title": "Mount Board",
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

    client.create_item.return_value = {"id": 4, "Part Number": "ME-CHAS-001", "Name": "Alu Chassis"}
    client.update_item.return_value = {"id": 1, "Part Number": "ASY-TOP-001", "Name": "Updated Name"}
    client.create_instruction.return_value = {"id": 502, "Step Number": 2, "Instruction Text": "Next step"}
    client.update_instruction.return_value = {"id": 501, "Step Number": 1, "Instruction Text": "Updated text"}

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
            "run_quality_scan",
            "get_work_instructions",
            "create_or_update_wi_step",
            "get_inventory_summary",
            "list_pn_categories",
            "list_item_lifecycle_states",
            "list_manufacturers_and_suppliers"
        ]
        for exp in expected_tools:
            assert exp in tool_names, f"Expected tool {exp} not registered"

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
        assert "hardware_problem_scan" in prompt_names

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
        mock_client.create_item.assert_called_once()

        # Update item
        res_upd = await server.call_tool("update_item", {
            "part_number_or_id": "ASY-TOP-001",
            "name": "Updated Top Assembly",
            "price_per_unit": 160.0
        })
        data_upd = json.loads(res_upd.content[0].text)
        assert "Successfully updated" in data_upd["message"]
        assert "Name" in data_upd["updated_fields"]

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
        assert len(data["sets"]) == 1
        assert data["sets"][0]["is_balanced"] is True
        assert len(data["sets"][0]["discrepancies"]) == 0

    asyncio.run(_test())


def test_run_quality_scan_tool(mock_client):
    async def _test():
        server = create_mcp_server(mock_client)

        # Fastener #3 has empty Datasheet, so rule triggers
        res = await server.call_tool("run_quality_scan", {})
        data = json.loads(res.content[0].text)
        assert data["total_items_with_issues"] >= 1
        assert 3 in [int(k) for k in data["diagnostics"].keys()]

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
    with patch("sys.argv", ["run.py", "--mcp-sse", "--mcp-port", "8888"]), \
         patch("app.mcp_server.run_mcp_sse") as mock_sse:
        run.main()
        mock_sse.assert_called_once_with(host="127.0.0.1", port=8888)


def test_run_cli_default_with_mcp():
    import run
    mock_app = MagicMock()
    with patch("sys.argv", ["run.py", "--port", "5005"]), \
         patch("app.mcp_server.start_mcp_background") as mock_bg, \
         patch("app.main.create_app", return_value=mock_app):
        run.main()
        mock_bg.assert_called_once_with(host="127.0.0.1", port=8001)
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
