import os
import io
import requests
import threading
import time
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from PIL import Image as PILImage

load_dotenv()
logger = logging.getLogger(__name__)

def normalize_uploaded_file(filename, content, content_type):
    """
    If the uploaded file is an image, normalize it via PIL to a standard format (PNG)
    to ensure full compatibility across Baserow, browser UI, and docx Work Instruction exports.
    Non-image files (e.g. PDF datasheets) are returned unmodified.
    """
    if not content:
        return filename, content, content_type

    is_image = False
    if content_type and content_type.startswith("image/"):
        is_image = True
    elif filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif', '.jfif', '.gif'):
            is_image = True

    if not is_image:
        return filename, content, content_type

    try:
        im = PILImage.open(io.BytesIO(content))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        normalized_content = buf.getvalue()

        base, _ = os.path.splitext(filename)
        new_filename = f"{base}.png" if base else "image.png"
        new_content_type = "image/png"

        return new_filename, normalized_content, new_content_type
    except Exception as e:
        logger.warning(f"Could not convert uploaded image {filename} to PNG, uploading original: {e}")
        return filename, content, content_type

def evaluate_condition(row, condition, is_in_assembly=False, has_children=False, bom_equilibrium=True, has_all_images=True):
    # If it is a logical group (AND/OR)
    if "type" in condition:
        logical_type = condition["type"].upper() # "AND" or "OR"
        sub_conditions = condition.get("conditions", [])
        if not sub_conditions:
            return True
        if logical_type == "AND":
            return all(evaluate_condition(row, c, is_in_assembly, has_children, bom_equilibrium, has_all_images) for c in sub_conditions)
        elif logical_type == "OR":
            return any(evaluate_condition(row, c, is_in_assembly, has_children, bom_equilibrium, has_all_images) for c in sub_conditions)
        return True
    
    # It is an atomic condition: { "field": "...", "operator": "...", "value": "..." }
    field = condition.get("field")
    operator = condition.get("operator")
    expected_value = condition.get("value")
    
    # Get actual value
    if field == "is_in_assembly":
        val = row.get("is_in_assembly", is_in_assembly)
        actual_value = str(val).lower() # "true" or "false"
    elif field == "has_children":
        val = row.get("has_children", has_children)
        actual_value = str(val).lower() # "true" or "false"
    elif field in ("bom_equilibrium", "bom_balance", "BOM equilibrium (balance)", "BOM Equilibrium (Balance)"):
        val = row.get("bom_equilibrium", bom_equilibrium)
        actual_value = str(val).lower() # "true" or "false"
    elif field in ("has_all_images", "Has all images", "has_all_photos", "Has all photos"):
        val = row.get("has_all_images", has_all_images)
        actual_value = str(val).lower() # "true" or "false"
    elif field in ("Blackbox", "blackbox"):
        val = row.get("Blackbox", False)
        is_bb = bool(val) if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes")
        actual_value = "true" if is_bb else "false"
    elif field in ("has_photos", "Has photos", "has_photo", "Has photo"):
        imgs = row.get("Image") or row.get("Photos") or row.get("Images") or []
        has_imgs = bool(imgs) if not isinstance(imgs, list) else len(imgs) > 0
        actual_value = "true" if has_imgs else "false"
    elif field in ("Price", "price", "Price per unit", "price_per_unit"):
        raw_val = row.get("Price per unit") if row.get("Price per unit") is not None else row.get("Price")
        if isinstance(raw_val, dict):
            actual_value = raw_val.get("value", "")
        else:
            actual_value = raw_val if raw_val is not None else ""
    elif field in ("External PN", "External Part Number"):
        raw_val = row.get("External PN") if row.get("External PN") is not None else row.get("External Part Number")
        if isinstance(raw_val, dict):
            actual_value = raw_val.get("value", "")
        elif isinstance(raw_val, list):
            actual_value = ", ".join(str(x.get("value") if isinstance(x, dict) else x) for x in raw_val)
        else:
            actual_value = raw_val if raw_val is not None else ""
    elif field in ("Source URL", "Source Link"):
        raw_val = row.get("Source URL") if row.get("Source URL") is not None else row.get("Source Link")
        if isinstance(raw_val, dict):
            actual_value = raw_val.get("value", "")
        elif isinstance(raw_val, list):
            actual_value = ", ".join(str(x.get("value") if isinstance(x, dict) else x) for x in raw_val)
        else:
            actual_value = raw_val if raw_val is not None else ""
    else:
        # Extract from Baserow row
        raw_val = row.get(field)
        if isinstance(raw_val, dict):
            actual_value = raw_val.get("value", "")
        elif isinstance(raw_val, list):
            actual_value = ", ".join(str(x.get("value") if isinstance(x, dict) else x) for x in raw_val)
        else:
            actual_value = raw_val if raw_val is not None else ""
            
    actual_value_str = str(actual_value).strip().lower() if actual_value is not None else ""
    expected_value_str = str(expected_value).strip().lower() if expected_value is not None else ""
    
    if operator in ("is_empty", "empty"):
        return actual_value is None or actual_value_str == ""
    elif operator in ("is_not_empty", "not_empty"):
        return actual_value is not None and actual_value_str != ""

    def try_float(val):
        if val is None:
            return None
        try:
            s = str(val).strip()
            if not s:
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

    actual_num = try_float(actual_value)
    expected_num = try_float(expected_value)

    if operator in ("greater_than", "gt", ">"):
        if actual_num is not None and expected_num is not None:
            return actual_num > expected_num
        return False
    elif operator in ("less_than", "lt", "<"):
        if actual_num is not None and expected_num is not None:
            return actual_num < expected_num
        return False
    elif operator in ("greater_than_or_equal", "gte", ">="):
        if actual_num is not None and expected_num is not None:
            return actual_num >= expected_num
        return False
    elif operator in ("less_than_or_equal", "lte", "<="):
        if actual_num is not None and expected_num is not None:
            return actual_num <= expected_num
        return False
    elif operator in ("equals", "=="):
        if actual_num is not None and expected_num is not None:
            return actual_num == expected_num
        return actual_value_str == expected_value_str
    elif operator in ("not_equals", "!="):
        if actual_num is not None and expected_num is not None:
            return actual_num != expected_num
        return actual_value_str != expected_value_str
    elif operator == "contains":
        return expected_value_str in actual_value_str
    elif operator == "not_contains":
        return expected_value_str not in actual_value_str
        
    return False

def get_next_revision_str(rev_str):
    if not rev_str:
        return "A"
    rev = str(rev_str).strip().upper()
    if not rev or not rev.isalpha():
        return "A"
    chars = list(rev)
    i = len(chars) - 1
    while i >= 0:
        if chars[i] == 'Z':
            chars[i] = 'A'
            i -= 1
        else:
            chars[i] = chr(ord(chars[i]) + 1)
            return "".join(chars)
    return "A" + "".join(chars)

