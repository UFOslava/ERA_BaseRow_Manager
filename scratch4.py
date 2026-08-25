import re

with open('backend/app/inventory_report.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_tab1 = '''            nested_items.append({
                "level": level,
                "excel_row": current_row_index,
                "parent_excel_row": parent_excel_row,
                "item_id": cid,
                "part": child_part,
                "unit_qty": unit_qty,
                "price": get_price(child_part),
                "is_blackbox": is_blackbox
            })'''

new_tab1 = '''            # Convert base qty to purchase qty
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
            })'''

content = content.replace(old_tab1, new_tab1)

with open('backend/app/inventory_report.py', 'w', encoding='utf-8') as f:
    f.write(content)
