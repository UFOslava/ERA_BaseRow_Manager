import sys

with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''            quantity = data.get("quantity")
            length = data.get("length")
            pcb_symbol = data.get("pcb_symbol")
            
            edge = client.create_assembly(parent_id, child_id, quantity, length, pcb_symbol)''',
'''            quantity = data.get("quantity")
            length = data.get("length")
            pcb_symbol = data.get("pcb_symbol")
            uom_id = data.get("uom_id")
            
            edge = client.create_assembly(parent_id, child_id, quantity, length, pcb_symbol, uom_id)'''
)

content = content.replace(
'''            pcb_symbol = data.get("pcb_symbol")
            parent_id = data.get("parent_id")
            child_id = data.get("child_id")
            
            edge = client.update_assembly(edge_id, quantity, length, pcb_symbol, parent_id, child_id)''',
'''            pcb_symbol = data.get("pcb_symbol")
            parent_id = data.get("parent_id")
            child_id = data.get("child_id")
            uom_id = data.get("uom_id")
            
            edge = client.update_assembly(edge_id, quantity, length, pcb_symbol, parent_id, child_id, uom_id)'''
)

with open('backend/app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
