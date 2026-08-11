import os

file_path = "backend/app/main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_code = """
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
            temp_path = os.path.join("backend/wi_templates", file.filename)
            file.save(temp_path)
            
            from app.wi_export import scan_template
            import json
            scan_res = scan_template(temp_path)
            
            data = {
                "Name": name,
                "Filename": file.filename,
                "Valid": scan_res["valid"],
                "Tokens Found": json.dumps(scan_res["found"]),
                "Invalid Tokens": json.dumps(scan_res["invalid"])
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
            
            temp_path = os.path.join("backend/wi_templates", file.filename)
            file.save(temp_path)
            
            from app.wi_export import scan_template
            import json
            scan_res = scan_template(temp_path)
            
            data = {
                "Filename": file.filename,
                "Valid": scan_res["valid"],
                "Tokens Found": json.dumps(scan_res["found"]),
                "Invalid Tokens": json.dumps(scan_res["invalid"])
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

    @app.route('/api/wi-templates/config', methods=['GET'])
    def get_wi_config():
        try:
            import json
            config_path = "backend/wi_export_config.json"
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
            with open("backend/wi_export_config.json", "w", encoding="utf-8") as f:
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
                
            template_path = os.path.join("backend/wi_templates", template["Filename"])
            if not os.path.exists(template_path):
                return jsonify({"error": "Template file missing"}), 404
                
            # 2. Fetch data
            item = client.get_item(item_id)
            details = client.get_instruction_set_details(item_id, set_index)
            
            # 3. Render
            from app.wi_export import render_wi_document
            import json
            out_filename = "export.docx"
            out_path = os.path.join("backend/wi_templates", out_filename)
            context = render_wi_document(template_path, out_path, item, details["steps"])
            
            # 4. Determine final filename using config
            config_path = "backend/wi_export_config.json"
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
            return jsonify({"error": str(e)}), 500
"""

marker = "    return app"
if "WI TEMPLATES ROUTES" not in content:
    content = content.replace(marker, new_code + "\n" + marker)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Routes added successfully.")
else:
    print("Routes already exist.")
