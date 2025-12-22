from flask import Flask, render_template, request, jsonify
from baserow_client import BaserowClient

app = Flask(__name__)
client = BaserowClient()

@app.route('/')
def index():
    roots = client.get_roots()
    return render_template('index.html', roots=roots)

@app.route('/children/<int:parent_id>')
def children(parent_id):
    children_list = client.get_children(parent_id)
    return render_template('tree_node.html', parts=children_list)

@app.route('/move', methods=['POST'])
def move():
    # Expecting JSON or Form data
    # item_id: ID of the part being dragged
    # new_parent_id: ID of the new parent part
    # edge_id: The ID of the edge row (if it was a child) - Optional

    data = request.form if request.form else request.json

    item_id = data.get('item_id')
    new_parent_id = data.get('new_parent_id')
    edge_id = data.get('edge_id') # Can be None/Empty

    if not item_id or not new_parent_id:
        return jsonify({"error": "Missing parameters"}), 400

    try:
        result = client.move_item(item_id, new_parent_id, edge_id)
        # Return the new edge_id so frontend can update
        return jsonify({"status": "success", "edge_id": result["edge_id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
