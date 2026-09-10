"""
mcp_server.py
Model Context Protocol (MCP) Server for ERA BaseRow ERP.

Provides tools, resources, and prompt templates for interacting with:
- Item & Catalog Management (Search, inspect, create, update, lifecycle states, categories)
- Multi-tier BOM Hierarchies & Where-Used (Traverse BOM trees, assembly parents)
- Automated BOM Equilibrium & Balance Audit (Math check between BOM quantities & WI step tolling)
- Dynamic Work Instructions & Step Management (Author and inspect steps, photos, tolling)
- Quality & Problem Rule Diagnostics (Missing datasheets, missing images, broken refs)
- Inventory Stock & Requirements Analysis (Flat/nested parts requirement calculations)
"""

import os
import json
import logging
import asyncio
import threading
from typing import Optional, Dict, Any, List, Union
from mcp.server.mcpserver import MCPServer
from app.baserow_client import BaserowClient, evaluate_condition

logger = logging.getLogger(__name__)


def _find_item_by_pn_or_id(client: BaserowClient, identifier: str) -> Optional[Dict[str, Any]]:
    """Helper to locate an item row by ID or Part Number / Full PN."""
    if not identifier:
        return None
    
    clean_id = str(identifier).strip()
    
    # Try by numeric ID first if numeric
    if clean_id.isdigit():
        try:
            item = client.get_item(int(clean_id))
            if item and not item.get("error"):
                return item
        except Exception:
            pass
            
    # Search all items by Part Number, Full PN, or Name
    try:
        items = client.get_items()
        clean_lower = clean_id.lower()
        for it in items:
            pn = str(it.get("Part Number", "")).strip().lower()
            full_pn = str(it.get("Full PN", "")).strip().lower()
            if clean_lower == pn or clean_lower == full_pn:
                return it
            
        # Partial match fallback
        for it in items:
            pn = str(it.get("Part Number", "")).strip().lower()
            name = str(it.get("Name") or it.get("Item description") or "").strip().lower()
            if clean_lower in pn or clean_lower in name:
                return it
    except Exception as e:
        logger.error(f"Error finding item '{identifier}': {e}")
        
    return None


def _extract_lifecycle_state(item: Dict[str, Any]) -> str:
    """Extract lifecycle state string from various Baserow field representations."""
    state_val = item.get("Item Lifecycle State") or item.get("Lifecycle State") or item.get("State")
    if isinstance(state_val, list) and len(state_val) > 0:
        first = state_val[0]
        return first.get("value", "") if isinstance(first, dict) else str(first or "")
    elif isinstance(state_val, dict):
        return state_val.get("value", "")
    elif state_val:
        return str(state_val)
    return ""


