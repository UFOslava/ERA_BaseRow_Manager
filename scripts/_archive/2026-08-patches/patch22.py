import sys

with open('backend/app/baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''    def create_assembly(self, parent_id, child_id, quantity=None, length=None, pcb_symbol=None):
        """Creates a new assembly edge/relation."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/?user_field_names=true"
        payload = {
            "Item": [parent_id],
            "Contains": [child_id],
            "Amount of Times": quantity if quantity is not None else 1,
            "Length (mm)": length if length is not None else 0,
            "PCB Symbol": pcb_symbol if pcb_symbol is not None else "N/A"
        }''',
'''    def create_assembly(self, parent_id, child_id, quantity=None, length=None, pcb_symbol=None, uom_id=None):
        """Creates a new assembly edge/relation."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/?user_field_names=true"
        payload = {
            "Item": [parent_id],
            "Contains": [child_id],
            "Amount of Times": quantity if quantity is not None else 1,
            "Measurement": length if length is not None else 0,
            "PCB Symbol": pcb_symbol if pcb_symbol is not None else "N/A"
        }
        if uom_id is not None:
            payload["Measurement UoM"] = [uom_id]'''
)

content = content.replace(
'''    def update_assembly(self, edge_id, quantity=None, length=None, pcb_symbol=None, parent_id=None, child_id=None):
        """Updates an existing relation edge in the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
        payload = {}
        if quantity is not None: payload["Amount of Times"] = quantity
        if length is not None: payload["Length (mm)"] = length
        if pcb_symbol is not None: payload["PCB Symbol"] = pcb_symbol
        if parent_id is not None: payload["Item"] = [parent_id]
        if child_id is not None: payload["Contains"] = [child_id]''',
'''    def update_assembly(self, edge_id, quantity=None, length=None, pcb_symbol=None, parent_id=None, child_id=None, uom_id=None):
        """Updates an existing relation edge in the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
        payload = {}
        if quantity is not None: payload["Amount of Times"] = quantity
        if length is not None: payload["Measurement"] = length
        if pcb_symbol is not None: payload["PCB Symbol"] = pcb_symbol
        if parent_id is not None: payload["Item"] = [parent_id]
        if child_id is not None: payload["Contains"] = [child_id]
        if uom_id is not None: payload["Measurement UoM"] = [uom_id]
        elif uom_id == "": payload["Measurement UoM"] = []'''
)

with open('backend/app/baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
