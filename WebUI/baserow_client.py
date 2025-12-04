import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

class BaserowClient:
    def __init__(self):
        self.api_url = os.getenv("BASEROW_API_URL")
        self.token = os.getenv("BASEROW_TOKEN")
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        self.table_parts = "508"
        self.table_hierarchy = "701"

        # Field IDs
        self.field_part_number = "field_6795"
        self.field_item_description = "field_6632"
        self.field_contained_by = "field_6805" # Link to 701

        self.field_edge_parent = "field_6802" # Link to 508
        self.field_edge_child = "field_6803"  # Link to 508
        self.field_edge_amount = "field_6806"

    def _get_all_rows(self, table_id, filters=None):
        """Helper to fetch all rows handling pagination if necessary, though basic fetch is usually 100."""
        url = f"{self.api_url}/api/database/rows/table/{table_id}/"
        params = {"user_field_names": "false"}
        if filters:
            params.update(filters)

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_roots(self):
        """
        Query Table 508. Filter for rows where field_6805 (Contained by) is empty.
        """
        # Filter: field_6805 is empty.
        # Baserow API filter syntax for empty link row might vary.
        # Usually filter__field_ID__empty=true works for many field types.
        filters = {
            f"filter__{self.field_contained_by}__empty": "true"
        }
        data = self._get_all_rows(self.table_parts, filters)

        # Sort by ID for consistency
        results = data.get("results", [])
        results.sort(key=lambda x: x["id"])
        return results

    def get_children(self, parent_id):
        """
        Query Table 701 for edges where parent is parent_id.
        Then fetch Table 508 for the children.
        """
        # 1. Get Edges
        # field_6802 is "Item" (Parent). It's a link field.
        # Filter syntax: filter__field_6802__link_row_has=parent_id
        filters = {
            f"filter__{self.field_edge_parent}__link_row_has": parent_id
        }
        edges_data = self._get_all_rows(self.table_hierarchy, filters)
        edges = edges_data.get("results", [])

        if not edges:
            return []

        # 2. Extract Child IDs and Map Edge IDs
        # Map child_id -> edge_id (so we can attach it to the node)
        # Note: A child should only appear once under a specific parent in a valid BOM,
        # but if it appears multiple times, we might have issues. Assuming unique edges.
        child_to_edge_map = {}
        child_ids = []

        for edge in edges:
            # field_6803 is "Contains" (Child).
            # It returns a list of objects usually: [{"id": 1, "value": "Name"}, ...]
            children_links = edge.get(self.field_edge_child, [])
            for link in children_links:
                c_id = link["id"]
                child_ids.append(c_id)
                child_to_edge_map[c_id] = edge["id"]

        if not child_ids:
            return []

        # 3. Fetch Parts Details
        # We need to fetch details for these IDs.
        # Constructing a filter for multiple IDs: filter__id__in=1,2,3
        # If the list is too long, we might need to batch, but for now assuming reasonable size.
        ids_str = ",".join(map(str, child_ids))
        part_filters = {
            "filter__id__in": ids_str
        }
        parts_data = self._get_all_rows(self.table_parts, part_filters)
        parts = parts_data.get("results", [])

        # 4. Attach Edge ID to the Part object for the UI
        final_list = []
        for part in parts:
            p_id = part["id"]
            # We create a wrapper or just inject the edge_id
            # Injecting into the dictionary is easiest for template rendering
            part["__edge_id"] = child_to_edge_map.get(p_id)
            final_list.append(part)

        # Sort by Part ID
        final_list.sort(key=lambda x: x["id"])
        return final_list

    def move_item(self, item_id, new_parent_id, edge_id=None):
        """
        Move item_id to new_parent_id.
        If edge_id is provided, it's an existing child being moved (PATCH).
        If edge_id is None, it's a Root being moved (POST).
        """
        if edge_id:
            # PATCH existing edge
            # We are changing the Parent (field_6802) to new_parent_id
            url = f"{self.api_url}/api/database/rows/table/{self.table_hierarchy}/{edge_id}/"
            payload = {
                self.field_edge_parent: [int(new_parent_id)] # Link fields expect list of IDs
            }
            params = {"user_field_names": "false"}
            response = requests.patch(url, headers=self.headers, json=payload, params=params)
            response.raise_for_status()
            # Return the edge ID (it stays the same)
            return {"edge_id": edge_id}
        else:
            # POST new edge (Root becoming Child)
            url = f"{self.api_url}/api/database/rows/table/{self.table_hierarchy}/"
            payload = {
                self.field_edge_parent: [int(new_parent_id)],
                self.field_edge_child: [int(item_id)],
                self.field_edge_amount: "1" # Default quantity
            }
            params = {"user_field_names": "false"}
            response = requests.post(url, headers=self.headers, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            # Return the new edge ID
            return {"edge_id": data["id"]}
