"""
Script to replace all empty / "None" Units of Measure (UoM) in the BOM database (Table 508)
with "Piece (pcs)".
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASEROW_URL = os.getenv("BASEROW_URL", "http://localhost:7070").rstrip("/")
DATABASE_TOKEN = os.getenv("BASEROW_DATABASE_TOKEN", "")
BOM_TABLE_ID = os.getenv("BASEROW_TABLE_BOM", "508")
UOM_TABLE_ID = os.getenv("BASEROW_TABLE_UOM", "48540")

headers = {
    "Authorization": f"Token {DATABASE_TOKEN}",
    "Content-Type": "application/json"
}

def get_piece_uom_id():
    url = f"{BASEROW_URL}/api/database/rows/table/{UOM_TABLE_ID}/?user_field_names=true"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    for row in data.get("results", []):
        name = (row.get("Name") or "").strip().lower()
        sym = (row.get("Symbol") or "").strip().lower()
        if name == "piece" or sym == "pcs":
            return row["id"]
    raise RuntimeError("Could not find 'Piece' in Units of Measure table.")

def update_bom_uoms_to_piece():
    piece_id = get_piece_uom_id()
    print(f"Found 'Piece' UoM with ID: {piece_id}")

    page = 1
    page_size = 100
    total_updated = 0

    while True:
        url = f"{BASEROW_URL}/api/database/rows/table/{BOM_TABLE_ID}/?user_field_names=true&page={page}&size={page_size}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 404:
            break
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("results", [])
        if not rows:
            break

        print(f"Processing page {page} ({len(rows)} items)...")
        for row in rows:
            row_id = row["id"]
            pur_uom = row.get("Purchase UoM") or []
            con_uom = row.get("Consumption UoM") or []

            needs_update = {}
            if not pur_uom:
                needs_update["Purchase UoM"] = [piece_id]
            if not con_uom:
                needs_update["Consumption UoM"] = [piece_id]

            if needs_update:
                patch_url = f"{BASEROW_URL}/api/database/rows/table/{BOM_TABLE_ID}/{row_id}/?user_field_names=true"
                patch_resp = requests.patch(patch_url, headers=headers, json=needs_update)
                patch_resp.raise_for_status()
                total_updated += 1
                pn = row.get("Part Number") or row.get("Full PN") or f"Item #{row_id}"
                print(f"  Updated row {row_id} ({pn}): {list(needs_update.keys())}")

        if not data.get("next"):
            break
        page += 1

    print(f"\nSuccessfully updated {total_updated} BOM item(s) to 'Piece (pcs)'!")

if __name__ == "__main__":
    update_bom_uoms_to_piece()
