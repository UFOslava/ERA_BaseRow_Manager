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

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    @app.route('/', methods=['GET'])
    def index():
        return "<h1>ERA BOM Backend API</h1><p>The frontend development server is running on <a href='http://localhost:3000'>http://localhost:3000</a>.</p>"

    return app
