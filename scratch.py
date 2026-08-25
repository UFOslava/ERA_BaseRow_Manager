import re

with open('backend/app/baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('edge.get("Length (mm)")', 'edge.get("Measurement")')

old_amount = '''            try:
                l_val = float(length) if length is not None and length != "" else None
            except (ValueError, TypeError):
                l_val = None

            if q_val is not None and q_val >= 1:
                amount_label = f"{int(q_val)} pcs"
                if l_val is not None and l_val > 0:
                    amount_label = f"{int(q_val)} x {int(l_val)}mm"
            elif l_val is not None and l_val >= 0:
                amount_label = f"{int(l_val)}mm"'''

new_amount = '''            uom_raw = edge.get("Measurement UoM", [])
            uom_val = uom_raw[0].get("value") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else ""
            
            try:
                l_val = float(length) if length is not None and length != "" else None
            except (ValueError, TypeError):
                l_val = None

            if q_val is not None and q_val >= 1:
                amount_label = f"{int(q_val)} pcs"
                if l_val is not None and l_val > 0:
                    amount_label = f"{int(q_val)} pcs ({l_val:g} {uom_val})".strip() if uom_val else f"{int(q_val)} pcs ({l_val:g})"
            elif l_val is not None and l_val >= 0:
                amount_label = f"{l_val:g} {uom_val}".strip() if uom_val else f"{l_val:g}"'''

content = content.replace(old_amount, new_amount)

with open('backend/app/baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
