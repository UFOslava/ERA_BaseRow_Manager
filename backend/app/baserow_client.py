import os
import requests
from dotenv import load_dotenv

load_dotenv()

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
        # 1. Fetch all items from BOM (703)
        bom_rows = self._get_all_rows(self.table_bom)
        # 2. Fetch all relations from Assembly (704)
        assembly_rows = self._get_all_rows(self.table_assembly)

        # 3. Create a map of BOM parts by ID
        bom_map = {row["id"]: row for row in bom_rows}

        # 4. Construct parent-to-children mapping
        parent_to_children = {}
        child_ids = set()

        for edge in assembly_rows:
            # Extract parent ID
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not parent_link or not child_link:
                continue

            parent_id = parent_link[0]["id"]
            child_id = child_link[0]["id"]

            # Record child ID to identify top-level elements
            child_ids.add(child_id)

            # Metadata
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

        # 5. Identify top-level items
        top_level_ids = [pid for pid in bom_map.keys() if pid not in child_ids]

        # 6. Recursive tree builder
        def build_branch(part_id, visited):
            part = bom_map.get(part_id)
            if not part:
                return None

            # Detect circular reference
            if part_id in visited:
                return {
                    "id": part_id,
                    "part_number": part.get("Part Number", "Unknown"),
                    "description": part.get("Item description", "Circular Reference Detected"),
                    "search_helper": part.get("Search helper", ""),
                    "quantity_label": "Err",
                    "children": [],
                    "is_circular": True
                }

            children = []
            relations = parent_to_children.get(part_id, [])
            for rel in relations:
                child_branch = build_branch(rel["child_id"], visited | {part_id})
                if child_branch:
                    # Attach edge relationship details
                    q = rel["quantity"]
                    l = rel["length"]
                    
                    # Formulate quantity label
                    if q is not None and q != "":
                        q_label = f"{q} pcs"
                    elif l is not None and l != "":
                        q_label = f"{l} mm"
                    else:
                        q_label = "1 pcs"  # fallback

                    child_branch["quantity_label"] = q_label
                    child_branch["pcb_symbol"] = rel["pcb_symbol"]
                    child_branch["edge_id"] = rel["id"]
                    children.append(child_branch)

            return {
                "id": part_id,
                "part_number": part.get("Part Number", ""),
                "description": part.get("Item description", ""),
                "search_helper": part.get("Search helper", ""),
                "children": children
            }

        # Build trees for all top-level items
        forest = []
        for tl_id in top_level_ids:
            tree = build_branch(tl_id, set())
            if tree:
                tree["quantity_label"] = "Root"
                tree["pcb_symbol"] = "N/A"
                forest.append(tree)

        # Sort by ID/Part Number for consistency
        forest.sort(key=lambda x: x["id"])
        return forest
