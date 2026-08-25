import re

with open('backend/app/baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace parent_to_children extraction
old_extract = '''            quantity = edge.get("Amount of Times")
            length = edge.get("Measurement")
            pcb_symbol = edge.get("PCB Symbol")

            rel = {
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "pcb_symbol": pcb_symbol,
                "edge_id": edge["id"]
            }'''

new_extract = '''            quantity = edge.get("Amount of Times")
            length = edge.get("Measurement")
            uom_list = edge.get("Measurement UoM", [])
            uom_val = uom_list[0].get("value") if (isinstance(uom_list, list) and len(uom_list) > 0) else ""
            pcb_symbol = edge.get("PCB Symbol")

            rel = {
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "uom": uom_val,
                "pcb_symbol": pcb_symbol,
                "edge_id": edge["id"]
            }'''
content = content.replace(old_extract, new_extract)

# Replace q_label generation
old_q_label = '''                q = rel["quantity"]
                l = rel["length"]
                
                qty = int(q) if (q is not None and q != "") else 1
                length = float(l) if (l is not None and l != "") else 0
                
                if length > 0:
                    q_label = f"{qty} x {int(length) if length.is_integer() else length}mm"
                else:
                    q_label = f"{qty} pcs"'''

new_q_label = '''                q = rel["quantity"]
                l = rel["length"]
                u = rel.get("uom", "")
                
                qty = int(q) if (q is not None and q != "") else 1
                try:
                    length = float(l) if (l is not None and l != "") else 0
                except (ValueError, TypeError):
                    length = 0
                
                if length > 0:
                    l_str = f"{length:g}"
                    if u:
                        q_label = f"{qty} pcs ({l_str} {u})"
                    else:
                        q_label = f"{qty} pcs ({l_str})"
                else:
                    if u:
                        q_label = f"{qty} {u}"
                    else:
                        q_label = f"{qty} pcs"'''

content = content.replace(old_q_label, new_q_label)

with open('backend/app/baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
