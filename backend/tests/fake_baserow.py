"""
In-memory stand-in for the Baserow REST API, used to run the real BaserowClient end to end
without a server. It covers the endpoints the client and MCP tools use: row CRUD with
pagination and link_row/equal filters, the fields endpoint, user-file uploads and media
downloads. Written link_row, file and single-select values are stored in the shape Baserow
returns them, so reads look like production rows.
"""

import copy
import hashlib
import json
import re
from urllib.parse import urlparse

import requests

API = "http://fake-baserow"

TABLE_BOM = "508"
TABLE_ASSEMBLY = "701"
TABLE_INSTRUCTIONS = "5770"
TABLE_MANUFACTURERS = "683"
TABLE_SUPPLIERS = "682"
TABLE_CONTACTS = "684"
TABLE_UOM = "48540"
TABLE_STATES = "48537"

TABLE_ENV = {
    "BASEROW_TABLE_BOM": TABLE_BOM,
    "BASEROW_TABLE_ASSEMBLY": TABLE_ASSEMBLY,
    "BASEROW_TABLE_INSTRUCTIONS": TABLE_INSTRUCTIONS,
    "BASEROW_TABLE_PN_CATEGORIES": "42471",
    "BASEROW_TABLE_ITEM_STATES": TABLE_STATES,
    "BASEROW_TABLE_WI_TEMPLATES": "48538",
    "BASEROW_TABLE_MANUFACTURERS": TABLE_MANUFACTURERS,
    "BASEROW_TABLE_SUPPLIERS": TABLE_SUPPLIERS,
    "BASEROW_TABLE_CONTACTS": TABLE_CONTACTS,
    "BASEROW_TABLE_UOM": TABLE_UOM,
}

STATES = {"Production Use": 1, "Engineerig Use": 2, "Unknown": 3,
          "Finish Stock (Use Up)": 4, "EOL": 5, "Do Not Use (Discard)": 6}
SOURCED_BY_OPTIONS = [
    {"id": 3001, "value": "Purchased by Contractor"},
    {"id": 3002, "value": "Produced by Contractor"},
    {"id": 3003, "value": "Purchased by ERA"},
    {"id": 3004, "value": "Produced by ERA"},
    {"id": 3005, "value": "TBD"},
]
UOMS = {3: "Piece", 4: "Millimeter", 5: "Centimeter", 6: "Meter"}

LINK_FIELDS = {
    TABLE_BOM: {"State": TABLE_STATES, "Manufacturer": TABLE_MANUFACTURERS,
                "Purchase UoM": TABLE_UOM, "Consumption UoM": TABLE_UOM, "PN Category": "42471"},
    TABLE_ASSEMBLY: {"Item": TABLE_BOM, "Contains": TABLE_BOM, "Measurement UoM": TABLE_UOM},
    TABLE_INSTRUCTIONS: {"Parent Item": TABLE_BOM, "Child Item": TABLE_BOM,
                         "Tool": TABLE_BOM, "Action Receiving Item": TABLE_BOM},
    TABLE_MANUFACTURERS: {"Suppliers": TABLE_SUPPLIERS},
    TABLE_SUPPLIERS: {"Imports From": TABLE_MANUFACTURERS, "Contacts": TABLE_CONTACTS},
    TABLE_CONTACTS: {"Suppliers": TABLE_SUPPLIERS},
}
FILE_FIELDS = {
    TABLE_BOM: ("Image", "Datasheet"),
    TABLE_INSTRUCTIONS: ("Photo",),
    TABLE_MANUFACTURERS: ("Logo",),
    TABLE_SUPPLIERS: ("Logo",),
}
SELECT_FIELDS = {TABLE_BOM: {"Sourced By": SOURCED_BY_OPTIONS}}


class FakeResponse:
    def __init__(self, status_code=200, data=None, content=None):
        self.status_code = status_code
        self._data = data
        self._content = content if content is not None else json.dumps(data).encode()

    def json(self):
        return copy.deepcopy(self._data)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def iter_content(self, chunk_size=65536):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]

    def close(self):
        pass


