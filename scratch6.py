import re

with open('backend/app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

bad_uom = '''    @app.route('/api/bom/uom', methods=['GET'])
def get_uoms():
    try:
        data = baserow.get_uoms()
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error fetching UOMs: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/bom/tree', methods=['GET'])'''

good_uom = '''    @app.route('/api/bom/uom', methods=['GET'])
    def get_uoms():
        try:
            data = baserow.get_uoms()
            return jsonify(data), 200
        except Exception as e:
            logger.error(f"Error fetching UOMs: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/api/bom/tree', methods=['GET'])'''

content = content.replace(bad_uom, good_uom)

with open('backend/app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
