import os
import sys
import json
import logging
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Base schema definition for all tables used by ERA ERP
ERA_SCHEMA_DEFINITIONS = {
    "BOM": {
        "env_var": "BASEROW_TABLE_BOM",
        "aliases": ["BOM", "Parts", "BOM Items", "Part Number"],
        "default_id": "508",
        "primary_field": {"name": "Part Number", "type": "text"},
        "fields": [
            {"name": "Item description", "type": "text"},
            {"name": "Search helper", "type": "text"},
            {"name": "External PN", "type": "text"},
            {"name": "Notes", "type": "long_text"},
            {"name": "State", "type": "link_row", "link_table": "States"},
            {"name": "PN Category", "type": "link_row", "link_table": "PN Categories"},
            {"name": "Price per unit", "type": "number", "number_decimal_places": 2},
            {"name": "Datasheet", "type": "file"},
            {"name": "Image", "type": "file"},
            {"name": "Blackbox", "type": "boolean"},
            {"name": "Source URL", "type": "url"},
            {"name": "Manufacturer", "type": "link_row", "link_table": "Manufacturers"},
            {"name": "Manufacturer PN", "type": "text"},
            {"name": "Suppliers", "type": "link_row", "link_table": "Suppliers"},
            {"name": "Supplier PN", "type": "text"},
        ]
    },
    "Assembly": {
        "env_var": "BASEROW_TABLE_ASSEMBLY",
        "aliases": ["Assembly", "Assemblies", "Assembly Relations"],
        "default_id": "701",
        "primary_field": {"name": "Item", "type": "link_row", "link_table": "BOM"},
        "fields": [
            {"name": "Contains", "type": "link_row", "link_table": "BOM"},
            {"name": "Amount of Times", "type": "number", "number_decimal_places": 0},
            {"name": "Length", "type": "number", "number_decimal_places": 2},
            {"name": "PCB Symbol", "type": "text"}
        ]
    },
    "Assembly Instructions": {
        "env_var": "BASEROW_TABLE_INSTRUCTIONS",
        "aliases": ["Assembly Instructions", "Instructions", "Work Instructions"],
        "default_id": "5770",
        "primary_field": {"name": "Title", "type": "text"},
        "fields": [
            {"name": "Parent Item", "type": "link_row", "link_table": "BOM"},
            {"name": "Set Index", "type": "number", "number_decimal_places": 0},
            {"name": "Step Number", "type": "number", "number_decimal_places": 0},
            {"name": "Description", "type": "long_text"},
            {"name": "Photo", "type": "file"},
            {"name": "Child Item", "type": "link_row", "link_table": "BOM"},
            {"name": "Quantity", "type": "number", "number_decimal_places": 0},
            {"name": "Toll", "type": "boolean"},
            {"name": "Toll Map", "type": "long_text"},
            {"name": "Notes", "type": "long_text"}
        ]
    },
    "PN Categories": {
        "env_var": "BASEROW_TABLE_PN_CATEGORIES",
        "aliases": ["PN Categories", "Part Categories", "Categories"],
        "default_id": "42471",
        "primary_field": {"name": "Prefix", "type": "text"},
        "fields": [
            {"name": "Name", "type": "text"},
            {"name": "Color", "type": "text"}
        ]
    },
    "States": {
        "env_var": "BASEROW_TABLE_ITEM_STATES",
        "aliases": ["States", "Item States", "Item Lifecycle States"],
        "default_id": "48537",
        "primary_field": {"name": "Name", "type": "text"},
        "fields": [
            {"name": "Color", "type": "text"}
        ]
    },
    "WI Templates": {
        "env_var": "BASEROW_TABLE_WI_TEMPLATES",
        "aliases": ["WI Templates", "Work Instruction Templates", "Document Templates"],
        "default_id": "48538",
        "primary_field": {"name": "Name", "type": "text"},
        "fields": [
            {"name": "File", "type": "file"},
            {"name": "Approved", "type": "boolean"},
            {"name": "Config", "type": "long_text"}
        ]
    },
    "Manufacturers": {
        "env_var": "BASEROW_TABLE_MANUFACTURERS",
        "aliases": ["Manufacturers", "Vendors"],
        "default_id": "683",
        "primary_field": {"name": "Name", "type": "text"},
        "fields": [
            {"name": "Website", "type": "url"},
            {"name": "Logo", "type": "file"},
            {"name": "Notes", "type": "long_text"},
            {"name": "Contacts", "type": "link_row", "link_table": "Contacts"}
        ]
    },
    "Suppliers": {
        "env_var": "BASEROW_TABLE_SUPPLIERS",
        "aliases": ["Suppliers", "Distributors"],
        "default_id": "682",
        "primary_field": {"name": "Name", "type": "text"},
        "fields": [
            {"name": "Website", "type": "url"},
            {"name": "Notes", "type": "long_text"},
            {"name": "Contacts", "type": "link_row", "link_table": "Contacts"}
        ]
    },
    "Contacts": {
        "env_var": "BASEROW_TABLE_CONTACTS",
        "aliases": ["Contacts", "Vendor Contacts", "Supplier Contacts"],
        "default_id": "684",
        "primary_field": {"name": "Name", "type": "text"},
        "fields": [
            {"name": "Email", "type": "email"},
            {"name": "Phone", "type": "text"},
            {"name": "Role", "type": "text"},
            {"name": "Notes", "type": "long_text"}
        ]
    }
}