class ProblemScanner:
    def __init__(self):
        self.status = "pending"  # "pending", "running", "completed", "failed"
        self.problems = {}  # part_id -> list of problem strings
        self._lock = threading.Lock()
        self.definitions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "problem_definitions.json")

    def load_definitions(self):
        try:
            if os.path.exists(self.definitions_path):
                with open(self.definitions_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading problem definitions: {e}")
        return []

    def save_definitions(self, definitions):
        try:
            with open(self.definitions_path, "w", encoding="utf-8") as f:
                json.dump(definitions, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving problem definitions: {e}")
            return False

    def start_scan(self, client):
        with self._lock:
            if self.status == "running":
                return
            self.status = "running"
            
        def run():
            try:
                # Simulate a delay
                time.sleep(5)
                
                definitions = self.load_definitions()
                
                # Fetch fresh data
                bom_rows = client._get_all_rows(client.table_bom)
                assembly_rows = client._get_all_rows(client.table_assembly)
                instruction_rows = client._get_all_rows(client.table_instructions)
                
                bom_map = {r["id"]: r for r in bom_rows}

                # Identify child IDs and parent IDs in Assembly
                child_ids = set()
                parent_ids = set()
                parent_to_children = {}
                for edge in assembly_rows:
                    child_link = edge.get("Contains")
                    parent_link = edge.get("Item")
                    cid = None
                    pid_val = None
                    if child_link:
                        if isinstance(child_link, list) and len(child_link) > 0:
                            c = child_link[0]
                            cid = c["id"] if isinstance(c, dict) else c
                        elif isinstance(child_link, dict):
                            cid = child_link["id"]
                        elif isinstance(child_link, (int, str)):
                            cid = child_link
                        if cid:
                            child_ids.add(cid)
                    if parent_link:
                        if isinstance(parent_link, list) and len(parent_link) > 0:
                            p = parent_link[0]
                            pid_val = p["id"] if isinstance(p, dict) else p
                        elif isinstance(parent_link, dict):
                            pid_val = parent_link["id"]
                        elif isinstance(parent_link, (int, str)):
                            pid_val = parent_link
                        if pid_val:
                            parent_ids.add(pid_val)
                    if pid_val and cid:
                        q = edge.get("Amount of Times")
                        qty = int(q) if (q is not None and q != "") else 1
                        if pid_val not in parent_to_children:
                            parent_to_children[pid_val] = []
                        parent_to_children[pid_val].append({"child_id": cid, "quantity": qty, "edge_id": edge.get("id")})

                # Group instruction steps by parent and set_index
                parent_to_instruction_sets = {}
                items_with_instructions = set()
                for row_inst in instruction_rows:
                    p_link = row_inst.get("Parent Item")
                    if p_link and isinstance(p_link, list) and len(p_link) > 0:
                        p_val = p_link[0]
                        p_id = p_val["id"] if isinstance(p_val, dict) else p_val
                        if p_id:
                            items_with_instructions.add(p_id)
                            s_idx = row_inst.get("Set Index") or 1
                            try:
                                s_idx = int(s_idx)
                            except (ValueError, TypeError):
                                s_idx = 1
                            if p_id not in parent_to_instruction_sets:
                                parent_to_instruction_sets[p_id] = {}
                            if s_idx not in parent_to_instruction_sets[p_id]:
                                parent_to_instruction_sets[p_id][s_idx] = []
                            parent_to_instruction_sets[p_id][s_idx].append(row_inst)

                new_problems = {}
                for row in bom_rows:
                    pid = row["id"]
                    row_problems = []
                    is_in_assembly = pid in child_ids
                    has_children = pid in parent_ids

                    sets_dict = parent_to_instruction_sets.get(pid, {})
                    num_sets = len(sets_dict)

                    if num_sets == 0:
                        # True by default if no instruction sets exist
                        bom_equilibrium = True
                        has_all_images = True
                    else:
                        # Calculate required totals for parent item
                        required_totals = {}
                        def traverse(current_id, current_multiplier, visited):
                            if current_id in visited:
                                return
                            rels = parent_to_children.get(current_id, [])
                            for rel in rels:
                                cid = rel["child_id"]
                                qty = rel["quantity"] * current_multiplier
                                child_part = bom_map.get(cid, {})
                                is_blackbox = bool(child_part.get("Blackbox", False))
                                has_inst = cid in items_with_instructions
                                child_has_children = bool(parent_to_children.get(cid))
                                if child_has_children and not is_blackbox and not has_inst:
                                    traverse(cid, qty, visited | {current_id})
                                else:
                                    required_totals[cid] = required_totals.get(cid, 0) + qty

                        traverse(pid, 1, set())

                        # When 1 or more sets exist, perform OR evaluation across sets
                        has_all_images = False
                        bom_equilibrium = False

                        for s_idx, set_steps in sets_dict.items():
                            # 1) Photos check for this set: at least 1 image per step
                            set_images_ok = bool(set_steps) and all(
                                bool(s.get("Photo")) and len(s.get("Photo")) > 0
                                for s in set_steps
                            )
                            if set_images_ok:
                                has_all_images = True

                            # 2) Equilibrium check for this set
                            instructed_totals = {}
                            for s in set_steps:
                                toll_map_str = s.get("Toll Map")
                                parsed_successfully = False
                                if toll_map_str:
                                    try:
                                        data = json.loads(toll_map_str)
                                        if isinstance(data, list):
                                            for slot in data:
                                                c_id = slot.get("id")
                                                if c_id and slot.get("toll", True):
                                                    try:
                                                        q_num = float(slot.get("quantity", 1))
                                                    except (ValueError, TypeError):
                                                        q_num = 1.0
                                                    instructed_totals[c_id] = instructed_totals.get(c_id, 0) + q_num
                                            parsed_successfully = True
                                        elif isinstance(data, dict):
                                            for c_id, entry in data.items():
                                                if str(c_id).isdigit():
                                                    c_id_int = int(c_id)
                                                    is_tolled = True
                                                    q = 1.0
                                                    if isinstance(entry, dict):
                                                        is_tolled = entry.get("toll", True)
                                                        try:
                                                            q = float(entry.get("qty", 1))
                                                        except (ValueError, TypeError):
                                                            q = 1.0
                                                    else:
                                                        is_tolled = bool(entry)
                                                    if is_tolled:
                                                        instructed_totals[c_id_int] = instructed_totals.get(c_id_int, 0) + q
                                            parsed_successfully = True
                                    except Exception:
                                        pass

                                if not parsed_successfully:
                                    child = s.get("Child Item")
                                    if child and isinstance(child, list):
                                        qty_fallback = s.get("Quantity") or 1
                                        try:
                                            qty_fallback = int(qty_fallback)
                                        except (ValueError, TypeError):
                                            qty_fallback = 1
                                        is_tolled = s.get("Toll") if s.get("Toll") is not None else True
                                        if is_tolled:
                                            for c_ref in child:
                                                c_id = c_ref.get("id")
                                                if c_id:
                                                    instructed_totals[c_id] = instructed_totals.get(c_id, 0) + qty_fallback

                            if required_totals == instructed_totals:
                                bom_equilibrium = True
                    
                    for definition in definitions:
                        rule = definition.get("rule")
                        if rule:
                            if evaluate_condition(
                                row,
                                rule,
                                is_in_assembly=is_in_assembly,
                                has_children=has_children,
                                bom_equilibrium=bom_equilibrium,
                                has_all_images=has_all_images
                            ):
                                row_problems.append(definition.get("name", "Unknown Problem"))
                                
                    new_problems[pid] = row_problems
                    
                with self._lock:
                    self.problems = new_problems
                    self.status = "completed"
            except Exception as e:
                print(f"Error during scan: {e}")
                with self._lock:
                    self.status = "failed"
                    
        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def reset(self):
        with self._lock:
            self.status = "pending"
            self.problems = {}

    def get_problem_count(self, definition_id):
        definitions = self.load_definitions()
        definition = next((d for d in definitions if d.get("id") == definition_id), None)
        if not definition:
            return None, "not_found"
            
        with self._lock:
            status = self.status
            problems_cache = self.problems
            
        if status == "running" or status == "pending":
            return None, status
            
        name = definition.get("name")
        count = 0
        for p_list in problems_cache.values():
            if name in p_list:
                count += 1
        return count, "completed"


def parse_toll_map(toll_map_str):
    """
    Parses a Toll Map JSON string into the canonical new list format:
    [{"edge_id": int|None, "item_id": int, "toll": bool, "qty": float, "length": float}]
    
    Handles all three formats: new list (with item_id key), old list (with id key), old dict.
    Returns empty list if parsing fails or input is empty/None.
    """
    if not toll_map_str:
        return []
    try:
        import json
        data = json.loads(toll_map_str)
        if isinstance(data, list):
            result = []
            for slot in data:
                if "item_id" in slot:
                    # New format or partially new format
                    item_id = int(slot["item_id"])
                    edge_id = slot.get("edge_id")
                    if edge_id is not None:
                        edge_id = int(edge_id)
                    qty = float(slot.get("qty", slot.get("quantity", 1)))
                    length = float(slot.get("length", 0))
                    toll = slot.get("toll", True)
                    result.append({"edge_id": edge_id, "item_id": item_id, "toll": toll, "qty": qty, "length": length})
                elif "id" in slot:
                    # Old list format
                    item_id = int(slot["id"])
                    qty = float(slot.get("quantity", 1))
                    toll = slot.get("toll", True)
                    result.append({"edge_id": None, "item_id": item_id, "toll": toll, "qty": qty, "length": 0})
            return result
        elif isinstance(data, dict):
            # Old dict format
            result = []
            for k, v in data.items():
                if not str(k).isdigit():
                    continue
                item_id = int(k)
                if isinstance(v, dict):
                    qty = float(v.get("qty", v.get("quantity", 1)))
                    toll = v.get("toll", True)
                else:
                    qty = 1.0
                    toll = bool(v)
                result.append({"edge_id": None, "item_id": item_id, "toll": toll, "qty": qty, "length": 0})
            return result
    except Exception as e:
        print(f"Error parsing Toll Map: {e}")
    return []


def serialize_toll_map(entries):
    """Serializes the canonical list to JSON string for storage."""
    import json
    return json.dumps(entries)


def format_relation_amount(q_val, l_val, uom_symbol):
    """
    Formats the relation amount label according to quantity, measurement, and unit symbol.
    Examples:
      q=1, l=10, uom='cm' -> '1 x 10cm'
      q=5, l=100.2, uom='mm' -> '5 x 100.2mm'
      q=2, l=0, uom='pcs' -> '2 pcs'
      q=1, l=0 -> '1 pcs'
    """
    try:
        q_num = float(q_val) if q_val is not None and str(q_val).strip() != "" else None
    except (ValueError, TypeError):
        q_num = None

    try:
        l_num = float(l_val) if l_val is not None and str(l_val).strip() != "" else 0
    except (ValueError, TypeError):
        l_num = 0

    if l_num > 0:
        sym = uom_symbol if (uom_symbol and uom_symbol != "pcs") else "mm"
        if q_num is not None and q_num >= 1:
            return f"{int(q_num)} x {l_num:g}{sym}"
        else:
            return f"{l_num:g}{sym}"
    else:
        qty_int = int(q_num) if (q_num is not None and q_num >= 1) else 1
        sym = uom_symbol if (uom_symbol and uom_symbol not in ["mm", "cm", "m", "ml", "L", "gal"]) else "pcs"
        return f"{qty_int} {sym}"


class BaserowClient:
    def __init__(self):
        self.api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070")
        self.token = os.getenv("BASEROW_TOKEN", "C2nLVGVxMf8Fb53S8fUi72XQIbCSII7L")
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        # Auto-discover table IDs if any are not configured in environment
        env_vars = [
            "BASEROW_TABLE_BOM", "BASEROW_TABLE_ASSEMBLY", "BASEROW_TABLE_INSTRUCTIONS",
            "BASEROW_TABLE_PN_CATEGORIES", "BASEROW_TABLE_ITEM_STATES", "BASEROW_TABLE_WI_TEMPLATES",
            "BASEROW_TABLE_MANUFACTURERS", "BASEROW_TABLE_SUPPLIERS", "BASEROW_TABLE_CONTACTS"
        ]
        if any(os.getenv(var) is None for var in env_vars):
            try:
                from app.baserow_init import discover_baserow_tables, update_env_files
                discovered = discover_baserow_tables(self.api_url, self.token)
                if discovered:
                    update_env_files(discovered)
                    for k, v in discovered.items():
                        if k not in os.environ:
                            os.environ[k] = str(v)
            except Exception as e:
                logger.debug(f"Auto-discovery during BaserowClient init: {e}")

        self.table_bom = os.getenv("BASEROW_TABLE_BOM", "508")
        self.table_assembly = os.getenv("BASEROW_TABLE_ASSEMBLY", "701")
        self.table_instructions = os.getenv("BASEROW_TABLE_INSTRUCTIONS", "5770")
        self.table_pn_categories = os.getenv("BASEROW_TABLE_PN_CATEGORIES", "42471")
        self.table_item_states = os.getenv("BASEROW_TABLE_ITEM_STATES", "48537")
        self.table_wi_templates = os.getenv("BASEROW_TABLE_WI_TEMPLATES", "48538")
        self.table_manufacturers = os.getenv("BASEROW_TABLE_MANUFACTURERS", "683")
        self.table_suppliers = os.getenv("BASEROW_TABLE_SUPPLIERS", "682")
        self.table_contacts = os.getenv("BASEROW_TABLE_CONTACTS", "684")
        self.table_uom = os.getenv("BASEROW_TABLE_UOM", "48540")
        self.scanner = ProblemScanner()
        self.rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "category_rules.json")
        self.templates_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quick_action_templates.json")
        self.rules = self._get_default_rules()
        self.states_map = self._get_default_states()
        self.states_loaded = False
        self.cached_uoms = None

    def reload_config(self):
        from dotenv import load_dotenv
        from app.baserow_init import find_env_files
        load_dotenv()
        for env_p in find_env_files():
            if os.path.exists(env_p):
                load_dotenv(env_p, override=True)
        self.api_url = os.getenv("BASEROW_API_URL", "http://localhost:7070").rstrip("/")
        self.token = os.getenv("BASEROW_TOKEN", "")
        self.headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/json"
        }
        self.table_bom = os.getenv("BASEROW_TABLE_BOM", "508")
        self.table_assembly = os.getenv("BASEROW_TABLE_ASSEMBLY", "701")
        self.table_instructions = os.getenv("BASEROW_TABLE_INSTRUCTIONS", "5770")
        self.table_pn_categories = os.getenv("BASEROW_TABLE_PN_CATEGORIES", "42471")
        self.table_item_states = os.getenv("BASEROW_TABLE_ITEM_STATES", "48537")
        self.table_wi_templates = os.getenv("BASEROW_TABLE_WI_TEMPLATES", "48538")
        self.table_manufacturers = os.getenv("BASEROW_TABLE_MANUFACTURERS", "683")
        self.table_suppliers = os.getenv("BASEROW_TABLE_SUPPLIERS", "682")
        self.table_contacts = os.getenv("BASEROW_TABLE_CONTACTS", "684")
        self.table_uom = os.getenv("BASEROW_TABLE_UOM", "48540")

    def load_templates(self):
        if os.path.exists(self.templates_path):
            try:
                with open(self.templates_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading templates: {e}")
        # Default templates using the new {a.1}, {a.2}, {t.1}, and {action} notation
        return [
            {"action": "Solder", "template": "{action} {a.1} onto {a.2} using {t.1}"},
            {"action": "Fasten", "template": "{action} {a.1} to {a.2} using {t.1}"},
            {"action": "Mount", "template": "{action} {a.1} onto {a.2}"},
            {"action": "Glue", "template": "{action} {a.1} to {a.2} with {t.1}"},
            {"action": "Inspect", "template": "{action} {a.1} on {a.2}"}
        ]

    def save_templates(self, templates):
        try:
            with open(self.templates_path, "w", encoding="utf-8") as f:
                json.dump(templates, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving templates: {e}")
            return False

    def _get_default_rules(self):
        try:
            if os.path.exists(self.rules_path):
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading fallback rules: {e}")
        return {
            "10": {"name": "Raw Material", "color": "#ff0000"},
            "20": {"name": "Mechanical COTS", "color": "#3b82f6"},
            "30": {"name": "Mechanical Custom", "color": "#8b5cf6"},
            "40": {"name": "Electrical COTS", "color": "#06b6d4"},
            "50": {"name": "Electrical Custom", "color": "#ec4899"},
            "55": {"name": "Assemblies & Kits", "color": "#ff0000"},
            "60": {"name": "Software", "color": "#00ff80"},
            "70": {"name": "Packaging & Labeling", "color": "#84cc16"},
            "80": {"name": "Products", "color": "#ef4444"},
            "90": {"name": "Tooling & Fixtures", "color": "#d946ef"},
            "99": {"name": "Prototype", "color": "#f97316"}
        }

    def load_rules(self):
        url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/?user_field_names=true&size=200"
        try:
            response = self._request("GET", url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                rules = {}
                for row in data.get("results", []):
                    prefix = str(row.get("Prefix", "")).strip()
                    if prefix:
                        rules[prefix] = {
                            "id": row.get("id"),
                            "name": row.get("Name", "Unknown"),
                            "color": row.get("Color", "#8e9095")
                        }
                if rules:
                    self.rules = rules
                    return rules
        except Exception as e:
            print(f"Error loading rules from Baserow: {e}")

        return self.rules

    def _get_default_states(self):
        return {
            "Production Use": {"id": None, "name": "Production Use", "color": "#00FF00"},
            "Engineerig Use": {"id": None, "name": "Engineerig Use", "color": "hsl(210, 75%, 50%)"},
            "Unknown": {"id": None, "name": "Unknown", "color": "hsl(0, 0%, 60%)"},
            "Finish Stock (Use Up)": {"id": None, "name": "Finish Stock (Use Up)", "color": "hsl(38, 95%, 50%)"},
            "EOL": {"id": None, "name": "EOL", "color": "hsl(25, 75%, 45%)"},
            "Do Not Use (Discard)": {"id": None, "name": "Do Not Use (Discard)", "color": "hsl(355, 80%, 50%)"}
        }

    def load_states(self):
        url = f"{self.api_url}/api/database/rows/table/{self.table_item_states}/?user_field_names=true&size=100"
        try:
            response = self._request("GET", url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                states = {}
                for row in data.get("results", []):
                    name = str(row.get("Name", "")).strip()
                    if name:
                        states[name] = {
                            "id": row.get("id"),
                            "name": name,
                            "color": row.get("Color", "#8e9095")
                        }
                if states:
                    self.states_map = states
                    return states
        except Exception as e:
            print(f"Error loading states from Baserow: {e}")
        return self.states_map

    def get_state_id(self, state_name):
        state_info = self.states_map.get(state_name)
        if state_info and state_info.get("id"):
            return [state_info["id"]]
        return []

    def save_rules(self, rules):
        try:
            existing_rules = self.load_rules()
            prefix_to_id = {}
            if isinstance(existing_rules, dict):
                for prefix, data in existing_rules.items():
                    if isinstance(data, dict) and "id" in data:
                        prefix_to_id[str(prefix)] = data["id"]

            for prefix, cat_data in rules.items():
                name = cat_data.get("name", "") if isinstance(cat_data, dict) else str(cat_data)
                color = cat_data.get("color", "#8e9095") if isinstance(cat_data, dict) else "#8e9095"
                str_prefix = str(prefix)
                payload = {"Prefix": str_prefix, "Name": name, "Color": color}

                if str_prefix in prefix_to_id:
                    row_id = prefix_to_id[str_prefix]
                    url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/{row_id}/?user_field_names=true"
                    self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
                else:
                    url = f"{self.api_url}/api/database/rows/table/{self.table_pn_categories}/?user_field_names=true"
                    self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        except Exception as e:
            print(f"Error saving rules to Baserow: {e}")

        self.rules = rules
        return True

    def get_pn_tag(self, part_number, item_data=None):
        if item_data and isinstance(item_data.get("PN Category"), list) and item_data["PN Category"]:
            cat_item = item_data["PN Category"][0]
            if isinstance(cat_item, dict):
                cat_id = cat_item.get("id")
                cat_value = cat_item.get("value", "")
                for prefix_code, rule in self.rules.items():
                    if isinstance(rule, dict) and (rule.get("id") == cat_id or rule.get("name") == cat_value):
                        return {
                            "name": rule.get("name", cat_value or "Unknown"),
                            "color": rule.get("color", "#8e9095")
                        }
                if cat_value:
                    return {"name": cat_value, "color": "#8e9095"}

        if not part_number:
            return {"name": "Unknown", "color": "#8e9095"}
        
        prefix = part_number[:2]
        rule = self.rules.get(prefix)
        if isinstance(rule, dict):
            return {
                "name": rule.get("name", "Unknown"),
                "color": rule.get("color", "#8e9095")
            }
        return {"name": "Unknown", "color": "#8e9095"}

    def _request(self, method, url, retries=4, backoff_factor=0.3, **kwargs):
        """Sends an HTTP request with automatic retries on 502, 503, 504, 429, and connection errors."""
        import time
        last_exception = None
        func = getattr(requests, method.lower())
        for attempt in range(retries + 1):
            try:
                response = func(url, **kwargs)
                if getattr(response, "status_code", None) in (429, 500, 502, 503, 504) and attempt < retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    time.sleep(sleep_time)
                    continue
                return response
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                last_exception = e
                if attempt < retries:
                    sleep_time = backoff_factor * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
                    raise e
        if last_exception:
            raise last_exception
        return response

    def get_uoms(self):
        if self.cached_uoms is not None:
            return self.cached_uoms
        uoms = self._get_all_rows(self.table_uom)
        self.cached_uoms = uoms
        return uoms

    def get_uom_symbol(self, uom_id_or_val):
        if not uom_id_or_val:
            return ""
        try:
            uoms = self.get_uoms()
            for u in uoms:
                if u.get("id") == uom_id_or_val or u.get("Name") == uom_id_or_val:
                    return u.get("Symbol") or u.get("Name") or ""
        except Exception:
            pass
        lookup = {
            "Piece": "pcs", "Millimeter": "mm", "Centimeter": "cm", "Meter": "m",
            "Milliliter": "ml", "Liter": "L", "Gallon": "gal",
            "pcs": "pcs", "mm": "mm", "cm": "cm", "m": "m", "ml": "ml", "L": "L", "gal": "gal",
            3: "pcs", 4: "mm", 5: "cm", 6: "m", 7: "ml", 8: "L", 9: "gal"
        }
        return lookup.get(uom_id_or_val, str(uom_id_or_val))

    def get_uom_multiplier(self, uom_id_or_val):
        """Returns the float multiplier for a given UoM (defaults to 1.0)."""
        if not uom_id_or_val:
            return 1.0
        uoms = self.get_uoms()
        for u in uoms:
            if u.get("id") == uom_id_or_val or u.get("value") == uom_id_or_val or u.get("Name") == uom_id_or_val:
                try:
                    return float(u.get("Multiplier to Base", 1.0))
                except (ValueError, TypeError):
                    return 1.0
        return 1.0

    def _get_all_rows(self, table_id, filters=None):
        """Helper to fetch all rows handling pagination."""
        url = f"{self.api_url}/api/database/rows/table/{table_id}/"
        params = {"user_field_names": "true", "size": 200}  # Baserow max page size
        if filters:
            params.update(filters)

        results = []
        next_url = url
        first_call = True

        while next_url:
            if first_call:
                response = self._request("GET", next_url, headers=self.headers, params=params, timeout=15)
                first_call = False
            else:
                response = self._request("GET", next_url, headers=self.headers, timeout=15)
            
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("results", []))
            next_url = data.get("next")
            
        return results

    def _get_assembly_rows_for_item(self, item_id):
        """Fetches only the assembly rows where item_id is a parent OR child.
        Uses two parallel filtered Baserow requests instead of fetching the full table."""
        base_url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/"
        as_parent_params = {
            "user_field_names": "true",
            "size": 200,
            "filter__Item__link_row_has": item_id
        }
        as_child_params = {
            "user_field_names": "true",
            "size": 200,
            "filter__Contains__link_row_has": item_id
        }

        def fetch(params):
            rows = []
            next_url = base_url
            first = True
            while next_url:
                if first:
                    resp = self._request("GET", next_url, headers=self.headers, params=params, timeout=15)
                    first = False
                else:
                    resp = self._request("GET", next_url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                rows.extend(data.get("results", []))
                next_url = data.get("next")
            return rows

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_parent = executor.submit(fetch, as_parent_params)
            fut_child = executor.submit(fetch, as_child_params)
            parent_edges = fut_parent.result()
            child_edges = fut_child.result()

        # Merge and deduplicate by edge id
        seen = set()
        merged = []
        for edge in parent_edges + child_edges:
            if edge["id"] not in seen:
                seen.add(edge["id"])
                merged.append(edge)
        return merged

    def get_top_level_items(self, state=None, offset=0, limit=50):
        """
        Return paginated top-level BOM items (root nodes — not a child of any assembly),
        optionally filtered by state. Also returns the total matching count.

        :param state: Optional state string to filter on (e.g. "Production Use").
        :param offset: Zero-based index of the first item to return.
        :param limit: Maximum number of items to return.
        :returns: dict { "total": int, "items": [ node_dict, ... ] }
        """
        # Fetch BOM and Assembly tables concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_assembly = executor.submit(self._get_all_rows, self.table_assembly)
            bom_rows = fut_bom.result()
            assembly_rows = fut_assembly.result()

        # Determine which item ids appear as children
        child_ids = set()
        parent_ids = set()
        for edge in assembly_rows:
            child_link = edge.get("Contains")
            parent_link = edge.get("Item")
            if child_link:
                child_ids.add(child_link[0]["id"])
            if parent_link:
                parent_ids.add(parent_link[0]["id"])

        def extract_state(row):
            raw_state = row.get("State")
            if not raw_state:
                return "Unknown"
            if isinstance(raw_state, list) and len(raw_state) > 0:
                return raw_state[0].get("value", "Unknown") if isinstance(raw_state[0], dict) else str(raw_state[0])
            if isinstance(raw_state, dict):
                return raw_state.get("value", "Unknown")
            return str(raw_state)

        # Collect qualifying root nodes
        matching = []
        for row in bom_rows:
            row_id = row["id"]
            if row_id in child_ids:
                continue  # not a root node
            row_state = extract_state(row)
            if state and row_state != state:
                continue
            matching.append({
                "id": row_id,
                "part_number": row.get("Part Number", ""),
                "revision": row.get("Revision", ""),
                "description": row.get("Item description") or row.get("Description", ""),
                "search_helper": row.get("Search helper") or row.get("Search Helper", ""),
                "external_pn": row.get("External PN") or row.get("External Part Number", ""),
                "notes": row.get("Notes", ""),
                "state": row_state,
                "pn_tag": self.get_pn_tag(row.get("Part Number")),
                "has_children": row_id in parent_ids,
                "has_parents": False,   # by definition — these are root nodes
                "quantity_label": "Root",
                "pcb_symbol": "N/A",
                "children": [],
                "problems_count": len(self.scanner.problems.get(row_id, [])) if self.scanner.status == "completed" else None
            })

        # Sort by id for stable pagination
        matching.sort(key=lambda x: x["id"])
        total = len(matching)
        page = matching[offset: offset + limit]
        return {"total": total, "items": page}

    def get_bom_tree(self):
        """
        Fetch BOM and Assembly tables in parallel, and build a nested tree structure.
        """
        # Trigger background scanner if pending
        if self.scanner.status == "pending":
            self.scanner.start_scan(self)

        # Fetch BOM and Assembly tables concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_assembly = executor.submit(self._get_all_rows, self.table_assembly)
            bom_rows = fut_bom.result()
            assembly_rows = fut_assembly.result()

        bom_map = {row["id"]: row for row in bom_rows}

        parent_to_children = {}
        child_ids = set()

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not parent_link or not child_link:
                continue

            parent_id = parent_link[0]["id"]
            child_id = child_link[0]["id"]

            child_ids.add(child_id)

            quantity = edge.get("Amount of Times")
            length = edge.get("Measurement")
            pcb_symbol = edge.get("PCB Symbol")
            uom_raw = edge.get("Measurement UoM", [])
            uom_id = uom_raw[0].get("id") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else None
            uom_val = uom_raw[0].get("value") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else ""

            rel = {
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "pcb_symbol": pcb_symbol,
                "uom_id": uom_id,
                "uom": uom_val,
                "id": edge["id"]
            }

            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(rel)

        top_level_ids = [pid for pid in bom_map.keys() if pid not in child_ids]

        def build_branch(part_id, visited):
            part = bom_map.get(part_id)
            if not part:
                return None

            if part_id in visited:
                return {
                    "id": part_id,
                    "part_number": part.get("Part Number", "Unknown"),
                    "revision": part.get("Revision", ""),
                    "description": part.get("Item description") or part.get("Description", "Circular Reference Detected"),
                    "search_helper": part.get("Search helper") or part.get("Search Helper", ""),
                    "quantity_label": "Err",
                    "problems_count": None,
                    "children": [],
                    "is_circular": True
                }

            children = []
            relations = parent_to_children.get(part_id, [])
            for rel in relations:
                child_branch = build_branch(rel["child_id"], visited | {part_id})
                if child_branch:
                    q = rel["quantity"]
                    l = rel["length"]
                    u_id = rel.get("uom_id")
                    u_val = rel.get("uom")

                    qty = int(q) if (q is not None and str(q).strip() != "") else 1
                    try:
                        length = float(l) if (l is not None and str(l).strip() != "") else 0
                    except (ValueError, TypeError):
                        length = 0

                    child_part = bom_map.get(rel["child_id"])
                    if not u_id and not u_val and child_part:
                        child_con = child_part.get("Consumption UoM", [])
                        child_pur = child_part.get("Purchase UoM", [])
                        if isinstance(child_con, list) and len(child_con) > 0:
                            u_id = child_con[0].get("id")
                            u_val = child_con[0].get("value")
                        elif isinstance(child_pur, list) and len(child_pur) > 0:
                            u_id = child_pur[0].get("id")
                            u_val = child_pur[0].get("value")

                    uom_sym = self.get_uom_symbol(u_id or u_val)
                    mult = self.get_uom_multiplier(u_id or u_val)
                    
                    display_length = length / mult if mult != 0 else length
                    q_label = format_relation_amount(qty, display_length, uom_sym)

                    child_branch["quantity_label"] = q_label
                    child_branch["pcb_symbol"] = rel["pcb_symbol"]
                    child_branch["edge_id"] = rel["id"]
                    child_branch["quantity"] = qty
                    child_branch["length"] = length
                    child_branch["uom_id"] = u_id
                    child_branch["uom"] = uom_sym or u_val
                    child_branch["parent_id"] = part_id
                    children.append(child_branch)

            problems_count = None
            if self.scanner.status == "completed":
                problems_count = len(self.scanner.problems.get(part_id, []))

            state_val = "Unknown"
            raw_state = part.get("State")
            if raw_state:
                if isinstance(raw_state, list) and len(raw_state) > 0:
                    state_val = raw_state[0].get("value", "Unknown") if isinstance(raw_state[0], dict) else str(raw_state[0])
                elif isinstance(raw_state, dict):
                    state_val = raw_state.get("value", "Unknown")
                else:
                    state_val = str(raw_state)
            return {
                "id": part_id,
                "part_number": part.get("Part Number", ""),
                "revision": part.get("Revision", ""),
                "description": part.get("Item description") or part.get("Description", ""),
                "search_helper": part.get("Search helper") or part.get("Search Helper", ""),
                "external_pn": part.get("External PN") or part.get("External Part Number", ""),
                "notes": part.get("Notes", ""),
                "state": state_val,
                "problems_count": problems_count,
                "pn_tag": self.get_pn_tag(part.get("Part Number")),
                "children": children
            }

        forest = []
        for tl_id in top_level_ids:
            tree = build_branch(tl_id, set())
            if tree:
                tree["quantity_label"] = "Root"
                tree["pcb_symbol"] = "N/A"
                forest.append(tree)

        forest.sort(key=lambda x: x["id"])
        return forest

    def get_graph_nexus_nodes(self):
        """Fetch all top-level (nexus) BOM nodes — items that are not a child of anything.

        Fetches BOM and Assembly tables in parallel (same pattern as get_bom_tree).
        Returns a list of nexus node dicts sorted by id.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("get_graph_nexus_nodes: fetching BOM and Assembly tables")

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_assembly = executor.submit(self._get_all_rows, self.table_assembly)
            bom_rows = fut_bom.result()
            assembly_rows = fut_assembly.result()

        bom_map = {row["id"]: row for row in bom_rows}

        parent_to_children = {}
        child_ids = set()

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not parent_link or not child_link:
                continue

            parent_id = parent_link[0]["id"]
            child_id = child_link[0]["id"]

            child_ids.add(child_id)

            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(child_id)

        nexus_ids = [pid for pid in bom_map.keys() if pid not in child_ids]

        result = []
        for pid in nexus_ids:
            part = bom_map[pid]
            images = part.get("Image") or []
            image_url = images[0]["url"] if images else None

            state_val = "Unknown"
            raw_state = part.get("State")
            if raw_state:
                if isinstance(raw_state, list) and len(raw_state) > 0:
                    state_val = raw_state[0].get("value", "Unknown") if isinstance(raw_state[0], dict) else str(raw_state[0])
                elif isinstance(raw_state, dict):
                    state_val = raw_state.get("value", "Unknown")
                else:
                    state_val = str(raw_state)

            result.append({
                "id": pid,
                "part_number": part.get("Part Number", ""),
                "description": part.get("Item description", ""),
                "state": state_val,
                "pn_tag": self.get_pn_tag(part.get("Part Number")),
                "image_url": image_url,
                "child_count": len(parent_to_children.get(pid, []))
            })

        result.sort(key=lambda x: x["id"])
        logger.debug("get_graph_nexus_nodes: returning %d nexus nodes", len(result))
        return result

    def get_graph_children(self, item_id):
        """Return all direct children of item_id with edge metadata.

        Fetches BOM and Assembly tables in parallel (same pattern as get_bom_tree).
        Returns a list of child dicts sorted by id.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("get_graph_children: fetching children for item_id=%s", item_id)

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_assembly = executor.submit(self._get_all_rows, self.table_assembly)
            bom_rows = fut_bom.result()
            assembly_rows = fut_assembly.result()

        bom_map = {row["id"]: row for row in bom_rows}

        parent_to_children = {}
        child_edges = []

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not parent_link or not child_link:
                continue

            parent_id = parent_link[0]["id"]
            child_id = child_link[0]["id"]

            if parent_id not in parent_to_children:
                parent_to_children[parent_id] = []
            parent_to_children[parent_id].append(child_id)

            if parent_id == item_id:
                child_edges.append({
                    "child_id": child_id,
                    "edge_id": edge["id"],
                    "quantity": edge.get("Amount of Times"),
                    "length": edge.get("Measurement")
                })

        result = []
        for rel in child_edges:
            cid = rel["child_id"]
            part = bom_map.get(cid)
            if not part:
                continue

            images = part.get("Image") or []
            image_url = images[0]["url"] if images else None

            state_val = "Unknown"
            raw_state = part.get("State")
            if raw_state:
                if isinstance(raw_state, list) and len(raw_state) > 0:
                    state_val = raw_state[0].get("value", "Unknown") if isinstance(raw_state[0], dict) else str(raw_state[0])
                elif isinstance(raw_state, dict):
                    state_val = raw_state.get("value", "Unknown")
                else:
                    state_val = str(raw_state)

            q = rel["quantity"]
            l = rel["length"]
            quantity = int(q) if (q is not None and q != "") else 1
            length = float(l) if (l is not None and l != "") else 0.0

            result.append({
                "id": cid,
                "part_number": part.get("Part Number", ""),
                "description": part.get("Item description", ""),
                "state": state_val,
                "pn_tag": self.get_pn_tag(part.get("Part Number")),
                "image_url": image_url,
                "child_count": len(parent_to_children.get(cid, [])),
                "edge_id": rel["edge_id"],
                "quantity": quantity,
                "length": length
            })

        result.sort(key=lambda x: x["id"])
        logger.debug("get_graph_children: returning %d children for item_id=%s", len(result), item_id)
        return result

    def _ensure_item_category(self, item_id, item):
        """Examines Part Number prefix to fill 'PN Category' if empty/blank."""
        if "PN Category" not in item:
            return item
        pn_category = item.get("PN Category", [])
        if not pn_category:
            pn = item.get("Part Number")
            if pn and "-" in pn:
                prefix = pn.split("-")[0]
                # Force load rules if they are fallback (no id)
                if not any("id" in r for r in self.rules.values() if isinstance(r, dict)):
                    self.load_rules()
                cat_rule = self.rules.get(str(prefix))
                if isinstance(cat_rule, dict) and "id" in cat_rule:
                    cat_id = cat_rule["id"]
                    try:
                        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
                        resp = self._request("PATCH", url, headers=self.headers, json={"PN Category": [cat_id]}, timeout=10)
                        resp.raise_for_status()
                        item["PN Category"] = [{"id": cat_id, "value": prefix}]
                    except Exception as e:
                        pass
        return item

    def get_item(self, item_id):
        """Gets a single item from the BOM table with its parent and child relations.
        Uses parallel, filtered requests so we only fetch the relevant edges and
        the specific BOM rows needed instead of entire tables."""
        item_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"

        # Fetch the item itself and its relevant assembly edges concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_item = executor.submit(
                self._request, "GET", item_url, headers=self.headers, timeout=15
            )
            fut_edges = executor.submit(self._get_assembly_rows_for_item, item_id)
            item_resp = fut_item.result()
            assembly_rows = fut_edges.result()

        item_resp.raise_for_status()
        item = item_resp.json()
        item = self._ensure_item_category(item_id, item)
        item["pn_tag"] = self.get_pn_tag(item.get("Part Number"))
        item["Blackbox"] = bool(item.get("Blackbox", False))
        item["Purchase Kit"] = bool(item.get("Purchase Kit", False))

        problems = []
        if self.scanner.status == "completed":
            problems = self.scanner.problems.get(item_id, [])

        item["problems"] = problems

        # Collect the neighbour BOM IDs we actually need from the filtered edges
        neighbour_ids = set()
        for edge in assembly_rows:
            p = edge.get("Item")
            c = edge.get("Contains")
            if isinstance(p, list) and p:
                neighbour_ids.add(p[0].get("id"))
            if isinstance(c, list) and c:
                neighbour_ids.add(c[0].get("id"))
        neighbour_ids.discard(item_id)  # we already have the item itself

        # Fetch only the needed BOM rows in parallel batches (one per neighbour)
        bom_map = {item_id: item}
        if neighbour_ids:
            def fetch_bom_row(nid):
                url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{nid}/?user_field_names=true"
                resp = self._request("GET", url, headers=self.headers, timeout=15)
                if resp.status_code == 200:
                    return nid, resp.json()
                return nid, None

            with ThreadPoolExecutor(max_workers=min(len(neighbour_ids), 6)) as executor:
                futures = {executor.submit(fetch_bom_row, nid): nid for nid in neighbour_ids}
                for fut in as_completed(futures):
                    nid, row = fut.result()
                    if row:
                        bom_map[nid] = row

        contained_items = []
        containing_items = []

        for edge in assembly_rows:
            parent_link = edge.get("Item")
            child_link = edge.get("Contains")

            if not isinstance(parent_link, list) or len(parent_link) == 0:
                continue
            if not isinstance(child_link, list) or len(child_link) == 0:
                continue

            parent_id = parent_link[0].get("id")
            child_id = child_link[0].get("id")

            if parent_id is None or child_id is None:
                continue

            quantity = edge.get("Amount of Times")
            length = edge.get("Measurement")
            pcb_symbol = edge.get("PCB Symbol")
            uom_raw = edge.get("Measurement UoM", [])
            uom_id = uom_raw[0].get("id") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else None
            uom_val = uom_raw[0].get("value") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else ""

            child_part = bom_map.get(child_id)
            if not uom_id and not uom_val and child_part:
                child_con = child_part.get("Consumption UoM", [])
                child_pur = child_part.get("Purchase UoM", [])
                if isinstance(child_con, list) and len(child_con) > 0:
                    uom_id = child_con[0].get("id")
                    uom_val = child_con[0].get("value")
                elif isinstance(child_pur, list) and len(child_pur) > 0:
                    uom_id = child_pur[0].get("id")
                    uom_val = child_pur[0].get("value")

            uom_sym = self.get_uom_symbol(uom_id or uom_val)
            mult = self.get_uom_multiplier(uom_id or uom_val)
            
            try:
                base_len = float(length) if length is not None else 0
            except (ValueError, TypeError):
                base_len = 0
                
            display_length = base_len / mult if mult != 0 else base_len
            amount_label = format_relation_amount(quantity, display_length, uom_sym)

            rel = {
                "edge_id": edge["id"],
                "parent_id": parent_id,
                "child_id": child_id,
                "quantity": quantity,
                "length": length,
                "pcb_symbol": pcb_symbol,
                "uom_id": uom_id,
                "uom": uom_sym or uom_val,
                "amount_label": amount_label
            }

            if parent_id == item_id:
                child_part = bom_map.get(child_id)
                if child_part:
                    rel.update({
                        "id": child_id,
                        "part_number": child_part.get("Part Number", ""),
                        "description": child_part.get("Item description", ""),
                        "revision": child_part.get("Revision", ""),
                        "Image": child_part.get("Image", []),
                        "Full PN": child_part.get("Full PN", ""),
                        "external_pn": child_part.get("External PN", ""),
                        "price": child_part.get("Price", None)
                    })
                    contained_items.append(rel)

            if child_id == item_id:
                parent_part = bom_map.get(parent_id)
                if parent_part:
                    rel.update({
                        "id": parent_id,
                        "part_number": parent_part.get("Part Number", ""),
                        "description": parent_part.get("Item description", ""),
                        "revision": parent_part.get("Revision", "")
                    })
                    containing_items.append(rel)

        item["contained_items"] = contained_items
        item["containing_items"] = containing_items
        return item

    def get_items(self):
        """Fetch all flat rows from the BOM table."""
        return self._get_all_rows(self.table_bom)

    def search_items(self, query: str, limit: int = 200):
        """Search BOM items using Baserow's native full-text search.
        Returns at most `limit` rows (capped at 200, Baserow's page max).
        Never paginates — one request, fast."""
        capped = min(max(1, limit), 200)
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/"
        params = {
            "user_field_names": "true",
            "size": capped,
            "search": query,
        }
        response = self._request("GET", url, headers=self.headers, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get("results", [])

    def update_item(self, item_id, data):
        """Updates an item in the BOM table."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        payload = dict(data)
        if "State" in payload and isinstance(payload["State"], str):
            state_id = self.get_state_id(payload["State"])
            if state_id:
                payload["State"] = state_id
        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        
        # Reset scanner to trigger re-evaluation of problems in background
        self.scanner.reset()
        return response.json()

    def get_manufacturers(self):
        """Fetch all rows from the Manufacturers table."""
        return self._get_all_rows(self.table_manufacturers)

    def get_manufacturer(self, mfg_id):
        """Fetch a single manufacturer row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_manufacturers}/{mfg_id}/?user_field_names=true"
        response = self._request("GET", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def create_manufacturer(self, data):
        """Create a new manufacturer row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_manufacturers}/?user_field_names=true"
        payload = {}
        if "Name" in data: payload["Name"] = data["Name"]
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Website" in data: payload["Website"] = data["Website"]
        if "Logo" in data: payload["Logo"] = data["Logo"]
        if "Suppliers" in data:
            suppliers = data["Suppliers"]
            payload["Suppliers"] = [s["id"] if isinstance(s, dict) and "id" in s else s for s in suppliers] if isinstance(suppliers, list) else []
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def update_manufacturer(self, mfg_id, data):
        """Update an existing manufacturer row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_manufacturers}/{mfg_id}/?user_field_names=true"
        payload = {}
        if "Name" in data: payload["Name"] = data["Name"]
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Website" in data: payload["Website"] = data["Website"]
        if "Logo" in data: payload["Logo"] = data["Logo"]
        if "Suppliers" in data:
            suppliers = data["Suppliers"]
            payload["Suppliers"] = [s["id"] if isinstance(s, dict) and "id" in s else s for s in suppliers] if isinstance(suppliers, list) else []
        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def delete_manufacturer(self, mfg_id):
        """Delete a manufacturer row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_manufacturers}/{mfg_id}/"
        response = self._request("DELETE", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return True

    def get_suppliers(self):
        """Fetch all rows from the Suppliers table."""
        return self._get_all_rows(self.table_suppliers)

    def get_supplier(self, supplier_id):
        """Fetch a single supplier row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_suppliers}/{supplier_id}/?user_field_names=true"
        response = self._request("GET", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def create_supplier(self, data):
        """Create a new supplier row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_suppliers}/?user_field_names=true"
        payload = {}
        name_val = data.get("Company Name", data.get("name"))
        if name_val is not None: payload["Company Name"] = name_val
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Online Store" in data: payload["Online Store"] = bool(data["Online Store"])
        elif "online_store" in data: payload["Online Store"] = bool(data["online_store"])
        if "URL" in data: payload["URL"] = data["URL"]
        elif "url" in data: payload["URL"] = data["url"]
        if "Logo" in data: payload["Logo"] = data["Logo"]
        if "Imports From" in data or "imports_from" in data:
            mfg_links = data.get("Imports From", data.get("imports_from", []))
            payload["Imports From"] = [m["id"] if isinstance(m, dict) and "id" in m else m for m in mfg_links] if isinstance(mfg_links, list) else []
        if "Contacts" in data or "contacts" in data:
            contact_links = data.get("Contacts", data.get("contacts", []))
            payload["Contacts"] = [c["id"] if isinstance(c, dict) and "id" in c else c for c in contact_links] if isinstance(contact_links, list) else []
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def update_supplier(self, supplier_id, data):
        """Update an existing supplier row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_suppliers}/{supplier_id}/?user_field_names=true"
        payload = {}
        if "Company Name" in data: payload["Company Name"] = data["Company Name"]
        elif "name" in data: payload["Company Name"] = data["name"]
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Online Store" in data: payload["Online Store"] = bool(data["Online Store"])
        elif "online_store" in data: payload["Online Store"] = bool(data["online_store"])
        if "URL" in data: payload["URL"] = data["URL"]
        elif "url" in data: payload["URL"] = data["url"]
        if "Logo" in data: payload["Logo"] = data["Logo"]
        if "Imports From" in data or "imports_from" in data:
            mfg_links = data.get("Imports From", data.get("imports_from", []))
            payload["Imports From"] = [m["id"] if isinstance(m, dict) and "id" in m else m for m in mfg_links] if isinstance(mfg_links, list) else []
        if "Contacts" in data or "contacts" in data:
            contact_links = data.get("Contacts", data.get("contacts", []))
            payload["Contacts"] = [c["id"] if isinstance(c, dict) and "id" in c else c for c in contact_links] if isinstance(contact_links, list) else []
        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def delete_supplier(self, supplier_id):
        """Delete a supplier row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_suppliers}/{supplier_id}/"
        response = self._request("DELETE", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return True

    def get_contacts(self, supplier_id=None):
        """Fetch all rows from the Contacts table (optionally filtered by supplier_id)."""
        contacts = self._get_all_rows(self.table_contacts)
        if supplier_id is not None:
            filtered = []
            target_id = int(supplier_id)
            for c in contacts:
                suppliers = c.get("Suppliers", [])
                if any(s.get("id") == target_id for s in suppliers if isinstance(s, dict)):
                    filtered.append(c)
            return filtered
        return contacts

    def get_contact(self, contact_id):
        """Fetch a single contact row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_contacts}/{contact_id}/?user_field_names=true"
        response = self._request("GET", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    def create_contact(self, data):
        """Create a new contact row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_contacts}/?user_field_names=true"
        payload = {}
        if "Name" in data: payload["Name"] = data["Name"]
        elif "name" in data: payload["Name"] = data["name"]
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Active" in data: payload["Active"] = bool(data["Active"])
        elif "active" in data: payload["Active"] = bool(data["active"])
        if "Email" in data: payload["Email"] = data["Email"]
        elif "email" in data: payload["Email"] = data["email"]
        if "Phone number" in data: payload["Phone number"] = data["Phone number"]
        elif "phone" in data: payload["Phone number"] = data["phone"]
        elif "phone_number" in data: payload["Phone number"] = data["phone_number"]
        if "Suppliers" in data or "suppliers" in data:
            supp_links = data.get("Suppliers", data.get("suppliers", []))
            payload["Suppliers"] = [s["id"] if isinstance(s, dict) and "id" in s else s for s in supp_links] if isinstance(supp_links, list) else []
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def update_contact(self, contact_id, data):
        """Update an existing contact row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_contacts}/{contact_id}/?user_field_names=true"
        payload = {}
        if "Name" in data: payload["Name"] = data["Name"]
        elif "name" in data: payload["Name"] = data["name"]
        if "Notes" in data: payload["Notes"] = data["Notes"]
        if "Active" in data: payload["Active"] = bool(data["Active"])
        elif "active" in data: payload["Active"] = bool(data["active"])
        if "Email" in data: payload["Email"] = data["Email"]
        elif "email" in data: payload["Email"] = data["email"]
        if "Phone number" in data: payload["Phone number"] = data["Phone number"]
        elif "phone" in data: payload["Phone number"] = data["phone"]
        elif "phone_number" in data: payload["Phone number"] = data["phone_number"]
        if "Suppliers" in data or "suppliers" in data:
            supp_links = data.get("Suppliers", data.get("suppliers", []))
            payload["Suppliers"] = [s["id"] if isinstance(s, dict) and "id" in s else s for s in supp_links] if isinstance(supp_links, list) else []
        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()

    def delete_contact(self, contact_id):
        """Delete a contact row."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_contacts}/{contact_id}/"
        response = self._request("DELETE", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return True

    def upload_file(self, filename, content, content_type):
        """Uploads a file to Baserow user-files, normalizing images to PNG format."""
        filename, content, content_type = normalize_uploaded_file(filename, content, content_type)
        url = f"{self.api_url}/api/user-files/upload-file/"
        files = {
            "file": (filename, content, content_type)
        }
        headers = {
            "Authorization": f"Token {self.token}"
        }
        response = self._request("POST", url, headers=headers, files=files, timeout=30)
        response.raise_for_status()
        return response.json()

    def create_assembly(self, parent_id, child_id, quantity=None, length=None, pcb_symbol=None, uom_id=None):
        """Creates a new assembly edge/relation."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/?user_field_names=true"
        payload = {
            "Item": [parent_id],
            "Contains": [child_id],
            "Amount of Times": quantity if quantity is not None else 1,
            "Measurement": length if length is not None else 0,
            "PCB Symbol": pcb_symbol if pcb_symbol is not None else "N/A"
        }
        if uom_id is not None:
            payload["Measurement UoM"] = [uom_id]
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def update_assembly(self, edge_id, quantity=None, length=None, pcb_symbol=None, parent_id=None, child_id=None, uom_id=None):
        """Updates an existing relation edge in the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
        payload = {}
        if quantity is not None: payload["Amount of Times"] = quantity
        if length is not None: payload["Measurement"] = length
        if pcb_symbol is not None: payload["PCB Symbol"] = pcb_symbol
        if parent_id is not None: payload["Item"] = [parent_id]
        if child_id is not None: payload["Contains"] = [child_id]
        if uom_id is not None: payload["Measurement UoM"] = [uom_id]
        elif uom_id == "": payload["Measurement UoM"] = []

        response = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        return response.json()

    def delete_assembly(self, edge_id):
        """Deletes a relation edge from the Assembly table (701)."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/"
        response = self._request("DELETE", url, headers=self.headers, timeout=10)
        response.raise_for_status()
        self.scanner.reset()

    def create_item(self, prefix, description):
        """Generates the next Part Number in category and creates a new BOM row."""
        items = self.get_items()
        
        prefix_dash = f"{prefix}-"
        existing_suffixes = []
        for item in items:
            pn = item.get("Part Number")
            if pn and pn.startswith(prefix_dash):
                suffix = pn[len(prefix_dash):]
                if suffix.isdigit():
                    existing_suffixes.append(int(suffix))
                    
        next_num = 0
        if existing_suffixes:
            next_num = max(existing_suffixes) + 1
            
        new_pn = f"{prefix}-{next_num:05d}"
        
        url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": description if description else f"New Item ({new_pn})",
            "Revision": "A",
        }
        state_id = self.get_state_id("Engineerig Use")
        if state_id:
            payload["State"] = state_id
        else:
            payload["State"] = "Engineerig Use"
        cat_rule = self.rules.get(str(prefix))
        if isinstance(cat_rule, dict) and "id" in cat_rule:
            payload["PN Category"] = [cat_rule["id"]]
        
        try:
            uoms = self.get_uoms()
            piece_uom = next((u for u in uoms if (u.get("Name") or "").strip().lower() == "piece" or (u.get("Symbol") or "").strip().lower() == "pcs"), None)
            if piece_uom:
                payload["Purchase UoM"] = [piece_uom["id"]]
                payload["Consumption UoM"] = [piece_uom["id"]]
        except Exception as e:
            logger.warning(f"Could not set default UoM on item creation: {e}")
        
        response = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        response.raise_for_status()
        self.scanner.reset()
        item = response.json()
        item = self._ensure_item_category(item["id"], item)
        return item

    def duplicate_item(self, source_id, new_prefix, new_description,
                       duplicate_parents=True,
                       duplicate_children=True,
                       duplicate_instructions=True,
                       duplicate_photos=True):
        """Duplicates the item under a new category prefix (generating the next PN),
        including images, children relationships, parent relationships, and instruction sets."""
        # 1. Fetch the source item raw row
        src_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{source_id}/?user_field_names=true"
        resp = self._request("GET", src_url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        src_item = resp.json()

        # 2. Generate the next Part Number in category
        items = self.get_items()
        prefix_dash = f"{new_prefix}-"
        existing_suffixes = []
        for item in items:
            pn = item.get("Part Number")
            if pn and pn.startswith(prefix_dash):
                suffix = pn[len(prefix_dash):]
                if suffix.isdigit():
                    existing_suffixes.append(int(suffix))
                    
        next_num = 0
        if existing_suffixes:
            next_num = max(existing_suffixes) + 1
        new_pn = f"{new_prefix}-{next_num:05d}"

        # 3. Form payload for duplicating the main item
        url_bom = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": new_description if new_description else f"{src_item.get('Item description', '')} - copy",
            "Revision": "A",
            "Notes": src_item.get("Notes", "") or "",
            "Blackbox": bool(src_item.get("Blackbox", False)),
            "Purchase Kit": bool(src_item.get("Purchase Kit", False))
        }

        # Handle External Part Number
        ext_pn = src_item.get("External Part Number") if src_item.get("External Part Number") is not None else src_item.get("External PN")
        if ext_pn is not None:
            payload["External Part Number"] = ext_pn

        # Handle Price per unit and Lot Size
        price_val = src_item.get("Price per unit") if src_item.get("Price per unit") is not None else src_item.get("Price")
        if price_val is not None and str(price_val).strip() != "":
            payload["Price per unit"] = price_val

        lot_size_val = src_item.get("Lot Size")
        if lot_size_val is not None and str(lot_size_val).strip() != "":
            payload["Lot Size"] = lot_size_val

        pur_uom = src_item.get("Purchase UoM", [])
        if pur_uom:
            payload["Purchase UoM"] = [x["id"] if isinstance(x, dict) else x for x in pur_uom if x]

        con_uom = src_item.get("Consumption UoM", [])
        if con_uom:
            payload["Consumption UoM"] = [x["id"] if isinstance(x, dict) else x for x in con_uom if x]

        # Handle Source URL
        source_url = src_item.get("Source URL") if src_item.get("Source URL") is not None else src_item.get("Source Link")
        if source_url is not None:
            payload["Source URL"] = source_url

        # Handle Sourced By
        sourced_by_raw = src_item.get("Sourced By") or src_item.get("Sourced by")
        if sourced_by_raw:
            if isinstance(sourced_by_raw, dict):
                payload["Sourced By"] = sourced_by_raw.get("id") or sourced_by_raw.get("value")
            elif isinstance(sourced_by_raw, list) and len(sourced_by_raw) > 0:
                payload["Sourced By"] = sourced_by_raw[0].get("id") if isinstance(sourced_by_raw[0], dict) else sourced_by_raw[0]
            else:
                payload["Sourced By"] = sourced_by_raw

        # Handle System (single_select)
        system_raw = src_item.get("System")
        if system_raw:
            if isinstance(system_raw, dict):
                payload["System"] = system_raw.get("id") or system_raw.get("value")
            elif isinstance(system_raw, list) and len(system_raw) > 0:
                payload["System"] = system_raw[0].get("id") if isinstance(system_raw[0], dict) else system_raw[0]
            else:
                payload["System"] = system_raw

        # Handle State field link/select
        state_raw = src_item.get("State")
        if state_raw:
            if isinstance(state_raw, list) and len(state_raw) > 0:
                state_entry = state_raw[0]
                state_id = state_entry.get("id") if isinstance(state_entry, dict) else state_entry
                payload["State"] = [state_id]
            elif isinstance(state_raw, dict):
                payload["State"] = [state_raw.get("id")]
            elif isinstance(state_raw, (int, str)):
                if isinstance(state_raw, str):
                    s_id = self.get_state_id(state_raw)
                    payload["State"] = [s_id] if s_id else [state_raw]
                else:
                    payload["State"] = [state_raw]

        # Handle Manufacturer link field
        mfg_raw = src_item.get("Manufacturer")
        if mfg_raw:
            if isinstance(mfg_raw, list):
                payload["Manufacturer"] = [m.get("id") if isinstance(m, dict) else m for m in mfg_raw if m]
            elif isinstance(mfg_raw, dict):
                payload["Manufacturer"] = [mfg_raw.get("id")]
            else:
                payload["Manufacturer"] = [mfg_raw]

        # Handle PN Category rule link
        cat_rule = self.rules.get(str(new_prefix))
        if isinstance(cat_rule, dict) and "id" in cat_rule:
            payload["PN Category"] = [cat_rule["id"]]

        # Handle Images copy (Do NOT copy datasheets!)
        if duplicate_photos and src_item.get("Image"):
            images = src_item["Image"]
            if isinstance(images, list):
                payload["Image"] = [{"name": img["name"]} for img in images if isinstance(img, dict) and "name" in img]
            else:
                payload["Image"] = images

        # Explicitly ensure Datasheet is NEVER copied
        payload.pop("Datasheet", None)

        # Create duplicate item row
        create_resp = self._request("POST", url_bom, headers=self.headers, json=payload, timeout=15)
        create_resp.raise_for_status()
        new_item = create_resp.json()
        new_item_id = new_item["id"]

        # 4. Fetch relationships and instruction steps concurrently if requested
        parent_edges = []
        child_edges = []
        inst_steps = []

        fetch_tasks = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            if duplicate_children:
                fetch_tasks["children"] = executor.submit(self._get_all_rows, self.table_assembly, {"filter__Item__link_row_has": source_id})
            if duplicate_parents:
                fetch_tasks["parents"] = executor.submit(self._get_all_rows, self.table_assembly, {"filter__Contains__link_row_has": source_id})
            if duplicate_instructions:
                fetch_tasks["instructions"] = executor.submit(self._get_all_rows, self.table_instructions, {"filter__Parent Item__link_row_has": source_id})
            
            if "children" in fetch_tasks:
                parent_edges = fetch_tasks["children"].result()
            if "parents" in fetch_tasks:
                child_edges = fetch_tasks["parents"].result()
            if "instructions" in fetch_tasks:
                inst_steps = fetch_tasks["instructions"].result()

        # 5. Populate and run duplicating requests concurrently
        url_assembly = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/?user_field_names=true"
        url_inst = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/?user_field_names=true"
        
        duplicate_payloads = []

        # Duplicate children relations (where duplicated item is Parent)
        for edge in parent_edges:
            child_link = edge.get("Contains")
            child_ids = [c.get("id") if isinstance(c, dict) else c for c in child_link] if child_link else []
            duplicate_payloads.append((
                url_assembly,
                {
                    "Item": [new_item_id],
                    "Contains": child_ids,
                    "Amount of Times": edge.get("Amount of Times"),
                    "Length (mm)": edge.get("Measurement"),
                    "PCB Symbol": edge.get("PCB Symbol")
                }
            ))

        # Duplicate parent relations (where duplicated item is Child)
        for edge in child_edges:
            parent_link = edge.get("Item")
            parent_ids = [p.get("id") if isinstance(p, dict) else p for p in parent_link] if parent_link else []
            duplicate_payloads.append((
                url_assembly,
                {
                    "Item": parent_ids,
                    "Contains": [new_item_id],
                    "Amount of Times": edge.get("Amount of Times"),
                    "Length (mm)": edge.get("Measurement"),
                    "PCB Symbol": edge.get("PCB Symbol")
                }
            ))

        # Duplicate instructions (steps of all sets)
        for step in inst_steps:
            action_rcv_link = step.get("Action Receiving Item")
            rcv_ids = [r.get("id") if isinstance(r, dict) else r for r in action_rcv_link] if action_rcv_link else []
            
            child_link = step.get("Child Item")
            child_ids = [c.get("id") if isinstance(c, dict) else c for c in child_link] if child_link else []
            
            tool_link = step.get("Tool")
            tool_ids = [t.get("id") if isinstance(t, dict) else t for t in tool_link] if tool_link else []
            
            step_payload = {
                "Parent Item": [new_item_id],
                "Set Index": step.get("Set Index"),
                "Step Order": step.get("Step Order"),
                "Action": step.get("Action"),
                "Description": step.get("Description"),
                "Toll Map": step.get("Toll Map"),
                "Tool Map": step.get("Tool Map")
            }
            if rcv_ids:
                step_payload["Action Receiving Item"] = rcv_ids
            if child_ids:
                step_payload["Child Item"] = child_ids
            if tool_ids:
                step_payload["Tool"] = tool_ids
            if step.get("Photo"):
                step_payload["Photo"] = step["Photo"]

            duplicate_payloads.append((url_inst, step_payload))

        # Execute all duplicate POSTs concurrently
        if duplicate_payloads:
            with ThreadPoolExecutor(max_workers=min(len(duplicate_payloads), 8)) as executor:
                futures = [
                    executor.submit(self._request, "POST", url, headers=self.headers, json=payload, timeout=15)
                    for url, payload in duplicate_payloads
                ]
                for fut in as_completed(futures):
                    fut.result()

        self.scanner.reset()
        new_item = self._ensure_item_category(new_item_id, new_item)
        return new_item



    def recategorize_item(self, item_id, new_prefix):
        """
        Duplicates the item under a new category prefix, re-links all assembly
        edges (where this item was parent or child) to the new item, and marks
        the old item as EOL.

        Returns the newly created item dict.
        """
        # 1. Fetch the source item row
        src_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        resp = self._request("GET", src_url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        src_item = resp.json()

        # 2. Determine new PN (next running number for new prefix)
        items = self.get_items()
        prefix_dash = f"{new_prefix}-"
        existing_suffixes = []
        for item in items:
            pn = item.get("Part Number")
            if pn and pn.startswith(prefix_dash):
                suffix = pn[len(prefix_dash):]
                if suffix.isdigit():
                    existing_suffixes.append(int(suffix))
        next_num = (max(existing_suffixes) + 1) if existing_suffixes else 0
        new_pn = f"{new_prefix}-{next_num:05d}"

        # Extract original State
        state_data = src_item.get("State")
        old_state = "Engineerig Use"
        if state_data:
            if isinstance(state_data, list) and len(state_data) > 0:
                old_state = state_data[0].get("value", "Engineerig Use") if isinstance(state_data[0], dict) else str(state_data[0])
            elif isinstance(state_data, dict):
                old_state = state_data.get("value", "Engineerig Use")
            else:
                old_state = str(state_data)

        # 3. Create new item copying fields from source
        create_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        payload = {
            "Part Number": new_pn,
            "Item description": src_item.get("Item description", ""),
            "Revision": src_item.get("Revision", "A"),
            "State": self.get_state_id(old_state) if self.get_state_id(old_state) else old_state,
            "Source URL": src_item.get("Source URL", ""),
            "External Part Number": src_item.get("External Part Number", ""),
            "Notes": src_item.get("Notes", ""),
        }

        cat_rule = self.rules.get(str(new_prefix))
        if isinstance(cat_rule, dict) and "id" in cat_rule:
            payload["PN Category"] = [cat_rule["id"]]

        # Copy manufacturer link if present
        manufacturer_links = src_item.get("Manufacturer", [])
        if manufacturer_links:
            payload["Manufacturer"] = [m["id"] for m in manufacturer_links if "id" in m]

        create_resp = self._request("POST", create_url, headers=self.headers, json=payload, timeout=10)
        create_resp.raise_for_status()
        new_item = create_resp.json()
        new_item_id = new_item["id"]

        # 4. Re-link assembly edges
        assembly_rows = self._get_all_rows(self.table_assembly)
        for edge in assembly_rows:
            parent_link = edge.get("Item") or []
            child_link = edge.get("Contains") or []
            edge_id = edge["id"]
            patch_payload = {}

            if parent_link and parent_link[0].get("id") == item_id:
                patch_payload["Item"] = [new_item_id]
            if child_link and child_link[0].get("id") == item_id:
                patch_payload["Contains"] = [new_item_id]

            if patch_payload:
                patch_url = f"{self.api_url}/api/database/rows/table/{self.table_assembly}/{edge_id}/?user_field_names=true"
                self._request("PATCH", patch_url, headers=self.headers, json=patch_payload, timeout=10).raise_for_status()

        # 5. Mark old item as EOL
        eol_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        eol_state_payload = {"State": self.get_state_id("EOL") if self.get_state_id("EOL") else "EOL"}
        self._request("PATCH", eol_url, headers=self.headers, json=eol_state_payload, timeout=10).raise_for_status()
        
        new_item = self._ensure_item_category(new_item_id, new_item)

        self.scanner.reset()
        return new_item

    def add_revision(self, item_id):
        """
        Creates a new revision of an existing item:
        - Same Part Number
        - Revision incremented (A->B, Z->AA, AZ->BA, etc.)
        - Identical BOM line fields
        - Copies previous revision's children (contained items), but NOT parent relationships.
        - Returns newly created item dict.
        """
        src_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/{item_id}/?user_field_names=true"
        resp = self._request("GET", src_url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        src_item = resp.json()

        pn = src_item.get("Part Number")
        if not pn:
            raise ValueError("Item has no Part Number")

        # Find all existing revisions for this PN
        all_items = self.get_items()
        matching_revs = [
            str(it.get("Revision")).strip().upper()
            for it in all_items
            if it.get("Part Number") == pn and it.get("Revision") and str(it.get("Revision")).strip().isalpha()
        ]

        if not matching_revs:
            src_rev = str(src_item.get("Revision", "")).strip().upper()
            matching_revs = [src_rev] if src_rev and src_rev.isalpha() else ["A"]

        # Sort by length then string to find highest revision
        matching_revs.sort(key=lambda r: (len(r), r))
        highest_rev = matching_revs[-1]
        next_rev = get_next_revision_str(highest_rev)

        # Extract original State
        state_data = src_item.get("State")
        old_state = "Engineerig Use"
        if state_data:
            if isinstance(state_data, list) and len(state_data) > 0:
                old_state = state_data[0].get("value", "Engineerig Use") if isinstance(state_data[0], dict) else str(state_data[0])
            elif isinstance(state_data, dict):
                old_state = state_data.get("value", "Engineerig Use")
            else:
                old_state = str(state_data)

        create_url = f"{self.api_url}/api/database/rows/table/{self.table_bom}/?user_field_names=true"
        price_val = src_item.get("Price per unit") if src_item.get("Price per unit") is not None else src_item.get("Price")
        sourced_by_raw = src_item.get("Sourced By") or src_item.get("Sourced by")
        sourced_by_val = "TBD"
        if sourced_by_raw:
            if isinstance(sourced_by_raw, dict):
                sourced_by_val = sourced_by_raw.get("id") or sourced_by_raw.get("value")
            else:
                sourced_by_val = sourced_by_raw

        payload = {
            "Part Number": pn,
            "Item description": src_item.get("Item description", ""),
            "Revision": next_rev,
            "State": self.get_state_id(old_state) if self.get_state_id(old_state) else old_state,
            "Source URL": src_item.get("Source URL", ""),
            "External Part Number": src_item.get("External Part Number", ""),
            "Notes": src_item.get("Notes", ""),
            "Blackbox": bool(src_item.get("Blackbox", False)),
            "Purchase Kit": bool(src_item.get("Purchase Kit", False)),
        }
        if "Price per unit" in src_item:
            payload["Price per unit"] = src_item["Price per unit"]
        elif "Price" in src_item:
            payload["Price"] = src_item["Price"]

        if "Lot Size" in src_item and src_item["Lot Size"] is not None:
            payload["Lot Size"] = src_item["Lot Size"]

        pur_uom = src_item.get("Purchase UoM", [])
        if pur_uom:
            payload["Purchase UoM"] = [x["id"] if isinstance(x, dict) else x for x in pur_uom if x]

        con_uom = src_item.get("Consumption UoM", [])
        if con_uom:
            payload["Consumption UoM"] = [x["id"] if isinstance(x, dict) else x for x in con_uom if x]

        if "Sourced By" in src_item:
            payload["Sourced By"] = sourced_by_val
        else:
            payload["Sourced by"] = sourced_by_val

        manufacturer_links = src_item.get("Manufacturer", [])
        if manufacturer_links:
            payload["Manufacturer"] = [m["id"] if isinstance(m, dict) else m for m in manufacturer_links if m]

        pn_category = src_item.get("PN Category", [])
        if pn_category:
            payload["PN Category"] = [x["id"] for x in pn_category if isinstance(x, dict) and "id" in x]

        create_resp = self._request("POST", create_url, headers=self.headers, json=payload, timeout=10)
        create_resp.raise_for_status()
        new_item = create_resp.json()
        new_item_id = new_item["id"]

        # Copy previous revision's children (contained items), but NOT parent relationships
        assembly_rows = self._get_all_rows(self.table_assembly)
        for edge in assembly_rows:
            parent_link = edge.get("Item") or []
            child_link = edge.get("Contains") or []

            if isinstance(parent_link, list) and len(parent_link) > 0 and parent_link[0].get("id") == item_id:
                if isinstance(child_link, list) and len(child_link) > 0:
                    child_id = child_link[0].get("id")
                    quantity = edge.get("Amount of Times")
                    length = edge.get("Measurement")
                    pcb_symbol = edge.get("PCB Symbol")
                    self.create_assembly(new_item_id, child_id, quantity, length, pcb_symbol)

        new_item = self._ensure_item_category(new_item_id, new_item)

        self.scanner.reset()
        return new_item

    def get_instruction_sets_for_item(self, parent_id):
        """Returns a list of available instruction sets for a parent item with step count and balance status."""
        self._ensure_instructions_fields()
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_inst = executor.submit(self._get_all_rows, self.table_instructions)
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_asm = executor.submit(self._get_all_rows, self.table_assembly)
            instruction_rows = fut_inst.result()
            bom_rows = fut_bom.result()
            assembly_rows = fut_asm.result()

        bom_map = {r["id"]: r for r in bom_rows}

        # Identify items that have ANY instructions
        items_with_instructions = set()
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                items_with_instructions.add(p_link[0].get("id"))

        # Group steps by set_index for this parent_id
        parent_steps_by_set = {}
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                if p_link[0].get("id") == parent_id:
                    s_idx = row.get("Set Index") or 1
                    try:
                        s_idx = int(s_idx)
                    except (ValueError, TypeError):
                        s_idx = 1
                    if s_idx not in parent_steps_by_set:
                        parent_steps_by_set[s_idx] = []
                    parent_steps_by_set[s_idx].append(row)

        if not parent_steps_by_set:
            return []

        # Hierarchy traversal to compute required quantities for parent_id
        parent_to_children = {}
        for edge in assembly_rows:
            p_link = edge.get("Item")
            c_link = edge.get("Contains")
            if p_link and c_link and isinstance(p_link, list) and isinstance(c_link, list):
                pid = p_link[0]["id"]
                cid = c_link[0]["id"]
                q = edge.get("Amount of Times")
                qty = int(q) if (q is not None and q != "") else 1
                if pid not in parent_to_children:
                    parent_to_children[pid] = []
                parent_to_children[pid].append({"child_id": cid, "quantity": qty})

        required_totals = {}

        def traverse(current_id, current_multiplier, visited):
            if current_id in visited:
                return
            rels = parent_to_children.get(current_id, [])
            for rel in rels:
                cid = rel["child_id"]
                qty = rel["quantity"] * current_multiplier
                child_part = bom_map.get(cid, {})
                is_blackbox = bool(child_part.get("Blackbox", False))
                has_instructions = cid in items_with_instructions
                child_has_children = bool(parent_to_children.get(cid))

                if child_has_children and not is_blackbox and not has_instructions:
                    traverse(cid, qty, visited | {current_id})
                else:
                    required_totals[cid] = required_totals.get(cid, 0) + qty

        traverse(parent_id, 1, set())

        import json
        sets = []
        for s_idx, set_steps in sorted(parent_steps_by_set.items()):
            instructed_totals = {}
            for s in set_steps:
                toll_map_str = s.get("Toll Map")
                parsed_successfully = False
                if toll_map_str:
                    try:
                        data = json.loads(toll_map_str)
                        if isinstance(data, list):
                            for slot in data:
                                c_id = slot.get("id")
                                if c_id and slot.get("toll", True):
                                    try:
                                        q_num = float(slot.get("quantity", 1))
                                    except (ValueError, TypeError):
                                        q_num = 1.0
                                    instructed_totals[c_id] = instructed_totals.get(c_id, 0) + q_num
                            parsed_successfully = True
                        elif isinstance(data, dict):
                            for c_id, entry in data.items():
                                if str(c_id).isdigit():
                                    c_id_int = int(c_id)
                                    is_tolled = True
                                    q = 1.0
                                    if isinstance(entry, dict):
                                        is_tolled = entry.get("toll", True)
                                        try:
                                            q = float(entry.get("qty", 1))
                                        except (ValueError, TypeError):
                                            q = 1.0
                                    else:
                                        is_tolled = bool(entry)
                                    if is_tolled:
                                        instructed_totals[c_id_int] = instructed_totals.get(c_id_int, 0) + q
                            parsed_successfully = True
                    except Exception:
                        pass

                if not parsed_successfully:
                    child = s.get("Child Item")
                    if child and isinstance(child, list):
                        qty_fallback = s.get("Quantity") or 1
                        try:
                            qty_fallback = int(qty_fallback)
                        except (ValueError, TypeError):
                            qty_fallback = 1
                        is_tolled = s.get("Toll") if s.get("Toll") is not None else True
                        if is_tolled:
                            for c_ref in child:
                                c_id = c_ref.get("id")
                                if c_id:
                                    instructed_totals[c_id] = instructed_totals.get(c_id, 0) + qty_fallback

            # Check if balanced
            is_balanced = True
            all_cids = set(required_totals.keys()) | set(instructed_totals.keys())
            for cid in all_cids:
                if required_totals.get(cid, 0) != instructed_totals.get(cid, 0):
                    is_balanced = False
                    break

            sets.append({
                "set_index": s_idx,
                "step_count": len(set_steps),
                "is_balanced": is_balanced
            })

        return sets

    def _ensure_instructions_fields(self):
        """Ensures that the 'Toll Map' and 'Tool Map' fields exist in the Assembly Instructions table."""
        # Only check once per application startup
        if getattr(self, "_instructions_fields_checked", False):
            return
        try:
            url = f"{self.api_url}/api/database/fields/table/{self.table_instructions}/"
            res = self._request("GET", url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                fields = res.json()
                field_names = {f["name"] for f in fields}
                missing = []
                if "Toll Map" not in field_names:
                    missing.append("Toll Map (text)")
                if "Tool Map" not in field_names:
                    missing.append("Tool Map (text)")
                if missing:
                    print(
                        f"[WARNING] Missing fields in Assembly Instructions table (table {self.table_instructions}): "
                        + ", ".join(missing) +
                        ". The API token does not have permission to create fields. "
                        "Please create these fields manually in Baserow. "
                        "Toll / Tool data will not be persisted until fields exist."
                    )
                    # Do NOT set _instructions_fields_checked=True so we retry on next request
                    return
                self._instructions_fields_checked = True
        except Exception as e:
            print(f"Error checking instructions fields: {e}")

    def get_instruction_set_details(self, parent_id, set_index):
        """
        Fetches steps for a specific parent item and set index, and calculates
        the comparison table (Assembly vs Instructions) adhering to Blackbox rules.
        All three table fetches run in parallel.
        """
        self._ensure_instructions_fields()
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_inst = executor.submit(self._get_all_rows, self.table_instructions)
            fut_bom = executor.submit(self._get_all_rows, self.table_bom)
            fut_asm = executor.submit(self._get_all_rows, self.table_assembly)
            instruction_rows = fut_inst.result()
            bom_rows = fut_bom.result()
            assembly_rows = fut_asm.result()

        bom_map = {r["id"]: r for r in bom_rows}

        # Identify items that have ANY instructions (in table 5770)
        items_with_instructions = set()
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                items_with_instructions.add(p_link[0].get("id"))

        # Filter steps for this parent_id and set_index
        set_steps = []
        for row in instruction_rows:
            p_link = row.get("Parent Item")
            if p_link and isinstance(p_link, list) and len(p_link) > 0:
                if p_link[0].get("id") == parent_id:
                    s_idx = row.get("Set Index") or 1
                    try:
                        s_idx = int(s_idx)
                    except (ValueError, TypeError):
                        s_idx = 1
                    if s_idx == set_index:
                        set_steps.append(row)

        # Sort steps by Step Order
        set_steps.sort(key=lambda x: int(x.get("Step Order") or 0))

        # Format steps output
        import json
        formatted_steps = []
        for s in set_steps:
            rec = s.get("Action Receiving Item")
            child = s.get("Child Item")
            tool = s.get("Tool")

            rec_item = bom_map.get(rec[0]["id"]) if (rec and isinstance(rec, list) and len(rec) > 0) else None

            # Reconstruct Part Slots from Toll Map
            part_slots = []
            toll_map_str = s.get("Toll Map", "")
            parsed_entries = parse_toll_map(toll_map_str)
            parsed_part_slots = [
                {
                    "id": e["item_id"],
                    "edge_id": e.get("edge_id"),
                    "quantity": e["qty"],
                    "length": e.get("length", 0),
                    "toll": e["toll"]
                }
                for e in parsed_entries
            ]
            
            # Re-serialize toll map for frontend to use canonical format
            canonical_toll_map = serialize_toll_map(parsed_entries) if parsed_entries else "[]"
            
            if not parsed_part_slots and child and isinstance(child, list):
                for c_ref in child:
                    parsed_part_slots.append({
                        "id": c_ref.get("id"),
                        "edge_id": None,
                        "quantity": 1,
                        "length": 0,
                        "toll": True
                    })
                    parsed_entries.append({
                        "edge_id": None,
                        "item_id": c_ref.get("id"),
                        "toll": True,
                        "qty": 1,
                        "length": 0
                    })
                canonical_toll_map = serialize_toll_map(parsed_entries)
            
            for slot in parsed_part_slots:
                c_id = slot.get("id")
                c_item = bom_map.get(c_id) if c_id else None
                part_no = ""
                desc = ""
                rev = ""
                ext_pn = ""
                image_url = ""
                if c_item:
                    part_no = c_item.get("Part Number") or ""
                    desc = c_item.get("Item description") or c_item.get("Description") or ""
                    rev = c_item.get("Revision") or ""
                    ext_pn = c_item.get("External PN") or ""
                    images = c_item.get("Image")
                    if images and isinstance(images, list) and len(images) > 0:
                        image_url = images[0].get("url") or ""

                try:
                    slot_qty = float(slot.get("quantity", 1))
                    slot_qty = int(slot_qty) if slot_qty.is_integer() else slot_qty
                except (ValueError, TypeError):
                    slot_qty = 1

                try:
                    slot_len = float(slot.get("length", 0))
                    slot_len = int(slot_len) if slot_len.is_integer() else slot_len
                except (ValueError, TypeError):
                    slot_len = 0

                part_slots.append({
                    "id": c_id,
                    "edge_id": slot.get("edge_id"),
                    "quantity": slot_qty,
                    "length": slot_len,
                    "toll": slot.get("toll", True),
                    "part_number": c_item.get("Full PN") or (
                        f"{part_no} Rev.{rev}" if rev else part_no
                    ) if c_item else None,
                    "pn": part_no,
                    "revision": rev,
                    "description": desc,
                    "ext_pn": ext_pn,
                    "image_url": image_url
                })

            # Reconstruct Tool Slots from Tool Map
            tool_slots = []
            tool_map_str = s.get("Tool Map", "")
            parsed_tool_slots = []
            if tool_map_str:
                try:
                    data = json.loads(tool_map_str)
                    if isinstance(data, list):
                        for slot in data:
                            t_id = slot.get("id")
                            if t_id:
                                try:
                                    q_val = float(slot.get("quantity", 1))
                                    q_val = int(q_val) if q_val.is_integer() else q_val
                                except (ValueError, TypeError):
                                    q_val = 1
                                parsed_tool_slots.append({
                                    "id": int(t_id),
                                    "quantity": q_val
                                })
                except Exception as e:
                    print(f"Error parsing Tool Map: {e}")
            
            if not parsed_tool_slots and tool and isinstance(tool, list):
                for t_ref in tool:
                    parsed_tool_slots.append({
                        "id": t_ref.get("id"),
                        "quantity": 1
                    })
            
            for slot in parsed_tool_slots:
                t_id = slot.get("id")
                t_item = bom_map.get(t_id) if t_id else None
                part_no = ""
                desc = ""
                rev = ""
                ext_pn = ""
                image_url = ""
                if t_item:
                    part_no = t_item.get("Part Number") or ""
                    desc = t_item.get("Item description") or t_item.get("Description") or ""
                    rev = t_item.get("Revision") or ""
                    ext_pn = t_item.get("External PN") or ""
                    images = t_item.get("Image")
                    if images and isinstance(images, list) and len(images) > 0:
                        image_url = images[0].get("url") or ""

                try:
                    slot_qty = float(slot.get("quantity", 1))
                    slot_qty = int(slot_qty) if slot_qty.is_integer() else slot_qty
                except (ValueError, TypeError):
                    slot_qty = 1

                tool_slots.append({
                    "id": t_id,
                    "quantity": slot_qty,
                    "part_number": t_item.get("Full PN") or (
                        f"{part_no} Rev.{rev}" if rev else part_no
                    ) if t_item else None,
                    "pn": part_no,
                    "revision": rev,
                    "description": desc,
                    "ext_pn": ext_pn,
                    "image_url": image_url
                })

            child_items = [slot for slot in part_slots if slot["id"] is not None]
            child_item = child_items[0] if child_items else None
            filled_tools = [slot for slot in tool_slots if slot["id"] is not None]
            tool_item = filled_tools[0] if filled_tools else None

            # Compute backward-compatible quantity and toll
            qty_val = s.get("Quantity")
            if qty_val is None:
                total_qty = sum(
                    float(slot.get("quantity", 1)) for slot in child_items
                ) if child_items else 1
                qty_val = int(total_qty) if isinstance(total_qty, float) and total_qty.is_integer() else total_qty
            else:
                try:
                    q_f = float(qty_val)
                    qty_val = int(q_f) if q_f.is_integer() else q_f
                except (ValueError, TypeError):
                    qty_val = 1

            toll_val = s.get("Toll")
            if toll_val is None:
                toll_val = all(slot.get("toll", True) for slot in child_items) if child_items else True

            formatted_steps.append({
                "id": s["id"],
                "set_index": set_index,
                "step_order": s.get("Step Order"),
                "action": s.get("Action", ""),
                "description": s.get("Description", ""),
                "photo": s.get("Photo", []),
                "toll_map": canonical_toll_map,
                "tool_map": tool_map_str,
                "receiving_item": {
                    "id": rec_item["id"],
                    "part_number": rec_item.get("Full PN") or (
                        f"{rec_item.get('Part Number')} Rev.{rec_item.get('Revision')}"
                        if rec_item.get("Revision") else rec_item.get("Part Number", "")
                    ),
                    "description": rec_item.get("Item description", "")
                } if rec_item else None,
                "child_item": child_item,
                "child_items": child_items,
                "part_slots": part_slots,
                "tool_slots": tool_slots,
                "tool": tool_item,
                "quantity": qty_val,
                "toll": toll_val
            })

        # Hierarchy traversal to compute required quantities and track source origins
        parent_to_children = {}
        for edge in assembly_rows:
            p_link = edge.get("Item")
            c_link = edge.get("Contains")
            if p_link and c_link and isinstance(p_link, list) and isinstance(c_link, list):
                pid = p_link[0]["id"]
                cid = c_link[0]["id"]
                q = edge.get("Amount of Times")
                qty = int(q) if (q is not None and q != "") else 1
                length = edge.get("Measurement")
                pcb_symbol = edge.get("PCB Symbol")
                
                uom_raw = edge.get("Measurement UoM", [])
                uom_id = uom_raw[0].get("id") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else None
                uom_val = uom_raw[0].get("value") if (isinstance(uom_raw, list) and len(uom_raw) > 0) else ""

                if pid not in parent_to_children:
                    parent_to_children[pid] = []
                parent_to_children[pid].append({
                    "child_id": cid,
                    "quantity": qty,
                    "edge_id": edge["id"],
                    "length": length,
                    "pcb_symbol": pcb_symbol,
                    "uom_id": uom_id,
                    "uom_val": uom_val
                })

        required_edges = {}
        expanded_parents = {}

        def traverse(current_id, current_multiplier, visited):
            if current_id in visited:
                return
            rels = parent_to_children.get(current_id, [])
            for rel in rels:
                cid = rel["child_id"]
                qty = rel["quantity"] * current_multiplier
                child_part = bom_map.get(cid, {})
                is_blackbox = bool(child_part.get("Blackbox", False))
                has_instructions = cid in items_with_instructions
                child_has_children = bool(parent_to_children.get(cid))

                if child_has_children and not is_blackbox and not has_instructions:
                    # Intermediate sub-assembly without own instructions and without Blackbox flag:
                    p_info = bom_map.get(cid, {})
                    expanded_parents[cid] = {
                        "id": cid,
                        "part_number": p_info.get("Full PN") or (
                            f"{p_info.get('Part Number')} Rev.{p_info.get('Revision')}"
                            if p_info.get("Revision") else p_info.get("Part Number", f"Item #{cid}")
                        ),
                        "description": p_info.get("Item description", ""),
                        "blackbox": bool(p_info.get("Blackbox", False))
                    }
                    # Explode into its constituent parts!
                    traverse(cid, qty, visited | {current_id})
                else:
                    # Terminal part for this instruction set (leaf item OR blackbox OR sub-assembly with own instructions)
                    edge_id = rel["edge_id"]
                    if edge_id not in required_edges:
                        p_obj = bom_map.get(current_id, {})
                        required_edges[edge_id] = {
                            "edge_id": edge_id,
                            "item_id": cid,
                            "unit_qty": rel["quantity"],
                            "total_qty": qty,
                            "length": rel.get("length", 0),
                            "pcb_symbol": rel.get("pcb_symbol"),
                            "uom_id": rel.get("uom_id"),
                            "uom_val": rel.get("uom_val"),
                            "parent_id": current_id,
                            "parent_pn": p_obj.get("Full PN") or (
                                f"{p_obj.get('Part Number')} Rev.{p_obj.get('Revision')}"
                                if p_obj.get("Revision") else p_obj.get("Part Number", f"Item #{current_id}")
                            ),
                            "parent_description": p_obj.get("Item description", ""),
                            "parent_blackbox": bool(p_obj.get("Blackbox", False)),
                            "is_derived": (current_id != parent_id)
                        }
                    else:
                        required_edges[edge_id]["total_qty"] += qty

        traverse(parent_id, 1, set())

        # Sum instructed quantities for this set
        instructed_edges = {}
        instructed_edges_by_item_id = {}

        for s in set_steps:
            toll_map_str = s.get("Toll Map")
            parsed_entries = parse_toll_map(toll_map_str)
            
            if parsed_entries:
                for entry in parsed_entries:
                    if not entry["toll"]:
                        continue
                    if entry["edge_id"]:
                        instructed_edges[entry["edge_id"]] = instructed_edges.get(entry["edge_id"], 0) + entry["qty"]
                    else:
                        instructed_edges_by_item_id[entry["item_id"]] = instructed_edges_by_item_id.get(entry["item_id"], 0) + entry["qty"]
            else:
                child = s.get("Child Item")
                if child and isinstance(child, list):
                    qty_fallback = s.get("Quantity") or 1
                    try:
                        qty_fallback = float(qty_fallback)
                    except (ValueError, TypeError):
                        qty_fallback = 1
                    is_tolled = s.get("Toll") if s.get("Toll") is not None else True
                    if is_tolled:
                        for c_ref in child:
                            c_id = c_ref.get("id")
                            if c_id:
                                instructed_edges_by_item_id[c_id] = instructed_edges_by_item_id.get(c_id, 0) + qty_fallback

        comparison = []

        # First, iterate required edges
        for edge_id, edge in required_edges.items():
            cid = edge["item_id"]
            part = bom_map.get(cid, {})
            req = edge["total_qty"]
            
            inst = instructed_edges.get(edge_id, 0)
            if cid in instructed_edges_by_item_id and inst == 0:
                # Use fallback pool
                available = instructed_edges_by_item_id[cid]
                if available >= req:
                    inst = req
                    instructed_edges_by_item_id[cid] -= req
                else:
                    inst = available
                    instructed_edges_by_item_id[cid] = 0

            in_hierarchy = True

            if inst == 0:
                discrepancy = "Missing Instruction"
            elif inst < req:
                discrepancy = "Under-instructed"
            elif inst > req:
                discrepancy = "Over-instructed"
            else:
                discrepancy = "OK"

            images = part.get("Image") or []
            img_url = ""
            if isinstance(images, list) and len(images) > 0 and isinstance(images[0], dict):
                img_url = images[0].get("url") or ""

            length = float(edge.get("length") or 0)
            uom_val = edge.get("uom_val")
            amount_label = format_relation_amount(req, length, uom_val)
            amount_label_instructed = format_relation_amount(inst, length, uom_val)

            comparison.append({
                "edge_id": edge_id,
                "item_id": cid,
                "part_number": part.get("Full PN") or (
                    f"{part.get('Part Number')} Rev.{part.get('Revision')}"
                    if part.get("Revision") else part.get("Part Number", f"Item #{cid}")
                ),
                "description": part.get("Item description", ""),
                "required_qty": req,
                "instructed_qty": inst,
                "required_length": length,
                "uom_symbol": uom_val,
                "uom_id": edge.get("uom_id"),
                "amount_label": amount_label,
                "amount_label_instructed": amount_label_instructed,
                "direct_required_qty": req if not edge.get("is_derived") else 0,
                "derived_required_qty": req if edge.get("is_derived") else 0,
                "discrepancy": discrepancy,
                "in_hierarchy": True,
                "image_url": img_url,
                "Image": images,
                "is_derived": edge.get("is_derived"),
                "parent_id": edge.get("parent_id"),
                "parent_pn": edge.get("parent_pn"),
                "parent_description": edge.get("parent_description"),
                "parent_blackbox": edge.get("parent_blackbox"),
                "unit_qty": edge.get("unit_qty"),
                "length": length,
                "pcb_symbol": edge.get("pcb_symbol")
            })

        # Add remaining instructed items not matched to required edges
        for cid, remaining_inst in instructed_edges_by_item_id.items():
            if remaining_inst > 0:
                part = bom_map.get(cid, {})
                images = part.get("Image") or []
                img_url = ""
                if isinstance(images, list) and len(images) > 0 and isinstance(images[0], dict):
                    img_url = images[0].get("url") or ""
                
                amount_label = format_relation_amount(0, 0, "pcs")
                amount_label_instructed = format_relation_amount(remaining_inst, 0, "pcs")
                
                comparison.append({
                    "edge_id": None,
                    "item_id": cid,
                    "part_number": part.get("Full PN") or (
                        f"{part.get('Part Number')} Rev.{part.get('Revision')}"
                        if part.get("Revision") else part.get("Part Number", f"Item #{cid}")
                    ),
                    "description": part.get("Item description", ""),
                    "required_qty": 0,
                    "instructed_qty": remaining_inst,
                    "required_length": 0,
                    "uom_symbol": "pcs",
                    "uom_id": None,
                    "amount_label": amount_label,
                    "amount_label_instructed": amount_label_instructed,
                    "direct_required_qty": 0,
                    "derived_required_qty": 0,
                    "discrepancy": "Not in Hierarchy",
                    "in_hierarchy": False,
                    "image_url": img_url,
                    "Image": images,
                    "is_derived": False,
                    "parent_id": parent_id,
                    "parent_pn": "",
                    "parent_description": "",
                    "parent_blackbox": False,
                    "unit_qty": 0,
                    "length": 0,
                    "pcb_symbol": ""
                })

        for edge_id, remaining_inst in instructed_edges.items():
            if edge_id not in required_edges and remaining_inst > 0:
                # Should not really happen but if it does, add it.
                pass

        return {
            "steps": formatted_steps,
            "comparison": comparison,
            "sub_assemblies": list(expanded_parents.values())
        }

    def _get_max_step_order(self, parent_id, set_index):
        """Lightweight query to find the current max Step Order for a given set.
        Uses a filtered, sorted, single-row Baserow query instead of fetching all rows."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/"
        params = {
            "user_field_names": "true",
            "size": 1,
            "order_by": "-Step Order",
            "filter__Parent Item__link_row_has": parent_id,
            "filter__Set Index__equal": set_index
        }
        try:
            resp = self._request("GET", url, headers=self.headers, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                return int(results[0].get("Step Order") or 0)
        except Exception:
            pass
        return 0

    def create_instruction_step(self, parent_id, set_index, step_data):
        """Creates a step in the Assembly Instructions table (5770)."""
        self._ensure_instructions_fields()
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/?user_field_names=true"

        max_order = self._get_max_step_order(parent_id, set_index)

        payload = {
            "Parent Item": [parent_id],
            "Set Index": set_index,
            "Step Order": step_data.get("step_order", max_order + 1),
            "Action": step_data.get("action", ""),
            "Description": step_data.get("description", ""),
            "Toll Map": step_data.get("toll_map", ""),
            "Tool Map": step_data.get("tool_map", "")
        }

        if step_data.get("receiving_item_id"):
            payload["Action Receiving Item"] = [step_data["receiving_item_id"]]
        if "child_item_ids" in step_data:
            payload["Child Item"] = step_data["child_item_ids"]
        elif step_data.get("child_item_id"):
            payload["Child Item"] = [step_data["child_item_id"]]
        if "tool_ids" in step_data:
            payload["Tool"] = step_data["tool_ids"]
        elif step_data.get("tool_id"):
            payload["Tool"] = [step_data["tool_id"]]
        if step_data.get("photo"):
            payload["Photo"] = step_data["photo"]

        res = self._request("POST", url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def update_instruction_step(self, step_id, step_data):
        """Updates a step in table 5770."""
        self._ensure_instructions_fields()
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/{step_id}/?user_field_names=true"
        payload = {}

        if "action" in step_data:
            payload["Action"] = step_data["action"]
        if "description" in step_data:
            payload["Description"] = step_data["description"]
        if "step_order" in step_data:
            payload["Step Order"] = step_data["step_order"]
        if "toll_map" in step_data:
            payload["Toll Map"] = step_data["toll_map"]
        if "tool_map" in step_data:
            payload["Tool Map"] = step_data["tool_map"]
        if "receiving_item_id" in step_data:
            payload["Action Receiving Item"] = [step_data["receiving_item_id"]] if step_data["receiving_item_id"] else []
        if "child_item_ids" in step_data:
            payload["Child Item"] = step_data["child_item_ids"] if step_data["child_item_ids"] else []
        elif "child_item_id" in step_data:
            payload["Child Item"] = [step_data["child_item_id"]] if step_data["child_item_id"] else []
        if "tool_ids" in step_data:
            payload["Tool"] = step_data["tool_ids"] if step_data["tool_ids"] else []
        elif "tool_id" in step_data:
            payload["Tool"] = [step_data["tool_id"]] if step_data["tool_id"] else []
        if "photo" in step_data:
            payload["Photo"] = step_data["photo"]

        res = self._request("PATCH", url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def delete_instruction_step(self, step_id):
        """Deletes a step in table 5770."""
        url = f"{self.api_url}/api/database/rows/table/{self.table_instructions}/{step_id}/"
        res = self._request("DELETE", url, headers=self.headers, timeout=10)
        res.raise_for_status()

    def reorder_instruction_steps(self, parent_id, set_index, step_ids):
        """Updates Step Order for a list of step IDs."""
        for idx, sid in enumerate(step_ids, start=1):
            self.update_instruction_step(sid, {"step_order": idx})

    def delete_instruction_set(self, parent_id, set_index):
        """Deletes all steps for a parent item and set index."""
        details = self.get_instruction_set_details(parent_id, set_index)
        for s in details["steps"]:
            self.delete_instruction_step(s["id"])

    # WI Templates API
    def get_wi_templates(self):
        url = f"{self.api_url}/api/database/rows/table/{self.table_wi_templates}/?user_field_names=true"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return response.json().get("results", [])
        return []

    def create_wi_template(self, data):
        url = f"{self.api_url}/api/database/rows/table/{self.table_wi_templates}/?user_field_names=true"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def update_wi_template(self, row_id, data):
        url = f"{self.api_url}/api/database/rows/table/{self.table_wi_templates}/{row_id}/?user_field_names=true"
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def delete_wi_template(self, row_id):
        url = f"{self.api_url}/api/database/rows/table/{self.table_wi_templates}/{row_id}/"
        response = requests.delete(url, headers=self.headers)
        response.raise_for_status()
        return True


