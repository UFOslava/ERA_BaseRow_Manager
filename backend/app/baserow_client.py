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

def get_next_revision_str(rev_str):
    if not rev_str:
        return "A"
    rev = str(rev_str).strip().upper()
    if not rev or not rev.isalpha():
        return "A"
    chars = list(rev)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] == 'Z':
            chars[i] = 'A'
            i -= 1
        else:
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
    return "A" + "".join(chars)

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
        self.table_instructions = "5770"
        self.table_pn_categories = os.getenv("BASEROW_TABLE_PN_CATEGORIES", "42471")
        self.scanner = ProblemScanner()
        self.rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "category_rules.json")
        self.rules = self._get_default_rules()

    def _get_default_rules(self):
        try:
            if os.path.exists(self.rules_path):
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading fallback rules: {e}")
        return {
            "10": {"name": "Raw Material", "color": "#ff0000"},
            "20": {"name": "Mechanical COTS", "color": "#3b82f6"},
            "30": {"name": "Mechanical Custom", "color": "#8b5cf6"},
            "40": {"name": "Electrical COTS", "color": "#06b6d4"},
            "50": {"name": "Electrical Custom", "color": "#ec4899"},
            "55": {"name": "Assemblies & Kits", "color": "#ff0000"},
            "60": {"name": "Software", "color": "#00ff80"},
            "70": {"name": "Packaging & Labeling", "color": "#84cc16"},
            "80": {"name": "Products", "color": "#ef4444"},
            "90": {"name": "Tooling & Fixtures", "color": "#d946ef"},
            "99": {"name": "Prototype", "color": "#f97316"}
        }

    def load_rules(self):
        url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/?user_field_names=true&size=200"
        try:
            response = self._request("GET", url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                rules = {}
                for row in data.get("results", []):
                    prefix = str(row.get("Prefix", "")).strip()
                    if prefix:
                        rules[prefix] = {
                            "id": row.get("id"),
                            "name": row.get("Name", "Unknown"),
                            "color": row.get("Color", "#8e9095")
                        }
                if rules:
                    self.rules = rules
                    return rules
        except Exception as e:
            print(f"Error loading rules from Baserow: {e}")

        return self.rules

    def save_rules(self, rules):
        try:
            existing_rules = self.load_rules()
            prefix_to_id = {}
            if isinstance(existing_rules, dict):
                for prefix, data in existing_rules.items():
                    if isinstance(data, dict) and "id" in data:
                        prefix_to_id[str(prefix)] = data["id"]

            for prefix, cat_data in rules.items():
                name = cat_data.get("name", "") if isinstance(cat_data, dict) else str(cat_data)
                color = cat_data.get("color", "#8e9095") if isinstance(cat_data, dict) else "#8e9095"
                str_prefix = str(prefix)
                payload = {"Prefix": str_prefix, "Name": name, "Color": color}

                if str_prefix in prefix_to_id:
                    row_id = prefix_to_id[str_prefix]
                    url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/{row_id}/?user_field_names=true"
                    self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
                else:
                    url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/?user_field_names=true"
                    self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Error saving rules to Baserow: {e}")

        self.rules = rules
        return True

    def get_pn_tag(self, part_number, item_data=None):
        if item_data and isinstance(item_data.get("PN Category"), list) and item_data["PN Category"]:
            cat_item = item_data["PN Category"][0]
            if isinstance(cat_item, dict):
                cat_id = cat_item.get("id")
                cat_value = cat_item.get("value", "")
                for prefix_code, rule in self.rules.items():
                    if isinstance(rule, dict) and (rule.get("id") == cat_id or rule.get("name") == cat_value):
                        return {
                            "name": rule.get("name", cat_value or "Unknown"),
                            "color": rule.get("color", "#8e9095")
                        }
                if cat_value:
                    return {"name": cat_value, "color": "#8e9095"}

        if not part_number:
            return {"name": "Unknown", "color": "#8e9095"}
        
        prefix = part_number[:2]
        rule = self.rules.get(prefix)
        if isinstance(rule, dict):
            return {
                "name": rule.get("name", "Unknown"),
                "color": rule.get("color", "#8e9095")
            }
        return {"name": "Unknown", "color": "#8e9095"}

    def _request(self, method, url, retries=4, backoff_factor=0.3, **kwargs):
        """Sends an HTTP request with automatic retries on 502, 503, 504, 429, and connection errors."""
        import time
        last_exception = None
        func = getattr(requests, method.lower())
        for attempt in range(retries + 1):
            try:
                response = func(url, **kwargs)
                if getattr(response, "status_code", None) in (429, 500, 502, 503, 504) and attempt < retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    time.sleep(sleep_time)
                    continue
                return response
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                last_exception = e
                if attempt < retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
                    raise e
        if last_exception:
            raise last_exception
        return response

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
                response = self._request("GET", next_url, headers=self.headers, params=params, timeout=10)
                first_call = False
            else:
                response = self._request("GET", next_url, headers=self.headers, timeout=10)
            
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
        response = self._request("GET", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        
        item = response.json()
        item["pn_tag"] = self.get_pn_tag(item.get("Part Number"))
        item["Blackbox"] = bool(item.get("Blackbox", False))
        
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
        response = self._request("PATCH", url, headers=self.headers, json=data, timeout=10)
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
        response = self._request("POST", url, headers=headers, files=files, timeout=30)
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
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def update_assembly(self, edge_id, quantity=None, length=None, pcb_symbol=None):
        """Updates an existing relation edge in the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
        payload = {}
        if quantity is not None: payload["Amount of Times"] = quantity
        if length is not None: payload["Length (mm)"] = length
        if pcb_symbol is not None: payload["PCB Symbol"] = pcb_symbol

        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def delete_assembly(self, edge_id):
        """Deletes a relation edge from the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/"
        response = self._request("DELETE", url, headers=self.headers, timeout=10)
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
        cat_rule = self.rules.get(str(prefix))
        if isinstance(cat_rule, dict) and "id" in cat_rule:
            payload["PN Category"] = [cat_rule["id"]]
        
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
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
        resp = self._request("GET", src_url, headers=self.headers, timeout=10)
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

        # Extract original State
        state_data = src_item.get("State")
        old_state = "Engineerig Use"
        if state_data:
            if isinstance(state_data, dict):
                old_state = state_data.get("value", "Engineerig Use")
            else:
                old_state = str(state_data)

        # 3. Create new item copying fields from source
        create_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": src_item.get("Item description", ""),
            "Revision": src_item.get("Revision", "A"),
            "State": old_state,
            "Source URL": src_item.get("Source URL", ""),
            "External Part Number": src_item.get("External Part Number", ""),
            "Notes": src_item.get("Notes", ""),
        }

        cat_rule = self.rules.get(str(new_prefix))
        if isinstance(cat_rule, dict) and "id" in cat_rule:
            payload["PN Category"] = [cat_rule["id"]]

        # Copy manufacturer link if present
        manufacturer_links = src_item.get("Manufacturer", [])
        if manufacturer_links:
            payload["Manufacturer"] = [m["id"] for m in manufacturer_links if "id" in m]

        create_resp = self._request("POST", create_url, headers=self.headers, json=payload, timeout=10)
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
                self._request("PATCH", patch_url, headers=self.headers, json=patch_payload, timeout=10).raise_for_status()

        # 5. Mark old item as EOL
        eol_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        self._request("PATCH", eol_url, headers=self.headers, json={"State": "EOL"}, timeout=10).raise_for_status()

        self.scanner.reset()
        return new_item

    def add_revision(self, item_id):
        """
        Creates a new revision of an existing item:
        - Same Part Number
        - Revision incremented (A->B, Z->AA, AZ->BA, etc.)
        - Identical BOM line fields
        - Copies previous revision's children (contained items), but NOT parent relationships.
        - Returns newly created item dict.
        """
        src_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        resp = self._request("GET", src_url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        src_item = resp.json()

        pn = src_item.get("Part Number")
        if not pn:
            raise ValueError("Item has no Part Number")

        # Find all existing revisions for this PN
        all_items = self.get_items()
        matching_revs = [
            str(it.get("Revision")).strip().upper()
            for it in all_items
            if it.get("Part Number") == pn and it.get("Revision") and str(it.get("Revision")).strip().isalpha()
        ]

        if not matching_revs:
            src_rev = str(src_item.get("Revision", "")).strip().upper()
            matching_revs = [src_rev] if src_rev and src_rev.isalpha() else ["A"]

        # Sort by length then string to find highest revision
        matching_revs.sort(key=lambda r: (len(r), r))
        highest_rev = matching_revs[-1]
        next_rev = get_next_revision_str(highest_rev)

        # Extract original State
        state_data = src_item.get("State")
        old_state = "Engineerig Use"
        if state_data:
            if isinstance(state_data, dict):
                old_state = state_data.get("value", "Engineerig Use")
            else:
                old_state = str(state_data)

        create_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": pn,
            "Item description": src_item.get("Item description", ""),
            "Revision": next_rev,
            "State": old_state,
            "Source URL": src_item.get("Source URL", ""),
            "External Part Number": src_item.get("External Part Number", ""),
            "Notes": src_item.get("Notes", ""),
        }

        manufacturer_links = src_item.get("Manufacturer", [])
        if manufacturer_links:
            payload["Manufacturer"] = [m["id"] for m in manufacturer_links if isinstance(m, dict) and "id" in m]

        pn_category = src_item.get("PN Category", [])
        if pn_category:
            payload["PN Category"] = [x["id"] for x in pn_category if isinstance(x, dict) and "id" in x]

        create_resp = self._request("POST", create_url, headers=self.headers, json=payload, timeout=10)
        create_resp.raise_for_status()
        new_item = create_resp.json()
        new_item_id = new_item["id"]

        # Copy previous revision's children (contained items), but NOT parent relationships
        assembly_rows = self._get_all_rows(self.table_assembly)
        for edge in assembly_rows:
            parent_link = edge.get("Item") or []
            child_link = edge.get("Contains") or []

            if isinstance(parent_link, list) and len(parent_link) > 0 and parent_link[0].get("id") == item_id:
                if isinstance(child_link, list) and len(child_link) > 0:
                    child_id = child_link[0].get("id")
                    quantity = edge.get("Amount of Times")
                    length = edge.get("Length (mm)")
                    pcb_symbol = edge.get("PCB Symbol")
                    self.create_assembly(new_item_id, child_id, quantity, length, pcb_symbol)

        self.scanner.reset()
        return new_item

    def get_instruction_sets_for_item(self, parent_id):
        """Returns a list of available instruction sets for a parent item."""
        instruction_rows = self._get_all_rows(self.table_instructions)
        set_counts = {}
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                if p_link[0].get("id") == parent_id:
                    s_idx = row.get("Set Index") or 1
                    try:
                        s_idx = int(s_idx)
                    except (ValueError, TypeError):
                        s_idx = 1
                    set_counts[s_idx] = set_counts.get(s_idx, 0) + 1

        sets = [{"set_index": s_idx, "step_count": count} for s_idx, count in sorted(set_counts.items())]
        return sets

    def get_instruction_set_details(self, parent_id, set_index):
        """
        Fetches steps for a specific parent item and set index, and calculates
        the comparison table (Assembly vs Instructions) adhering to Blackbox rules.
        """
        instruction_rows = self._get_all_rows(self.table_instructions)
        bom_rows = self._get_all_rows(self.table_bom)
        assembly_rows = self._get_all_rows(self.table_assembly)

        bom_map = {r["id"]: r for r in bom_rows}

        # Identify items that have ANY instructions (in table 5770)
        items_with_instructions = set()
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                items_with_instructions.add(p_link[0].get("id"))

        # Filter steps for this parent_id and set_index
        set_steps = []
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                if p_link[0].get("id") == parent_id:
                    s_idx = row.get("Set Index") or 1
                    try:
                        s_idx = int(s_idx)
                    except (ValueError, TypeError):
                        s_idx = 1
                    if s_idx == set_index:
                        set_steps.append(row)

        # Sort steps by Step Order
        set_steps.sort(key=lambda x: int(x.get("Step Order") or 0))

        # Format steps output
        formatted_steps = []
        for s in set_steps:
            rec = s.get("Action Receiving Item")
            child = s.get("Child Item")
            tool = s.get("Tool")

            rec_item = bom_map.get(rec[0]["id"]) if (rec and isinstance(rec, list) and len(rec) > 0) else None
            child_item = bom_map.get(child[0]["id"]) if (child and isinstance(child, list) and len(child) > 0) else None
            tool_item = bom_map.get(tool[0]["id"]) if (tool and isinstance(tool, list) and len(tool) > 0) else None

            formatted_steps.append({
                "id": s["id"],
                "set_index": set_index,
                "step_order": s.get("Step Order"),
                "action": s.get("Action", ""),
                "quantity": s.get("Quantity", 1),
                "description": s.get("Description", ""),
                "photo": s.get("Photo", []),
                "receiving_item": {
                    "id": rec_item["id"],
                    "part_number": rec_item.get("Part Number", ""),
                    "description": rec_item.get("Item description", "")
                } if rec_item else None,
                "child_item": {
                    "id": child_item["id"],
                    "part_number": child_item.get("Part Number", ""),
                    "description": child_item.get("Item description", "")
                } if child_item else None,
                "tool": {
                    "id": tool_item["id"],
                    "part_number": tool_item.get("Part Number", ""),
                    "description": tool_item.get("Item description", "")
                } if tool_item else None
            })

        # Hierarchy traversal to compute required quantities
        parent_to_children = {}
        for edge in assembly_rows:
            p_link = edge.get("Item")
            c_link = edge.get("Contains")
            if p_link and c_link and isinstance(p_link, list) and isinstance(c_link, list):
                pid = p_link[0]["id"]
                cid = c_link[0]["id"]
                q = edge.get("Amount of Times")
                qty = int(q) if (q is not None and q != "") else 1
                if pid not in parent_to_children:
                    parent_to_children[pid] = []
                parent_to_children[pid].append({"child_id": cid, "quantity": qty, "edge_id": edge["id"]})

        required_totals = {}

        def traverse(current_id, current_multiplier, visited):
            if current_id in visited:
                return
            rels = parent_to_children.get(current_id, [])
            for rel in rels:
                cid = rel["child_id"]
                qty = rel["quantity"] * current_multiplier
                required_totals[cid] = required_totals.get(cid, 0) + qty

                child_part = bom_map.get(cid, {})
                is_blackbox = bool(child_part.get("Blackbox", False))
                has_instructions = cid in items_with_instructions

                if not is_blackbox and not has_instructions:
                    traverse(cid, qty, visited | {current_id})

        traverse(parent_id, 1, set())

        # Sum instructed quantities for this set
        instructed_totals = {}
        for s in set_steps:
            child = s.get("Child Item")
            if child and isinstance(child, list) and len(child) > 0:
                cid = child[0]["id"]
                q = s.get("Quantity") or 1
                try:
                    q = int(q)
                except (ValueError, TypeError):
                    q = 1
                instructed_totals[cid] = instructed_totals.get(cid, 0) + q

        all_child_ids = set(required_totals.keys()) | set(instructed_totals.keys())
        comparison = []

        for cid in sorted(all_child_ids):
            part = bom_map.get(cid, {})
            req = required_totals.get(cid, 0)
            inst = instructed_totals.get(cid, 0)

            in_hierarchy = cid in required_totals

            if not in_hierarchy:
                discrepancy = "Not in Hierarchy"
            elif inst == 0:
                discrepancy = "Missing Instruction"
            elif inst < req:
                discrepancy = "Under-instructed"
            elif inst > req:
                discrepancy = "Over-instructed"
            else:
                discrepancy = "OK"

            comparison.append({
                "item_id": cid,
                "part_number": part.get("Part Number", f"Item #{cid}"),
                "description": part.get("Item description", ""),
                "required_qty": req,
                "instructed_qty": inst,
                "discrepancy": discrepancy,
                "in_hierarchy": in_hierarchy
            })

        return {
            "steps": formatted_steps,
            "comparison": comparison
        }

    def create_instruction_step(self, parent_id, set_index, step_data):
        """Creates a step in the Assembly Instructions table (5770)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/?user_field_names=true"
        
        existing_steps = self.get_instruction_set_details(parent_id, set_index)["steps"]
        max_order = max([int(s["step_order"] or 0) for s in existing_steps], default=0)

        payload = {
            "Parent Item": [parent_id],
            "Set Index": set_index,
            "Step Order": step_data.get("step_order", max_order + 1),
            "Action": step_data.get("action", ""),
            "Quantity": step_data.get("quantity", 1),
            "Description": step_data.get("description", "")
        }

        if step_data.get("receiving_item_id"):
            payload["Action Receiving Item"] = [step_data["receiving_item_id"]]
        if step_data.get("child_item_id"):
            payload["Child Item"] = [step_data["child_item_id"]]
        if step_data.get("tool_id"):
            payload["Tool"] = [step_data["tool_id"]]
        if step_data.get("photo"):
            payload["Photo"] = step_data["photo"]

        res = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def update_instruction_step(self, step_id, step_data):
        """Updates a step in table 5770."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/{step_id}/?user_field_names=true"
        payload = {}

        if "action" in step_data:
            payload["Action"] = step_data["action"]
        if "quantity" in step_data:
            payload["Quantity"] = step_data["quantity"]
        if "description" in step_data:
            payload["Description"] = step_data["description"]
        if "step_order" in step_data:
            payload["Step Order"] = step_data["step_order"]
        if "receiving_item_id" in step_data:
            payload["Action Receiving Item"] = [step_data["receiving_item_id"]] if step_data["receiving_item_id"] else []
        if "child_item_id" in step_data:
            payload["Child Item"] = [step_data["child_item_id"]] if step_data["child_item_id"] else []
        if "tool_id" in step_data:
            payload["Tool"] = [step_data["tool_id"]] if step_data["tool_id"] else []
        if "photo" in step_data:
            payload["Photo"] = step_data["photo"]

        res = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def delete_instruction_step(self, step_id):
        """Deletes a step in table 5770."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/{step_id}/"
        res = self._request("DELETE", url, headers=self.headers, timeout=10)
        res.raise_for_status()

    def reorder_instruction_steps(self, parent_id, set_index, step_ids):
        """Updates Step Order for a list of step IDs."""
        for idx, sid in enumerate(step_ids, start=1):
            self.update_instruction_step(sid, {"step_order": idx})

    def delete_instruction_set(self, parent_id, set_index):
        """Deletes all steps for a parent item and set index."""
        details = self.get_instruction_set_details(parent_id, set_index)
        for s in details["steps"]:
            self.delete_instruction_step(s["id"])


