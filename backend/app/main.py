from flask import Flask, jsonify, request
from flask_cors import CORS
from app.baserow_client import BaserowClient

def create_app(db_path=None):
    app = Flask(__name__)
    CORS(app)

    client = BaserowClient()

    @app.route('/api/bom/tree', methods=['GET'])
    def get_bom_tree():
        try:
            tree = client.get_bom_tree()
            return jsonify(tree)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/bom/items', methods=['GET'])
    def get_items():
        try:
            items = client.get_items()
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

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    @app.route('/', methods=['GET'])
    def index():
        return "<h1>ERA BOM Backend API</h1><p>The frontend development server is running on <a href='http://localhost:3000'>http://localhost:3000</a>.</p>"

    return app
