"""
End-to-end tests for the ERA MCP endpoint gaps G1-G10 (item fields, file attachments,
revision re-pointing of work instructions, WI step sync, compact reads, dry-run, audit log
and revert). The real BaserowClient runs against the in-memory FakeBaserow API, so no live
Baserow is touched.
"""

import asyncio
import base64
import json

import pytest

from app.baserow_client import BaserowClient
from app.mcp_server import create_mcp_server
from app import mcp_write_guard
from tests.fake_baserow import (
    FakeBaserow, TABLE_ENV, TABLE_BOM, TABLE_ASSEMBLY, TABLE_INSTRUCTIONS,
    TABLE_MANUFACTURERS, TABLE_SUPPLIERS, STATES,
)

FAN_B = 20
ASSY = 10
SCREW = 30
VISE = 40
OLD_LINK = "https://mou.sr/3RkK4fC"
NEW_LINK = "https://www.mouser.com/ProductDetail/Same-Sky/CFM-8015BF-230-301-20"
DATASHEET_URL = "https://sameskydevices.com/product/resource/cfm-80bf.pdf"


def make_pdf(text: str) -> bytes:
    """A one-page PDF whose text layer is `text`."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


@pytest.fixture
def env(monkeypatch):
    for k, v in TABLE_ENV.items():
        monkeypatch.setenv(k, v)
    fake = FakeBaserow()
    client = fake.attach(BaserowClient())

    fake.add_row(TABLE_SUPPLIERS, {"Company Name": "Mouser", "Online Store": True}, row_id=1)
    fake.add_row(TABLE_MANUFACTURERS, {"Name": "NMB", "Suppliers": [1]}, row_id=1)
    fake.add_row(TABLE_MANUFACTURERS, {"Name": "Same Sky", "Suppliers": [1]}, row_id=2)
    photo = fake.add_user_file("nmb_fan.png", b"png-bytes", "image/png")

    fake.add_row(TABLE_BOM, {"Part Number": "55-00022", "Revision": "A", "Item description": "Fan tray assembly",
                             "State": [STATES["Production Use"]]}, row_id=ASSY)
    fake.add_row(TABLE_BOM, {"Part Number": "40-00014", "Revision": "B", "Item description": "Fan 80mm 230V",
                             "State": [STATES["Production Use"]], "Manufacturer": [1], "Notes": "NMB fan",
                             "External Part Number": "NMB-3110KL", "Source URL": OLD_LINK, "Lot Size": 1,
                             "Price per unit": 12.5, "Image": [{"name": photo["name"]}]}, row_id=FAN_B)
    fake.add_row(TABLE_BOM, {"Part Number": "20-00001", "Revision": "A", "Item description": "M3x8 screw",
                             "State": [STATES["Production Use"]]}, row_id=SCREW)
    fake.add_row(TABLE_BOM, {"Part Number": "90-00001", "Revision": "A", "Item description": "Stationary vise",
                             "State": [STATES["Production Use"]]}, row_id=VISE)

    fake.add_row(TABLE_ASSEMBLY, {"Item": [ASSY], "Contains": [FAN_B], "Amount of Times": 1, "Measurement": 0,
                                  "PCB Symbol": "N/A"}, row_id=101)
    fake.add_row(TABLE_ASSEMBLY, {"Item": [ASSY], "Contains": [SCREW], "Amount of Times": 4, "Measurement": 0,
                                  "PCB Symbol": "N/A"}, row_id=102)

    fake.add_row(TABLE_INSTRUCTIONS, {
        "Parent Item": [ASSY], "Set Index": "1", "Step Order": "1", "Action": "Place",
        "Description": "Place the fan in the tray.", "Action Receiving Item": [ASSY],
        "Child Item": [FAN_B], "Tool": [VISE],
        "Toll Map": json.dumps([{"edge_id": 101, "item_id": FAN_B, "toll": True, "qty": 1, "length": 0}]),
        "Tool Map": json.dumps([{"id": VISE, "quantity": 1}]),
    }, row_id=133)
    fake.add_row(TABLE_INSTRUCTIONS, {
        "Parent Item": [ASSY], "Set Index": "1", "Step Order": "2", "Action": "Screw",
        "Description": "Fasten the fan.", "Child Item": [SCREW, FAN_B],
        "Toll Map": json.dumps([{"edge_id": 102, "item_id": SCREW, "toll": True, "qty": 4, "length": 0},
                                {"edge_id": 101, "item_id": FAN_B, "toll": False, "qty": 1, "length": 0}]),
    }, row_id=134)
    fake.add_row(TABLE_INSTRUCTIONS, {
        "Parent Item": [ASSY], "Set Index": "1", "Step Order": "3", "Action": "Inspect",
        "Description": "Spin the fan by hand.",
    }, row_id=135)
    # The fan's own (historical) instruction: must not be re-pointed by a revision.
    fake.add_row(TABLE_INSTRUCTIONS, {
        "Parent Item": [FAN_B], "Set Index": "1", "Step Order": "1", "Action": "Label",
        "Description": "Label the fan.", "Action Receiving Item": [FAN_B],
    }, row_id=140)

    server = create_mcp_server(client)

    def call(tool, **args):
        res = asyncio.run(server.call_tool(tool, args))
        return json.loads(res.content[0].text)

    return fake, client, call


def row(fake, table, row_id):
    return fake.tables[table][row_id]


def link_ids(value):
    return [x["id"] for x in value or []]


# ---------------------------------------------------------------- P1: item fields (G1, G3, G4)

def test_update_item_sets_source_url_and_details_show_it(env):
    fake, _, call = env
    res = call("update_item", part_number_or_id="40-00014 Rev.B", source_url=NEW_LINK)
    assert "error" not in res, res
    assert res["updated_fields"] == ["Source URL"]
    assert row(fake, TABLE_BOM, FAN_B)["Source URL"] == NEW_LINK
    assert call("get_item_details", part_number_or_id="40-00014 Rev.B")["source_url"] == NEW_LINK


def test_update_item_rejects_conflicting_name_and_description(env):
    fake, _, call = env
    before = fake.checksum()
    res = call("update_item", part_number_or_id=str(FAN_B), name="A", description="B")
    assert "error" in res and "Item description" in res["error"]
    assert fake.checksum() == before

    same = call("update_item", part_number_or_id=str(FAN_B), name="Fan", description="Fan")
    assert "error" not in same
    assert row(fake, TABLE_BOM, FAN_B)["Item description"] == "Fan"


def test_update_item_sourced_by_lot_size_and_uoms(env):
    fake, _, call = env
    res = call("update_item", part_number_or_id=str(FAN_B), sourced_by="purchased by era",
               lot_size=10, purchase_uom="pcs", consumption_uom="Meter")
    assert "error" not in res, res
    r = row(fake, TABLE_BOM, FAN_B)
    assert r["Sourced By"]["value"] == "Purchased by ERA"
    assert r["Lot Size"] == 10.0
    assert link_ids(r["Purchase UoM"]) == [3]
    assert link_ids(r["Consumption UoM"]) == [6]

    cleared = call("update_item", part_number_or_id=str(FAN_B), purchase_uom="")
    assert "error" not in cleared
    assert row(fake, TABLE_BOM, FAN_B)["Purchase UoM"] == []


def test_update_item_rejects_unknown_sourced_by_and_uom(env):
    fake, _, call = env
    before = fake.checksum()
    bad = call("update_item", part_number_or_id=str(FAN_B), sourced_by="Bought somewhere")
    assert "Invalid sourced_by" in bad["error"] and "Purchased by ERA" in bad["error"]
    bad_uom = call("update_item", part_number_or_id=str(FAN_B), consumption_uom="furlong")
    assert "unit of measure" in bad_uom["error"]
    assert fake.checksum() == before


def test_sourced_by_falls_back_to_row_values_without_fields_permission(env):
    fake, client, call = env
    fake.fields_endpoint_status = 401
    client.update_item(SCREW, {"Sourced By": 3002})
    res = call("update_item", part_number_or_id=str(FAN_B), sourced_by="Produced by Contractor")
    assert "error" not in res, res
    assert row(fake, TABLE_BOM, FAN_B)["Sourced By"]["id"] == 3002


def test_supplier_and_nre_cost_explain_missing_fields(env):
    fake, _, call = env
    before = fake.checksum()
    sup = call("update_item", part_number_or_id=str(FAN_B), supplier="Mouser")
    assert "no 'Supplier' field" in sup["error"]
    nre = call("update_item", part_number_or_id=str(FAN_B), nre_cost=250)
    assert "no 'NRE Cost' field" in nre["error"]
    assert fake.checksum() == before


def test_supplier_and_nre_cost_write_when_fields_exist(env):
    fake, _, call = env
    row(fake, TABLE_BOM, FAN_B)["Supplier"] = []
    row(fake, TABLE_BOM, FAN_B)["NRE Cost"] = None
    res = call("update_item", part_number_or_id=str(FAN_B), supplier="Mouser", nre_cost=250)
    assert "error" not in res, res
    assert row(fake, TABLE_BOM, FAN_B)["Supplier"] == [1]
    assert row(fake, TABLE_BOM, FAN_B)["NRE Cost"] == 250.0


def test_create_item_accepts_new_fields(env):
    fake, _, call = env
    res = call("create_item", part_number="40-00200", description="Fan guard",
               source_url="https://example.com/guard", sourced_by="TBD", lot_size=5)
    assert "error" not in res, res
    new = row(fake, TABLE_BOM, res["item"]["id"])
    assert new["Item description"] == "Fan guard"
    assert new["Source URL"] == "https://example.com/guard"
    assert new["Sourced By"]["value"] == "TBD"
    assert new["Lot Size"] == 5.0

    conflict = call("create_item", part_number="40-00201", name="Short", description="Long spec text")
    assert "error" in conflict
    missing = call("create_item", part_number="40-00202")
    assert "required" in missing["error"]


# ---------------------------------------------------------------- P2: files (G2, G9)

def test_upload_datasheet_by_url_and_list_it(env):
    fake, _, call = env
    pdf = make_pdf("CFM-80BF datasheet rated 230VAC")
    fake.remote[DATASHEET_URL] = (pdf, "application/pdf")

    res = call("upload_item_file", part_number_or_id="40-00014 Rev.B", field="Datasheet",
               source_url=DATASHEET_URL, filename="cfm-80bf.pdf")
    assert res.get("ok") is True, res
    assert res["file"]["visible_name"] == "cfm-80bf.pdf"
    assert res["file"]["mime_type"] == "application/pdf"

    listed = call("list_item_files", part_number_or_id="40-00014 Rev.B")
    assert [f["visible_name"] for f in listed["Datasheet"]] == ["cfm-80bf.pdf"]
    assert [f["visible_name"] for f in listed["Image"]] == ["nmb_fan.png"]
    assert "thumbnails" not in json.dumps(listed)

    text = call("download_item_file", part_number_or_id=str(FAN_B), file_name="cfm-80bf.pdf")
    assert text["encoding"] == "text"
    assert "230VAC" in text["content"]
    assert text["page_count"] == 1

    raw = call("download_item_file", part_number_or_id=str(FAN_B), file_name="cfm-80bf.pdf", as_text=False)
    assert base64.b64decode(raw["content"]) == pdf

    capped = call("download_item_file", part_number_or_id=str(FAN_B), file_name="cfm-80bf.pdf", max_bytes=10)
    assert "max_bytes" in capped["error"]


def test_upload_appends_or_replaces_and_remove_detaches(env):
    fake, _, call = env
    b64 = base64.b64encode(b"spec sheet text").decode()
    first = call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                 file_base64=b64, filename="notes.txt")
    assert first["ok"] is True, first
    second = call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                  file_base64=b64, filename="notes-v2.txt")
    assert second["field_file_count"] == 2
    as_text = call("download_item_file", part_number_or_id=str(FAN_B), file_name="notes-v2.txt")
    assert as_text["content"] == "spec sheet text"

    replaced = call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                    file_base64=b64, filename="final.txt", replace=True)
    assert replaced["field_file_count"] == 1

    removed = call("remove_item_file", part_number_or_id=str(FAN_B), field="Image", file_name="nmb_fan.png")
    assert removed["ok"] is True and removed["remaining"] == []
    assert row(fake, TABLE_BOM, FAN_B)["Image"] == []
    assert [f["visible_name"] for f in row(fake, TABLE_BOM, FAN_B)["Datasheet"]] == ["final.txt"]


def test_file_tool_validation(env):
    fake, _, call = env
    before = fake.checksum()
    assert "exactly one" in call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                                 filename="x.pdf")["error"]
    assert "Invalid field" in call("upload_item_file", part_number_or_id=str(FAN_B), field="Manual",
                                   source_url=DATASHEET_URL)["error"]
    assert "valid base64" in call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                                  file_base64="***", filename="x.pdf")["error"]
    assert "Present" in call("remove_item_file", part_number_or_id=str(FAN_B), field="Image",
                             file_name="nope.png")["error"]
    assert "error" in call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
                           source_url="https://unreachable.example/x.pdf")
    assert fake.checksum() == before


def test_upload_directory_logo(env):
    fake, _, call = env
    fake.remote["https://www.sameskydevices.com/logo.png"] = (b"logo", "image/png")
    res = call("upload_directory_logo", kind="manufacturer", name_or_id="Same Sky",
               source_url="https://www.sameskydevices.com/logo.png")
    assert res["ok"] is True, res
    assert [f["visible_name"] for f in row(fake, TABLE_MANUFACTURERS, 2)["Logo"]] == ["logo.png"]
    assert "kind must be" in call("upload_directory_logo", kind="contact", name_or_id="x",
                                  source_url="https://x/y.png")["error"]


# ---------------------------------------------------------------- P3: revisions (G5, G6)

def test_revision_repoints_work_instructions(env):
    fake, _, call = env
    res = call("create_item_revision", part_number_or_id="40-00014 Rev.B")
    assert res["ok"] is True, res
    new_id = res["new"]["id"]
    assert res["new"]["full_pn"] == "40-00014 Rev.C"
    assert res["edges_repointed"] == 1

    touched = {s["step_id"]: s["fields"] for s in res["work_instruction_steps_repointed"]}
    assert set(touched) == {133, 134}
    assert touched[133] == ["Child Item", "Toll Map"]

    s133 = row(fake, TABLE_INSTRUCTIONS, 133)
    assert json.loads(s133["Toll Map"]) == [{"edge_id": 101, "item_id": new_id, "toll": True, "qty": 1.0, "length": 0.0}]
    assert link_ids(s133["Child Item"]) == [new_id]
    assert link_ids(s133["Tool"]) == [VISE]
    assert link_ids(row(fake, TABLE_INSTRUCTIONS, 134)["Child Item"]) == [SCREW, new_id]
    # The fan's own instruction keeps pointing at the old revision.
    assert link_ids(row(fake, TABLE_INSTRUCTIONS, 140)["Action Receiving Item"]) == [FAN_B]
    assert link_ids(row(fake, TABLE_ASSEMBLY, 101)["Contains"]) == [new_id]

    wi = call("get_work_instructions", part_number_or_id="55-00022", compact=True)
    assert "40-00014 Rev.B" not in json.dumps(wi["steps"])
    assert "40-00014 Rev.B" not in json.dumps(wi["balance"])
    assert all(s["child_item_in_sync"] for s in wi["steps"])


def test_revision_without_wi_repoint_leaves_steps(env):
    fake, _, call = env
    res = call("create_item_revision", part_number_or_id=str(FAN_B), repoint_work_instructions=False)
    assert res["ok"] is True and res["work_instruction_steps_repointed"] == []
    assert link_ids(row(fake, TABLE_INSTRUCTIONS, 133)["Child Item"]) == [FAN_B]


def test_revision_copy_fields_and_overrides(env):
    fake, _, call = env
    res = call("create_item_revision", part_number_or_id=str(FAN_B), copy_fields=["notes", "images"],
               overrides={"source_url": NEW_LINK, "external_pn": "CFM-8015BF-230-301-20",
                          "manufacturer": "Same Sky", "description": "Fan 80mm 230V (Same Sky)"})
    assert res["ok"] is True, res
    new = row(fake, TABLE_BOM, res["new"]["id"])
    assert new["Source URL"] == NEW_LINK
    assert new["External Part Number"] == "CFM-8015BF-230-301-20"
    assert link_ids(new["Manufacturer"]) == [2]
    assert new["Notes"] == "NMB fan"
    assert [f["visible_name"] for f in new["Image"]] == ["nmb_fan.png"]
    assert new["Price per unit"] is None
    assert new["Item description"] == "Fan 80mm 230V (Same Sky)"
    old = row(fake, TABLE_BOM, FAN_B)
    assert old["Source URL"] == OLD_LINK
    assert link_ids(old["State"]) == [STATES["EOL"]]

    default = call("create_item_revision", part_number_or_id=res["new"]["full_pn"])
    newer = row(fake, TABLE_BOM, default["new"]["id"])
    assert newer["Source URL"] == NEW_LINK
    assert newer["Image"] == []


def test_revision_rejects_bad_options_before_writing(env):
    fake, _, call = env
    before = fake.checksum()
    assert "Unknown copy_fields" in call("create_item_revision", part_number_or_id=str(FAN_B),
                                         copy_fields=["colour"])["error"]
    assert "Unknown overrides" in call("create_item_revision", part_number_or_id=str(FAN_B),
                                       overrides={"Source URL": "x"})["error"]
    assert "manufacturer" in call("create_item_revision", part_number_or_id=str(FAN_B),
                                  overrides={"manufacturer": "Nobody"})["error"]
    assert fake.checksum() == before


# ---------------------------------------------------------------- P4: WI steps (G7)

def test_wi_step_syncs_child_item_tools_receiving_and_photo(env):
    fake, _, call = env
    fake.remote["https://img.example/step1.jpg"] = (b"jpeg", "image/jpeg")
    res = call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=1,
               tolling_items=[{"edge_id": 101, "item_id": FAN_B, "qty": 1, "toll": True},
                              {"id": SCREW, "quantity": 2}],
               tools=[{"part_number": "90-00001", "quantity": 2}],
               receiving_item="55-00022 Rev.A", photo_url="https://img.example/step1.jpg")
    assert "error" not in res, res
    s = row(fake, TABLE_INSTRUCTIONS, 133)
    assert link_ids(s["Child Item"]) == [FAN_B, SCREW]
    assert [e["item_id"] for e in json.loads(s["Toll Map"])] == [FAN_B, SCREW]
    assert json.loads(s["Tool Map"]) == [{"id": VISE, "quantity": 2}]
    assert link_ids(s["Tool"]) == [VISE]
    assert link_ids(s["Action Receiving Item"]) == [ASSY]
    assert [f["visible_name"] for f in s["Photo"]] == ["step1.jpg"]
    assert s["Description"] == "Place the fan in the tray."

    cleared = call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=1,
                   tools=[], receiving_item="")
    assert "error" not in cleared
    s = row(fake, TABLE_INSTRUCTIONS, 133)
    assert s["Tool"] == [] and json.loads(s["Tool Map"]) == [] and s["Action Receiving Item"] == []


def test_wi_step_repairs_stale_child_item_and_flags_it(env):
    fake, client, call = env
    client.update_instruction(134, {"Child Item": [SCREW, VISE]})
    wi = call("get_work_instructions", part_number_or_id="55-00022")
    step2 = next(s for s in wi["steps"] if s["step_id"] == 134)
    assert step2["child_item_in_sync"] is False
    assert step2["child_item_link_ids"] == sorted([SCREW, VISE])

    toll = json.loads(row(fake, TABLE_INSTRUCTIONS, 134)["Toll Map"])
    call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=2, tolling_items=toll)
    wi = call("get_work_instructions", part_number_or_id="55-00022")
    assert all(s["child_item_in_sync"] for s in wi["steps"])


def test_wi_step_validation(env):
    fake, _, call = env
    before = fake.checksum()
    assert "unknown item IDs" in call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=1,
                                      tolling_items=[{"item_id": 99999, "qty": 1}])["error"]
    assert "item_id" in call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=1,
                             tolling_items=[{"qty": 1}])["error"]
    assert "required when creating" in call("create_or_update_wi_step", assembly_pn_or_id="55-00022",
                                            step_number=9)["error"]
    assert "not found" in call("create_or_update_wi_step", assembly_pn_or_id="55-00022", step_number=1,
                               tools=[{"part_number": "90-99999"}])["error"]
    assert fake.checksum() == before


def test_delete_wi_step_renumbers_following_steps(env):
    fake, _, call = env
    res = call("delete_wi_step", assembly_pn_or_id="55-00022", step_number=1)
    assert res["ok"] is True, res
    assert 133 not in fake.tables[TABLE_INSTRUCTIONS]
    assert res["renumbered"] == [{"step_id": 134, "from": 2, "to": 1}, {"step_id": 135, "from": 3, "to": 2}]
    assert row(fake, TABLE_INSTRUCTIONS, 134)["Step Order"] == 1
    assert row(fake, TABLE_INSTRUCTIONS, 140)["Step Order"] == "1"
    assert "not found" in call("delete_wi_step", assembly_pn_or_id="55-00022", step_number=7)["error"]


# ---------------------------------------------------------------- P5: compact reads (G8)

def test_compact_work_instructions_stay_small(env):
    fake, _, call = env
    big_image = [{"name": fake.add_user_file(f"view{i}.png", b"x" * 10, "image/png")["name"]} for i in range(3)]
    part_ids = []
    for i in range(12):
        r = fake.add_row(TABLE_BOM, {"Part Number": f"20-0010{i:02d}", "Revision": "A",
                                     "Item description": f"Part {i} " + "spec " * 20, "Image": big_image})
        edge = fake.add_row(TABLE_ASSEMBLY, {"Item": [ASSY], "Contains": [r["id"]], "Amount of Times": 1})
        part_ids.append((r["id"], edge["id"]))
    for n in range(6):
        slots = part_ids[n * 2:n * 2 + 2]
        fake.add_row(TABLE_INSTRUCTIONS, {
            "Parent Item": [ASSY], "Set Index": "2", "Step Order": str(n + 1), "Action": "Fit",
            "Description": f"Fit parts for step {n + 1}.", "Child Item": [p for p, _ in slots],
            "Toll Map": json.dumps([{"edge_id": e, "item_id": p, "toll": True, "qty": 1, "length": 0} for p, e in slots]),
            "Photo": big_image,
        })

    compact = call("get_work_instructions", part_number_or_id="55-00022", set_index=2)
    full = call("get_work_instructions", part_number_or_id="55-00022", set_index=2, compact=False)
    compact_len = len(json.dumps(compact))
    assert len(compact["steps"]) == 6
    assert compact_len < 6000
    assert len(json.dumps(full, indent=2)) > 3 * compact_len
    assert "thumbnails" not in json.dumps(compact)
    assert compact["steps"][0]["photos"] == ["view0.png", "view1.png", "view2.png"]


def test_directory_listings_are_compact_by_default(env):
    fake, _, call = env
    logo = fake.add_user_file("mouser.png", b"logo", "image/png")
    fake.tables[TABLE_SUPPLIERS][1]["Logo"] = [logo]
    compact = call("list_suppliers")
    assert compact["suppliers"][0]["Logo"] == ["mouser.png"]
    full = call("list_suppliers", compact=False)
    assert "thumbnails" in full["suppliers"][0]["Logo"][0]
    both = call("list_manufacturers_and_suppliers")
    assert both["suppliers"][0]["Logo"] == ["mouser.png"]


# ---------------------------------------------------------------- P6: dry run, audit log, revert (G10)

def test_dry_run_writes_nothing_and_reports_diff(env, isolated_audit_log):
    fake, _, call = env
    before = fake.checksum()
    res = call("update_item", part_number_or_id="40-00014 Rev.B", source_url=NEW_LINK, dry_run=True)
    assert res["dry_run"] is True
    assert fake.checksum() == before
    [write] = res["would_write"]
    assert write["method"] == "update_item" and write["row_id"] == FAN_B
    assert write["changes"] == {"Source URL": {"before": OLD_LINK, "after": NEW_LINK}}
    assert res["result_preview"]["updated_fields"] == ["Source URL"]
    assert not isolated_audit_log.exists()


def test_dry_run_revision_previews_without_writing(env):
    fake, _, call = env
    before = fake.checksum()
    res = call("create_item_revision", part_number_or_id=str(FAN_B), dry_run=True,
               overrides={"source_url": NEW_LINK})
    assert fake.checksum() == before
    preview = res["result_preview"]
    assert preview["new"]["full_pn"] == "40-00014 Rev.C"
    assert preview["edges_repointed"] == 1
    assert {s["step_id"] for s in preview["work_instruction_steps_repointed"]} == {133, 134}
    methods = [w["method"] for w in res["would_write"]]
    assert methods[0] == "add_revision" and methods.count("update_instruction") == 2


def test_dry_run_upload_and_step_tools(env):
    fake, _, call = env
    fake.remote[DATASHEET_URL] = (make_pdf("x"), "application/pdf")
    before_files = dict(fake.user_files)
    before = fake.checksum()
    up = call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
              source_url=DATASHEET_URL, dry_run=True)
    assert up["dry_run"] is True and [w["kind"] for w in up["would_write"]] == ["upload", "update"]
    dele = call("delete_wi_step", assembly_pn_or_id="55-00022", step_number=1, dry_run=True)
    assert [w["kind"] for w in dele["would_write"]] == ["delete", "update", "update"]
    edge = call("delete_bom_edge", edge_id="102", dry_run=True)
    assert edge["would_write"][0]["before"]["Amount of Times"] == 4
    assert fake.checksum() == before
    assert fake.user_files == before_files


def test_audit_log_and_revert_update(env, isolated_audit_log):
    fake, _, call = env
    before = fake.checksum()
    res = call("update_item", part_number_or_id=str(FAN_B), source_url=NEW_LINK, notes="Same Sky now")
    change_id = res["change_id"]
    assert isolated_audit_log.exists()

    changes = call("list_changes", part_number_or_id="40-00014 Rev.B")
    assert changes["changes"][0]["change_id"] == change_id
    assert changes["changes"][0]["writes"][0]["changes"]["Source URL"]["before"] == OLD_LINK

    unconfirmed = call("revert_change", change_id=change_id)
    assert unconfirmed["requires_confirmation"] is True
    assert row(fake, TABLE_BOM, FAN_B)["Source URL"] == NEW_LINK

    done = call("revert_change", change_id=change_id, confirm=True)
    assert done["ok"] is True and done["skipped"] == []
    assert fake.checksum() == before
    assert "already reverted" in call("revert_change", change_id=change_id, confirm=True)["error"]
    assert call("list_changes")["changes"][0]["reverted_by"] == done["revert_change_id"]
    assert "not found" in call("revert_change", change_id="chg_missing", confirm=True)["error"]


def test_revert_revision_restores_original_state(env):
    fake, _, call = env
    before = fake.checksum()
    res = call("create_item_revision", part_number_or_id=str(FAN_B), copy_fields=[],
               overrides={"source_url": NEW_LINK})
    assert res["ok"] is True and fake.checksum() != before
    done = call("revert_change", change_id=res["change_id"], confirm=True)
    assert done["ok"] is True, done
    assert fake.checksum() == before


def test_revert_create_and_skips_deletes(env):
    fake, _, call = env
    created = call("create_item", part_number="40-00300", description="Temp part")
    new_id = created["item"]["id"]
    call("revert_change", change_id=created["change_id"], confirm=True)
    assert new_id not in fake.tables[TABLE_BOM]

    deleted = call("delete_bom_edge", edge_id="102")
    out = call("revert_change", change_id=deleted["change_id"], confirm=True)
    assert out["reverted"] == [] and "cannot be undone" in out["skipped"][0]["reason"]


def test_audit_log_can_be_disabled(env, monkeypatch, isolated_audit_log):
    fake, _, call = env
    monkeypatch.setenv("ERA_AUDIT_LOG", "off")
    res = call("update_item", part_number_or_id=str(FAN_B), notes="x")
    assert "change_id" not in res and res["writes_count"] == 1
    assert mcp_write_guard.audit_log_path() is None


def test_guarded_client_passes_through_outside_tools(env):
    fake, client, _ = env
    from app.mcp_write_guard import GuardedClient
    guarded = GuardedClient(client)
    guarded.update_item(SCREW, {"Notes": "direct"})
    assert row(fake, TABLE_BOM, SCREW)["Notes"] == "direct"
    guarded.cached_uoms = ["x"]
    assert client.cached_uoms == ["x"]


def test_to_writable_shapes():
    assert mcp_write_guard.to_writable([{"id": 3, "value": "Piece"}]) == [3]
    assert mcp_write_guard.to_writable([{"name": "f.pdf", "visible_name": "F", "mime_type": "x"}]) == [
        {"name": "f.pdf", "visible_name": "F"}]
    assert mcp_write_guard.to_writable({"id": 7, "value": "TBD", "color": "blue"}) == 7
    assert mcp_write_guard.to_writable("text") == "text"


def test_audit_log_omits_large_arguments(env, isolated_audit_log):
    fake, _, call = env
    payload = base64.b64encode(b"z" * 4000).decode()
    res = call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet",
               file_base64=payload, filename="big.txt")
    assert res["ok"] is True
    [entry] = mcp_write_guard.read_audit_log()
    assert entry["args"]["file_base64"] == f"<{len(payload)} characters omitted>"


def test_pdf_download_falls_back_to_base64_without_pypdf(env, monkeypatch):
    import builtins
    fake, _, call = env
    pdf = make_pdf("hello")
    fake.remote[DATASHEET_URL] = (pdf, "application/pdf")
    call("upload_item_file", part_number_or_id=str(FAN_B), field="Datasheet", source_url=DATASHEET_URL)
    real_import = builtins.__import__

    def no_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("no pypdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pypdf)
    res = call("download_item_file", part_number_or_id=str(FAN_B), file_name="cfm-80bf.pdf")
    assert res["encoding"] == "base64" and "pypdf" in res["note"]
    assert base64.b64decode(res["content"]) == pdf
