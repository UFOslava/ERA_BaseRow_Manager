import logging
import io
import requests
import os
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from app.baserow_client import BaserowClient
from app.baserow_init import (
    get_auth_status_summary,
    discover_baserow_schema,
    save_auth_configuration,
    combine_url_and_port,
    parse_url_and_port
)
from app.logger import setup_logging, get_log_level, set_log_level, get_active_log_info

logger = logging.getLogger(__name__)

def create_app(db_path=None):
    setup_logging()
    logger.info("Starting up Flask application")
    app = Flask(__name__)
    CORS(app, expose_headers=["Content-Disposition"])

    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    client = BaserowClient()

    def is_auth_configured():
        return bool(client.token and str(client.token).strip() and client.table_bom)

    # Path resolution for WI export configurations and templates
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    wi_templates_dir = os.path.join(base_dir, "wi_templates")
    wi_config_path = os.path.join(base_dir, "wi_export_config.json")
    os.makedirs(wi_templates_dir, exist_ok=True)

    def limit_tree_nodes(tree, limit):
        count = 0
        
        def traverse(node):
            nonlocal count
            if count >= limit:
                return None
            
            count += 1
            new_node = {k: v for k, v in node.items() if k != 'children'}
            
            new_children = []
            if 'children' in node:
                for child in node['children']:
                    child_res = traverse(child)
                    if child_res is not None:
                        new_children.append(child_res)
                    else:
                        break
            new_node['children'] = new_children
            return new_node

        result = []
        for root in tree:
            root_res = traverse(root)
            if root_res is not None:
                result.append(root_res)
            else:
                break
        return result

    @app.route('/api/bom/uom', methods=['GET'])
    def get_uoms():
        try:
            data = client.get_uoms()
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Error fetching UOMs: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/bom/tree', methods=['GET'])
    def get_bom_tree():
        try:
            logger.trace("GET /api/bom/tree requested")
            if not is_auth_configured():
                return jsonify({"error": "Baserow configuration is incomplete. Please configure authentication in Settings.", "auth_incomplete": True}), 503
            limit = min(int(request.args.get('limit', 10000)), 10000)
            tree = client.get_bom_tree()
            truncated_tree = limit_tree_nodes(tree, limit)
            return jsonify(truncated_tree)
        except Exception as e:
            logger.exception("Error getting BOM tree")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/top-level', methods=['GET'])
    def get_top_level_items():
        try:
            state = request.args.get('state', None)
            offset = int(request.args.get('offset', 0))
            limit = min(int(request.args.get('limit', 50)), 200)
            result = client.get_top_level_items(state=state, offset=offset, limit=limit)
            return jsonify(result)
        except Exception as e:
            logger.exception("Error getting top-level items")
            return jsonify({"error": str(e)}), 500


    @app.route('/api/bom/items', methods=['GET'])
    def get_items():
        try:
            search = request.args.get('search', '').strip()
            limit = min(int(request.args.get('limit', 10000)), 10000)
            logger.trace("GET /api/bom/items requested")

            if search and len(search) >= 3:
                items = client.search_items(search, limit)
            else:
                items = client.get_items()
                if limit:
                    items = items[:limit]

            result = [{
                "id": item["id"],
                "Part Number": item.get("Part Number"),
                "Revision": item.get("Revision"),
                "Item description": item.get("Item description") or item.get("Description"),
                "Image": item.get("Image", []),
                "External PN": item.get("External PN") or item.get("External Part Number"),
                "Notes": item.get("Notes"),
                "Search helper": item.get("Search helper") or item.get("Search Helper"),
                "Manufacturer": item.get("Manufacturer", []),
                "State": item.get("State"),
                "Full PN": item.get("Full PN")
            } for item in items]
            return jsonify(result)
        except Exception as e:
            logger.exception("Error getting items")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items', methods=['POST'])
    def create_item():
        try:
            data = request.json or {}
            prefix = data.get("prefix")
            description = data.get("description")
            if not prefix:
                return jsonify({"error": "Missing prefix"}), 400
            new_item = client.create_item(prefix, description)
            return jsonify(new_item)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>', methods=['GET'])
    def get_item(item_id):
        try:
            item = client.get_item(item_id)
            return jsonify(item)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/export', methods=['GET'])
    def export_item_excel(item_id):
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.drawing.image import Image as OpenpyxlImage
            from PIL import Image as PILImage

            item = client.get_item(item_id)
            contained_items = item.get("contained_items", [])
            
            # Create Workbook
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "BOM Components"
            
            # Grid lines visible
            ws.views.sheetView[0].showGridLines = True
            
            # Styles
            font_family = "Segoe UI"
            header_font = Font(name=font_family, size=11, bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid") # Dark Blue
            header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            
            data_font = Font(name=font_family, size=10)
            data_align_center = Alignment(horizontal="center", vertical="center")
            data_align_left = Alignment(horizontal="left", vertical="center")
            data_align_right = Alignment(horizontal="right", vertical="center")
            
            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'),
                right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'),
                bottom=Side(style='thin', color='D9D9D9')
            )
            
            # Column widths
            ws.column_dimensions['A'].width = 12  # Image
            ws.column_dimensions['B'].width = 18  # ERA PN & Revision
            ws.column_dimensions['C'].width = 16  # External PN
            ws.column_dimensions['D'].width = 40  # Description
            ws.column_dimensions['E'].width = 18  # Quantity
            ws.column_dimensions['F'].width = 14  # Price
            ws.column_dimensions['G'].width = 14  # Subtotal
            
            # Set headers
            headers = ["Image", "ERA PN & Rev", "External PN", "Description", "Quantity", "Price", "Subtotal"]
            ws.append(headers)
            ws.row_dimensions[1].height = 28
            
            for col_idx in range(1, 8):
                cell = ws.cell(row=1, column=col_idx)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                cell.border = thin_border
                
            row_num = 2
            total_price_sum = 0.0
            has_any_price = False
            
            for child in contained_items:
                ws.row_dimensions[row_num].height = 45  # make room for image thumbnail
                
                # Format Quantity (length or PCB designator in parentheses)
                qty = child.get("quantity")
                length = child.get("length")
                pcb_symbol = child.get("pcb_symbol")
                
                qty_label = ""
                try:
                    qty_val = float(qty) if qty is not None and qty != "" else None
                except (ValueError, TypeError):
                    qty_val = None
                    
                try:
                    len_val = float(length) if length is not None and length != "" else None
                except (ValueError, TypeError):
                    len_val = None
                    
                if len_val is not None and len_val > 0:
                    if qty_val is not None:
                        qty_label = f"{int(qty_val) if qty_val.is_integer() else qty_val} ({int(len_val) if len_val.is_integer() else len_val}mm)"
                    else:
                        qty_label = f"({int(len_val) if len_val.is_integer() else len_val}mm)"
                elif pcb_symbol:
                    if qty_val is not None:
                        qty_label = f"{int(qty_val) if qty_val.is_integer() else qty_val} ({pcb_symbol})"
                    else:
                        qty_label = f"({pcb_symbol})"
                else:
                    if qty_val is not None:
                        qty_label = str(int(qty_val) if qty_val.is_integer() else qty_val)
                    else:
                        qty_label = ""
                
                # Price parsing
                price_raw = child.get("price")
                price_val = None
                if price_raw is not None and price_raw != "":
                    try:
                        price_val = float(price_raw)
                    except (ValueError, TypeError):
                        price_val = None
                
                # ERA PN & Rev
                full_pn = child.get("Full PN") or child.get("part_number") or ""
                rev = child.get("revision") or ""
                if not child.get("Full PN") and rev:
                    full_pn = f"{full_pn} Rev.{rev}"
                    
                external_pn = child.get("external_pn") or ""
                description = child.get("description") or ""
                
                # Write text columns
                ws.cell(row=row_num, column=2, value=full_pn)      # Col B
                ws.cell(row=row_num, column=3, value=external_pn)  # Col C
                ws.cell(row=row_num, column=4, value=description)  # Col D
                ws.cell(row=row_num, column=5, value=qty_label)    # Col E
                
                # Alignments
                ws.cell(row=row_num, column=2).alignment = data_align_center
                ws.cell(row=row_num, column=3).alignment = data_align_center
                ws.cell(row=row_num, column=4).alignment = data_align_left
                ws.cell(row=row_num, column=5).alignment = data_align_center
                
                # Write Price and Subtotal
                if price_val is not None:
                    ws.cell(row=row_num, column=6, value=price_val)
                    ws.cell(row=row_num, column=6).number_format = "$#,##0.00"
                    ws.cell(row=row_num, column=6).alignment = data_align_right
                    
                    # Subtotal calculation
                    q_factor = qty_val if qty_val is not None else 1.0
                    subtotal_val = price_val * q_factor
                    ws.cell(row=row_num, column=7, value=subtotal_val)
                    ws.cell(row=row_num, column=7).number_format = "$#,##0.00"
                    ws.cell(row=row_num, column=7).alignment = data_align_right
                    
                    total_price_sum += subtotal_val
                    has_any_price = True
                else:
                    ws.cell(row=row_num, column=6, value="N/A")
                    ws.cell(row=row_num, column=6).alignment = data_align_center
                    ws.cell(row=row_num, column=7, value="N/A")
                    ws.cell(row=row_num, column=7).alignment = data_align_center
                    
                # Borders
                for col_idx in range(1, 8):
                    ws.cell(row=row_num, column=col_idx).font = data_font
                    ws.cell(row=row_num, column=col_idx).border = thin_border
                    
                # Image download and embedding
                images = child.get("Image", [])
                if images and isinstance(images, list):
                    img_url = images[0].get("url")
                    if img_url:
                        try:
                            # Fetch image
                            img_resp = requests.get(img_url, timeout=5)
                            if img_resp.status_code == 200:
                                img_data = io.BytesIO(img_resp.content)
                                pil_img = PILImage.open(img_data)
                                pil_img.thumbnail((45, 45))
                                
                                # Save to in-memory PNG
                                png_data = io.BytesIO()
                                pil_img.save(png_data, format="PNG")
                                png_data.seek(0)
                                
                                xl_img = OpenpyxlImage(png_data)
                                xl_img.anchor = f"A{row_num}"
                                ws.add_image(xl_img)
                        except Exception as e:
                            logger.error(f"Failed to embed image for child in export: {e}")
                            
                row_num += 1
                
            # Add Total Row
            ws.row_dimensions[row_num].height = 24
            
            # Border style for total row: top thin, bottom double
            double_bottom = Border(
                top=Side(style='thin', color='000000'),
                bottom=Side(style='double', color='000000')
            )
            
            total_label_cell = ws.cell(row=row_num, column=4, value="Total Sum")
            total_label_cell.font = Font(name=font_family, size=10, bold=True)
            total_label_cell.alignment = Alignment(horizontal="right", vertical="center")
            total_label_cell.border = double_bottom
            
            total_val_cell = ws.cell(row=row_num, column=7)
            if has_any_price:
                total_val_cell.value = total_price_sum
                total_val_cell.number_format = "$#,##0.00"
                total_val_cell.alignment = data_align_right
            else:
                total_val_cell.value = "N/A"
                total_val_cell.alignment = data_align_center
                
            total_val_cell.font = Font(name=font_family, size=10, bold=True)
            total_val_cell.border = double_bottom
            
            # Empty border columns for the rest of total row
            for col_idx in [1, 2, 3, 5, 6]:
                ws.cell(row=row_num, column=col_idx).border = double_bottom
                
            # Save workbook to memory
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            part_number = item.get("Part Number", "BOM")
            revision = item.get("Revision", "")
            filename = f"BOM_Export_{part_number}"
            if revision:
                filename += f"_Rev_{revision}"
            filename += ".xlsx"
            
            return send_file(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.exception("Error exporting BOM to Excel")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/inventory-report', methods=['GET'])
    def export_inventory_report(item_id):
        try:
            from app.inventory_report import generate_inventory_report
            build_qty_str = request.args.get("build_qty", "1")
            try:
                build_qty = float(build_qty_str)
                if build_qty <= 0:
                    build_qty = 1.0
            except (ValueError, TypeError):
                build_qty = 1.0

            item = client.get_item(item_id)
            full_pn = item.get("Full PN") or (
                f"{item.get('Part Number')} Rev.{item.get('Revision')}"
                if item.get("Revision") else item.get("Part Number", f"Item_{item_id}")
            )
            clean_pn = "".join(c for c in full_pn if c.isalnum() or c in (' ', '-', '_', '.')).strip()
            filename = f"{clean_pn} - Inventory Requirement Report.xlsx"

            stream = generate_inventory_report(client, item_id, target_build_qty=build_qty)
            return send_file(
                stream,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            logger.exception("Error exporting Inventory Requirement Report to Excel")
            return jsonify({"error": str(e)}), 500


    @app.route('/api/bom/items/<int:item_id>', methods=['PATCH'])
    def update_item(item_id):
        try:
            data = request.json
            updated_item = client.update_item(item_id, data)
            return jsonify(updated_item)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/recategorize', methods=['POST'])
    def recategorize_item(item_id):
        try:
            data = request.json or {}
            new_prefix = data.get("new_prefix")
            if not new_prefix:
                return jsonify({"error": "Missing new_prefix"}), 400
            new_item = client.recategorize_item(item_id, new_prefix)
            return jsonify({"id": new_item["id"], "Part Number": new_item.get("Part Number")})
        except Exception as e:
            logger.exception("Error recategorizing item")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/duplicate', methods=['POST'])
    def duplicate_item_api(item_id):
        try:
            data = request.json or {}
            prefix = data.get("prefix")
            description = data.get("description")
            if not prefix:
                return jsonify({"error": "Missing prefix"}), 400
            
            dup_parents = data.get("duplicate_parents", True)
            dup_children = data.get("duplicate_children", True)
            dup_instructions = data.get("duplicate_instructions", True)
            dup_photos = data.get("duplicate_photos", True)
            
            new_item = client.duplicate_item(
                item_id, 
                prefix, 
                description,
                duplicate_parents=dup_parents,
                duplicate_children=dup_children,
                duplicate_instructions=dup_instructions,
                duplicate_photos=dup_photos
            )
            return jsonify(new_item)
        except Exception as e:
            logger.exception("Error duplicating item")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/revision', methods=['POST'])
    def add_item_revision(item_id):
        try:
            new_item = client.add_revision(item_id)
            return jsonify(new_item)
        except Exception as e:
            logger.exception("Error adding item revision")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/scan-status', methods=['GET'])
    def get_scan_status():
        try:
            return jsonify({"status": client.scanner.status})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/rules', methods=['GET'])
    def get_rules():
        try:
            return jsonify(client.rules)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/states', methods=['GET'])
    def get_states():
        try:
            client.load_states()
            return jsonify(client.states_map)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/rules', methods=['POST'])
    def update_rules():
        try:
            data = request.json
            success = client.save_rules(data)
            if success:
                return jsonify({"status": "success", "rules": client.rules})
            else:
                return jsonify({"error": "Failed to save rules"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/templates', methods=['GET'])
    def get_templates():
        try:
            return jsonify(client.load_templates())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/templates', methods=['POST'])
    def update_templates():
        try:
            data = request.json
            success = client.save_templates(data)
            if success:
                return jsonify({"status": "success", "templates": client.load_templates()})
            else:
                return jsonify({"error": "Failed to save templates"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/problem-definitions', methods=['GET'])
    def get_problem_definitions():
        try:
            return jsonify(client.scanner.load_definitions())
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/problem-definitions', methods=['POST'])
    def update_problem_definitions():
        try:
            data = request.json
            success = client.scanner.save_definitions(data)
            if success:
                client.scanner.reset()
                client.scanner.start_scan(client)
                return jsonify({"status": "success", "definitions": client.scanner.load_definitions()})
            else:
                return jsonify({"error": "Failed to save problem definitions"}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/problem-definitions/<string:definition_id>/count', methods=['GET'])
    def get_definition_count(definition_id):
        try:
            if client.scanner.status == "pending":
                client.scanner.start_scan(client)
            count, status = client.scanner.get_problem_count(definition_id)
            if status == "not_found":
                return jsonify({"id": definition_id, "count": None, "status": "unsaved"}), 404
            return jsonify({"id": definition_id, "count": count, "status": status})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/scan/rescan', methods=['POST'])
    def trigger_rescan():
        try:
            client.scanner.reset()
            client.scanner.start_scan(client)
            return jsonify({"status": "running"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/manufacturers', methods=['GET'])
    def get_manufacturers():
        try:
            detailed = request.args.get('detailed', 'false').lower() == 'true'
            manufacturers = client.get_manufacturers()
            if detailed:
                return jsonify(manufacturers)
            result = [{"id": m["id"], "name": m.get("Name", "Unknown")} for m in manufacturers]
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/manufacturers/<int:mfg_id>', methods=['GET'])
    def get_manufacturer(mfg_id):
        try:
            mfg = client.get_manufacturer(mfg_id)
            return jsonify(mfg)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/manufacturers', methods=['POST'])
    def create_manufacturer():
        try:
            data = request.json or {}
            mfg = client.create_manufacturer(data)
            return jsonify(mfg), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/manufacturers/<int:mfg_id>', methods=['PATCH', 'PUT'])
    def update_manufacturer(mfg_id):
        try:
            data = request.json or {}
            mfg = client.update_manufacturer(mfg_id, data)
            return jsonify(mfg)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/manufacturers/<int:mfg_id>', methods=['DELETE'])
    def delete_manufacturer(mfg_id):
        try:
            client.delete_manufacturer(mfg_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/suppliers', methods=['GET'])
    def get_suppliers():
        try:
            suppliers = client.get_suppliers()
            return jsonify(suppliers)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/suppliers/<int:supplier_id>', methods=['GET'])
    def get_supplier(supplier_id):
        try:
            supplier = client.get_supplier(supplier_id)
            return jsonify(supplier)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/suppliers', methods=['POST'])
    def create_supplier():
        try:
            data = request.json or {}
            supplier = client.create_supplier(data)
            return jsonify(supplier), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/suppliers/<int:supplier_id>', methods=['PATCH', 'PUT'])
    def update_supplier(supplier_id):
        try:
            data = request.json or {}
            supplier = client.update_supplier(supplier_id, data)
            return jsonify(supplier)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/suppliers/<int:supplier_id>', methods=['DELETE'])
    def delete_supplier(supplier_id):
        try:
            client.delete_supplier(supplier_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/contacts', methods=['GET'])
    def get_contacts():
        try:
            supplier_id = request.args.get('supplier_id')
            contacts = client.get_contacts(supplier_id=supplier_id)
            return jsonify(contacts)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/contacts/<int:contact_id>', methods=['GET'])
    def get_contact(contact_id):
        try:
            contact = client.get_contact(contact_id)
            return jsonify(contact)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/contacts', methods=['POST'])
    def create_contact():
        try:
            data = request.json or {}
            contact = client.create_contact(data)
            return jsonify(contact), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/contacts/<int:contact_id>', methods=['PATCH', 'PUT'])
    def update_contact(contact_id):
        try:
            data = request.json or {}
            contact = client.update_contact(contact_id, data)
            return jsonify(contact)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
    def delete_contact(contact_id):
        try:
            client.delete_contact(contact_id)
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/upload-file', methods=['POST'])
    def upload_file():
        try:
            if 'file' not in request.files:
                return jsonify({"error": "No file part"}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400
            
            uploaded = client.upload_file(file.filename, file.read(), file.content_type)
            return jsonify(uploaded)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/assembly', methods=['POST'])
    def create_assembly():
        try:
            data = request.json
            parent_id = data.get("parent_id")
            child_id = data.get("child_id")
            quantity = data.get("quantity")
            length = data.get("length")
            pcb_symbol = data.get("pcb_symbol")
            uom_id = data.get("uom_id")
            
            edge = client.create_assembly(parent_id, child_id, quantity, length, pcb_symbol, uom_id)
            return jsonify(edge)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/assembly/<int:edge_id>', methods=['PATCH'])
    def update_assembly(edge_id):
        try:
            data = request.json
            quantity = data.get("quantity")
            length = data.get("length")
            pcb_symbol = data.get("pcb_symbol")
            parent_id = data.get("parent_id")
            child_id = data.get("child_id")
            uom_id = data.get("uom_id")
            
            edge = client.update_assembly(edge_id, quantity, length, pcb_symbol, parent_id, child_id, uom_id)
            return jsonify(edge)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/assembly/<int:edge_id>', methods=['DELETE'])
    def delete_assembly(edge_id):
        try:
            client.delete_assembly(edge_id)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:parent_id>/instruction-sets', methods=['GET'])
    def get_instruction_sets(parent_id):
        try:
            sets = client.get_instruction_sets_for_item(parent_id)
            return jsonify(sets)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:parent_id>/instruction-sets/<int:set_index>', methods=['GET'])
    def get_instruction_set_details(parent_id, set_index):
        try:
            details = client.get_instruction_set_details(parent_id, set_index)
            return jsonify(details)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:parent_id>/instruction-sets/<int:set_index>/steps', methods=['POST'])
    def create_instruction_step(parent_id, set_index):
        try:
            data = request.json or {}
            step = client.create_instruction_step(parent_id, set_index, data)
            return jsonify(step)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/instructions/<int:step_id>', methods=['PATCH'])
    def update_instruction_step(step_id):
        try:
            data = request.json or {}
            step = client.update_instruction_step(step_id, data)
            return jsonify(step)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/instructions/<int:step_id>', methods=['DELETE'])
    def delete_instruction_step(step_id):
        try:
            client.delete_instruction_step(step_id)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:parent_id>/instruction-sets/<int:set_index>/reorder', methods=['POST'])
    def reorder_instruction_steps(parent_id, set_index):
        try:
            data = request.json or {}
            step_ids = data.get("step_ids", [])
            client.reorder_instruction_steps(parent_id, set_index, step_ids)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:parent_id>/instruction-sets/<int:set_index>', methods=['DELETE'])
    def delete_instruction_set(parent_id, set_index):
        try:
            client.delete_instruction_set(parent_id, set_index)
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


    @app.route('/api/bom/graph', methods=['GET'])
    def get_graph():
        try:
            logger.trace("GET /api/bom/graph requested")
            nodes = client.get_graph_nexus_nodes()
            return jsonify(nodes)
        except Exception as e:
            logger.exception("Error getting graph nexus nodes")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/graph/<int:item_id>/children', methods=['GET'])
    def get_graph_children(item_id):
        try:
            logger.trace("GET /api/bom/graph/%s/children requested", item_id)
            children = client.get_graph_children(item_id)
            return jsonify(children)
        except Exception as e:
            logger.exception("Error getting graph children for item_id=%s", item_id)
            return jsonify({"error": str(e)}), 500

    @app.route('/api/logs/config', methods=['GET'])
    def get_logs_config():
        try:
            level = get_log_level()
            return jsonify({"level": level})
        except Exception as e:
            logger.exception("Error getting logs config")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/logs/config', methods=['POST'])
    def update_logs_config():
        try:
            data = request.json or {}
            level = data.get("level")
            if not level:
                return jsonify({"error": "Missing level"}), 400
            set_log_level(level)
            logger.info(f"Log verbosity level updated to: {level}")
            return jsonify({"status": "success", "level": get_log_level()})
        except Exception as e:
            logger.exception("Error updating logs config")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/logs/active', methods=['GET'])
    def get_active_log():
        try:
            logger.trace("Fetching active log info")
            info = get_active_log_info()
            return jsonify(info)
        except Exception as e:
            logger.exception("Error reading active log")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/auth/status', methods=['GET'])
    def get_auth_status():
        try:
            status = get_auth_status_summary()
            return jsonify(status)
        except Exception as e:
            logger.exception("Error getting auth status")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/auth/config', methods=['GET'])
    def get_auth_config():
        try:
            schema = discover_baserow_schema()
            return jsonify(schema)
        except Exception as e:
            logger.exception("Error getting auth config")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/auth/test', methods=['POST'])
    def test_auth():
        try:
            data = request.json or {}
            host = data.get("host", "http://localhost")
            port = data.get("port", "")
            token_in = (data.get("token") or "").strip()
            token = os.getenv("BASEROW_TOKEN", "") if (not token_in or "•" in token_in) else token_in

            email_in = data.get("admin_email")
            admin_email = os.getenv("BASEROW_ADMIN_EMAIL", "") if (email_in is None or "•" in str(email_in)) else str(email_in).strip()

            pw_in = data.get("admin_password")
            admin_password = os.getenv("BASEROW_ADMIN_PASSWORD", "") if (pw_in is None or "•" in str(pw_in) or pw_in == "") else str(pw_in)

            database_id = data.get("database_id")
            table_overrides = data.get("table_ids") or {}

            api_url = combine_url_and_port(host, port)
            result = discover_baserow_schema(
                api_url=api_url,
                token=token,
                admin_email=admin_email,
                admin_password=admin_password,
                database_id=database_id,
                table_overrides=table_overrides
            )
            return jsonify(result)
        except Exception as e:
            logger.exception("Error testing auth config")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/auth/save', methods=['POST'])
    def save_auth():
        try:
            data = request.json or {}
            res = save_auth_configuration(data)
            if not res.get("success"):
                return jsonify(res), 400
            client.reload_config()
            return jsonify(res)
        except Exception as e:
            logger.exception("Error saving auth config")
            return jsonify({"error": str(e)}), 500

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    @app.route('/', methods=['GET'])
    def index():
        return "<h1>ERA BOM Backend API</h1><p>The frontend development server is running on <a href='http://localhost:3000'>http://localhost:3000</a>.</p>"


    # WI TEMPLATES ROUTES
    @app.route('/api/wi-templates', methods=['GET'])
    def list_wi_templates():
        try:
            templates = client.get_wi_templates()
            return jsonify(templates)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates', methods=['POST'])
    def upload_wi_template():
        try:
            if 'file' not in request.files:
                return jsonify({"error": "No file part"}), 400
            file = request.files['file']
            name = request.form.get("name", file.filename)
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400
            
            # Save file temporarily to scan
            temp_path = os.path.join(wi_templates_dir, file.filename)
            file.save(temp_path)
            
            from app.wi_export import scan_template
            import json
            scan_res = scan_template(temp_path)
            
            data = {
                "Name": name,
                "Filename": file.filename,
                "Valid": scan_res["valid"],
                "Tokens Found": json.dumps(scan_res["found"]),
                "Invalid Tokens": json.dumps(scan_res["invalid"]),
                "Approved": False
            }
            row = client.create_wi_template(data)
            return jsonify(row)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates/<int:template_id>', methods=['PUT'])
    def replace_wi_template(template_id):
        try:
            if 'file' not in request.files:
                return jsonify({"error": "No file part"}), 400
            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "No selected file"}), 400
            
            temp_path = os.path.join(wi_templates_dir, file.filename)
            file.save(temp_path)
            
            from app.wi_export import scan_template
            import json
            scan_res = scan_template(temp_path)
            
            data = {
                "Filename": file.filename,
                "Valid": scan_res["valid"],
                "Tokens Found": json.dumps(scan_res["found"]),
                "Invalid Tokens": json.dumps(scan_res["invalid"]),
                "Approved": False
            }
            row = client.update_wi_template(template_id, data)
            return jsonify(row)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates/<int:template_id>', methods=['DELETE'])
    def delete_wi_template(template_id):
        try:
            client.delete_wi_template(template_id)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates/<int:template_id>/approve', methods=['POST'])
    def approve_wi_template(template_id):
        try:
            data = request.json or {}
            approved = bool(data.get("approved", True))
            row = client.update_wi_template(template_id, {"Approved": approved})
            return jsonify(row)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates/config', methods=['GET'])
    def get_wi_config():
        try:
            import json
            config_path = wi_config_path
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))
            return jsonify({"filename_pattern": "ERA_{{pn}}_Rev{{revision}}_WI"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/wi-templates/config', methods=['POST'])
    def save_wi_config():
        try:
            import json
            data = request.json
            with open(wi_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items/<int:item_id>/instruction-sets/<int:set_index>/export-wi', methods=['POST'])
    def export_wi(item_id, set_index):
        try:
            data = request.json
            template_id = data.get("template_id")
            
            # 1. Fetch template metadata
            templates = client.get_wi_templates()
            template = next((t for t in templates if t["id"] == int(template_id)), None)
            if not template:
                return jsonify({"error": "Template not found"}), 404
                
            is_valid = bool(template.get("Valid", False))
            is_approved = bool(template.get("Approved", False))
            if not is_valid and not is_approved:
                return jsonify({"error": "Template is not approved or valid for use"}), 400
                
            template_path = os.path.join(wi_templates_dir, template["Filename"])
            if not os.path.exists(template_path):
                return jsonify({"error": "Template file missing"}), 404
                
            # 2. Fetch data
            item = client.get_item(item_id)
            details = client.get_instruction_set_details(item_id, set_index)
            
            # 3. Render
            from app.wi_export import render_wi_document
            import json
            out_filename = "export.docx"
            out_path = os.path.join(wi_templates_dir, out_filename)
            context = render_wi_document(template_path, out_path, item, details["steps"], client=client)
            
            # 4. Determine final filename using config
            config_path = wi_config_path
            pattern = "ERA_{{pn}}_Rev{{revision}}_WI"
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    pattern = json.load(f).get("filename_pattern", pattern)
                    
            final_name = pattern
            for k, v in context.items():
                if isinstance(v, str):
                    final_name = final_name.replace(f"{{{{{k}}}}}", v)
            if not final_name.endswith(".docx"):
                final_name += ".docx"
                
            from flask import send_file
            return send_file(out_path, as_attachment=True, download_name=final_name)
        except Exception as e:
            logger.exception("Error exporting WI document")
            return jsonify({"error": str(e)}), 500

    # BACKUP AND RESTORE ROUTES
    @app.route('/api/backup/list', methods=['GET'])
    def get_backups():
        try:
            from app.backup_manager import list_backups
            backups = list_backups()
            return jsonify(backups)
        except Exception as e:
            logger.exception("Error listing backups")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/create', methods=['POST'])
    def trigger_backup():
        try:
            from app.backup_manager import create_backup
            data = request.json or {}
            backup_type = data.get("type", "manual")
            note = data.get("note", "")
            manifest = create_backup(backup_type=backup_type, custom_note=note)
            return jsonify(manifest)
        except Exception as e:
            logger.exception("Error creating backup")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/restore', methods=['POST'])
    def trigger_restore():
        try:
            from app.backup_manager import restore_backup
            data = request.json or {}
            backup_id = data.get("backup_id")
            if not backup_id:
                return jsonify({"error": "Missing backup_id"}), 400
            res = restore_backup(backup_id)
            client.reload_config()
            return jsonify(res)
        except Exception as e:
            logger.exception("Error restoring backup")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/download/<backup_id>', methods=['GET'])
    def download_backup_zip(backup_id):
        try:
            from app.backup_manager import get_backups_dir
            zip_path = os.path.join(get_backups_dir(), f"{backup_id}.zip")
            if not os.path.exists(zip_path):
                return jsonify({"error": "Backup file not found"}), 404
            return send_file(zip_path, as_attachment=True, download_name=f"{backup_id}.zip")
        except Exception as e:
            logger.exception("Error downloading backup")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/<backup_id>', methods=['DELETE'])
    def delete_backup_file(backup_id):
        try:
            from app.backup_manager import delete_backup
            success = delete_backup(backup_id)
            if success:
                return jsonify({"status": "success", "backup_id": backup_id})
            return jsonify({"error": "Backup not found"}), 404
        except Exception as e:
            logger.exception("Error deleting backup")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/config', methods=['GET'])
    def get_backup_schedule_config():
        try:
            from app.backup_manager import load_backup_config
            cfg = load_backup_config()
            return jsonify(cfg)
        except Exception as e:
            logger.exception("Error getting backup config")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/backup/config', methods=['POST'])
    def update_backup_schedule_config():
        try:
            from app.backup_manager import save_backup_config
            data = request.json or {}
            updated = save_backup_config(data)
            return jsonify(updated)
        except Exception as e:
            logger.exception("Error updating backup config")
            return jsonify({"error": str(e)}), 500

    # Start automated backup daemon
    try:
        from app.backup_manager import backup_scheduler
        backup_scheduler.start()
    except Exception as e:
        logger.warning(f"Could not start backup scheduler daemon: {e}")

    return app
