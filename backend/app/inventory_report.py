"""
inventory_report.py
Generates the 2-tab Inventory Requirement Report (.xlsx) for a given BOM assembly item.
Tab 1: Nested BOM Requirements (with visual indents, dynamic parent-child Excel formulas, NRE, and total costs).
Tab 2: Flat BOM Requirements (aggregated terminal & blackbox parts sorted by Full PN, with inventory deduction formulas).
"""

import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


def generate_inventory_report(client, item_id: int, target_build_qty: float = 1.0) -> io.BytesIO:
    """
    Builds the 2-tab Inventory Requirement Report Excel workbook for item_id.
    Returns a BytesIO stream containing the .xlsx workbook.
    """
    # 1. Fetch raw data from Baserow
    bom_rows = client._get_all_rows(client.table_bom)
    assembly_rows = client._get_all_rows(client.table_assembly)
    uom_rows = client.get_uoms()
    uom_map = {r["id"]: r for r in uom_rows}

    bom_map = {row["id"]: row for row in bom_rows}
    root_item = bom_map.get(item_id)
    if not root_item:
        raise ValueError(f"Item #{item_id} not found in BOM database.")

    # Helper for formatted Full PN
    def get_full_pn(part):
        if not part:
            return ""
        full_pn = part.get("Full PN")
        if full_pn:
            return str(full_pn).strip()
        pn = part.get("Part Number", "")
        rev = part.get("Revision", "")
        if rev:
            return f"{pn} Rev.{rev}"
        return str(pn) if pn else ""

    def get_sourced_by(part):
        if not part:
            return ""
        sb = part.get("Sourced By")
        if isinstance(sb, dict):
            return sb.get("value", "")
        if isinstance(sb, str):
            return sb
        return ""

    def get_price(part):
        if not part:
            return None
        p = part.get("Price per unit") if part.get("Price per unit") is not None else part.get("Price")
        if p is not None and str(p).strip() != "":
            try:
                base_price = float(p)
                lot_size = part.get("Lot Size")
                if lot_size is not None and str(lot_size).strip() != "":
                    try:
                        ls_val = float(lot_size)
                        if ls_val > 0:
                            return base_price / ls_val
                    except (ValueError, TypeError):
                        pass
                return base_price
            except (ValueError, TypeError):
                return None
        return None

    # Build parent -> children map
    parent_to_children = {}
    for edge in assembly_rows:
        p_list = edge.get("Item")
        c_list = edge.get("Contains")
        if p_list and c_list and isinstance(p_list, list) and isinstance(c_list, list):
            pid = p_list[0].get("id")
            cid = c_list[0].get("id")
            if pid is not None and cid is not None:
                q_val = edge.get("Amount of Times")
                try:
                    qty = float(q_val) if q_val is not None and str(q_val).strip() != "" else 1.0
                except (ValueError, TypeError):
                    qty = 1.0
                
                # Measurement is already stored in base units
                meas = edge.get("Measurement")
                if meas is not None:
                    try:
                        m_val = float(meas)
                        qty = qty * m_val
                    except (ValueError, TypeError):
                        pass

                if pid not in parent_to_children:
                    parent_to_children[pid] = []
                parent_to_children[pid].append({
                    "child_id": cid,
                    "quantity": qty,
                    "measurement": edge.get("Measurement"),
                    "measurement_uom": edge.get("Measurement UoM"),
                    "pcb_symbol": edge.get("PCB Symbol"),
                    "edge_id": edge.get("id")
                })

    def to_purchase_qty(part, base_qty):
        if not part:
            return base_qty
        purchase_uom_list = part.get("Purchase UoM", [])
        div = 1.0
        if purchase_uom_list:
            p_uom_id = purchase_uom_list[0].get("id")
            p_rec = uom_map.get(p_uom_id, {})
            raw_mult = p_rec.get("Multiplier to Base")
            if raw_mult:
                try:
                    div = float(raw_mult)
                except (ValueError, TypeError):
                    pass
        return base_qty / div if div != 0 else base_qty

    # 2. Traverse hierarchy for Nested BOM (Tab 1) and Flat BOM (Tab 2)
    nested_items = []
    flat_kits = {}        # kit_id -> { "part": kit_part, "unit_qty": float, "children": { child_id: { "part": child_part, "unit_qty": float } } }
    flat_leaf_items = {}  # cid -> { "part": child_part, "unit_qty": float }

    def traverse(current_id, level, parent_excel_row, visited):
        if current_id in visited:
            return
        rels = parent_to_children.get(current_id, [])
        for rel in rels:
            cid = rel["child_id"]
            child_part = bom_map.get(cid, {})
            unit_qty = rel["quantity"]
            is_blackbox = bool(child_part.get("Blackbox", False))
            child_has_children = bool(parent_to_children.get(cid))

            current_row_index = len(nested_items) + 5  # Data rows start at row 5 in Excel
            final_unit_qty = to_purchase_qty(child_part, unit_qty)

            nested_items.append({
                "level": level,
                "excel_row": current_row_index,
                "parent_excel_row": parent_excel_row,
                "item_id": cid,
                "part": child_part,
                "unit_qty": final_unit_qty,
                "price": get_price(child_part),
                "is_blackbox": is_blackbox
            })

            # Check if terminal for Flat BOM or recurse further
            if not child_has_children or is_blackbox:
                pass
            else:
                traverse(cid, level + 1, current_row_index, visited | {current_id})

    # Also compute exact flat multiplier sums for flat BOM
    def traverse_flat(current_id, current_multiplier, visited, in_kit_id=None):
        if current_id in visited:
            return
        rels = parent_to_children.get(current_id, [])
        for rel in rels:
            cid = rel["child_id"]
            child_part = bom_map.get(cid, {})
            base_rel_qty = rel["quantity"]
            qty = base_rel_qty * current_multiplier
            is_blackbox = bool(child_part.get("Blackbox", False))
            is_kit = bool(child_part.get("Purchase Kit", False))
            child_has_children = bool(parent_to_children.get(cid))

            if in_kit_id is not None:
                # We are traversing inside a purchase kit
                if cid not in flat_kits[in_kit_id]["children"]:
                    flat_kits[in_kit_id]["children"][cid] = {
                        "part": child_part,
                        "unit_qty": 0.0
                    }
                flat_kits[in_kit_id]["children"][cid]["unit_qty"] += qty
                if child_has_children and not is_blackbox:
                    traverse_flat(cid, qty, visited | {current_id}, in_kit_id=in_kit_id)
            elif is_kit:
                # This item is a Purchase Kit parent
                if cid not in flat_kits:
                    flat_kits[cid] = {
                        "part": child_part,
                        "unit_qty": 0.0,
                        "children": {}
                    }
                flat_kits[cid]["unit_qty"] += qty
                # Traverse the kit's children
                traverse_flat(cid, current_multiplier=qty, visited=visited | {current_id}, in_kit_id=cid)
            elif not child_has_children or is_blackbox:
                if cid not in flat_leaf_items:
                    flat_leaf_items[cid] = {
                        "part": child_part,
                        "unit_qty": 0.0
                    }
                flat_leaf_items[cid]["unit_qty"] += qty
            else:
                traverse_flat(cid, qty, visited | {current_id}, in_kit_id=None)

    # Start traversals
    traverse(item_id, level=1, parent_excel_row=None, visited=set())
    traverse_flat(item_id, current_multiplier=1.0, visited=set())

    # --- Virtual Kit Pulling Logic ---
    # Find all global purchase kits and their contents
    global_kits_contents = {}
    for edge in assembly_rows:
        p_list = edge.get("Item")
        c_list = edge.get("Contains")
        if p_list and c_list and isinstance(p_list, list) and isinstance(c_list, list):
            pid = p_list[0].get("id")
            cid = c_list[0].get("id")
            if pid is not None and cid is not None:
                parent_part = bom_map.get(pid, {})
                if bool(parent_part.get("Purchase Kit", False)):
                    # Calculate qty provided by the kit
                    q_val = edge.get("Amount of Times")
                    try:
                        qty = float(q_val) if q_val is not None and str(q_val).strip() != "" else 1.0
                    except (ValueError, TypeError):
                        qty = 1.0
                    
                    meas = edge.get("Measurement")
                    if meas is not None:
                        try:
                            m_val = float(meas)
                            if m_val != 0.0:  # If measurement is 0, don't multiply by 0, treat as absent or 1 depending on logic? Wait, previous logic was `qty = qty * m_val` directly. Let's replicate.
                                qty = qty * m_val
                        except (ValueError, TypeError):
                            pass
                    
                    if pid not in global_kits_contents:
                        global_kits_contents[pid] = {}
                    # In case of duplicate edges, sum the quantities
                    global_kits_contents[pid][cid] = global_kits_contents[pid].get(cid, 0.0) + qty

    # Iteratively pull virtual kits for standalone items
    while True:
        best_kit = None
        best_score = 0
        for k_id, contents in global_kits_contents.items():
            score = sum(1 for c_id in contents if c_id in flat_leaf_items)
            if score > best_score:
                best_score = score
                best_kit = k_id
        
        if best_score == 0:
            break
            
        # We found a kit to pull. Calculate how many kits we need per assembly
        kits_needed = 0.0
        for c_id, qty_per_kit in global_kits_contents[best_kit].items():
            if c_id in flat_leaf_items and qty_per_kit > 0:
                needed = flat_leaf_items[c_id]["unit_qty"] / qty_per_kit
                if needed > kits_needed:
                    kits_needed = needed
                    
        if kits_needed == 0:
            break
            
        # Add kit to flat_kits
        kit_part = bom_map.get(best_kit, {})
        if best_kit not in flat_kits:
            flat_kits[best_kit] = {
                "part": kit_part,
                "unit_qty": 0.0,
                "children": {}
            }
        flat_kits[best_kit]["unit_qty"] += kits_needed
        
        # Add all kit contents to the kit's children
        for c_id, qty_per_kit in global_kits_contents[best_kit].items():
            child_part = bom_map.get(c_id, {})
            qty_provided = kits_needed * qty_per_kit
            if c_id not in flat_kits[best_kit]["children"]:
                flat_kits[best_kit]["children"][c_id] = {
                    "part": child_part,
                    "unit_qty": 0.0
                }
            flat_kits[best_kit]["children"][c_id]["unit_qty"] += qty_provided
            
            # Remove from standalone items since it's now fulfilled by the kit
            if c_id in flat_leaf_items:
                del flat_leaf_items[c_id]

    # Create Workbook
    wb = openpyxl.Workbook()

    # Styling definitions
    font_name = "Segoe UI"
    title_font = Font(name=font_name, size=14, bold=True, color="1F4E78")
    meta_label_font = Font(name=font_name, size=10, bold=True, color="404040")
    meta_val_font = Font(name=font_name, size=11, bold=True, color="1F4E78")
    header_font = Font(name=font_name, size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    data_font = Font(name=font_name, size=10)
    data_font_bold = Font(name=font_name, size=10, bold=True)
    total_font = Font(name=font_name, size=11, bold=True, color="1F4E78")
    total_fill = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

    border_thin = Side(style='thin', color='D9D9D9')
    border_double = Side(style='double', color='1F4E78')
    cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)
    total_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_double)

    currency_format = "$#,##0.00;($#,##0.00);\"-\""
    qty_format = "#,##0.##"

    root_full_pn = get_full_pn(root_item)
    root_desc = root_item.get("Item description", "")

    # =========================================================================
    # TAB 1: Nested BOM Requirements
    # =========================================================================
    ws1 = wb.active
    ws1.title = "Nested BOM Requirements"
    ws1.views.sheetView[0].showGridLines = True

    # Title & Metadata
    ws1["A1"] = f"{root_full_pn} - {root_desc}"
    ws1["A1"].font = title_font
    ws1.row_dimensions[1].height = 24

    ws1["A2"] = "Target Assembly Quantity:"
    ws1["A2"].font = meta_label_font
    ws1["A2"].alignment = align_left

    ws1["B2"] = float(target_build_qty) if target_build_qty else 1.0
    ws1["B2"].font = meta_val_font
    ws1["B2"].alignment = align_center
    ws1["B2"].number_format = "#,##0"
    ws1["B2"].fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    ws1["B2"].border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)
    ws1.row_dimensions[2].height = 20

    # Headers at Row 4
    headers_tab1 = [
        "Level",
        "ERA PN & Rev",
        "External PN",
        "Description",
        "Sourced By",
        "Unit Qty",
        "Total Qty",
        "Unit Price",
        "NRE Cost",
        "Total Cost"
    ]
    ws1.row_dimensions[4].height = 26
    for col_idx, h_text in enumerate(headers_tab1, start=1):
        cell = ws1.cell(row=4, column=col_idx, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_header
        cell.border = cell_border

    start_row = 5
    current_row = start_row

    for item in nested_items:
        lvl = item["level"]
        part = item["part"]
        p_row = item["parent_excel_row"]
        full_pn = get_full_pn(part)
        ext_pn = part.get("External Part Number") or ""
        desc = part.get("Item description") or ""
        sourced_by = get_sourced_by(part)
        unit_qty = item["unit_qty"]
        price = item["price"]

        # Visual tree indentation
        indent_prefix = ("    " * (lvl - 1)) + "└── " if lvl > 1 else ""
        display_pn = f"{indent_prefix}{full_pn}"

        ws1.row_dimensions[current_row].height = 20

        # Col A: Level
        c_lvl = ws1.cell(row=current_row, column=1, value=lvl)
        c_lvl.font = data_font
        c_lvl.alignment = align_center
        c_lvl.border = cell_border

        # Col B: ERA PN & Rev (Indented)
        c_pn = ws1.cell(row=current_row, column=2, value=display_pn)
        c_pn.font = data_font_bold if lvl == 1 else data_font
        c_pn.alignment = align_left
        c_pn.border = cell_border

        # Col C: External PN
        c_ext = ws1.cell(row=current_row, column=3, value=ext_pn)
        c_ext.font = data_font
        c_ext.alignment = align_left
        c_ext.border = cell_border

        # Col D: Description
        c_desc = ws1.cell(row=current_row, column=4, value=desc)
        c_desc.font = data_font
        c_desc.alignment = align_left
        c_desc.border = cell_border

        # Col E: Sourced By
        c_sb = ws1.cell(row=current_row, column=5, value=sourced_by)
        c_sb.font = data_font
        c_sb.alignment = align_left
        c_sb.border = cell_border

        # Col F: Unit Qty
        c_uq = ws1.cell(row=current_row, column=6, value=unit_qty)
        c_uq.font = data_font
        c_uq.alignment = align_right
        c_uq.number_format = qty_format
        c_uq.border = cell_border

        # Col G: Total Qty (Formula)
        if lvl == 1:
            total_qty_formula = f"=F{current_row}*$B$2"
        else:
            total_qty_formula = f"=F{current_row}*G{p_row}"
        c_tq = ws1.cell(row=current_row, column=7, value=total_qty_formula)
        c_tq.font = data_font
        c_tq.alignment = align_right
        c_tq.number_format = qty_format
        c_tq.border = cell_border

        # Col H: Unit Price
        c_pr = ws1.cell(row=current_row, column=8, value=price if price is not None else "")
        c_pr.font = data_font
        c_pr.alignment = align_right
        if price is not None:
            c_pr.number_format = currency_format
        c_pr.border = cell_border

        # Col I: NRE Cost (Default 0.00)
        c_nre = ws1.cell(row=current_row, column=9, value=0.0)
        c_nre.font = data_font
        c_nre.alignment = align_right
        c_nre.number_format = currency_format
        c_nre.border = cell_border

        # Col J: Total Cost (Formula: =Total_Qty * Unit_Price + NRE)
        total_cost_formula = f"=IF(ISNUMBER(H{current_row}), (G{current_row}*H{current_row})+I{current_row}, I{current_row})"
        c_tc = ws1.cell(row=current_row, column=10, value=total_cost_formula)
        c_tc.font = data_font_bold if lvl == 1 else data_font
        c_tc.alignment = align_right
        c_tc.number_format = currency_format
        c_tc.border = cell_border

        current_row += 1

    # Bottom Summary Row for Tab 1
    last_data_row = current_row - 1
    if last_data_row >= start_row:
        ws1.row_dimensions[current_row].height = 24

        # Merge A:H for Summary label
        ws1.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=8)
        lbl_cell = ws1.cell(row=current_row, column=1, value="Total Assembly Cost:")
        lbl_cell.font = total_font
        lbl_cell.alignment = align_right
        for c in range(1, 9):
            ws1.cell(row=current_row, column=c).border = total_border
            ws1.cell(row=current_row, column=c).fill = total_fill

        # Col I: Total NRE
        c_sum_nre = ws1.cell(row=current_row, column=9, value=f"=SUM(I{start_row}:I{last_data_row})")
        c_sum_nre.font = total_font
        c_sum_nre.alignment = align_right
        c_sum_nre.number_format = currency_format
        c_sum_nre.border = total_border
        c_sum_nre.fill = total_fill

        # Col J: Total Cost
        c_sum_tc = ws1.cell(row=current_row, column=10, value=f"=SUM(J{start_row}:J{last_data_row})")
        c_sum_tc.font = total_font
        c_sum_tc.alignment = align_right
        c_sum_tc.number_format = currency_format
        c_sum_tc.border = total_border
        c_sum_tc.fill = total_fill

    # Set Tab 1 column widths
    tab1_col_widths = {
        'A': 8,   # Level
        'B': 30,  # ERA PN & Rev
        'C': 18,  # External PN
        'D': 38,  # Description
        'E': 22,  # Sourced By
        'F': 12,  # Unit Qty
        'G': 14,  # Total Qty
        'H': 14,  # Unit Price
        'I': 14,  # NRE Cost
        'J': 16   # Total Cost
    }
    for col_letter, width in tab1_col_widths.items():
        ws1.column_dimensions[col_letter].width = width

    # =========================================================================
    # TAB 2: Flat BOM Requirements
    # =========================================================================
    ws2 = wb.create_sheet(title="Flat BOM Requirements")
    ws2.views.sheetView[0].showGridLines = True

    # Title & Metadata
    ws2["A1"] = f"{root_full_pn} - Flat BOM Requirements"
    ws2["A1"].font = title_font
    ws2.row_dimensions[1].height = 24

    ws2["A2"] = "Target Assembly Quantity:"
    ws2["A2"].font = meta_label_font
    ws2["A2"].alignment = align_left

    # Reference Tab 1's B2 cell so editing B2 in Tab 1 updates Tab 2 as well!
    ws2["B2"] = "='Nested BOM Requirements'!B2"
    ws2["B2"].font = meta_val_font
    ws2["B2"].alignment = align_center
    ws2["B2"].number_format = "#,##0"
    ws2["B2"].fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    ws2["B2"].border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)
    ws2.row_dimensions[2].height = 20

    # Headers at Row 4
    headers_tab2 = [
        "ERA PN & Rev",
        "External PN",
        "Description",
        "Sourced By",
        "Unit Price",
        "Unit Qty / Assy",
        "Required Qty",
        "Current Inventory",
        "Units to Purchase",
        "Purchase Cost",
        "Source URL"
    ]
    ws2.row_dimensions[4].height = 26
    for col_idx, h_text in enumerate(headers_tab2, start=1):
        cell = ws2.cell(row=4, column=col_idx, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_header
        cell.border = cell_border

    kit_fill = PatternFill(start_color="E9EEF4", end_color="E9EEF4", fill_type="solid")
    section_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    section_font = Font(name=font_name, size=10, bold=True, color="1F4E78")
    link_font = Font(name=font_name, size=10, color="0563C1", underline="single")

    sorted_kit_ids = sorted(
        flat_kits.keys(),
        key=lambda k: get_full_pn(flat_kits[k]["part"]).lower()
    )

    sorted_standalone_cids = sorted(
        flat_leaf_items.keys(),
        key=lambda k: get_full_pn(flat_leaf_items[k]["part"]).lower()
    )

    start_row_tab2 = 5
    curr_row_tab2 = start_row_tab2

    def write_source_url(cell, part):
        url = part.get("Source URL") or part.get("Source Link") or ""
        cell.value = url if url else ""
        cell.alignment = align_left
        cell.border = cell_border
        if url:
            if url.startswith("http://") or url.startswith("https://"):
                cell.hyperlink = url
                cell.font = link_font
            else:
                cell.font = data_font
        else:
            cell.font = data_font

    # A. Render Purchase Kits and their children
    for kid in sorted_kit_ids:
        k_entry = flat_kits[kid]
        k_part = k_entry["part"]
        k_full_pn = get_full_pn(k_part)
        k_ext_pn = k_part.get("External Part Number") or ""
        k_desc = k_part.get("Item description") or ""
        k_sb = get_sourced_by(k_part)
        k_price = get_price(k_part)
        k_unit_qty = to_purchase_qty(k_part, k_entry["unit_qty"])

        kit_row_idx = curr_row_tab2
        ws2.row_dimensions[kit_row_idx].height = 20

        # Col A: KIT: <Full PN>
        c_pn = ws2.cell(row=kit_row_idx, column=1, value=f"KIT: {k_full_pn}")
        c_pn.font = data_font_bold
        c_pn.alignment = align_left
        c_pn.border = cell_border
        c_pn.fill = kit_fill

        # Col B: External PN
        c_ext = ws2.cell(row=kit_row_idx, column=2, value=k_ext_pn)
        c_ext.font = data_font_bold
        c_ext.alignment = align_left
        c_ext.border = cell_border
        c_ext.fill = kit_fill

        # Col C: Description
        c_desc = ws2.cell(row=kit_row_idx, column=3, value=k_desc)
        c_desc.font = data_font_bold
        c_desc.alignment = align_left
        c_desc.border = cell_border
        c_desc.fill = kit_fill

        # Col D: Sourced By
        c_sb = ws2.cell(row=kit_row_idx, column=4, value=k_sb)
        c_sb.font = data_font_bold
        c_sb.alignment = align_left
        c_sb.border = cell_border
        c_sb.fill = kit_fill

        # Col E: Unit Price
        c_pr = ws2.cell(row=kit_row_idx, column=5, value=k_price if k_price is not None else "")
        c_pr.font = data_font_bold
        c_pr.alignment = align_right
        if k_price is not None:
            c_pr.number_format = currency_format
        c_pr.border = cell_border
        c_pr.fill = kit_fill

        # Col F: Unit Qty / Assy
        c_uq = ws2.cell(row=kit_row_idx, column=6, value=k_unit_qty)
        c_uq.font = data_font_bold
        c_uq.alignment = align_right
        c_uq.number_format = qty_format
        c_uq.border = cell_border
        c_uq.fill = kit_fill

        # Col G: Required Qty: =F{kit_row_idx}*$B$2
        c_rq = ws2.cell(row=kit_row_idx, column=7, value=f"=F{kit_row_idx}*$B$2")
        c_rq.font = data_font_bold
        c_rq.alignment = align_right
        c_rq.number_format = qty_format
        c_rq.border = cell_border
        c_rq.fill = kit_fill

        # Col H: Current Inventory (default 0)
        c_inv = ws2.cell(row=kit_row_idx, column=8, value=0)
        c_inv.font = data_font_bold
        c_inv.alignment = align_right
        c_inv.number_format = qty_format
        c_inv.border = cell_border
        c_inv.fill = kit_fill

        # Col I: Units to Purchase: =MAX(0, G{kit_row_idx}-H{kit_row_idx})
        c_utp = ws2.cell(row=kit_row_idx, column=9, value=f"=MAX(0, G{kit_row_idx}-H{kit_row_idx})")
        c_utp.font = data_font_bold
        c_utp.alignment = align_right
        c_utp.number_format = qty_format
        c_utp.border = cell_border
        c_utp.fill = kit_fill

        # Col J: Purchase Cost: =IF(ISNUMBER(E{kit_row_idx}), I{kit_row_idx}*E{kit_row_idx}, 0)
        c_pc = ws2.cell(row=kit_row_idx, column=10, value=f"=IF(ISNUMBER(E{kit_row_idx}), I{kit_row_idx}*E{kit_row_idx}, 0)")
        c_pc.font = data_font_bold
        c_pc.alignment = align_right
        c_pc.number_format = currency_format
        c_pc.border = cell_border
        c_pc.fill = kit_fill

        # Col K: Source URL
        c_src = ws2.cell(row=kit_row_idx, column=11)
        write_source_url(c_src, k_part)
        c_src.fill = kit_fill

        curr_row_tab2 += 1

        # Render kit children
        sorted_child_cids = sorted(
            k_entry["children"].keys(),
            key=lambda k: get_full_pn(k_entry["children"][k]["part"]).lower()
        )
        for child_cid in sorted_child_cids:
            c_entry = k_entry["children"][child_cid]
            c_part = c_entry["part"]
            ch_full_pn = get_full_pn(c_part)
            ch_ext_pn = c_part.get("External Part Number") or ""
            ch_desc = c_part.get("Item description") or ""
            ch_sb = get_sourced_by(c_part)
            ch_unit_qty = to_purchase_qty(c_part, c_entry["unit_qty"])

            ch_row_idx = curr_row_tab2
            ws2.row_dimensions[ch_row_idx].height = 20

            # Col A: Indented child PN
            c_pn = ws2.cell(row=ch_row_idx, column=1, value=f"    └── {ch_full_pn}")
            c_pn.font = data_font
            c_pn.alignment = align_left
            c_pn.border = cell_border

            # Col B: External PN
            c_ext = ws2.cell(row=ch_row_idx, column=2, value=ch_ext_pn)
            c_ext.font = data_font
            c_ext.alignment = align_left
            c_ext.border = cell_border

            # Col C: Description
            c_desc = ws2.cell(row=ch_row_idx, column=3, value=ch_desc)
            c_desc.font = data_font
            c_desc.alignment = align_left
            c_desc.border = cell_border

            # Col D: Sourced By
            c_sb = ws2.cell(row=ch_row_idx, column=4, value=ch_sb)
            c_sb.font = data_font
            c_sb.alignment = align_left
            c_sb.border = cell_border

            # Col E: Unit Price (Included in kit -> 0.00)
            c_pr = ws2.cell(row=ch_row_idx, column=5, value=0.0)
            c_pr.font = data_font
            c_pr.alignment = align_right
            c_pr.number_format = currency_format
            c_pr.border = cell_border

            # Col F: Unit Qty / Assy
            c_uq = ws2.cell(row=ch_row_idx, column=6, value=ch_unit_qty)
            c_uq.font = data_font
            c_uq.alignment = align_right
            c_uq.number_format = qty_format
            c_uq.border = cell_border

            # Col G: Required Qty: =F{ch_row_idx}*$B$2
            c_rq = ws2.cell(row=ch_row_idx, column=7, value=f"=F{ch_row_idx}*$B$2")
            c_rq.font = data_font
            c_rq.alignment = align_right
            c_rq.number_format = qty_format
            c_rq.border = cell_border

            # Col H: Current Inventory (default 0)
            c_inv = ws2.cell(row=ch_row_idx, column=8, value=0)
            c_inv.font = data_font
            c_inv.alignment = align_right
            c_inv.number_format = qty_format
            c_inv.border = cell_border

            # Col I: Resulting amount from kit purchase: =(F{ch_row_idx}/F{kit_row_idx})*I{kit_row_idx}
            c_utp = ws2.cell(row=ch_row_idx, column=9, value=f"=(F{ch_row_idx}/F{kit_row_idx})*I{kit_row_idx}")
            c_utp.font = data_font
            c_utp.alignment = align_right
            c_utp.number_format = qty_format
            c_utp.border = cell_border

            # Col J: Purchase Cost: 0.00
            c_pc = ws2.cell(row=ch_row_idx, column=10, value=0.0)
            c_pc.font = data_font
            c_pc.alignment = align_right
            c_pc.number_format = currency_format
            c_pc.border = cell_border

            # Col K: Source URL
            c_src = ws2.cell(row=ch_row_idx, column=11)
            write_source_url(c_src, c_part)

            curr_row_tab2 += 1

    # B. Render Standalone Section Header (if kits exist and standalone items exist)
    if sorted_kit_ids and sorted_standalone_cids:
        sec_row_idx = curr_row_tab2
        ws2.row_dimensions[sec_row_idx].height = 22
        ws2.merge_cells(start_row=sec_row_idx, start_column=1, end_row=sec_row_idx, end_column=11)
        sec_cell = ws2.cell(row=sec_row_idx, column=1, value="STANDALONE / INDIVIDUAL COMPONENTS")
        sec_cell.font = section_font
        sec_cell.alignment = align_left
        for col_c in range(1, 12):
            ws2.cell(row=sec_row_idx, column=col_c).border = cell_border
            ws2.cell(row=sec_row_idx, column=col_c).fill = section_fill
        curr_row_tab2 += 1

    # C. Render Standalone items
    for cid in sorted_standalone_cids:
        entry = flat_leaf_items[cid]
        part = entry["part"]
        full_pn = get_full_pn(part)
        ext_pn = part.get("External Part Number") or ""
        desc = part.get("Item description") or ""
        sourced_by = get_sourced_by(part)
        price = get_price(part)
        unit_qty = to_purchase_qty(part, entry["unit_qty"])

        ws2.row_dimensions[curr_row_tab2].height = 20

        # Col A: ERA PN & Rev
        c_pn = ws2.cell(row=curr_row_tab2, column=1, value=full_pn)
        c_pn.font = data_font_bold
        c_pn.alignment = align_left
        c_pn.border = cell_border

        # Col B: External PN
        c_ext = ws2.cell(row=curr_row_tab2, column=2, value=ext_pn)
        c_ext.font = data_font
        c_ext.alignment = align_left
        c_ext.border = cell_border

        # Col C: Description
        c_desc = ws2.cell(row=curr_row_tab2, column=3, value=desc)
        c_desc.font = data_font
        c_desc.alignment = align_left
        c_desc.border = cell_border

        # Col D: Sourced By
        c_sb = ws2.cell(row=curr_row_tab2, column=4, value=sourced_by)
        c_sb.font = data_font
        c_sb.alignment = align_left
        c_sb.border = cell_border

        # Col E: Unit Price
        c_pr = ws2.cell(row=curr_row_tab2, column=5, value=price if price is not None else "")
        c_pr.font = data_font
        c_pr.alignment = align_right
        if price is not None:
            c_pr.number_format = currency_format
        c_pr.border = cell_border

        # Col F: Unit Qty / Assy
        c_uq = ws2.cell(row=curr_row_tab2, column=6, value=unit_qty)
        c_uq.font = data_font
        c_uq.alignment = align_right
        c_uq.number_format = qty_format
        c_uq.border = cell_border

        # Col G: Required Qty (Formula: =Unit_Qty * Target_Build_Qty)
        c_rq = ws2.cell(row=curr_row_tab2, column=7, value=f"=F{curr_row_tab2}*$B$2")
        c_rq.font = data_font_bold
        c_rq.alignment = align_right
        c_rq.number_format = qty_format
        c_rq.border = cell_border

        # Col H: Current Inventory (Default 0, highlighted for user input)
        c_inv = ws2.cell(row=curr_row_tab2, column=8, value=0)
        c_inv.font = data_font
        c_inv.alignment = align_right
        c_inv.number_format = qty_format
        c_inv.border = cell_border

        # Col I: Units to Purchase (Formula: =MAX(0, Required_Qty - Current_Inventory))
        c_utp = ws2.cell(row=curr_row_tab2, column=9, value=f"=MAX(0, G{curr_row_tab2}-H{curr_row_tab2})")
        c_utp.font = data_font_bold
        c_utp.alignment = align_right
        c_utp.number_format = qty_format
        c_utp.border = cell_border

        # Col J: Purchase Cost (Formula: =Units_to_Purchase * Unit_Price)
        c_pc = ws2.cell(row=curr_row_tab2, column=10, value=f"=IF(ISNUMBER(E{curr_row_tab2}), I{curr_row_tab2}*E{curr_row_tab2}, 0)")
        c_pc.font = data_font_bold
        c_pc.alignment = align_right
        c_pc.number_format = currency_format
        c_pc.border = cell_border

        # Col K: Source URL
        c_src = ws2.cell(row=curr_row_tab2, column=11)
        write_source_url(c_src, part)

        curr_row_tab2 += 1

    # Bottom Summary Row for Tab 2
    last_row_tab2 = curr_row_tab2 - 1
    if last_row_tab2 >= start_row_tab2:
        ws2.row_dimensions[curr_row_tab2].height = 24

        # Merge A:F for Summary label
        ws2.merge_cells(start_row=curr_row_tab2, start_column=1, end_row=curr_row_tab2, end_column=6)
        lbl_tab2 = ws2.cell(row=curr_row_tab2, column=1, value="Total Summary:")
        lbl_tab2.font = total_font
        lbl_tab2.alignment = align_right
        for c in range(1, 7):
            ws2.cell(row=curr_row_tab2, column=c).border = total_border
            ws2.cell(row=curr_row_tab2, column=c).fill = total_fill

        # Col G: Total Required Qty
        c_sum_rq = ws2.cell(row=curr_row_tab2, column=7, value=f"=SUM(G{start_row_tab2}:G{last_row_tab2})")
        c_sum_rq.font = total_font
        c_sum_rq.alignment = align_right
        c_sum_rq.number_format = qty_format
        c_sum_rq.border = total_border
        c_sum_rq.fill = total_fill

        # Col H: Total Inventory
        c_sum_inv = ws2.cell(row=curr_row_tab2, column=8, value=f"=SUM(H{start_row_tab2}:H{last_row_tab2})")
        c_sum_inv.font = total_font
        c_sum_inv.alignment = align_right
        c_sum_inv.number_format = qty_format
        c_sum_inv.border = total_border
        c_sum_inv.fill = total_fill

        # Col I: Total Units to Purchase
        c_sum_utp = ws2.cell(row=curr_row_tab2, column=9, value=f"=SUM(I{start_row_tab2}:I{last_row_tab2})")
        c_sum_utp.font = total_font
        c_sum_utp.alignment = align_right
        c_sum_utp.number_format = qty_format
        c_sum_utp.border = total_border
        c_sum_utp.fill = total_fill

        # Col J: Total Purchase Cost
        c_sum_pc = ws2.cell(row=curr_row_tab2, column=10, value=f"=SUM(J{start_row_tab2}:J{last_row_tab2})")
        c_sum_pc.font = total_font
        c_sum_pc.alignment = align_right
        c_sum_pc.number_format = currency_format
        c_sum_pc.border = total_border
        c_sum_pc.fill = total_fill

        # Col K: empty border/fill
        c_sum_src = ws2.cell(row=curr_row_tab2, column=11, value="")
        c_sum_src.border = total_border
        c_sum_src.fill = total_fill

    # Set Tab 2 column widths
    tab2_col_widths = {
        'A': 28,  # ERA PN & Rev
        'B': 18,  # External PN
        'C': 38,  # Description
        'D': 22,  # Sourced By
        'E': 14,  # Unit Price
        'F': 16,  # Unit Qty / Assy
        'G': 16,  # Required Qty
        'H': 18,  # Current Inventory
        'I': 18,  # Units to Purchase
        'J': 18,  # Purchase Cost
        'K': 30   # Source URL
    }
    for col_letter, width in tab2_col_widths.items():
        ws2.column_dimensions[col_letter].width = width

    # Save to BytesIO stream
    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    return output_stream