def _extract_name_desc(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract name and description respecting Baserow field conventions."""
    name = item.get("Name") or item.get("Item description")
    desc = item.get("Description") or item.get("Item description")
    return name, desc



def create_mcp_server(client: Optional[BaserowClient] = None) -> MCPServer:
    """
    Creates and configures the ERA ERP MCPServer with all tools, resources, and prompts.
    """
    if client is None:
        client = BaserowClient()

    server = MCPServer(
        name="ERA-ERP-MCP",
        instructions=(
            "ERA BaseRow ERP MCP Server. Allows AI agents to interact with manufacturing BOMs, "
            "part catalogs, Work Instructions (WIs), tolling quantities, BOM equilibrium balance, "
            "quality problem diagnostics, and inventory requirements."
        )
    )

    # =========================================================================
    # TOOLS - ITEM & CATALOG MANAGEMENT
    # =========================================================================

    @server.tool()
    def search_items(query: str = "", category: str = "", lifecycle_state: str = "", limit: int = 50) -> str:
        """
        Search for items/parts in the ERA ERP database by query string, category prefix, or lifecycle state.

        Args:
            query: Keyword to search in Part Number, Name, Description, or External PN.
            category: Optional category filter (e.g., 'EL-PCBA', 'ME-CHAS', 'RAW-MET').
            lifecycle_state: Optional lifecycle state filter (e.g., 'Production Use', 'Engineering Use').
            limit: Maximum number of items to return (default 50).
        """
        try:
            if query and len(query) >= 3:
                items = client.search_items(query, limit=limit)
            else:
                items = client.get_items()

            results = []
            for it in items:
                # Category filter
                cat_val = it.get("Category")
                cat_name = cat_val.get("value", "") if isinstance(cat_val, dict) else str(cat_val or "")
                if category and category.lower() not in cat_name.lower():
                    continue

                # Lifecycle state filter
                state_name = _extract_lifecycle_state(it)
                if lifecycle_state and lifecycle_state.lower() not in state_name.lower():
                    continue

                # Text filter if short query
                name, desc = _extract_name_desc(it)
                if query and len(query) < 3:
                    text_blob = f"{it.get('Part Number', '')} {name or ''} {desc or ''}".lower()
                    if query.lower() not in text_blob:
                        continue

                results.append({
                    "id": it.get("id"),
                    "part_number": it.get("Part Number"),
                    "revision": it.get("Revision"),
                    "full_pn": it.get("Full PN"),
                    "name": name,
                    "description": desc,
                    "category": cat_name,
                    "lifecycle_state": state_name,
                    "blackbox": it.get("Blackbox", False),
                    "price_per_unit": it.get("Price per unit") or it.get("Price"),
                    "external_pn": it.get("External PN") or it.get("External Part Number"),
                    "manufacturer": it.get("Manufacturer")
                })
                if len(results) >= limit:
                    break

            return json.dumps({"count": len(results), "items": results}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to search items: {str(e)}"})

    @server.tool()
    def get_item_details(part_number_or_id: str) -> str:
        """
        Get complete details for a specific item/part by Part Number (e.g. 'ME-CHAS-001') or Baserow Row ID.

        Args:
            part_number_or_id: The Part Number, Full PN, or numeric row ID of the item.
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found in BOM catalog."})
            
            # Enrich with where-used summary & WI summary
            item_id = item.get("id")
            parents = client.get_graph_parents(item_id) if hasattr(client, "get_graph_parents") else []
            children = client.get_graph_children(item_id) if hasattr(client, "get_graph_children") else []
            
            name, desc = _extract_name_desc(item)
            cat_val = item.get("Category")
            cat_name = cat_val.get("value", "") if isinstance(cat_val, dict) else str(cat_val or "")
            summary = {
                "id": item.get("id"),
                "part_number": item.get("Part Number"),
                "revision": item.get("Revision"),
                "full_pn": item.get("Full PN"),
                "name": name,
                "description": desc,
                "category": cat_name,
                "lifecycle_state": _extract_lifecycle_state(item),
                "blackbox": item.get("Blackbox", False),
                "price_per_unit": item.get("Price per unit") or item.get("Price"),
                "lot_size": item.get("Lot Size"),
                "nre_cost": item.get("NRE Cost"),
                "external_pn": item.get("External PN") or item.get("External Part Number"),
                "manufacturer": item.get("Manufacturer"),
                "supplier": item.get("Supplier"),
                "source_url": item.get("Source URL") or item.get("Source Link"),
                "notes": item.get("Notes"),
                "child_components_count": len(children),
                "used_in_assemblies_count": len(parents),
                "has_photos": bool(item.get("Image") or item.get("Photos") or item.get("Images")),
                "has_datasheets": bool(item.get("Datasheet") or item.get("Datasheets"))
            }
            return json.dumps(summary, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get item details: {str(e)}"})

    @server.tool()
    def create_item(
        part_number: str,
        name: str,
        category: str = "",
        description: str = "",
        lifecycle_state: str = "Engineering Use",
        price_per_unit: Optional[float] = None,
        external_pn: str = "",
        manufacturer: str = "",
        blackbox: bool = False
    ) -> str:
        """
        Create a new item/component in the ERA ERP catalog.

        Args:
            part_number: Unique part number (e.g., 'EL-PCBA-001' or 'ME-FAST-010').
            name: Human-readable component name.
            category: Category name or prefix.
            description: Optional technical description.
            lifecycle_state: Initial state (default 'Engineering Use', options: 'Production Use', 'Engineering Use', 'Finish Stock', 'EOL', 'Discard').
            price_per_unit: Unit price (USD).
            external_pn: Manufacturer or vendor part number.
            manufacturer: Manufacturer name.
            blackbox: Whether this assembly should be treated as an indivisible blackbox in BOM explosions.
        """
        try:
            payload: Dict[str, Any] = {
                "Part Number": part_number.strip(),
                "Name": name.strip(),
                "Item description": name.strip(),
                "Description": description.strip() if description else name.strip(),
                "Blackbox": bool(blackbox)
            }
            if category:
                payload["Category"] = category.strip()
            if lifecycle_state:
                payload["Item Lifecycle State"] = lifecycle_state.strip()
                payload["State"] = lifecycle_state.strip()
            if price_per_unit is not None:
                payload["Price per unit"] = str(price_per_unit)
            if external_pn:
                payload["External PN"] = external_pn.strip()
            if manufacturer:
                payload["Manufacturer"] = manufacturer.strip()

            created = client.create_item(payload)
            return json.dumps({
                "message": f"Successfully created item '{part_number}'",
                "item": created
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to create item: {str(e)}"})

    @server.tool()
    def update_item(
        part_number_or_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        price_per_unit: Optional[float] = None,
        external_pn: Optional[str] = None,
        manufacturer: Optional[str] = None,
        blackbox: Optional[bool] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Update fields of an existing item in the ERA ERP catalog.

        Args:
            part_number_or_id: Part Number or Row ID of the item to update.
            name: New name (or None to keep current).
            description: New description (or None to keep current).
            category: New category (or None to keep current).
            lifecycle_state: New lifecycle state (or None to keep current).
            price_per_unit: New unit price (or None to keep current).
            external_pn: New external part number (or None to keep current).
            manufacturer: New manufacturer (or None to keep current).
            blackbox: New blackbox flag (or None to keep current).
            notes: Engineering notes (or None to keep current).
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found."})
            
            item_id = item["id"]
            payload: Dict[str, Any] = {}
            if name is not None:
                payload["Name"] = name
                payload["Item description"] = name
            if description is not None:
                payload["Description"] = description
                payload["Item description"] = description
            if category is not None:
                payload["Category"] = category
            if lifecycle_state is not None:
                payload["Item Lifecycle State"] = lifecycle_state
                payload["State"] = lifecycle_state
            if price_per_unit is not None:
                payload["Price per unit"] = str(price_per_unit)
            if external_pn is not None:
                payload["External PN"] = external_pn
            if manufacturer is not None:
                payload["Manufacturer"] = manufacturer
            if blackbox is not None:
                payload["Blackbox"] = bool(blackbox)
            if notes is not None:
                payload["Notes"] = notes

            if not payload:
                return json.dumps({"message": "No fields provided to update.", "item": item})

            updated = client.update_item(item_id, payload)
            return json.dumps({
                "message": f"Successfully updated item #{item_id} ({item.get('Part Number')})",
                "updated_fields": list(payload.keys()),
                "item": updated
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to update item: {str(e)}"})

    # =========================================================================
    # TOOLS - BOM HIERARCHY & WHERE-USED
    # =========================================================================

    @server.tool()
    def get_bom_tree(part_number_or_id: str = "", max_depth: int = 10) -> str:
        """
        Retrieve the multi-tier nested Bill of Materials (BOM) hierarchy for an assembly or all top-level assemblies.

        Args:
            part_number_or_id: Optional Part Number or ID of the root assembly. If empty, returns top-level trees.
            max_depth: Maximum hierarchy depth to traverse (default 10).
        """
        try:
            tree = client.get_bom_tree()
            if not part_number_or_id:
                # Return entire or top-level tree
                return json.dumps({"root_count": len(tree), "bom_tree": tree[:10]}, indent=2)

            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            target_id = target["id"]

            def find_subtree(nodes):
                for n in nodes:
                    if n.get("id") == target_id:
                        return n
                    sub = find_subtree(n.get("children", []))
                    if sub:
                        return sub
                return None

            subtree = find_subtree(tree)
            if not subtree:
                # Build localized tree from graph children
                children = client.get_graph_children(target_id) if hasattr(client, "get_graph_children") else []
                name, _ = _extract_name_desc(target)
                subtree = {
                    "id": target_id,
                    "part_number": target.get("Part Number"),
                    "name": name,
                    "children": children
                }

            return json.dumps(subtree, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get BOM tree: {str(e)}"})

    @server.tool()
    def get_where_used(part_number_or_id: str) -> str:
        """
        Find all parent assemblies that use or contain this specific component (Where-Used Analysis).

        Args:
            part_number_or_id: Part Number or Row ID of the child component.
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found."})

            item_id = item["id"]
            parents = client.get_graph_parents(item_id) if hasattr(client, "get_graph_parents") else []
            name, _ = _extract_name_desc(item)
            return json.dumps({
                "component": {
                    "id": item_id,
                    "part_number": item.get("Part Number"),
                    "name": name
                },
                "used_in_count": len(parents),
                "parent_assemblies": parents
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get parent assemblies: {str(e)}"})

    # =========================================================================
    # TOOLS - BOM EQUILIBRIUM & QUALITY PROBLEM SCANNER
    # =========================================================================

    @server.tool()
    def audit_bom_balance(part_number_or_id: str) -> str:
        """
        Audit the mathematical BOM equilibrium / balance for an assembly: compares declared BOM child
        quantities against the tolling quantities consumed across all Work Instruction (WI) steps.

        Args:
            part_number_or_id: Part Number or Row ID of the assembly to audit.
        """
        try:
            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            pid = target["id"]
            bom_rows = client._get_all_rows(client.table_bom)
            assembly_rows = client._get_all_rows(client.table_assembly)
            instruction_rows = client._get_all_rows(client.table_instructions)
            
            bom_map = {r["id"]: r for r in bom_rows}

            # Map assembly relations (parent -> children)
            parent_to_children = {}
            for edge in assembly_rows:
                child_link = edge.get("Contains")
                parent_link = edge.get("Item")
                cid = None
                p_val = None
                if child_link:
                    cid = child_link[0]["id"] if isinstance(child_link, list) and child_link else (child_link.get("id") if isinstance(child_link, dict) else child_link)
                if parent_link:
                    p_val = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                if p_val and cid:
                    qty = edge.get("Quantity", 1)
                    try:
                        qty = float(qty) if qty is not None else 1.0
                    except (ValueError, TypeError):
                        qty = 1.0
                    parent_to_children.setdefault(p_val, []).append({"child_id": cid, "quantity": qty})

            # Map instructions
            parent_to_instruction_sets = {}
            for row in instruction_rows:
                parent_link = row.get("Parent Item")
                if parent_link:
                    parent_item_id = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                    if parent_item_id:
                        s_idx = row.get("Instruction Set Index", 0)
                        try:
                            s_idx = int(s_idx) if s_idx is not None else 0
                        except (ValueError, TypeError):
                            s_idx = 0
                        parent_to_instruction_sets.setdefault(parent_item_id, {}).setdefault(s_idx, []).append(row)

            # Calculate required totals
            items_with_instructions = set(parent_to_instruction_sets.keys())
            required_totals = {}

            def traverse(current_id, current_multiplier, visited):
                if current_id in visited:
                    return
                rels = parent_to_children.get(current_id, [])
                for rel in rels:
                    cid = rel["child_id"]
                    qty = rel["quantity"] * current_multiplier
                    child_part = bom_map.get(cid, {})
                    is_blackbox = bool(child_part.get("Blackbox", False))
                    has_inst = cid in items_with_instructions
                    child_has_children = bool(parent_to_children.get(cid))
                    if child_has_children and not is_blackbox and not has_inst:
                        traverse(cid, qty, visited | {current_id})
                    else:
                        required_totals[cid] = required_totals.get(cid, 0) + qty

            traverse(pid, 1, set())

            sets_dict = parent_to_instruction_sets.get(pid, {})
            num_sets = len(sets_dict)

            audit_sets = []
            overall_balanced = False

            if num_sets == 0:
                overall_balanced = True
            else:
                for s_idx, set_steps in sets_dict.items():
                    instructed_totals = {}
                    steps_detail = []
                    has_missing_photos = False

                    for s in set_steps:
                        photos = s.get("Photo") or s.get("Photos") or []
                        has_photo = bool(photos) and len(photos) > 0
                        if not has_photo:
                            has_missing_photos = True

                        toll_map_str = s.get("Toll Map")
                        toll_items = []
                        if toll_map_str:
                            try:
                                data = json.loads(toll_map_str)
                                if isinstance(data, list):
                                    for slot in data:
                                        c_id = slot.get("id")
                                        if c_id and slot.get("toll", True):
                                            try:
                                                q_num = float(slot.get("quantity", 1))
                                            except (ValueError, TypeError):
                                                q_num = 1.0
                                            instructed_totals[c_id] = instructed_totals.get(c_id, 0) + q_num
                                            toll_items.append({"part_id": c_id, "quantity": q_num})
                            except Exception:
                                pass

                        steps_detail.append({
                            "step_id": s.get("id"),
                            "step_number": s.get("Step Number"),
                            "title": s.get("Step Title"),
                            "has_photo": has_photo,
                            "tolled_items": toll_items
                        })

                    # Compare required vs instructed
                    component_discrepancies = []
                    all_pids = set(required_totals.keys()) | set(instructed_totals.keys())
                    is_set_balanced = True

                    for cid in all_pids:
                        req_q = required_totals.get(cid, 0)
                        inst_q = instructed_totals.get(cid, 0)
                        c_part = bom_map.get(cid, {})
                        c_pn = c_part.get("Part Number", f"ID-{cid}")
                        
                        if abs(req_q - inst_q) > 0.0001:
                            is_set_balanced = False
                            component_discrepancies.append({
                                "part_id": cid,
                                "part_number": c_pn,
                                "required_bom_qty": req_q,
                                "tolled_wi_qty": inst_q,
                                "variance": inst_q - req_q,
                                "status": "OVER_TOLLED" if inst_q > req_q else "UNDER_TOLLED"
                            })

                    if is_set_balanced:
                        overall_balanced = True

                    audit_sets.append({
                        "set_index": s_idx,
                        "step_count": len(set_steps),
                        "has_missing_photos": has_missing_photos,
                        "is_balanced": is_set_balanced,
                        "discrepancies": component_discrepancies,
                        "steps": steps_detail
                    })

            audit_target_name, _ = _extract_name_desc(target)
            return json.dumps({
                "assembly": {
                    "id": pid,
                    "part_number": target.get("Part Number"),
                    "name": audit_target_name
                },
                "bom_equilibrium_balanced": overall_balanced,
                "instruction_sets_count": num_sets,
                "sets": audit_sets
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to audit BOM balance: {str(e)}"})

    @server.tool()
    def run_quality_scan(part_number_or_id: str = "") -> str:
        """
        Run automated problem diagnostics across all items or for a specific item to identify quality violations:
        missing datasheets, missing component images, broken BOM assembly links, or unassigned lifecycle states.

        Args:
            part_number_or_id: Optional Part Number or Row ID to filter scan. If empty, scans all items.
        """
        try:
            scanner = client.scanner
            definitions = scanner.load_definitions()
            
            bom_rows = client._get_all_rows(client.table_bom)
            assembly_rows = client._get_all_rows(client.table_assembly)
            instruction_rows = client._get_all_rows(client.table_instructions)
            
            bom_map = {r["id"]: r for r in bom_rows}

            target_id = None
            if part_number_or_id:
                target = _find_item_by_pn_or_id(client, part_number_or_id)
                if not target:
                    return json.dumps({"error": f"Item '{part_number_or_id}' not found."})
                target_id = target["id"]

            problems_by_item = {}
            for row in bom_rows:
                rid = row["id"]
                if target_id and rid != target_id:
                    continue

                item_issues = []
                for def_item in definitions:
                    condition = def_item.get("condition")
                    if not condition:
                        continue
                    
                    matches = evaluate_condition(row, condition)
                    if matches:
                        item_issues.append({
                            "rule_id": def_item.get("id"),
                            "name": def_item.get("name"),
                            "severity": def_item.get("severity", "warning"),
                            "description": def_item.get("description", "")
                        })

                if item_issues:
                    r_name, _ = _extract_name_desc(row)
                    problems_by_item[rid] = {
                        "part_number": row.get("Part Number"),
                        "name": r_name,
                        "lifecycle_state": _extract_lifecycle_state(row),
                        "issues": item_issues
                    }

            return json.dumps({
                "total_items_with_issues": len(problems_by_item),
                "diagnostics": problems_by_item
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to run quality scan: {str(e)}"})

    # =========================================================================
    # TOOLS - WORK INSTRUCTIONS (WI) & TOLLING
    # =========================================================================

    @server.tool()
    def get_work_instructions(part_number_or_id: str, set_index: int = 0) -> str:
        """
        Retrieve step-by-step Work Instructions (WIs) and tolling mappings for an assembly.

        Args:
            part_number_or_id: Part Number or Row ID of the parent assembly.
            set_index: Instruction set index (default 0). If 0 and only set 1+ exists, falls back to the first available set.
        """
        try:
            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            parent_id = target["id"]
            sets = client.get_instruction_sets_for_item(parent_id)
            effective_set = set_index
            if sets and set_index == 0 and not any(s.get("set_index") == 0 for s in sets):
                effective_set = sets[0].get("set_index", 0)
            details = client.get_instruction_set_details(parent_id, effective_set)
            wi_target_name, _ = _extract_name_desc(target)
            
            return json.dumps({
                "assembly": {
                    "id": parent_id,
                    "part_number": target.get("Part Number"),
                    "name": wi_target_name
                },
                "available_sets": sets,
                "current_set_index": effective_set,
                "steps": details
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get work instructions: {str(e)}"})

    @server.tool()
    def create_or_update_wi_step(
        assembly_pn_or_id: str,
        step_number: int,
        instruction_text: str,
        step_title: str = "",
        set_index: int = 0,
        tolling_items: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create or update a Work Instruction (WI) step for an assembly item.

        Args:
            assembly_pn_or_id: Part Number or Row ID of the parent assembly.
            step_number: 1-indexed step sequence number.
            instruction_text: Full step markdown or descriptive instruction text.
            step_title: Short step summary/title (e.g. 'Mount PCB onto Chassis').
            set_index: Instruction set index (default 0).
            tolling_items: Optional list of dicts specifying parts tolled in this step: [{'id': 123, 'quantity': 2, 'toll': True}].
        """
        try:
            target = _find_item_by_pn_or_id(client, assembly_pn_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{assembly_pn_or_id}' not found."})

            parent_id = target["id"]
            
            # Find existing step for this set and step_number
            existing_steps = client.get_instruction_set_details(parent_id, set_index)
            matched_step = None
            for s in (existing_steps if isinstance(existing_steps, list) else []):
                if s.get("Step Number") == step_number:
                    matched_step = s
                    break

            payload: Dict[str, Any] = {
                "Parent Item": [parent_id],
                "Step Number": step_number,
                "Instruction Text": instruction_text,
                "Instruction Set Index": set_index
            }
            if step_title:
                payload["Step Title"] = step_title
            if tolling_items is not None:
                payload["Toll Map"] = json.dumps(tolling_items)

            if matched_step:
                step_id = matched_step["id"]
                updated = client.update_instruction(step_id, payload)
                return json.dumps({
                    "message": f"Updated Step #{step_number} (ID: {step_id}) for {target.get('Part Number')}",
                    "step": updated
                }, indent=2)
            else:
                created = client.create_instruction(payload)
                return json.dumps({
                    "message": f"Created Step #{step_number} for {target.get('Part Number')}",
                    "step": created
                }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to create/update WI step: {str(e)}"})

    # =========================================================================
    # TOOLS - INVENTORY & STOCK REQUIREMENTS
    # =========================================================================

    @server.tool()
    def get_inventory_summary(part_number_or_id: str = "", target_build_qty: float = 1.0) -> str:
        """
        Calculate inventory requirements and component demand for building target quantity of an assembly.

        Args:
            part_number_or_id: Part Number or Row ID of the assembly to build.
            target_build_qty: Target quantity of assemblies to produce (default 1.0).
        """
        try:
            if not part_number_or_id:
                # Return general top level items summary
                top_items = client.get_top_level_items(limit=20)
                return json.dumps({
                    "summary": "Top-level production assemblies available for build calculation",
                    "assemblies": top_items
                }, indent=2)

            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            item_id = target["id"]
            
            # Compute requirements
            bom_rows = client._get_all_rows(client.table_bom)
            assembly_rows = client._get_all_rows(client.table_assembly)
            bom_map = {r["id"]: r for r in bom_rows}

            parent_to_children = {}
            for edge in assembly_rows:
                child_link = edge.get("Contains")
                parent_link = edge.get("Item")
                cid = child_link[0]["id"] if isinstance(child_link, list) and child_link else (child_link.get("id") if isinstance(child_link, dict) else child_link)
                pid = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                if pid and cid:
                    qty = edge.get("Quantity", 1)
                    try:
                        qty = float(qty) if qty is not None else 1.0
                    except (ValueError, TypeError):
                        qty = 1.0
                    parent_to_children.setdefault(pid, []).append({"child_id": cid, "quantity": qty})

            flat_requirements = {}

            def explode(current_id, current_qty):
                rels = parent_to_children.get(current_id, [])
                if not rels:
                    flat_requirements[current_id] = flat_requirements.get(current_id, 0) + current_qty
                    return

                part = bom_map.get(current_id, {})
                if bool(part.get("Blackbox", False)):
                    flat_requirements[current_id] = flat_requirements.get(current_id, 0) + current_qty
                    return

                for rel in rels:
                    explode(rel["child_id"], rel["quantity"] * current_qty)

            explode(item_id, target_build_qty)

            exploded_list = []
            total_est_cost = 0.0
            for cid, qty in flat_requirements.items():
                c_part = bom_map.get(cid, {})
                p_unit = c_part.get("Price per unit") or c_part.get("Price") or 0.0
                try:
                    p_unit = float(p_unit)
                except (ValueError, TypeError):
                    p_unit = 0.0
                subtotal = p_unit * qty
                total_est_cost += subtotal

                c_name, _ = _extract_name_desc(c_part)
                exploded_list.append({
                    "part_id": cid,
                    "part_number": c_part.get("Part Number"),
                    "name": c_name,
                    "category": c_part.get("Category"),
                    "required_quantity": qty,
                    "unit_price": p_unit,
                    "subtotal_cost": round(subtotal, 4)
                })

            inv_target_name, _ = _extract_name_desc(target)
            return json.dumps({
                "assembly": {
                    "id": item_id,
                    "part_number": target.get("Part Number"),
                    "name": inv_target_name,
                    "target_build_qty": target_build_qty
                },
                "total_unique_terminal_parts": len(exploded_list),
                "total_estimated_unit_bom_cost": round(total_est_cost, 2),
                "required_parts": exploded_list
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to compute inventory summary: {str(e)}"})

    # =========================================================================
    # TOOLS - REFERENCE DATA & METADATA
    # =========================================================================

    @server.tool()
    def list_pn_categories() -> str:
        """
        List all defined Part Number (PN) categories, prefixes, descriptions, and rule settings.
        """
        try:
            rules = client.rules if hasattr(client, "rules") else []
            return json.dumps({"categories": rules}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list PN categories: {str(e)}"})

    @server.tool()
    def list_item_lifecycle_states() -> str:
        """
        List all available item lifecycle states (e.g. Production Use, Engineering Use, Finish Stock, EOL, Discard).
        """
        try:
            states = client.states_map if hasattr(client, "states_map") else {}
            return json.dumps({"lifecycle_states": states}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list lifecycle states: {str(e)}"})

    @server.tool()
    def list_manufacturers_and_suppliers() -> str:
        """
        List all registered manufacturers and suppliers in the directory.
        """
        try:
            mfgs = client.get_manufacturers() if hasattr(client, "get_manufacturers") else []
            sups = client.get_suppliers() if hasattr(client, "get_suppliers") else []
            return json.dumps({
                "manufacturers_count": len(mfgs),
                "manufacturers": mfgs,
                "suppliers_count": len(sups),
                "suppliers": sups
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list manufacturers and suppliers: {str(e)}"})

    # =========================================================================
    # RESOURCES
    # =========================================================================

    @server.resource("era://items/{part_number}")
    def item_resource(part_number: str) -> str:
        """Provides direct JSON metadata for an item by Part Number."""
        return get_item_details(part_number)

    @server.resource("era://bom/{part_number}")
    def bom_resource(part_number: str) -> str:
        """Provides direct JSON BOM hierarchy tree for an assembly."""
        return get_bom_tree(part_number)

    @server.resource("era://wi/{part_number}")
    def wi_resource(part_number: str) -> str:
        """Provides direct JSON Work Instructions for an assembly."""
        return get_work_instructions(part_number)

    @server.resource("era://inventory/{part_number}")
    def inventory_resource(part_number: str) -> str:
        """Provides direct JSON inventory requirement explosion for an assembly."""
        return get_inventory_summary(part_number)

    @server.resource("era://categories")
    def categories_resource() -> str:
        """Provides list of PN category configurations."""
        return list_pn_categories()

    @server.resource("era://states")
    def states_resource() -> str:
        """Provides list of item lifecycle states."""
        return list_item_lifecycle_states()

    # =========================================================================
    # PROMPTS
    # =========================================================================

    @server.prompt()
    def audit_bom_balance(part_number: str) -> str:
        """
        Interactive audit prompt to verify BOM equilibrium and diagnose tolling discrepancies for an assembly.
        """
        return (
            f"Please conduct an in-depth BOM balance audit for assembly '{part_number}'.\n"
            f"1. Use the `audit_bom_balance` tool to inspect child components and Work Instruction tolling.\n"
            f"2. Identify any over-tolled or under-tolled parts.\n"
            f"3. Verify whether all instruction steps include required assembly photos.\n"
            f"4. Recommend specific step modifications to restore full BOM equilibrium."
        )

    @server.prompt()
    def create_assembly_wi(part_number: str) -> str:
        """
        Prompt template to guide authoring standard operating Work Instructions for an assembly.
        """
        return (
            f"Please assist in creating or refining Work Instructions for assembly '{part_number}'.\n"
            f"1. Call `get_bom_tree` or `get_item_details` to understand all sub-components and fasteners.\n"
            f"2. Draft logical, step-by-step assembly instructions covering prep, mechanical mounting, wiring/routing, and QA test.\n"
            f"3. Allocate the appropriate tolling quantities per step using `create_or_update_wi_step`.\n"
            f"4. Run `audit_bom_balance` to guarantee zero component leakage."
        )

    @server.prompt()
    def hardware_problem_scan(part_number: str = "") -> str:
        """
        Prompt template to scan quality issues and draft an engineering remediation plan.
        """
        target_str = f" for '{part_number}'" if part_number else " across all catalog items"
        return (
            f"Please run a hardware quality scan{target_str}.\n"
            f"1. Use `run_quality_scan` to evaluate problem rules.\n"
            f"2. Group findings by severity (missing datasheets, missing images, unassigned states, disconnected assemblies).\n"
            f"3. Provide actionable engineering recommendations to resolve each diagnostic violation."
        )

    return server


# =============================================================================
# RUNNER HELPERS
# =============================================================================

def run_mcp_stdio(client: Optional[BaserowClient] = None) -> None:
    """Runs the MCP server over standard input/output (stdio transport)."""
    server = create_mcp_server(client)
    server.run(transport="stdio")


def run_mcp_sse(host: str = "127.0.0.1", port: int = 8001, client: Optional[BaserowClient] = None) -> None:
    """Runs the MCP server over Server-Sent Events (SSE HTTP transport)."""
    server = create_mcp_server(client)
    asyncio.run(server.run_sse_async(host=host, port=port))


def start_mcp_background(host: str = "127.0.0.1", port: int = 8001, client: Optional[BaserowClient] = None) -> threading.Thread:
    """
    Starts the MCP SSE server in a background daemon thread.
    Returns the started Thread object.
    """
    def _runner():
        run_mcp_sse(host=host, port=port, client=client)

    thread = threading.Thread(
        target=_runner,
        name="ERA-MCP-Server-Thread",
        daemon=True
    )
    thread.start()
    logger.info(f"ERA MCP SSE Server started in background on http://{host}:{port}/sse")
    return thread
