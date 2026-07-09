import os
import requests
import threading
import time
from dotenv import load_dotenv

load_dotenv()

class ProblemScanner:
    def __init__(self):
        self.status = "pending"  # "pending", "running", "completed", "failed"
        self.problems = {}  # part_id -> list of problem strings
        self._lock = threading.Lock()

    def start_scan(self, client):
        with self._lock:
            if self.status == "running":
                return
            self.status = "running"
            
        def run():
            try:
                # Simulate a delay so the user sees the asynchronous nature in action
                time.sleep(5)
                
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
                    
                    # Problem #1: Production Use but not in assembly
                    state_obj = row.get("State")
                    is_production = state_obj and state_obj.get("value") == "Production Use"
                    is_in_assembly = pid in child_ids
                    
                    if is_production and not is_in_assembly:
                        row_problems.append("Production item not belonging in any assembly")
                        
                    # Problem #2: Source is not Octopart
                    source = row.get("Source")
                    if source and source.strip() != "":
                        if "octopart.com" not in source.lower():
                            row_problems.append("Source link is not an Octopart link")
                            
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


class BaserowClient:
    def __init__(self):
        self.api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070")
        self.token = os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        self.table_bom = "703"
        self.table_assembly = "704"
        self.scanner = ProblemScanner()

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
                response = requests.get(next_url, headers=self.headers, params=params)
                first_call = False
            else:
                response = requests.get(next_url, headers=self.headers)
            
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
                    
                    if q is not None and q != "":
                        q_label = f"{q} pcs"
                    elif l is not None and l != "":
                        q_label = f"{l} mm"
                    else:
                        q_label = "1 pcs"

                    child_branch["quantity_label"] = q_label
                    child_branch["pcb_symbol"] = rel["pcb_symbol"]
                    child_branch["edge_id"] = rel["id"]
                    children.append(child_branch)

            problems_count = None
            if self.scanner.status == "completed":
                problems_count = len(self.scanner.problems.get(part_id, []))

            return {
                "id": part_id,
                "part_number": part.get("Part Number", ""),
                "description": part.get("Item description", ""),
                "search_helper": part.get("Search helper", ""),
                "problems_count": problems_count,
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
        """Gets a single item from the BOM table."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        item = response.json()
        
        problems = []
        if self.scanner.status == "completed":
            problems = self.scanner.problems.get(item_id, [])
            
        item["problems"] = problems
        return item

    def update_item(self, item_id, data):
        """Updates an item in the BOM table."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
        
        # Reset scanner to trigger re-evaluation of problems in background
        self.scanner.reset()
        return response.json()
