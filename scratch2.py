import re

with open('backend/app/inventory_report.py', 'r', encoding='utf-8') as f:
    content = f.read()

# fetch UOMs
uom_init = '''    # 1. Fetch raw data from Baserow
    bom_rows = client._get_all_rows(client.table_bom)
    assembly_rows = client._get_all_rows(client.table_assembly)
    uom_rows = client.get_uoms()
    uom_map = {r["id"]: r for r in uom_rows}'''

content = content.replace('    # 1. Fetch raw data from Baserow\n    bom_rows = client._get_all_rows(client.table_bom)\n    assembly_rows = client._get_all_rows(client.table_assembly)', uom_init)

edge_parsing_old = '''                q_val = edge.get("Amount of Times")
                try:
                    qty = float(q_val) if q_val is not None and str(q_val).strip() != "" else 1.0
                except (ValueError, TypeError):
                    qty = 1.0
                if pid not in parent_to_children:
                    parent_to_children[pid] = []
                parent_to_children[pid].append({
                    "child_id": cid,
                    "quantity": qty,
                    "length": edge.get("Length (mm)"),
                    "pcb_symbol": edge.get("PCB Symbol"),
                    "edge_id": edge.get("id")
                })'''

edge_parsing_new = '''                q_val = edge.get("Amount of Times")
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
                })'''

content = content.replace(edge_parsing_old, edge_parsing_new)

# Wait, the prompt also says:
# "and then use the BOM item's Purchase UoM to calculate the Total Purchase Qty."
# So I need to do that as well, later in the file.

with open('backend/app/inventory_report.py', 'w', encoding='utf-8') as f:
    f.write(content)
