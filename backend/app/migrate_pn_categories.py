import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

DEFAULT_CATEGORIES = [
    {"Prefix": "10", "Name": "Raw Material", "Color": "#ff0000"},
    {"Prefix": "20", "Name": "Mechanical COTS", "Color": "#3b82f6"},
    {"Prefix": "30", "Name": "Mechanical Custom", "Color": "#8b5cf6"},
    {"Prefix": "40", "Name": "Electrical COTS", "Color": "#06b6d4"},
    {"Prefix": "50", "Name": "Electrical Custom", "Color": "#ec4899"},
    {"Prefix": "55", "Name": "Assemblies & Kits", "Color": "#ff0000"},
    {"Prefix": "60", "Name": "Software", "Color": "#00ff80"},
    {"Prefix": "70", "Name": "Packaging & Labeling", "Color": "#84cc16"},
    {"Prefix": "80", "Name": "Products", "Color": "#ef4444"},
    {"Prefix": "90", "Name": "Tooling & Fixtures", "Color": "#d946ef"},
    {"Prefix": "99", "Name": "Prototype", "Color": "#f97316"},
]

def get_jwt_token(api_url, email, password):
    resp = requests.post(f"{api_url}/api/user/token-auth/", json={"username": email, "password": password})
    resp.raise_for_status()
    return resp.json()["token"]

def run_migration():
    api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070").rstrip("/")
    admin_email = os.getenv("BASEROW_ADMIN_EMAIL")
    admin_password = os.getenv("BASEROW_ADMIN_PASSWORD")
    db_token = os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")

    if not admin_email or not admin_password:
        raise ValueError("BASEROW_ADMIN_EMAIL and BASEROW_ADMIN_PASSWORD must be configured in environment.")

    jwt_token = get_jwt_token(api_url, admin_email, admin_password)
    jwt_headers = {"Authorization": f"JWT {jwt_token}", "Content-Type": "application/json"}
    db_headers = {"Authorization": f"Token {db_token}", "Content-Type": "application/json"}

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

    # 2. Check if "PN Categories" table already exists
    tables_resp = requests.get(f"{api_url}/api/database/tables/database/{database_id}/", headers=jwt_headers)
    tables_resp.raise_for_status()
    tables = tables_resp.json()

    pn_cat_table = next((t for t in tables if t["name"] == "PN Categories"), None)

    if not pn_cat_table:
        print("Creating table 'PN Categories'...")
        create_resp = requests.post(
            f"{api_url}/api/database/tables/database/{database_id}/",
            headers=jwt_headers,
            json={"name": "PN Categories"}
        )
        create_resp.raise_for_status()
        pn_cat_table = create_resp.json()
        print(f"Table 'PN Categories' created with ID {pn_cat_table['id']}")

    pn_cat_table_id = pn_cat_table["id"]

    # 3. Ensure fields (Prefix, Name, Color) exist on PN Categories table
    fields_resp = requests.get(f"{api_url}/api/database/fields/table/{pn_cat_table_id}/", headers=jwt_headers)
    fields_resp.raise_for_status()
    fields = fields_resp.json()

    primary_field = next((f for f in fields if f.get("primary")), None)
    if primary_field and primary_field["name"] != "Prefix":
        requests.patch(
            f"{api_url}/api/database/fields/{primary_field['id']}/",
            headers=jwt_headers,
            json={"name": "Prefix"}
        )

    field_names = {f["name"] for f in fields}
    if "Name" not in field_names:
        requests.post(
            f"{api_url}/api/database/fields/table/{pn_cat_table_id}/",
            headers=jwt_headers,
            json={"name": "Name", "type": "text"}
        )

    if "Color" not in field_names:
        requests.post(
            f"{api_url}/api/database/fields/table/{pn_cat_table_id}/",
            headers=jwt_headers,
            json={"name": "Color", "type": "text"}
        )

    # 4. Seed default categories if table is empty
    rows_resp = requests.get(f"{api_url}/api/database/rows/table/{pn_cat_table_id}/?user_field_names=true", headers=jwt_headers)
    rows_resp.raise_for_status()
    existing_cat_rows = rows_resp.json().get("results", [])

    existing_prefixes = {str(r.get("Prefix")) for r in existing_cat_rows if r.get("Prefix")}
    for cat in DEFAULT_CATEGORIES:
        if cat["Prefix"] not in existing_prefixes:
            requests.post(
                f"{api_url}/api/database/rows/table/{pn_cat_table_id}/?user_field_names=true",
                headers=jwt_headers,
                json=cat
            )
            print(f"Added category row for prefix {cat['Prefix']}")

    # Refresh categories mapping
    rows_resp = requests.get(f"{api_url}/api/database/rows/table/{pn_cat_table_id}/?user_field_names=true", headers=jwt_headers)
    rows_resp.raise_for_status()
    cat_rows = rows_resp.json().get("results", [])
    prefix_to_cat_id = {str(r["Prefix"]): r["id"] for r in cat_rows if r.get("Prefix")}

    # 5. Check if link_row field "PN Category" exists in Table 508 (BOM)
    bom_fields_resp = requests.get(f"{api_url}/api/database/fields/table/508/", headers=jwt_headers)
    bom_fields_resp.raise_for_status()
    bom_fields = bom_fields_resp.json()

    pn_cat_link_field = next((f for f in bom_fields if f["name"] == "PN Category"), None)

    if not pn_cat_link_field:
        print("Creating link_row field 'PN Category' in BOM table (508)...")
        link_field_resp = requests.post(
            f"{api_url}/api/database/fields/table/508/",
            headers=jwt_headers,
            json={
                "name": "PN Category",
                "type": "link_row",
                "link_row_table_id": pn_cat_table_id
            }
        )
        link_field_resp.raise_for_status()
        pn_cat_link_field = link_field_resp.json()
        print("Field 'PN Category' created in BOM table.")

    # 6. Backfill existing BOM items
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


    linked_count = 0
    import time
    for item in bom_rows:
        pn = item.get("Part Number")
        if pn and len(pn) >= 2:
            prefix = pn[:2]
            cat_id = prefix_to_cat_id.get(prefix)
            current_link = item.get("PN Category")
            current_link_ids = [x["id"] for x in current_link] if isinstance(current_link, list) else []

            if cat_id and (not current_link_ids or current_link_ids[0] != cat_id):
                for attempt in range(3):
                    try:
                        patch_resp = requests.patch(
                            f"{api_url}/api/database/rows/table/508/{item['id']}/?user_field_names=true",
                            headers=jwt_headers,
                            json={"PN Category": [cat_id]}
                        )
                        if patch_resp.status_code == 200:
                            linked_count += 1
                            break
                    except Exception as e:
                        time.sleep(0.5)
                time.sleep(0.05)

    print(f"Migration completed! PN Categories table ID: {pn_cat_table_id}. Backfilled {linked_count} BOM items.")
    return {
        "pn_cat_table_id": pn_cat_table_id,
        "backfilled_count": linked_count
    }

if __name__ == "__main__":
    run_migration()