class FakeBaserow:
    """In-memory Baserow. Install with fake.attach(client)."""

    def __init__(self):
        self.tables = {t: {} for t in (TABLE_BOM, TABLE_ASSEMBLY, TABLE_INSTRUCTIONS,
                                       TABLE_MANUFACTURERS, TABLE_SUPPLIERS, TABLE_CONTACTS)}
        self.tables[TABLE_UOM] = {i: {"id": i, "Name": n, "Symbol": n[:2].lower()} for i, n in UOMS.items()}
        self.tables[TABLE_STATES] = {i: {"id": i, "Name": n} for n, i in STATES.items()}
        self.next_id = 1000
        self.user_files = {}
        self.remote = {}
        self.calls = []
        self.fields_endpoint_status = 200

    # ------------------------------------------------------------------ helpers
    def attach(self, client):
        client.api_url = API
        client._request = self.request
        client.states_map = {n: {"id": i, "name": n} for n, i in STATES.items()}
        client.states_loaded = True
        client._instructions_fields_checked = True
        client._assembly_quantity_decimals = 0
        return client

    def checksum(self):
        return hashlib.sha256(json.dumps(self.tables, sort_keys=True, default=str).encode()).hexdigest()

    def _primary(self, table, row_id):
        row = self.tables.get(table, {}).get(row_id)
        if not row:
            return str(row_id)
        if table == TABLE_BOM:
            return row.get("Full PN")
        return row.get("Name") or row.get("Company Name") or str(row_id)

    def _file_entry(self, ref):
        stored = self.user_files.get(ref.get("name"))
        if stored is None:
            raise ValueError(f"unknown user file {ref.get('name')}")
        entry = copy.deepcopy(stored["meta"])
        if ref.get("visible_name"):
            entry["visible_name"] = ref["visible_name"]
        return entry

    def _normalize(self, table, data):
        out = {}
        for field, value in data.items():
            if field in LINK_FIELDS.get(table, {}):
                target = LINK_FIELDS[table][field]
                ids = []
                for v in value or []:
                    ids.append(v["id"] if isinstance(v, dict) else v)
                out[field] = [{"id": i, "value": self._primary(target, i)} for i in ids]
            elif field in FILE_FIELDS.get(table, ()):
                out[field] = [self._file_entry(v) for v in (value or [])]
            elif field in SELECT_FIELDS.get(table, {}):
                if value is None:
                    out[field] = None
                else:
                    opt = next(o for o in SELECT_FIELDS[table][field] if o["id"] == value or o["value"] == value)
                    out[field] = {"id": opt["id"], "value": opt["value"], "color": "blue"}
            else:
                out[field] = value
        return out

    def _refresh_formulas(self, table, row):
        if table == TABLE_BOM:
            rev = row.get("Revision") or ""
            row["Full PN"] = f"{row.get('Part Number')} Rev.{rev}" if rev else row.get("Part Number")

    def add_row(self, table, data, row_id=None):
        row_id = row_id if row_id is not None else self._new_id()
        base = {"id": row_id, "order": "1.00000000000000000000"}
        if table == TABLE_BOM:
            base.update({"Image": [], "Datasheet": [], "Source URL": "", "Notes": "", "Lot Size": None,
                         "Sourced By": None, "Purchase UoM": [], "Consumption UoM": [],
                         "Manufacturer": [], "State": [], "External Part Number": "",
                         "Blackbox": False, "Purchase Kit": False, "Price per unit": None,
                         "Item description": "", "Revision": "", "PN Category": []})
        if table == TABLE_INSTRUCTIONS:
            base.update({"Child Item": [], "Tool": [], "Action Receiving Item": [], "Photo": [],
                         "Toll Map": "", "Tool Map": "", "Action": "", "Description": ""})
        base.update(self._normalize(table, data))
        self._refresh_formulas(table, base)
        self.tables[table][row_id] = base
        return copy.deepcopy(base)

    def add_user_file(self, original_name, content, mime_type):
        idx = len(self.user_files) + 1
        stored_name = f"stored{idx}_{original_name}"
        meta = {
            "url": f"{API}/media/user_files/{stored_name}",
            "thumbnails": {"tiny": {"url": f"{API}/media/thumbnails/tiny/{stored_name}", "width": 21, "height": 21},
                           "small": {"url": f"{API}/media/thumbnails/small/{stored_name}", "width": 48, "height": 48},
                           "card_cover": {"url": f"{API}/media/thumbnails/card_cover/{stored_name}", "width": 300, "height": 160}},
            "visible_name": original_name,
            "name": stored_name,
            "size": len(content),
            "mime_type": mime_type,
            "is_image": mime_type.startswith("image/"),
            "image_width": None,
            "image_height": None,
            "uploaded_at": "2026-11-01T09:00:00+00:00",
        }
        self.user_files[stored_name] = {"meta": meta, "content": content}
        return copy.deepcopy(meta)

    def _new_id(self):
        self.next_id += 1
        return self.next_id

    @staticmethod
    def _matches(row, params):
        for key, val in params.items():
            if key.startswith("filter__") and key.endswith("__link_row_has"):
                field = key[len("filter__"):-len("__link_row_has")]
                if int(val) not in [x.get("id") for x in row.get(field) or []]:
                    return False
            elif key.startswith("filter__") and key.endswith("__equal"):
                field = key[len("filter__"):-len("__equal")]
                if str(row.get(field)) != str(val):
                    return False
        return True

    # ------------------------------------------------------------------ HTTP
    def request(self, method, url, retries=4, backoff_factor=0.3, **kwargs):
        method = method.upper()
        parsed = urlparse(url)
        path = parsed.path
        self.calls.append((method, path))

        if path.startswith("/media/"):
            stored = self.user_files.get(path.rsplit("/", 1)[-1])
            return FakeResponse(200, content=stored["content"]) if stored else FakeResponse(404, {"error": "not found"})

        if path == "/api/user-files/upload-file/" and method == "POST":
            name, content, mime = kwargs["files"]["file"]
            return FakeResponse(200, self.add_user_file(name, content, mime))
        if path == "/api/user-files/upload-via-url/" and method == "POST":
            remote_url = kwargs["json"]["url"]
            if remote_url not in self.remote:
                return FakeResponse(400, {"error": "ERROR_FILE_URL_COULD_NOT_BE_REACHED"})
            content, mime = self.remote[remote_url]
            return FakeResponse(200, self.add_user_file(remote_url.rsplit("/", 1)[-1], content, mime))

        m = re.match(r"^/api/database/fields/table/(\d+)/$", path)
        if m:
            if self.fields_endpoint_status != 200:
                return FakeResponse(self.fields_endpoint_status, {"error": "ERROR_NO_PERMISSION"})
            table = m.group(1)
            fields = [{"name": f, "type": "text"} for f in ("Toll Map", "Tool Map")]
            fields.append({"name": "Amount of Times", "type": "number", "number_decimal_places": 0})
            for name, opts in SELECT_FIELDS.get(table, {}).items():
                fields.append({"name": name, "type": "single_select", "select_options": opts})
            return FakeResponse(200, fields)

        m = re.match(r"^/api/database/rows/table/(\d+)/(?:(\d+)/)?$", path)
        if not m:
            return FakeResponse(404, {"error": f"unknown endpoint {path}"})
        table, row_id = m.group(1), m.group(2)
        rows = self.tables.setdefault(table, {}) if method == "POST" else self.tables.get(table, {})

        if row_id is None and method == "GET":
            params = dict(kwargs.get("params") or {})
            for part in (parsed.query or "").split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params.setdefault(k, v)
            result = [copy.deepcopy(r) for r in rows.values() if self._matches(r, params)]
            order = params.get("order_by")
            if order:
                field = order.lstrip("-")
                result.sort(key=lambda r: float(r.get(field) or 0), reverse=order.startswith("-"))
            size = int(params.get("size", 100))
            return FakeResponse(200, {"count": len(result), "next": None, "previous": None, "results": result[:size]})
        if row_id is None and method == "POST":
            return FakeResponse(200, self.add_row(table, kwargs.get("json") or {}))

        row_id = int(row_id)
        if row_id not in rows:
            return FakeResponse(404, {"error": "ERROR_ROW_DOES_NOT_EXIST"})
        if method == "GET":
            return FakeResponse(200, copy.deepcopy(rows[row_id]))
        if method == "PATCH":
            rows[row_id].update(self._normalize(table, kwargs.get("json") or {}))
            self._refresh_formulas(table, rows[row_id])
            return FakeResponse(200, copy.deepcopy(rows[row_id]))
        if method == "DELETE":
            del rows[row_id]
            for other_table, link_fields in LINK_FIELDS.items():
                for other in self.tables.get(other_table, {}).values():
                    for field, target in link_fields.items():
                        if target == table and other.get(field):
                            other[field] = [x for x in other[field] if x.get("id") != row_id]
            return FakeResponse(204, {})
        return FakeResponse(405, {"error": "method not allowed"})
