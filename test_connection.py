import os
import requests
import sys

def test_connection():
    print("----------------------------------------------------------------")
    print("Testing connection to Baserow...")

    baserow_url = os.environ.get("BASEROW_API_URL")
    baserow_token = os.environ.get("BASEROW_TOKEN")

    if not baserow_url or not baserow_token:
        print("❌ FAILURE: Missing env vars.")
        sys.exit(1)

    if "://" in baserow_url:
        protocol, rest = baserow_url.split("://", 1)
        masked_url = f"{protocol}://{rest[:4]}...{rest[-4:]}" if len(rest) > 8 else baserow_url
    else:
        masked_url = baserow_url
    print(f"Loaded BASEROW_API_URL: {masked_url}")

    # Use /api/settings/ as suggested by user to confirm connectivity
    # Ensure trailing slash
    endpoint = f"{baserow_url}/api/settings/"

    headers = {
        "Authorization": f"Token {baserow_token}",
        "Content-Type": "application/json"
    }

    try:
        print(f"GET {endpoint}")
        response = requests.get(endpoint, headers=headers)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # print(data)
            print("✅ SUCCESS: Accessed /api/settings/")

            # Now try the original goal: Table 508 schema
            print("Attempting to fetch Table 508 schema...")
            table_endpoint = f"{baserow_url}/api/database/fields/table/508/"
            resp_table = requests.get(table_endpoint, headers=headers)

            if resp_table.status_code == 200:
                fields = resp_table.json()
                print(f"✅ SUCCESS: Found {len(fields)} fields in Table 508")
            else:
                print(f"❌ FAILURE (Table 508): {resp_table.status_code}")
                print(resp_table.text[:200])

        else:
            print(f"❌ FAILURE: {response.status_code}")
            print(response.text[:500])

    except requests.exceptions.RequestException as e:
        print(f"❌ FAILURE: Connection error: {e}")
        sys.exit(1)

    print("----------------------------------------------------------------")

if __name__ == "__main__":
    test_connection()