DEFAULT_PN_CATEGORIES = [
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

DEFAULT_STATES = [
    {"Name": "Production Use", "Color": "#00FF00"},
    {"Name": "Engineerig Use", "Color": "hsl(210, 75%, 50%)"},
    {"Name": "Unknown", "Color": "hsl(0, 0%, 60%)"},
    {"Name": "Finish Stock (Use Up)", "Color": "hsl(38, 95%, 50%)"},
    {"Name": "EOL", "Color": "hsl(25, 75%, 45%)"},
    {"Name": "Do Not Use (Discard)", "Color": "hsl(355, 80%, 50%)"},
]

DEFAULT_QUICK_ACTION_TEMPLATES = [
    {"action": "Solder", "template": "{action} {a.1} onto {a.2} using {t.1}"},
    {"action": "Fasten", "template": "{action} {a.1} to {a.2} using {t.1}"},
    {"action": "Mount", "template": "{action} {a.1} onto {a.2}"},
    {"action": "Glue", "template": "{action} {a.1} to {a.2} with {t.1}"},
    {"action": "Inspect", "template": "{action} {a.1} on {a.2}"}
]

def format_detailed_error(action_attempted: str, error_detail: str, required_actions: list = None):
    """Formats a detailed, actionable error message for Baserow database administration."""
    lines = [
        "",
        "=" * 70,
        "⚠️  BASEROW DATABASE INITIALIZATION / SCHEMA NOTICE",
        "=" * 70,
        f"Action Attempted : {action_attempted}",
        f"Diagnostic Error : {error_detail}",
        "",
        "Why did this happen?",
        "- Baserow Database Tokens (Token ...) possess row-level data access by default.",
        "- Schema-level operations (creating tables/fields, inspecting applications)",
        "  require administrative privileges or a user token in Baserow.",
        "",
        "HOW TO RESOLVE:",
        "Option 1 (Automated):",
        "  Provide BASEROW_ADMIN_EMAIL and BASEROW_ADMIN_PASSWORD in your .env file",
        "  so the initialization script can automatically authenticate and sync schema.",
        "",
        "Option 2 (Manual Setup in Baserow UI):",
        "  Create or verify the required tables and fields in your Baserow database:"
    ]
    if required_actions:
        for idx, act in enumerate(required_actions, 1):
            lines.append(f"  {idx}. {act}")
    else:
        for name, defn in ERA_SCHEMA_DEFINITIONS.items():
            field_list = [f"{defn['primary_field']['name']} ({defn['primary_field']['type']})"]
            field_list.extend([f"{f['name']} ({f['type']})" for f in defn.get("fields", [])])
            lines.append(f"  - Table '{name}' -> Fields: {', '.join(field_list)}")
            
    lines.append("")
    lines.append("Once created, configure their Table IDs in your .env file (e.g. BASEROW_TABLE_BOM=...).")
    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def get_jwt_token(api_url, email, password):
    """Attempts to obtain a JWT token for administrative schema actions."""
    if not email or not password:
        return None
    try:
        resp = requests.post(f"{api_url.rstrip('/')}/api/user/token-auth/", json={"username": email, "password": password}, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("token")
    except Exception as e:
        logger.warning(f"Could not obtain JWT token with admin credentials: {e}")
    return None


def find_env_files():
    """Finds root .env and backend/.env paths."""
    current_dir = os.path.dirname(os.path.abspath(__file__)) # backend/app
    backend_dir = os.path.dirname(current_dir)               # backend
    project_root = os.path.dirname(backend_dir)             # project root

    env_paths = []
    root_env = os.path.join(project_root, ".env")
    backend_env = os.path.join(backend_dir, ".env")

    env_paths.append(root_env)
    if os.path.abspath(root_env) != os.path.abspath(backend_env):
        env_paths.append(backend_env)

    return env_paths


def update_env_files(key_values: dict):
    """
    Non-destructively updates key-value pairs in root .env and backend/.env files.
    If a key already exists, its value is updated; otherwise it is appended.
    """
    if not key_values:
        return

    env_paths = find_env_files()
    for env_path in env_paths:
        existing_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                existing_lines = f.readlines()

        keys_remaining = dict(key_values)
        updated_lines = []

        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in keys_remaining:
                    updated_lines.append(f"{k}={keys_remaining[k]}\n")
                    del keys_remaining[k]
                    continue
            updated_lines.append(line if line.endswith("\n") else line + "\n")

        # Append any new keys that were not previously present
        if keys_remaining:
            if updated_lines and not updated_lines[-1].endswith("\n"):
                updated_lines.append("\n")
            if updated_lines and updated_lines[-1].strip() != "":
                updated_lines.append("\n")
            updated_lines.append("# Discovered Baserow Table IDs\n")
            for k, v in keys_remaining.items():
                updated_lines.append(f"{k}={v}\n")

        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)
            logger.info(f"Updated environment configuration in {env_path}")
        except Exception as e:
            logger.error(f"Failed to update environment file {env_path}: {e}")


def discover_baserow_tables(api_url=None, token=None, admin_email=None, admin_password=None):
    """
    Queries Baserow API to discover all existing table IDs matching ERA ERP tables.
    Returns a dictionary of {ENV_VAR_NAME: table_id_str}.
    """
    api_url = (api_url or os.getenv("BASEROW_API_URL", "http://localhost:7070")).rstrip("/")
    token = token or os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")
    admin_email = admin_email or os.getenv("BASEROW_ADMIN_EMAIL")
    admin_password = admin_password or os.getenv("BASEROW_ADMIN_PASSWORD")

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    jwt_token = get_jwt_token(api_url, admin_email, admin_password)
    auth_headers = {"Authorization": f"JWT {jwt_token}", "Content-Type": "application/json"} if jwt_token else headers

    discovered_ids = {}

    # Attempt 1: Fetch through /api/applications/
    tables_found = []
    try:
        resp = requests.get(f"{api_url}/api/applications/", headers=auth_headers, timeout=10)
        if resp.status_code == 200:
            apps = resp.json()
            for app in apps:
                if app.get("type") == "database":
                    t_resp = requests.get(f"{api_url}/api/database/tables/database/{app['id']}/", headers=auth_headers, timeout=10)
                    if t_resp.status_code == 200:
                        tables_found.extend(t_resp.json())
        elif resp.status_code in (401, 403) and not jwt_token:
            logger.debug("Database Token does not have permission to query /api/applications/.")
    except Exception as e:
        logger.debug(f"Error querying applications: {e}")

    # Map discovered tables by matching names / aliases
    for table_name, schema in ERA_SCHEMA_DEFINITIONS.items():
        env_var = schema["env_var"]
        # Match from tables_found list
        match = next((t for t in tables_found if t.get("name") in schema["aliases"]), None)
        if match:
            discovered_ids[env_var] = str(match["id"])
            continue

        # If not found in applications list, check if currently configured env var or default ID is responsive
        current_val = os.getenv(env_var) or schema.get("default_id")
        if current_val:
            try:
                # Test querying the table with token
                test_resp = requests.get(f"{api_url}/api/database/rows/table/{current_val}/?user_field_names=true&size=1", headers=headers, timeout=5)
                if test_resp.status_code == 200:
                    discovered_ids[env_var] = str(current_val)
            except Exception:
                pass

    return discovered_ids


def seed_default_data(api_url, token_or_jwt_headers, table_ids):
    """Seeds default PN categories, states, and configuration if missing."""
    seeded_info = []

    # 1. Seed PN Categories
    pn_cat_id = table_ids.get("BASEROW_TABLE_PN_CATEGORIES")
    if pn_cat_id:
        try:
            resp = requests.get(f"{api_url}/api/database/rows/table/{pn_cat_id}/?user_field_names=true&size=200", headers=token_or_jwt_headers, timeout=10)
            if resp.status_code == 200:
                existing = {str(r.get("Prefix")) for r in resp.json().get("results", []) if r.get("Prefix")}
                for cat in DEFAULT_PN_CATEGORIES:
                    if cat["Prefix"] not in existing:
                        requests.post(f"{api_url}/api/database/rows/table/{pn_cat_id}/?user_field_names=true", headers=token_or_jwt_headers, json=cat, timeout=10)
                        seeded_info.append(f"PN Category {cat['Prefix']} - {cat['Name']}")
        except Exception as e:
            logger.warning(f"Failed seeding PN Categories: {e}")

    # 2. Seed Item States
    states_id = table_ids.get("BASEROW_TABLE_ITEM_STATES")
    if states_id:
        try:
            resp = requests.get(f"{api_url}/api/database/rows/table/{states_id}/?user_field_names=true&size=200", headers=token_or_jwt_headers, timeout=10)
            if resp.status_code == 200:
                existing = {str(r.get("Name")) for r in resp.json().get("results", []) if r.get("Name")}
                for st in DEFAULT_STATES:
                    if st["Name"] not in existing:
                        requests.post(f"{api_url}/api/database/rows/table/{states_id}/?user_field_names=true", headers=token_or_jwt_headers, json=st, timeout=10)
                        seeded_info.append(f"Item State: {st['Name']}")
        except Exception as e:
            logger.warning(f"Failed seeding Item States: {e}")

    # 3. Seed Quick Action Templates file if missing
    templates_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quick_action_templates.json")
    if not os.path.exists(templates_file):
        try:
            with open(templates_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_QUICK_ACTION_TEMPLATES, f, indent=2)
            seeded_info.append("Quick Action Templates file created")
        except Exception as e:
            logger.warning(f"Failed creating default quick action templates: {e}")

    # 4. Ensure problem definitions file is empty list []
    prob_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "problem_definitions.json")
    try:
        with open(prob_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        seeded_info.append("Problem Definitions initialized to empty []")
    except Exception as e:
        logger.warning(f"Failed initializing empty problem definitions: {e}")

    return seeded_info


def init_baserow_schema(auto_update_env=True):
    """
    Main initialization routine:
    1. Reads environment config.
    2. Attempts token authentication and schema discovery.
    3. If tables/fields are missing and admin credentials exist, creates/updates them.
    4. If token lacks schema permission, outputs a clear, detailed instruction message.
    5. Seeds default values (PN categories, States, Quick Actions, empty problem definitions).
    6. Updates .env files with discovered/created table IDs.
    """
    load_dotenv()
    for env_p in find_env_files():
        if os.path.exists(env_p):
            load_dotenv(env_p)

    api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070").rstrip("/")
    token = os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")
    admin_email = os.getenv("BASEROW_ADMIN_EMAIL")
    admin_password = os.getenv("BASEROW_ADMIN_PASSWORD")

    print("\n" + "=" * 60)
    print("  ERA ERP - Baserow Database Initialization & Sync  ")
    print("=" * 60)
    print(f"API Endpoint: {api_url}")
    print(f"Auth Method : API Token (Token {'*' * 8})")

    token_headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    jwt_token = get_jwt_token(api_url, admin_email, admin_password)
    active_auth_headers = {"Authorization": f"JWT {jwt_token}", "Content-Type": "application/json"} if jwt_token else token_headers

    # Check connection
    try:
        health_check = requests.get(f"{api_url}/api/_health/", timeout=5)
    except Exception as e:
        msg = f"Cannot reach Baserow at {api_url}: {e}"
        print(format_detailed_error("Connect to Baserow API", msg))
        return False

    # 1. Discover existing tables
    discovered_ids = discover_baserow_tables(api_url, token, admin_email, admin_password)
    print(f"\n[+] Discovered {len(discovered_ids)} / {len(ERA_SCHEMA_DEFINITIONS)} table IDs:")
    for env_var, tid in discovered_ids.items():
        table_name = next((k for k, v in ERA_SCHEMA_DEFINITIONS.items() if v["env_var"] == env_var), env_var)
        print(f"    - {table_name:<25} ({env_var}) = ID {tid}")

    # Check for missing tables
    missing_tables = [name for name, defn in ERA_SCHEMA_DEFINITIONS.items() if defn["env_var"] not in discovered_ids]

    if missing_tables:
        print(f"\n[-] {len(missing_tables)} required tables are missing or unresolved: {', '.join(missing_tables)}")
        if not jwt_token:
            error_msg = (
                f"Missing tables: {', '.join(missing_tables)}.\n"
                "The current API token does not have administrative rights to create new tables.\n"
                "To resolve automatically, provide BASEROW_ADMIN_EMAIL and BASEROW_ADMIN_PASSWORD in .env."
            )
            print(format_detailed_error("Create Missing Baserow Tables", error_msg))
        else:
            # We have admin JWT token, let's locate or create the database and tables
            try:
                apps_resp = requests.get(f"{api_url}/api/applications/", headers=active_auth_headers, timeout=10)
                apps_resp.raise_for_status()
                apps = apps_resp.json()
                db_app = next((a for a in apps if a.get("type") == "database"), None)
                if not db_app:
                    # Create database
                    print("Creating new Baserow Database 'ERA Manufacturing'...")
                    create_db_resp = requests.post(
                        f"{api_url}/api/applications/",
                        headers=active_auth_headers,
                        json={"name": "ERA Manufacturing", "type": "database"},
                        timeout=10
                    )
                    create_db_resp.raise_for_status()
                    db_app = create_db_resp.json()

                db_id = db_app["id"]
                # Create missing tables
                for tname in missing_tables:
                    schema = ERA_SCHEMA_DEFINITIONS[tname]
                    print(f"Creating table '{tname}' in Database ID {db_id}...")
                    create_tbl_resp = requests.post(
                        f"{api_url}/api/database/tables/database/{db_id}/",
                        headers=active_auth_headers,
                        json={"name": tname},
                        timeout=10
                    )
                    if create_tbl_resp.status_code in (200, 201):
                        new_table = create_tbl_resp.json()
                        discovered_ids[schema["env_var"]] = str(new_table["id"])
                        print(f"    [✓] Created '{tname}' with ID {new_table['id']}")

            except Exception as e:
                print(format_detailed_error("Automated Table Creation", str(e)))

    # 2. Seed default data for resolved tables
    print("\n[+] Checking & seeding default seed data...")
    seeded_items = seed_default_data(api_url, active_auth_headers, discovered_ids)
    for item in seeded_items:
        print(f"    [✓] {item}")

    # 3. Update .env files
    if auto_update_env and discovered_ids:
        print("\n[+] Updating local environment configuration (.env)...")
        update_env_files(discovered_ids)
        print("    [✓] Environment files updated.")

    print("\n" + "=" * 60)
    print("  Baserow Initialization & Sync Complete!  ")
    print("=" * 60 + "\n")
    return True


if __name__ == "__main__":
    success = init_baserow_schema(auto_update_env=True)
    sys.exit(0 if success else 1)
