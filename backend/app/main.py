import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from app.baserow_client import BaserowClient
from app.logger import setup_logging, get_log_level, set_log_level, get_active_log_info

logger = logging.getLogger(__name__)

def create_app(db_path=None):
    setup_logging()
    logger.info("Starting up Flask application")
    app = Flask(__name__)
    CORS(app)

    client = BaserowClient()

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

    @app.route('/api/bom/tree', methods=['GET'])
    def get_bom_tree():
        try:
            logger.trace("GET /api/bom/tree requested")
            limit = min(int(request.args.get('limit', 100)), 100)
            tree = client.get_bom_tree()
            truncated_tree = limit_tree_nodes(tree, limit)
            return jsonify(truncated_tree)
        except Exception as e:
            logger.exception("Error getting BOM tree")
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items', methods=['GET'])
    def get_items():
        try:
            search = request.args.get('search', '').strip()
            limit = min(int(request.args.get('limit', 100)), 100)
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
                "Item description": item.get("Item description"),
                "Image": item.get("Image", []),
                "External PN": item.get("External PN"),
                "Notes": item.get("Notes"),
                "Search helper": item.get("Search helper")
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
            manufacturers = client.get_manufacturers()
            result = [{"id": m["id"], "name": m.get("Name", "Unknown")} for m in manufacturers]
            return jsonify(result)
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
            
            edge = client.create_assembly(parent_id, child_id, quantity, length, pcb_symbol)
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
            
            edge = client.update_assembly(edge_id, quantity, length, pcb_symbol)
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

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    @app.route('/', methods=['GET'])
    def index():
        return "<h1>ERA BOM Backend API</h1><p>The frontend development server is running on <a href='http://localhost:3000'>http://localhost:3000</a>.</p>"

    return app
