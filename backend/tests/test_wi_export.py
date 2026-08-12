import pytest
import json
from unittest.mock import patch, MagicMock
from app.main import create_app
from app.wi_export import scan_template, evaluate_instruction_text, get_recursive_flat_bom, preprocess_docx_runs

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch('app.wi_export.Document')
def test_scan_template(mock_document):
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "Here is {{ item_pn }}, {{ loop.index }}, and {{ part.pn }} with {{ unknown_token | width:123 }}"
    mock_doc.paragraphs = [mock_para]
    mock_doc.tables = []
    mock_doc.sections = []
    mock_document.return_value = mock_doc

    result = scan_template("dummy.docx")
    
    assert not result["valid"]
    assert "item_pn" in result["found"]
    assert "part" in result["found"]
    assert "unknown_token" in result["found"]
    assert "unknown_token" in result["invalid"]

def test_evaluate_instruction_text():
    step = {
        "description": "Attach {a.1} using {t.1}.",
        "action": "Assemble",
        "part_slots": [{"id": 1, "quantity": 2, "description": "Screw", "pn": "SC-01"}],
        "tool_slots": [{"id": 2, "quantity": 1, "description": "Screwdriver", "pn": "SD-01"}]
    }
    result = evaluate_instruction_text(step)
    assert 'Screw' in result
    assert 'SC-01' in result
    assert 'Screwdriver' in result

def test_preprocess_docx_runs():
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_run = MagicMock()
    mock_run.text = "Here is a {{ image | width:8cm }}"
    mock_para.runs = [mock_run]
    mock_doc.paragraphs = [mock_para]
    mock_doc.tables = []
    mock_doc.sections = []
    
    preprocess_docx_runs(mock_doc)
    assert "width('8cm')" in mock_run.text

@patch('app.baserow_client.BaserowClient.get_wi_templates')
def test_get_wi_templates(mock_get, client):
    mock_get.return_value = [{"id": 1, "Name": "Test", "Valid": True, "Approved": False}]
    response = client.get('/api/wi-templates')
    assert response.status_code == 200
    assert response.json[0]["Name"] == "Test"

@patch('app.baserow_client.BaserowClient.create_wi_template')
@patch('app.wi_export.scan_template')
@patch('werkzeug.datastructures.FileStorage.save')
def test_upload_wi_template(mock_save, mock_scan, mock_create, client):
    mock_scan.return_value = {"valid": True, "found": ["pn"], "invalid": []}
    mock_create.return_value = {"id": 1, "Name": "Test", "Valid": True, "Approved": False}
    
    import io
    data = {'file': (io.BytesIO(b'dummy'), 'test.docx'), 'name': 'Test'}
    response = client.post('/api/wi-templates', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    assert response.json["Name"] == "Test"

@patch('app.baserow_client.BaserowClient.update_wi_template')
def test_approve_wi_template(mock_update, client):
    mock_update.return_value = {"id": 1, "Approved": True}
    response = client.post('/api/wi-templates/1/approve', json={"approved": True})
    assert response.status_code == 200
    assert response.json["Approved"] is True
    mock_update.assert_called_once_with(1, {"Approved": True})

def test_get_recursive_flat_bom():
    mock_client = MagicMock()
    mock_client.table_bom = "bom"
    mock_client.table_assembly = "assembly"
    mock_client.table_instructions = "instructions"
    
    # Mock tables data
    mock_client._get_all_rows.side_effect = lambda table_name: {
        "bom": [
            {"id": 1, "Part Number": "P01", "Revision": "A", "Item description": "Parent Item"},
            {"id": 2, "Part Number": "P02", "Revision": "B", "Item description": "Child Item 1"},
            {"id": 3, "Part Number": "P03", "Revision": "C", "Item description": "Child Item 2 (Blackbox)", "Blackbox": True},
            {"id": 4, "Part Number": "P04", "Revision": "A", "Item description": "Child Item 3"}
        ],
        "assembly": [
            {"id": 101, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 2},
            {"id": 102, "Item": [{"id": 1}], "Contains": [{"id": 3}], "Amount of Times": 1},
            {"id": 103, "Item": [{"id": 2}], "Contains": [{"id": 4}], "Amount of Times": 3}
        ],
        "instructions": [
            {"id": 201, "Parent Item": [{"id": 3}]} # Item 3 has instructions, so traversal should stop there
        ]
    }[table_name]
    
    bom_items = get_recursive_flat_bom(mock_client, 1)
    
    # Traversal should traverse 1 -> 2 -> 4, and 1 -> 3 (stopping at 3 because it is a blackbox and has instructions)
    # We should have child 2 (quantity 2), child 4 (quantity 2 * 3 = 6), and child 3 (quantity 1)
    item_map = {item["id"]: item for item in bom_items}
    assert 2 in item_map
    assert 3 in item_map
    assert 4 in item_map
    
    assert item_map[2]["quantity"] == 2
    assert item_map[3]["quantity"] == 1
    assert item_map[4]["quantity"] == 6

@patch('app.baserow_client.BaserowClient.get_item')
@patch('app.baserow_client.BaserowClient.get_instruction_set_details')
@patch('app.baserow_client.BaserowClient.get_wi_templates')
@patch('app.wi_export.render_wi_document')
@patch('os.path.exists')
@patch('flask.send_file')
def test_export_wi(mock_send_file, mock_exists, mock_render, mock_get_templates, mock_details, mock_get_item, client):
    mock_get_templates.return_value = [{"id": 1, "Filename": "test.docx", "Valid": True, "Approved": False}]
    mock_exists.side_effect = lambda path: not path.endswith('.json')
    mock_get_item.return_value = {"Part Number": "123", "Revision": "A", "Description": "Test"}
    mock_details.return_value = {"steps": []}
    mock_render.return_value = {"pn": "123", "revision": "A"}
    mock_send_file.return_value = "file_content"

    response = client.post('/api/bom/items/1/instruction-sets/0/export-wi', json={"template_id": 1})
    assert response.status_code == 200
