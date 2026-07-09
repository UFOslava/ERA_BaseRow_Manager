from flask import Flask, request, jsonify
from flask_cors import CORS
from app.database import Database
import os

def create_app(db_path=None):
    app = Flask(__name__)
    CORS(app)

    db = Database(db_path)
    db.seed_data()

    @app.route('/api/parts', methods=['GET'])
    def get_parts():
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM parts")
        parts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(parts)

    @app.route('/api/parts/<int:part_id>', methods=['GET'])
    def get_part(part_id):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return jsonify({"error": "Part not found"}), 404
        return jsonify(dict(row))

    @app.route('/api/parts', methods=['POST'])
    def create_part():
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description', '')
        parent_id = data.get('parent_id')

        if not name:
            return jsonify({"error": "Name is required"}), 400

        conn = db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO parts (name, description, parent_id) VALUES (?, ?, ?)",
                (name, description, parent_id)
            )
            part_id = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
            new_part = dict(cursor.fetchone())
            return jsonify(new_part), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        finally:
            conn.close()

    @app.route('/api/parts/<int:part_id>', methods=['PUT'])
    def update_part(part_id):
        data = request.get_json() or {}
        name = data.get('name')
        description = data.get('description')
        parent_id = data.get('parent_id')

        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"error": "Part not found"}), 404

        try:
            updates = []
            params = []
            if name is not None:
                updates.append("name = ?")
                params.append(name)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if parent_id is not None:
                updates.append("parent_id = ?")
                params.append(parent_id)

            if updates:
                params.append(part_id)
                cursor.execute(
                    f"UPDATE parts SET {', '.join(updates)} WHERE id = ?",
                    tuple(params)
                )
                conn.commit()

            cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
            updated_part = dict(cursor.fetchone())
            return jsonify(updated_part)
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        finally:
            conn.close()

    @app.route('/api/parts/<int:part_id>', methods=['DELETE'])
    def delete_part(part_id):
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"error": "Part not found"}), 404

        cursor.execute("DELETE FROM parts WHERE id = ?", (part_id,))
        conn.commit()
        conn.close()
        return jsonify({"message": f"Part {part_id} deleted successfully"})

    @app.route('/api/parts/move', methods=['POST'])
    def move_part():
        data = request.get_json() or {}
        part_id = data.get('part_id')
        new_parent_id = data.get('new_parent_id')

        if part_id is None:
            return jsonify({"error": "part_id is required"}), 400

        if part_id == new_parent_id:
            return jsonify({"error": "A part cannot be its own parent"}), 400

        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM parts WHERE id = ?", (part_id,))
        if cursor.fetchone() is None:
            conn.close()
            return jsonify({"error": "Part not found"}), 404

        if new_parent_id is not None:
            cursor.execute("SELECT * FROM parts WHERE id = ?", (new_parent_id,))
            if cursor.fetchone() is None:
                conn.close()
                return jsonify({"error": "Parent part not found"}), 404

            # Detect circular reference up the chain
            curr_parent = new_parent_id
            while curr_parent is not None:
                cursor.execute("SELECT parent_id FROM parts WHERE id = ?", (curr_parent,))
                row = cursor.fetchone()
                if row is None:
                    break
                curr_parent = row['parent_id']
                if curr_parent == part_id:
                    conn.close()
                    return jsonify({"error": "Circular reference detected: Parent cannot be a descendant of the child"}), 400

        try:
            cursor.execute("UPDATE parts SET parent_id = ? WHERE id = ?", (new_parent_id, part_id))
            conn.commit()
            return jsonify({"message": "Part moved successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        finally:
            conn.close()

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "healthy"})

    return app
