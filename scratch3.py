import re

with open('backend/app/inventory_report.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_tab2 = '''        price = get_price(part)
        unit_qty = entry["unit_qty"]

        ws2.row_dimensions[curr_row_tab2].height = 20'''

new_tab2 = '''        price = get_price(part)
        
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

        ws2.row_dimensions[curr_row_tab2].height = 20'''

content = content.replace(old_tab2, new_tab2)

with open('backend/app/inventory_report.py', 'w', encoding='utf-8') as f:
    f.write(content)
