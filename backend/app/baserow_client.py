import os
import requests
import threading
import time
import json
from dotenv import load_dotenv

load_dotenv()

def evaluate_condition(row, condition, is_in_assembly):
    # If it is a logical group (AND/OR)
    if "type" in condition:
        logical_type = condition["type"].upper() # "AND" or "OR"
        sub_conditions = condition.get("conditions", [])
        if not sub_conditions:
            return True
        if logical_type == "AND":
            return all(evaluate_condition(row, c, is_in_assembly) for c in sub_conditions)
        elif logical_type == "OR":
            return any(evaluate_condition(row, c, is_in_assembly) for c in sub_conditions)
        return True
    
    # It is an atomic condition: { "field": "...", "operator": "...", "value": "..." }
    field = condition.get("field")
    operator = condition.get("operator")
    expected_value = condition.get("value")
    
    # Get actual value
    if field == "is_in_assembly":
        actual_value = str(is_in_assembly).lower() # "true" or "false"
    else:
        # Extract from Baserow row
        raw_val = row.get(field)
        if isinstance(raw_val, dict):
            actual_value = raw_val.get("value", "")
        elif isinstance(raw_val, list):
            actual_value = ", ".join(str(x.get("value") if isinstance(x, dict) else x) for x in raw_val)
        else:
            actual_value = raw_val if raw_val is not None else ""
            
    actual_value_str = str(actual_value).strip().lower()
    expected_value_str = str(expected_value).strip().lower() if expected_value is not None else ""
    
    if operator == "equals":
        return actual_value_str == expected_value_str
    elif operator == "not_equals":
        return actual_value_str != expected_value_str
    elif operator == "contains":
        return expected_value_str in actual_value_str
    elif operator == "not_contains":
        return expected_value_str not in actual_value_str
    elif operator == "is_empty":
        return actual_value_str == ""
    elif operator == "is_not_empty":
        return actual_value_str != ""
        
    return False

