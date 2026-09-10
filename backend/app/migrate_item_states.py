import os
import requests
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

DEFAULT_STATES = [
    {"Name": "Production Use", "Color": "#00FF00"},
    {"Name": "Engineerig Use", "Color": "hsl(210, 75%, 50%)"},
    {"Name": "Unknown", "Color": "hsl(0, 0%, 60%)"},
    {"Name": "Finish Stock (Use Up)", "Color": "hsl(38, 95%, 50%)"},
    {"Name": "EOL", "Color": "hsl(25, 75%, 45%)"},
    {"Name": "Do Not Use (Discard)", "Color": "hsl(355, 80%, 50%)"},
]

def get_jwt_token(api_url, email, password):
    for attempt in range(5):
        try:
            resp = requests.post(f"{api_url}/api/user/token-auth/", json={"username": email, "password": password}, timeout=15)
            if resp.status_code == 200:
                return resp.json()["token"]
            elif resp.status_code in (502, 503, 504, 429):
                time.sleep(2)
            else:
                resp.raise_for_status()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(2)
    raise ConnectionError("Failed to get JWT token after multiple attempts due to connection issues.")

def run_migration():
    api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070").rstrip("/")
    admin_email = os.getenv("BASEROW_ADMIN_EMAIL")
    admin_password = os.getenv("BASEROW_ADMIN_PASSWORD")
    db_token = os.getenv("BASEROW_TOKEN", "")

    if not admin_email or not admin_password:
        raise ValueError("BASEROW_ADMIN_EMAIL and BASEROW_ADMIN_PASSWORD must be configured in environment.")

    jwt_token = get_jwt_token(api_url, admin_email, admin_password)
    jwt_headers = {"Authorization": f"JWT {jwt_token}", "Content-Type": "application/json"}

    # 1. Find Database ID containing Table 508 (BOM)
    apps_resp = requests.get(f"{api_url}/api/applications/", headers=jwt_headers)
    apps_resp.raise_for_status()
    apps = apps_resp.json()

    database_id = None
    for app in apps:
        if app.get("type") == "database":
            tables_resp = requests.get(f"{api_url}/api/database/tables/database/{app['id']}/", headers=jwt_headers)
            if tables_resp.status_code == 200:
                tables = tables_resp.json()
                if any(t["id"] == 508 or t["name"] == "BOM" for t in tables):
                    database_id = app["id"]
                    break

    if not database_id:
        raise ValueError("Could not locate database containing BOM table (508).")

    # 2. Check if "States" table already exists
    tables_resp = requests.get(f"{api_url}/api/database/tables/database/{database_id}/", headers=jwt_headers)
    tables_resp.raise_for_status()
    tables = tables_resp.json()

    states_table = next((t for t in tables if t["name"] == "States"), None)

    if not states_table:
        print("Creating table 'States'...")
        create_resp = requests.post(
            f"{api_url}/api/database/tables/database/{database_id}/",
            headers=jwt_headers,
            json={"name": "States"}
        )
        create_resp.raise_for_status()
        states_table = create_resp.json()
        print(f"Table 'States' created with ID {states_table['id']}")

    states_table_id = states_table["id"]

    # 3. Ensure fields (Name, Color) exist on States table
    fields_resp = requests.get(f"{api_url}/api/database/fields/table/{states_table_id}/", headers=jwt_headers)
    fields_resp.raise_for_status()
    fields = fields_resp.json()

    primary_field = next((f for f in fields if f.get("primary")), None)
    if primary_field and primary_field["name"] != "Name":
        requests.patch(
            f"{api_url}/api/database/fields/{primary_field['id']}/",
            headers=jwt_headers,
            json={"name": "Name"}
        )

    field_names = {f["name"] for f in fields}
    if "Color" not in field_names:
        requests.post(
            f"{api_url}/api/database/fields/table/{states_table_id}/",
            headers=jwt_headers,
            json={"name": "Color", "type": "text"}
        )

    # 4. Seed default states if table is empty
    rows_resp = requests.get(f"{api_url}/api/database/rows/table/{states_table_id}/?user_field_names=true", headers=jwt_headers)
    rows_resp.raise_for_status()
    existing_state_rows = rows_resp.json().get("results", [])

    existing_names = {str(r.get("Name")) for r in existing_state_rows if r.get("Name")}
    for state in DEFAULT_STATES:
        if state["Name"] not in existing_names:
            requests.post(
                f"{api_url}/api/database/rows/table/{states_table_id}/?user_field_names=true",
                headers=jwt_headers,
                json=state
            )
            print(f"Added state row for {state['Name']}")

    # Refresh states mapping
    rows_resp = requests.get(f"{api_url}/api/database/rows/table/{states_table_id}/?user_field_names=true", headers=jwt_headers)
    rows_resp.raise_for_status()
    state_rows = rows_resp.json().get("results", [])
    name_to_state_id = {str(r["Name"]): r["id"] for r in state_rows if r.get("Name")}

    # 5. Locate existing BOM State field, fetch all current rows to map original State values
    bom_fields_resp = requests.get(f"{api_url}/api/database/fields/table/508/", headers=jwt_headers)
    bom_fields_resp.raise_for_status()
    bom_fields = bom_fields_resp.json()

    state_field = next((f for f in bom_fields if f["name"] == "State"), None)
    if not state_field:
        raise ValueError("Could not find field 'State' in BOM table (508).")

    # Fetch BOM rows to remember original State values
    bom_rows = []
    page = 1
    while True:
        resp = requests.get(f"{api_url}/api/database/rows/table/508/?user_field_names=true&page={page}&size=100", headers=jwt_headers)
        resp.raise_for_status()
        data = resp.json()
        bom_rows.extend(data.get("results", []))
        if not data.get("next"):
            break
        page += 1

    row_to_original_state = {}
    for item in bom_rows:
        val = item.get("State")
        # Extract name if it's a dict (single-select format)
        if isinstance(val, dict):
            state_val = val.get("value")
            if state_val:
                row_to_original_state[item["id"]] = state_val
        elif isinstance(val, list):
            # Already link_row, skip
            pass
        elif val:
            state_val = str(val)
            row_to_original_state[item["id"]] = state_val

    # 6. Change "State" field type to link_row if it is not already
    if state_field.get("type") != "link_row":
        print("Changing field 'State' in BOM table (508) to link_row field...")
        update_resp = requests.patch(
            f"{api_url}/api/database/fields/{state_field['id']}/",
            headers=jwt_headers,
            json={
                "name": "State",
                "type": "link_row",
                "link_row_table_id": states_table_id
            }
        )
        update_resp.raise_for_status()
        print("Field 'State' changed to link_row type.")

    # 7. Backfill state links
    linked_count = 0
    for item_id, orig_state in row_to_original_state.items():
        state_id = name_to_state_id.get(orig_state)
        # Fallback to "Unknown" if state not found
        if not state_id:
            state_id = name_to_state_id.get("Unknown")
            
        if state_id:
            for attempt in range(3):
                try:
                    patch_resp = requests.patch(
                        f"{api_url}/api/database/rows/table/508/{item_id}/?user_field_names=true",
                        headers=jwt_headers,
                        json={"State": [state_id]}
                    )
                    if patch_resp.status_code == 200:
                        linked_count += 1
                        break
                except Exception:
                    time.sleep(0.5)
            time.sleep(0.05)

    print(f"Migration completed! States table ID: {states_table_id}. Backfilled {linked_count} BOM items.")
    return {
        "states_table_id": states_table_id,
        "backfilled_count": linked_count
    }

if __name__ == "__main__":
    run_migration()
