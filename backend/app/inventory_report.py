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
        p = part.get("Price per unit")
        if p is not None and str(p).strip() != "":
            try:
                return float(p)
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
                
                # Apply UoM Multiplier
                meas = edge.get("Measurement")
                meas_uom_list = edge.get("Measurement UoM", [])
                if meas is not None:
                    try:
                        m_val = float(meas)
                        mult = 1.0
                        if meas_uom_list:
                            uom_id = meas_uom_list[0].get("id")
                            u_rec = uom_map.get(uom_id, {})
                            raw_mult = u_rec.get("Multiplier to Base")
                            if raw_mult:
                                mult = float(raw_mult)
                        qty = qty * m_val * mult
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

    # 2. Traverse hierarchy for Nested BOM (Tab 1) and Flat BOM (Tab 2)
    nested_items = []
    flat_leaf_items = {}

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

            # Convert base qty to purchase qty
            purchase_uom_list = child_part.get("Purchase UoM", [])
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
            final_unit_qty = unit_qty / div if div != 0 else unit_qty

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
    def traverse_flat(current_id, current_multiplier, visited):
        if current_id in visited:
            return
        rels = parent_to_children.get(current_id, [])
        for rel in rels:
            cid = rel["child_id"]
            child_part = bom_map.get(cid, {})
            qty = rel["quantity"] * current_multiplier
            is_blackbox = bool(child_part.get("Blackbox", False))
            child_has_children = bool(parent_to_children.get(cid))

            if not child_has_children or is_blackbox:
                if cid not in flat_leaf_items:
                    flat_leaf_items[cid] = {
                        "part": child_part,
                        "unit_qty": 0.0
                    }
                flat_leaf_items[cid]["unit_qty"] += qty
            else:
                traverse_flat(cid, qty, visited | {current_id})

    # Start traversals
    traverse(item_id, level=1, parent_excel_row=None, visited=set())
    traverse_flat(item_id, current_multiplier=1.0, visited=set())

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
        "Purchase Cost"
    ]
    ws2.row_dimensions[4].height = 26
    for col_idx, h_text in enumerate(headers_tab2, start=1):
        cell = ws2.cell(row=4, column=col_idx, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_header
        cell.border = cell_border

    # Sort flat items alphabetically by Full PN
    sorted_flat_cids = sorted(
        flat_leaf_items.keys(),
        key=lambda k: get_full_pn(flat_leaf_items[k]["part"]).lower()
    )

    start_row_tab2 = 5
    curr_row_tab2 = start_row_tab2

    for cid in sorted_flat_cids:
        entry = flat_leaf_items[cid]
        part = entry["part"]
        full_pn = get_full_pn(part)
        ext_pn = part.get("External Part Number") or ""
        desc = part.get("Item description") or ""
        sourced_by = get_sourced_by(part)
        price = get_price(part)
        
        # Apply Purchase UoM divisor
        base_unit_qty = entry["unit_qty"]
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
        unit_qty = base_unit_qty / div if div != 0 else base_unit_qty

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

    # Set Tab 2 column widths
    tab2_col_widths = {
        'A': 22,  # ERA PN & Rev
        'B': 18,  # External PN
        'C': 38,  # Description
        'D': 22,  # Sourced By
        'E': 14,  # Unit Price
        'F': 16,  # Unit Qty / Assy
        'G': 16,  # Required Qty
        'H': 18,  # Current Inventory
        'I': 18,  # Units to Purchase
        'J': 16   # Purchase Cost
    }
    for col_letter, width in tab2_col_widths.items():
        ws2.column_dimensions[col_letter].width = width

    # Save to BytesIO stream
    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    return output_stream
