from flask import Flask, jsonify
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

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    @app.route('/', methods=['GET'])
    def index():
        return "<h1>ERA BOM Backend API</h1><p>The frontend development server is running on <a href='http://localhost:3000'>http://localhost:3000</a>.</p>"

    return app