class ProblemScanner:
    def __init__(self):
        self.status = "pending"  # "pending", "running", "completed", "failed"
        self.problems = {}  # part_id -> list of problem strings
        self._lock = threading.Lock()
        self.definitions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "problem_definitions.json")

    def load_definitions(self):
        try:
            if os.path.exists(self.definitions_path):
                with open(self.definitions_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading problem definitions: {e}")
        return []

    def save_definitions(self, definitions):
        try:
            with open(self.definitions_path, "w", encoding="utf-8") as f:
                json.dump(definitions, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving problem definitions: {e}")
            return False

    def start_scan(self, client):
        with self._lock:
            if self.status == "running":
                return
            self.status = "running"
            
        def run():
            try:
                # Simulate a delay
                time.sleep(5)
                
                definitions = self.load_definitions()
                
                # Fetch fresh data
                bom_rows = client._get_all_rows(client.table_bom)
                assembly_rows = client._get_all_rows(client.table_assembly)
                
                # Identify child IDs in Assembly
                child_ids = set()
                for edge in assembly_rows:
                    child_link = edge.get("Contains")
                    if child_link:
                        child_ids.add(child_link[0]["id"])
                
                new_problems = {}
                for row in bom_rows:
                    pid = row["id"]
                    row_problems = []
                    is_in_assembly = pid in child_ids
                    
                    for definition in definitions:
                        rule = definition.get("rule")
                        if rule:
                            if evaluate_condition(row, rule, is_in_assembly):
                                row_problems.append(definition.get("name", "Unknown Problem"))
                                
                    new_problems[pid] = row_problems
                    
                with self._lock:
                    self.problems = new_problems
                    self.status = "completed"
            except Exception as e:
                print(f"Error during scan: {e}")
                with self._lock:
                    self.status = "failed"
                    
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def reset(self):
        with self._lock:
            self.status = "pending"
            self.problems = {}

    def get_problem_count(self, definition_id):
        definitions = self.load_definitions()
        definition = next((d for d in definitions if d.get("id") == definition_id), None)
        if not definition:
            return None, "not_found"
            
        with self._lock:
            status = self.status
            problems_cache = self.problems
            
        if status == "running" or status == "pending":
            return None, status
            
        name = definition.get("name")
        count = 0
        for p_list in problems_cache.values():
            if name in p_list:
                count += 1
        return count, "completed"


class BaserowClient:
    def __init__(self):
        self.api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070")
        self.token = os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        self.table_bom = "508"
        self.table_assembly = "701"
        self.scanner = ProblemScanner()
        self.rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "category_rules.json")
        self.rules = self.load_rules()

    def load_rules(self):
        import json
        try:
            if os.path.exists(self.rules_path):
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading rules: {e}")
        return {}

    def save_rules(self, rules):
        import json
        try:
            with open(self.rules_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=2)
            self.rules = rules
            return True
        except Exception as e:
            print(f"Error saving rules: {e}")
            return False

    def get_pn_tag(self, part_number):
        if not part_number:
            return {"name": "Unknown", "color": "#8e9095"}
        
        prefix = part_number[:2]
        rule = self.rules.get(prefix)
        if rule:
            return {
                "name": rule.get("name", "Unknown"),
                "color": rule.get("color", "#8e9095")
            }
        return {"name": "Unknown", "color": "#8e9095"}

    def _get_all_rows(self, table_id, filters=None):
        """Helper to fetch all rows handling pagination."""
        url = f"{self.api_url}/api/database/rows/table/{table_id}/"
        params = {"user_field_names": "true", "size": 120}  # Fetch larger batches
        if filters:
            params.update(filters)

        results = []
        next_url = url
        first_call = True

        while next_url:
            if first_call:
                response = requests.get(next_url, headers=self.headers, params=params, timeout=10)
                first_call = False
            else:
                response = requests.get(next_url, headers=self.headers, timeout=10)
            
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            next_url = data.get("next")
            
        return results

    def get_bom_tree(self):
        """
        Fetch BOM and Assembly tables, and build a nested tree structure.
        """
        # Trigger background scanner if pending
        if self.scanner.status == "pending":
            self.scanner.start_scan(self)

        bom_rows = self._get_all_rows(self.table_bom)
        assembly_rows = self._get_all_rows(self.table_assembly)

        bom_map = {row["id"]: row for row in bom_rows}

        parent_to_children = {}
        child_ids = set()

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not parent_link or not child_link:
                continue

            parent_id = parent_link[0]["id"]
            child_id = child_link[0]["id"]

            child_ids.add(child_id)

            quantity = edge.get("Amount of Times")
            length = edge.get("Length (mm)")
            pcb_symbol = edge.get("PCB Symbol")

            rel = {
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "pcb_symbol": pcb_symbol,
                "id": edge["id"]
            }

            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(rel)

        top_level_ids = [pid for pid in bom_map.keys() if pid not in child_ids]

        def build_branch(part_id, visited):
            part = bom_map.get(part_id)
            if not part:
                return None

            if part_id in visited:
                return {
                    "id": part_id,
                    "part_number": part.get("Part Number", "Unknown"),
                    "description": part.get("Item description", "Circular Reference Detected"),
                    "search_helper": part.get("Search helper", ""),
                    "quantity_label": "Err",
                    "problems_count": None,
                    "children": [],
                    "is_circular": True
                }

            children = []
            relations = parent_to_children.get(part_id, [])
            for rel in relations:
                child_branch = build_branch(rel["child_id"], visited | {part_id})
                if child_branch:
                    q = rel["quantity"]
                    l = rel["length"]
                    
                    qty = int(q) if (q is not None and q != "") else 1
                    length = float(l) if (l is not None and l != "") else 0
                    
                    if length > 0:
                        q_label = f"{qty} x {int(length) if length.is_integer() else length}mm"
                    else:
                        q_label = f"{qty} pcs"

                    child_branch["quantity_label"] = q_label
                    child_branch["pcb_symbol"] = rel["pcb_symbol"]
                    child_branch["edge_id"] = rel["id"]
                    child_branch["quantity"] = qty
                    child_branch["length"] = length
                    child_branch["parent_id"] = part_id
                    children.append(child_branch)

            problems_count = None
            if self.scanner.status == "completed":
                problems_count = len(self.scanner.problems.get(part_id, []))

            state_val = part.get("State", {}).get("value", "Unknown") if part.get("State") else "Unknown"
            return {
                "id": part_id,
                "part_number": part.get("Part Number", ""),
                "description": part.get("Item description", ""),
                "search_helper": part.get("Search helper", ""),
                "external_pn": part.get("External PN", ""),
                "notes": part.get("Notes", ""),
                "state": state_val,
                "problems_count": problems_count,
                "pn_tag": self.get_pn_tag(part.get("Part Number")),
                "children": children
            }

        forest = []
        for tl_id in top_level_ids:
            tree = build_branch(tl_id, set())
            if tree:
                tree["quantity_label"] = "Root"
                tree["pcb_symbol"] = "N/A"
                forest.append(tree)

        forest.sort(key=lambda x: x["id"])
        return forest

    def get_item(self, item_id):
        """Gets a single item from the BOM table with its parent and child relations."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        
        item = response.json()
        item["pn_tag"] = self.get_pn_tag(item.get("Part Number"))
        
        problems = []
        if self.scanner.status == "completed":
            problems = self.scanner.problems.get(item_id, [])
            
        item["problems"] = problems

        # Fetch all assembly relations and BOM rows to build lists
        assembly_rows = self._get_all_rows(self.table_assembly)
        bom_rows = self._get_all_rows(self.table_bom)
        bom_map = {row["id"]: row for row in bom_rows}

        contained_items = []
        containing_items = []

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not isinstance(parent_link, list) or len(parent_link) == 0:
                continue
            if not isinstance(child_link, list) or len(child_link) == 0:
                continue

            parent_id = parent_link[0].get("id")
            child_id = child_link[0].get("id")

            if parent_id is None or child_id is None:
                continue

            quantity = edge.get("Amount of Times")
            length = edge.get("Length (mm)")
            pcb_symbol = edge.get("PCB Symbol")

            amount_label = ""
            try:
                q_val = float(quantity) if quantity is not None and quantity != "" else None
            except (ValueError, TypeError):
                q_val = None

            try:
                l_val = float(length) if length is not None and length != "" else None
            except (ValueError, TypeError):
                l_val = None

            if q_val is not None and q_val >= 1:
                amount_label = f"{int(q_val)} pcs"
                if l_val is not None and l_val > 0:
                    amount_label = f"{int(q_val)} x {int(l_val)}mm"
            elif l_val is not None and l_val >= 0:
                amount_label = f"{int(l_val)}mm"

            rel = {
                "edge_id": edge["id"],
                "parent_id": parent_id,
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "pcb_symbol": pcb_symbol,
                "amount_label": amount_label
            }

            if parent_id == item_id:
                child_part = bom_map.get(child_id)
                if child_part:
                    rel.update({
                        "id": child_id,
                        "part_number": child_part.get("Part Number", ""),
                        "description": child_part.get("Item description", ""),
                        "revision": child_part.get("Revision", "")
                    })
                    contained_items.append(rel)

            if child_id == item_id:
                parent_part = bom_map.get(parent_id)
                if parent_part:
                    rel.update({
                        "id": parent_id,
                        "part_number": parent_part.get("Part Number", ""),
                        "description": parent_part.get("Item description", ""),
                        "revision": parent_part.get("Revision", "")
                    })
                    containing_items.append(rel)

        item["contained_items"] = contained_items
        item["containing_items"] = containing_items
        return item

    def get_items(self):
        """Fetch all flat rows from the BOM table."""
        return self._get_all_rows(self.table_bom)

    def update_item(self, item_id, data):
        """Updates an item in the BOM table."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        response = requests.patch(url, headers=self.headers, json=data, timeout=10)
        response.raise_for_status()
        
        # Reset scanner to trigger re-evaluation of problems in background
        self.scanner.reset()
        return response.json()

    def get_manufacturers(self):
        """Fetch all rows from the Manufacturers table (683)."""
        return self._get_all_rows("683")

    def upload_file(self, filename, content, content_type):
        """Uploads a file to Baserow user-files."""
        url = f"{self.api_url}/api/user-files/upload-file/"
        files = {
            "file": (filename, content, content_type)
        }
        headers = {
            "Authorization": f"Token {self.token}"
        }
        response = requests.post(url, headers=headers, files=files, timeout=30)
        response.raise_for_status()
        return response.json()

    def create_assembly(self, parent_id, child_id, quantity=None, length=None, pcb_symbol=None):
        """Creates a new assembly edge/relation."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/?user_field_names=true"
        payload = {
            "Item": [parent_id],
            "Contains": [child_id],
            "Amount of Times": quantity if quantity is not None else 1,
            "Length (mm)": length if length is not None else 0,
            "PCB Symbol": pcb_symbol if pcb_symbol is not None else "N/A"
        }
        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def update_assembly(self, edge_id, quantity=None, length=None, pcb_symbol=None):
        """Updates assembly edge/relation properties."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
        payload = {}
        if quantity is not None:
            payload["Amount of Times"] = quantity
        if length is not None:
            payload["Length (mm)"] = length
        if pcb_symbol is not None:
            payload["PCB Symbol"] = pcb_symbol
            
        response = requests.patch(url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def delete_assembly(self, edge_id):
        """Deletes an assembly edge/relation."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/"
        response = requests.delete(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        self.scanner.reset()

    def create_item(self, prefix, description):
        """Generates the next Part Number in category and creates a new BOM row."""
        items = self.get_items()
        
        prefix_dash = f"{prefix}-"
        existing_suffixes = []
        for item in items:
            pn = item.get("Part Number")
            if pn and pn.startswith(prefix_dash):
                suffix = pn[len(prefix_dash):]
                if suffix.isdigit():
                    existing_suffixes.append(int(suffix))
                    
        next_num = 0
        if existing_suffixes:
            next_num = max(existing_suffixes) + 1
            
        new_pn = f"{prefix}-{next_num:05d}"
        
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": description if description else f"New Item ({new_pn})",
            "Revision": "A",
            "State": "Engineerig Use"
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def recategorize_item(self, item_id, new_prefix):
        """
        Duplicates the item under a new category prefix, re-links all assembly
        edges (where this item was parent or child) to the new item, and marks
        the old item as EOL.

        Returns the newly created item dict.
        """
        # 1. Fetch the source item row
        src_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        resp = requests.get(src_url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        src_item = resp.json()

        # 2. Determine new PN (next running number for new prefix)
        items = self.get_items()
        prefix_dash = f"{new_prefix}-"
        existing_suffixes = []
        for item in items:
            pn = item.get("Part Number")
            if pn and pn.startswith(prefix_dash):
                suffix = pn[len(prefix_dash):]
                if suffix.isdigit():
                    existing_suffixes.append(int(suffix))
        next_num = (max(existing_suffixes) + 1) if existing_suffixes else 0
        new_pn = f"{new_prefix}-{next_num:05d}"

        # 3. Create new item copying fields from source
        create_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": src_item.get("Item description", ""),
            "Revision": src_item.get("Revision", "A"),
            "State": "Engineerig Use",
            "Source URL": src_item.get("Source URL", ""),
            "External Part Number": src_item.get("External Part Number", ""),
            "Notes": src_item.get("Notes", ""),
        }

        # Copy manufacturer link if present
        manufacturer_links = src_item.get("Manufacturer", [])
        if manufacturer_links:
            payload["Manufacturer"] = [m["id"] for m in manufacturer_links if "id" in m]

        create_resp = requests.post(create_url, headers=self.headers, json=payload, timeout=10)
        create_resp.raise_for_status()
        new_item = create_resp.json()
        new_item_id = new_item["id"]

        # 4. Re-link assembly edges
        assembly_rows = self._get_all_rows(self.table_assembly)
        for edge in assembly_rows:
            parent_link = edge.get("Item") or []
            child_link = edge.get("Contains") or []
            edge_id = edge["id"]
            patch_payload = {}

            if parent_link and parent_link[0].get("id") == item_id:
                patch_payload["Item"] = [new_item_id]
            if child_link and child_link[0].get("id") == item_id:
                patch_payload["Contains"] = [new_item_id]

            if patch_payload:
                patch_url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
                requests.patch(patch_url, headers=self.headers, json=patch_payload, timeout=10).raise_for_status()

        # 5. Mark old item as EOL
        eol_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        requests.patch(eol_url, headers=self.headers, json={"State": "EOL"}, timeout=10).raise_for_status()

        self.scanner.reset()
        return new_item

