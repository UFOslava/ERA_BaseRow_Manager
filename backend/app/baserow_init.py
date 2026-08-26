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
        "primary_field": {"name": "Full PN", "type": "formula", "aliases": ["Full Part Number", "Part Number"]},
        "fields": [
            {"name": "Part Number", "type": "text", "aliases": ["PN", "Part No"]},
            {"name": "Revision", "type": "text", "aliases": ["Rev", "Revision"]},
            {"name": "Item description", "type": "long_text", "aliases": ["Description", "Item Description"]},
            {"name": "External Part Number", "type": "text", "aliases": ["External PN", "Ext PN", "Manufacturer PN", "Supplier PN"]},
            {"name": "Manufacturer", "type": "link_row", "link_table": "Manufacturers"},
            {"name": "Price per unit", "type": "number", "aliases": ["Price", "Unit Price"]},
            {"name": "Image", "type": "file", "aliases": ["Photo", "Picture"]},
            {"name": "Datasheet", "type": "file", "aliases": ["Documentation", "PDF"]},
            {"name": "Source URL", "type": "url", "aliases": ["Website", "URL", "Link"]},
            {"name": "Notes", "type": "long_text", "aliases": ["Comments", "Remarks"]},
            {"name": "State", "type": "link_row", "link_table": "States", "aliases": ["Status", "Item State"]},
            {"name": "PN Category", "type": "link_row", "link_table": "PN Categories", "aliases": ["Category", "Part Category"]},
            {"name": "Containing", "type": "link_row", "link_table": "BOM"},
            {"name": "Lot Size", "type": "number", "aliases": ["Lot Quantity", "LotSize", "Price Lot Size"]},
            {"name": "Purchase UoM", "type": "link_row", "link_table": "Units of Measure", "aliases": ["Purchase Unit"]},
            {"name": "Consumption UoM", "type": "link_row", "link_table": "Units of Measure", "aliases": ["Consumption Unit"]},
            {"name": "Blackbox", "type": "boolean"},
            {"name": "Purchase Kit", "type": "boolean", "aliases": ["Kit", "PurchaseKit", "Purchase kit"]},
            {"name": "Search helper", "type": "formula", "aliases": ["Search Helper"]},
        ]
    },
    "Assembly": {
        "env_var": "BASEROW_TABLE_ASSEMBLY",
        "aliases": ["Assembly", "Assemblies", "Assembly Relations"],
        "default_id": "701",
        "primary_field": {"name": "ID", "type": "autonumber", "aliases": ["Id", "Row ID", "Item"]},
        "fields": [
            {"name": "Item", "type": "link_row", "link_table": "BOM", "aliases": ["Parent", "Parent Item", "Assembly"]},
            {"name": "Contains", "type": "link_row", "link_table": "BOM", "aliases": ["Child", "Child Item", "Component"]},
            {"name": "Amount of Times", "type": "number", "aliases": ["Quantity", "Qty", "Amount"]},
            {"name": "Length (mm)", "type": "number", "aliases": ["Length", "Length mm", "Length (mm)"]},
            {"name": "PCB Symbol", "type": "text", "aliases": ["Designator", "Symbol", "RefDes"]},
            {"name": "Search Helper", "type": "formula", "aliases": ["Search helper"]}
        ]
    },
    "Assembly Instructions": {
        "env_var": "BASEROW_TABLE_INSTRUCTIONS",
        "aliases": ["Assembly Instructions", "Instructions", "Work Instructions"],
        "default_id": "5770",
        "primary_field": {"name": "UUID", "type": "uuid", "aliases": ["Id", "ID", "Title"]},
        "fields": [
            {"name": "Parent Item", "type": "link_row", "link_table": "BOM", "aliases": ["Parent", "Assembly Item", "Item"]},
            {"name": "Set Index", "type": "number", "aliases": ["Set", "Instruction Set"]},
            {"name": "Step Order", "type": "number", "aliases": ["Step", "Step Number", "Order"]},
            {"name": "Action Receiving Item", "type": "link_row", "link_table": "BOM", "aliases": ["Receiving Item"]},
            {"name": "Child Item", "type": "link_row", "link_table": "BOM", "aliases": ["Component", "Part"]},
            {"name": "Tool", "type": "link_row", "link_table": "BOM", "aliases": ["Tooling", "Equipment"]},
            {"name": "Action", "type": "text", "aliases": ["Verb", "Action Type"]},
            {"name": "Description", "type": "long_text", "aliases": ["Details", "Instruction Details"]},
            {"name": "Photo", "type": "file", "aliases": ["Image", "Step Photo"]},
            {"name": "Tool Map", "type": "long_text", "aliases": ["Toll Map", "Tool Mapping"]}
        ]
    },
    "PN Categories": {
        "env_var": "BASEROW_TABLE_PN_CATEGORIES",
        "aliases": ["PN Categories", "Part Categories", "Categories"],
        "default_id": "42471",
        "primary_field": {"name": "Prefix", "type": "text", "aliases": ["Category Prefix", "Code"]},
        "fields": [
            {"name": "Name", "type": "text", "aliases": ["Category Name", "Title"]},
            {"name": "Color", "type": "text", "aliases": ["Tag Color", "Hex Color"]},
            {"name": "BOM", "type": "link_row", "link_table": "BOM"}
        ]
    },
    "States": {
        "env_var": "BASEROW_TABLE_ITEM_STATES",
        "aliases": ["States", "Item States", "Item Lifecycle States"],
        "default_id": "48537",
        "primary_field": {"name": "Name", "type": "text", "aliases": ["State Name", "Status"]},
        "fields": [
            {"name": "Color", "type": "text", "aliases": ["Tag Color", "Hex Color"]},
            {"name": "BOM", "type": "link_row", "link_table": "BOM"}
        ]
    },
    "WI Templates": {
        "env_var": "BASEROW_TABLE_WI_TEMPLATES",
        "aliases": ["WI Templates", "Work Instruction Templates", "Document Templates", "Templates"],
        "default_id": "48538",
        "primary_field": {"name": "Name", "type": "text", "aliases": ["Template Name", "Title"]},
        "fields": [
            {"name": "Filename", "type": "text", "aliases": ["File Name", "File", "Path"]},
            {"name": "Valid", "type": "boolean", "aliases": ["Is Valid", "Verified"]},
            {"name": "Tokens Found", "type": "long_text", "aliases": ["Found Tokens", "Tokens"]},
            {"name": "Invalid Tokens", "type": "long_text", "aliases": ["Missing Tokens", "Errors"]},
            {"name": "Approved", "type": "boolean", "aliases": ["Is Approved", "Active"]},
            {"name": "Created At", "type": "date", "aliases": ["Date", "Created Date"]}
        ]
    },
    "Manufacturers": {
        "env_var": "BASEROW_TABLE_MANUFACTURERS",
        "aliases": ["Manufacturers", "Vendors"],
        "default_id": "683",
        "primary_field": {"name": "Name", "type": "text", "aliases": ["Manufacturer Name", "Company Name"]},
        "fields": [
            {"name": "Website", "type": "url", "aliases": ["URL", "Site"]},
            {"name": "Logo", "type": "file", "aliases": ["Image", "Icon"]},
            {"name": "Notes", "type": "long_text", "aliases": ["Description", "Remarks"]},
            {"name": "Suppliers", "type": "link_row", "link_table": "Suppliers", "aliases": ["Distributors", "Contacts"]},
            {"name": "BOM", "type": "link_row", "link_table": "BOM"}
        ]
    },
    "Suppliers": {
        "env_var": "BASEROW_TABLE_SUPPLIERS",
        "aliases": ["Suppliers", "Distributors"],
        "default_id": "682",
        "primary_field": {"name": "Company Name", "type": "text", "aliases": ["Name", "Supplier Name"]},
        "fields": [
            {"name": "Notes", "type": "long_text", "aliases": ["Description", "Remarks"]},
            {"name": "Online Store", "type": "boolean", "aliases": ["Online", "Store"]},
            {"name": "Contacts", "type": "link_row", "link_table": "Contacts"},
            {"name": "Imports From", "type": "link_row", "link_table": "Manufacturers", "aliases": ["Manufacturers"]},
            {"name": "Logo", "type": "file", "aliases": ["Image", "Icon"]},
            {"name": "URL", "type": "url", "aliases": ["Website", "Site", "Link"]}
        ]
    },
    "Contacts": {
        "env_var": "BASEROW_TABLE_CONTACTS",
        "aliases": ["Contacts", "Vendor Contacts", "Supplier Contacts"],
        "default_id": "684",
        "primary_field": {"name": "Name", "type": "text", "aliases": ["Contact Name", "Full Name"]},
        "fields": [
            {"name": "Email", "type": "email", "aliases": ["E-mail", "Mail"]},
            {"name": "Phone number", "type": "phone_number", "aliases": ["Phone", "Telephone", "Mobile"]},
            {"name": "Notes", "type": "long_text", "aliases": ["Remarks", "Comments"]},
            {"name": "Active", "type": "boolean", "aliases": ["Is Active", "Status"]},
            {"name": "Suppliers", "type": "link_row", "link_table": "Suppliers"}
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


def parse_url_and_port(url_str: str):
    """
    Parses a URL string into (host, port).
    e.g. 'http://localhost:7070' -> ('http://localhost', '7070')
    'http://localhost' -> ('http://localhost', '')
    """
    if not url_str:
        return ("http://localhost", "7070")
    
    clean = url_str.strip().rstrip("/")
    # Check if port is in host part (after last colon, not counting protocol ://)
    proto_split = clean.split("://", 1)
    if len(proto_split) == 2:
        proto, rest = proto_split
        if ":" in rest:
            host_part, port_part = rest.split(":", 1)
            # Remove any path from port
            port = port_part.split("/", 1)[0]
            return (f"{proto}://{host_part}", port)
        else:
            host_only = rest.split("/", 1)[0]
            return (f"{proto}://{host_only}", "")
    else:
        if ":" in clean:
            host_part, port_part = clean.split(":", 1)
            port = port_part.split("/", 1)[0]
            return (f"http://{host_part}", port)
        return (f"http://{clean}", "")


def combine_url_and_port(host: str, port: str = None):
    """
    Combines host/protocol and optional port into a normalized API URL without trailing slash.
    e.g. ('http://localhost', '7070') -> 'http://localhost:7070'
    ('http://localhost:7070', '') -> 'http://localhost:7070'
    """
    if not host:
        host = "http://localhost"
    host = host.strip().rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = f"http://{host}"

    if port:
        port_str = str(port).strip()
        # If host already has port, don't duplicate
        proto_split = host.split("://", 1)
        if len(proto_split) == 2 and ":" in proto_split[1]:
            # host already contains a port
            return host
        if port_str:
            return f"{host}:{port_str}"
    return host


def mask_token(token: str) -> str:
    """Masks a token showing first char and last 2 chars, e.g. C••••••••••••••••••••7L."""
    if not token or not str(token).strip():
        return ""
    t = str(token).strip()
    if len(t) > 6:
        return t[0] + ("•" * min(len(t) - 3, 24)) + t[-2:]
    return "•" * len(t)


def mask_email(email: str) -> str:
    """Masks an email showing first char of user and domain, e.g. U•••••••@hotmail.com."""
    if not email or not str(email).strip():
        return ""
    e = str(email).strip()
    if "@" in e:
        local, domain = e.split("@", 1)
        if len(local) > 1:
            return local[0] + ("•" * min(len(local) - 1, 6)) + "@" + domain
        return local + "@" + domain
    return e[0] + "•••••"


def mask_password(password: str) -> str:
    """Returns fixed masked preview if password exists."""
    if not password or not str(password).strip():
        return ""
    return "••••••••"


def test_baserow_connection(api_url: str):
    """Checks if Baserow server is reachable."""
    if not api_url:
        return {"success": False, "message": "No Baserow API URL provided."}
    api_url = api_url.rstrip("/")
    try:
        resp = requests.get(f"{api_url}/api/_health/", timeout=4)
        if resp.status_code in (200, 204):
            return {"success": True, "message": "Baserow server reached successfully."}
        # Fallback check
        resp2 = requests.get(f"{api_url}/api/applications/", timeout=4)
        if resp2.status_code in (200, 401, 403):
            return {"success": True, "message": "Baserow server responded."}
        return {"success": False, "message": f"Server returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Cannot connect to Baserow at {api_url}: {e}"}


def test_token_permissions(api_url: str, token: str, table_id: str = None):
    """Tests if the provided API token has valid access."""
    if not token or not str(token).strip():
        return {"valid": False, "warning": "API Token is missing."}
    api_url = api_url.rstrip("/")
    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
    
    # Try querying table rows if table_id is known
    tid = table_id or os.getenv("BASEROW_TABLE_BOM", "508")
    try:
        resp = requests.get(f"{api_url}/api/database/rows/table/{tid}/?user_field_names=true&size=1", headers=headers, timeout=5)
        if resp.status_code == 200:
            return {"valid": True, "warning": None}
        elif resp.status_code == 401:
            return {"valid": False, "warning": "API Token is invalid or expired (HTTP 401 Unauthorized)."}
        elif resp.status_code == 403:
            return {"valid": False, "warning": "API Token lacks permissions to access tables (HTTP 403 Forbidden)."}
        elif resp.status_code == 404:
            # Table ID might not exist, but token might still be valid; try user applications or general endpoint
            return {"valid": True, "warning": f"Table ID {tid} not found on server, but token accepted."}
        else:
            return {"valid": False, "warning": f"Unexpected response from Baserow: HTTP {resp.status_code}"}
    except Exception as e:
        return {"valid": False, "warning": f"Connection error validating token: {e}"}


def test_jwt_credentials(api_url: str, email: str, password: str):
    """Tests admin JWT credentials against Baserow."""
    if not email or not password:
        return {"provided": False, "valid": False, "token": None, "message": "Optional admin credentials not provided."}
    api_url = api_url.rstrip("/")
    try:
        resp = requests.post(f"{api_url}/api/user/token-auth/", json={"username": email, "password": password}, timeout=6)
        if resp.status_code == 200:
            jwt_token = resp.json().get("token")
            return {"provided": True, "valid": True, "token": jwt_token, "message": "JWT Admin credentials authenticated successfully."}
        else:
            return {"provided": True, "valid": False, "token": None, "message": "Invalid admin email or password."}
    except Exception as e:
        return {"provided": True, "valid": False, "token": None, "message": f"Error authenticating JWT: {e}"}


def discover_baserow_schema(api_url=None, token=None, admin_email=None, admin_password=None, database_id=None, table_overrides=None):
    """
    Detailed schema discovery:
    Discovers Database ID, all required Table IDs, and all Field IDs & Types for each required table.
    """
    api_url = (api_url or os.getenv("BASEROW_API_URL", "http://localhost:7070")).rstrip("/")
    token = token or os.getenv("BASEROW_TOKEN", "")
    admin_email = admin_email if admin_email is not None else os.getenv("BASEROW_ADMIN_EMAIL")
    admin_password = admin_password if admin_password is not None else os.getenv("BASEROW_ADMIN_PASSWORD")
    table_overrides = table_overrides or {}

    conn_test = test_baserow_connection(api_url)
    token_test = test_token_permissions(api_url, token)
    jwt_res = test_jwt_credentials(api_url, admin_email, admin_password)

    jwt_token = jwt_res.get("token")
    token_headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"} if token else {}
    jwt_headers = {"Authorization": f"JWT {jwt_token}", "Content-Type": "application/json"} if jwt_token else {}
    active_headers = jwt_headers if jwt_token else token_headers

    discovered_db_id = database_id or os.getenv("BASEROW_DATABASE_ID")
    tables_found_from_api = []

    if conn_test["success"] and (jwt_headers or token_headers):
        # 1. Attempt to find database applications
        try:
            apps_resp = requests.get(f"{api_url}/api/applications/", headers=active_headers, timeout=6)
            if apps_resp.status_code == 200:
                apps = apps_resp.json()
                db_apps = [a for a in apps if a.get("type") == "database"]
                if db_apps and not discovered_db_id:
                    # Prefer database named 'ERA' or first
                    era_db = next((a for a in db_apps if "era" in a.get("name", "").lower()), db_apps[0])
                    discovered_db_id = str(era_db.get("id"))
                
                # Fetch tables for the database if found
                if discovered_db_id:
                    t_resp = requests.get(f"{api_url}/api/database/tables/database/{discovered_db_id}/", headers=active_headers, timeout=6)
                    if t_resp.status_code == 200:
                        tables_found_from_api = t_resp.json()
                elif db_apps:
                    for db in db_apps:
                        t_resp = requests.get(f"{api_url}/api/database/tables/database/{db['id']}/", headers=active_headers, timeout=6)
                        if t_resp.status_code == 200:
                            tables_found_from_api.extend(t_resp.json())
        except Exception as e:
            logger.debug(f"Schema discovery applications query: {e}")

    # Build detailed table & field schema status
    tables_report = {}
    all_tables_found = True
    all_fields_found = True

    for table_name, schema in ERA_SCHEMA_DEFINITIONS.items():
        env_var = schema["env_var"]
        # Determine table ID:
        # Priority 1: User override
        # Priority 2: Matched from API database tables
        # Priority 3: Current env variable
        # Priority 4: Default ID if responsive
        resolved_table_id = None
        if env_var in table_overrides and str(table_overrides[env_var]).strip():
            resolved_table_id = str(table_overrides[env_var]).strip()
        else:
            api_match = next((t for t in tables_found_from_api if t.get("name") in schema["aliases"] or t.get("name") == table_name), None)
            if api_match:
                resolved_table_id = str(api_match["id"])
            else:
                env_id = os.getenv(env_var)
                if env_id and str(env_id).strip():
                    resolved_table_id = str(env_id).strip()
                elif schema.get("default_id"):
                    resolved_table_id = str(schema["default_id"]).strip()

        table_data = {
            "name": table_name,
            "env_var": env_var,
            "id": resolved_table_id,
            "found": False,
            "fields": [],
            "all_fields_found": False,
            "error": None
        }

        if not resolved_table_id:
            table_data["error"] = "Table ID not configured or discovered."
            all_tables_found = False
            all_fields_found = False
            tables_report[table_name] = table_data
            continue

        # Verify table responsiveness and fetch field definitions
        fields_found_api = []
        table_verified = False

        if conn_test["success"]:
            # Try fetching fields metadata via /api/database/fields/table/{id}/
            try:
                f_resp = requests.get(f"{api_url}/api/database/fields/table/{resolved_table_id}/", headers=active_headers, timeout=5)
                if f_resp.status_code == 200:
                    fields_found_api = f_resp.json()
                    table_verified = True
                elif f_resp.status_code in (401, 403):
                    # Try verifying by querying 1 row with user field names
                    r_resp = requests.get(f"{api_url}/api/database/rows/table/{resolved_table_id}/?user_field_names=true&size=1", headers=token_headers, timeout=5)
                    if r_resp.status_code == 200:
                        table_verified = True
                        res_data = r_resp.json()
                        rows = res_data.get("results", [])
                        if rows and isinstance(rows[0], dict):
                            fields_found_api = [{"name": k, "type": "unknown", "id": None} for k in rows[0].keys()]
                        else:
                            table_verified = True
                elif f_resp.status_code == 404:
                    table_data["error"] = f"Table ID {resolved_table_id} does not exist on Baserow."
            except Exception as e:
                table_data["error"] = str(e)

        table_data["found"] = table_verified or (resolved_table_id is not None)
        if not table_data["found"]:
            all_tables_found = False

        # Match required fields
        req_fields_list = []
        # Primary field
        pri = schema.get("primary_field")
        if pri:
            req_fields_list.append({
                "name": pri["name"],
                "type": pri["type"],
                "primary": True,
                "aliases": pri.get("aliases", [pri["name"]])
            })
        for f in schema.get("fields", []):
            req_fields_list.append({
                "name": f["name"],
                "type": f["type"],
                "primary": False,
                "aliases": f.get("aliases", [f["name"]])
            })

        import re

        def _normalize(s):
            return re.sub(r"[^a-z0-9]", "", str(s).lower()) if s else ""

        fields_status = []
        table_all_fields = True

        for req in req_fields_list:
            req_name = req["name"]
            req_aliases = req.get("aliases", [req_name])
            req_norm_set = {_normalize(a) for a in req_aliases if a}
            req_norm_set.add(_normalize(req_name))

            # 1. Exact case-insensitive match on name or aliases
            matched_field = None
            for f in fields_found_api:
                fname = str(f.get("name", "")).strip()
                fname_lower = fname.lower()
                if fname_lower == req_name.lower() or any(fname_lower == str(a).lower() for a in req_aliases):
                    matched_field = f
                    break

            # 2. Normalized match (ignoring special symbols, brackets, spaces)
            if not matched_field:
                for f in fields_found_api:
                    fname_norm = _normalize(f.get("name", ""))
                    if fname_norm and fname_norm in req_norm_set:
                        matched_field = f
                        break
            
            f_entry = {
                "name": req["name"],
                "actual_name": matched_field.get("name") if matched_field else req["name"],
                "type": matched_field.get("type", req["type"]) if matched_field else req["type"],
                "primary": req["primary"],
                "id": matched_field.get("id") if matched_field else None,
                "found": bool(matched_field) if fields_found_api else True # If API couldn't list fields, mark as expected
            }
            if not f_entry["found"]:
                table_all_fields = False
                all_fields_found = False
            fields_status.append(f_entry)

        table_data["fields"] = fields_status
        table_data["all_fields_found"] = table_all_fields
        tables_report[table_name] = table_data

    host, port = parse_url_and_port(api_url)
    is_complete = bool(conn_test["success"] and token_test["valid"] and all_tables_found)

    return {
        "is_complete": is_complete,
        "is_connected": conn_test["success"],
        "connection_message": conn_test["message"],
        "has_token": bool(token and str(token).strip()),
        "token_preview": mask_token(token),
        "token_valid": token_test["valid"],
        "token_warning": token_test["warning"],
        "has_admin_email": bool(admin_email and str(admin_email).strip()),
        "admin_email_preview": mask_email(admin_email),
        "has_admin_password": bool(admin_password and str(admin_password).strip()),
        "admin_password_preview": mask_password(admin_password),
        "jwt_provided": jwt_res["provided"],
        "jwt_valid": jwt_res["valid"],
        "jwt_message": jwt_res["message"],
        "api_url": api_url,
        "host": host,
        "port": port,
        "database_id": discovered_db_id,
        "tables": tables_report,
        "all_tables_found": all_tables_found,
        "all_fields_found": all_fields_found
    }


def get_auth_status_summary():
    """Lightweight check of current authentication and schema completeness."""
    api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070").rstrip("/")
    token = os.getenv("BASEROW_TOKEN", "")
    admin_email = os.getenv("BASEROW_ADMIN_EMAIL", "")
    admin_password = os.getenv("BASEROW_ADMIN_PASSWORD", "")
    host, port = parse_url_and_port(api_url)

    missing = []
    if not token or not str(token).strip():
        missing.append("Baserow API Token")
    
    missing_tables = []
    for tname, defn in ERA_SCHEMA_DEFINITIONS.items():
        env_val = os.getenv(defn["env_var"])
        if not env_val or not str(env_val).strip():
            missing_tables.append(tname)

    if missing_tables:
        missing.append(f"Table IDs ({', '.join(missing_tables)})")

    # Fast connection check
    conn = test_baserow_connection(api_url)
    token_check = test_token_permissions(api_url, token) if token and conn["success"] else {"valid": bool(token), "warning": None if token else "Token missing"}
    jwt_check = test_jwt_credentials(api_url, admin_email, admin_password) if admin_email and admin_password and conn["success"] else {"provided": bool(admin_email), "valid": False, "message": "Not configured"}

    is_complete = bool(len(missing) == 0 and conn["success"] and token_check["valid"])

    return {
        "is_complete": is_complete,
        "is_connected": conn["success"],
        "has_token": bool(token and str(token).strip()),
        "token_preview": mask_token(token),
        "token_valid": token_check["valid"],
        "token_warning": token_check["warning"],
        "has_admin_email": bool(admin_email and str(admin_email).strip()),
        "admin_email_preview": mask_email(admin_email),
        "has_admin_password": bool(admin_password and str(admin_password).strip()),
        "admin_password_preview": mask_password(admin_password),
        "jwt_provided": jwt_check.get("provided", False),
        "jwt_valid": jwt_check.get("valid", False),
        "jwt_message": jwt_check.get("message", ""),
        "missing": missing,
        "api_url": api_url,
        "host": host,
        "port": port,
        "database_id": os.getenv("BASEROW_DATABASE_ID"),
        "has_admin_credentials": bool(admin_email and admin_password)
    }


def save_auth_configuration(payload: dict):
    """
    Validates, discovers schema, writes to .env, and updates runtime environment.
    If secret fields are untouched/contain mask characters (•), existing saved secrets are preserved.
    """
    host = payload.get("host", "http://localhost")
    port = payload.get("port", "")
    token_input = (payload.get("token") or "").strip()
    admin_email_input = payload.get("admin_email")
    admin_password_input = payload.get("admin_password")
    database_id = payload.get("database_id")
    table_overrides = payload.get("table_ids") or {}

    api_url = combine_url_and_port(host, port)

    # 1. Resolve token: keep existing if untouched/masked
    existing_token = os.getenv("BASEROW_TOKEN", "")
    if not token_input or "•" in token_input:
        token = existing_token
    else:
        token = token_input
        # Validate new token
        token_check = test_token_permissions(api_url, token)
        if not token_check["valid"]:
            return {
                "success": False,
                "error": f"Provided Baserow API Token is invalid: {token_check.get('warning', 'Unauthorized')}"
            }

    # 2. Resolve admin email & password: keep existing if untouched/masked
    existing_email = os.getenv("BASEROW_ADMIN_EMAIL", "")
    existing_pw = os.getenv("BASEROW_ADMIN_PASSWORD", "")

    if admin_email_input is None or "•" in str(admin_email_input):
        admin_email = existing_email
    else:
        admin_email = str(admin_email_input).strip()

    if admin_password_input is None or "•" in str(admin_password_input) or admin_password_input == "":
        admin_password = existing_pw
    else:
        admin_password = str(admin_password_input)

    # If new credentials were provided, test them
    if (admin_email != existing_email or admin_password != existing_pw) and admin_email and admin_password:
        jwt_check = test_jwt_credentials(api_url, admin_email, admin_password)
        if not jwt_check["valid"]:
            return {
                "success": False,
                "error": f"Provided Admin JWT credentials failed: {jwt_check.get('message', 'Authentication failed')}"
            }

    # Perform discovery
    schema_report = discover_baserow_schema(
        api_url=api_url,
        token=token,
        admin_email=admin_email,
        admin_password=admin_password,
        database_id=database_id,
        table_overrides=table_overrides
    )

    # Prepare key-values to save in .env
    env_updates = {
        "BASEROW_API_URL": api_url,
        "BASEROW_TOKEN": token
    }
    if admin_email:
        env_updates["BASEROW_ADMIN_EMAIL"] = admin_email
    if admin_password:
        env_updates["BASEROW_ADMIN_PASSWORD"] = admin_password
    if schema_report.get("database_id"):
        env_updates["BASEROW_DATABASE_ID"] = str(schema_report["database_id"])

    for tname, tdata in schema_report.get("tables", {}).items():
        if tdata.get("id"):
            env_updates[tdata["env_var"]] = str(tdata["id"])

    # Update .env files
    update_env_files(env_updates)

    # Update in-memory os.environ
    for k, v in env_updates.items():
        os.environ[k] = str(v)

    return {
        "success": True,
        "schema": schema_report,
        "status": get_auth_status_summary()
    }



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
