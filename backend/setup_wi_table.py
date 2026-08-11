import requests
import os

ADMIN_URL = "http://localhost:7070/api/user/token-auth/"
APPS_URL = "http://localhost:7070/api/applications/"

# 1. Get Admin Token
resp = requests.post(ADMIN_URL, json={"username": "UFOslava@hotmail.com", "password": "AGBdlcid46"})
if resp.status_code != 200:
    print("Failed to get admin token:", resp.text)
    exit(1)
token = resp.json()["token"]
headers = {"Authorization": f"JWT {token}", "Content-Type": "application/json"}

# 2. Find database ID
resp = requests.get(APPS_URL, headers=headers)
apps = resp.json()
db_id = None
for app in apps:
    if app["type"] == "database":
        db_id = app["id"]
        break

if not db_id:
    print("No database found.")
    exit(1)

print(f"Database ID: {db_id}")

# 3. Check if table exists
tables_url = f"http://localhost:7070/api/database/tables/database/{db_id}/"
resp = requests.get(tables_url, headers=headers)
tables = resp.json()
wi_table_id = None
for t in tables:
    if t["name"] == "WI Templates":
        wi_table_id = t["id"]
        break

if wi_table_id:
    print(f"WI Templates table already exists (ID: {wi_table_id})")
else:
    # 4. Create table
    print("Creating WI Templates table...")
    resp = requests.post(tables_url, headers=headers, json={"name": "WI Templates"})
    if resp.status_code != 200:
        print("Failed to create table:", resp.text)
        exit(1)
    wi_table_id = resp.json()["id"]
    print(f"Created table ID: {wi_table_id}")

    # 5. Create fields
    fields_url = f"http://localhost:7070/api/database/fields/table/{wi_table_id}/"
    fields = [
        {"name": "Name", "type": "text"},
        {"name": "Filename", "type": "text"},
        {"name": "Valid", "type": "boolean"},
        {"name": "Tokens Found", "type": "long_text"},
        {"name": "Invalid Tokens", "type": "long_text"},
        {"name": "Created At", "type": "date", "date_format": "ISO", "date_include_time": True, "date_time_format": "24"}
    ]
    # Delete default fields first (except Name if it exists)
    resp = requests.get(fields_url, headers=headers)
    existing_fields = resp.json()
    for f in existing_fields:
        if f["name"] != "Name":
            requests.delete(f"http://localhost:7070/api/database/fields/{f['id']}/", headers=headers)
    
    resp = requests.get(fields_url, headers=headers)
    existing_fields = resp.json()
    has_name = any(f["name"] == "Name" for f in existing_fields)
    
    for field in fields:
        if field["name"] == "Name" and has_name:
            continue
        print(f"Creating field: {field['name']}")
        res = requests.post(fields_url, headers=headers, json=field)
        if res.status_code != 200:
            print("Failed to create field:", res.text)
    
print("Done.")
