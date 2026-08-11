import pytest
import json
from unittest.mock import patch, MagicMock
from app.main import create_app
from app.wi_export import scan_template, evaluate_instruction_text

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
    mock_para.text = "Here is a {{ item_pn }} and {% for step in steps %} with {{ unknown_token | filter:123 }} {% endfor %}"
    mock_doc.paragraphs = [mock_para]
    mock_doc.tables = []
    mock_document.return_value = mock_doc

    result = scan_template("dummy.docx")
    
    assert not result["valid"]
    assert "item_pn" in result["found"]
    assert "for" in result["found"]
    assert "step" in result["found"]
    assert "steps" in result["found"]
    assert "unknown_token" in result["found"]
    assert "unknown_token" in result["invalid"]

def test_evaluate_instruction_text():
    step = {
        "Instruction Text": "Attach [PARTS] using [TOOLS].",
        "parts": [{"part_name": "Screw", "part_qty": 2}],
        "tools": [{"tool_name": "Screwdriver"}]
    }
    result = evaluate_instruction_text(step)
    assert result == "Attach Screw (2x) using Screwdriver."

@patch('app.baserow_client.BaserowClient.get_wi_templates')
def test_get_wi_templates(mock_get, client):
    mock_get.return_value = [{"id": 1, "Name": "Test", "Valid": True}]
    response = client.get('/api/wi-templates')
    assert response.status_code == 200
    assert response.json[0]["Name"] == "Test"

@patch('app.baserow_client.BaserowClient.create_wi_template')
@patch('app.wi_export.scan_template')
@patch('werkzeug.datastructures.FileStorage.save')
def test_upload_wi_template(mock_save, mock_scan, mock_create, client):
    mock_scan.return_value = {"valid": True, "found": ["pn"], "invalid": []}
    mock_create.return_value = {"id": 1, "Name": "Test", "Valid": True}
    
    import io
    data = {'file': (io.BytesIO(b'dummy'), 'test.docx'), 'name': 'Test'}
    response = client.post('/api/wi-templates', data=data, content_type='multipart/form-data')
    if response.status_code != 200:
        print(response.json)
    assert response.status_code == 200
    assert response.json["Name"] == "Test"

@patch('app.baserow_client.BaserowClient.get_item')
@patch('app.baserow_client.BaserowClient.get_instruction_set_details')
@patch('app.baserow_client.BaserowClient.get_wi_templates')
@patch('app.wi_export.render_wi_document')
@patch('os.path.exists')
@patch('flask.send_file')
def test_export_wi(mock_send_file, mock_exists, mock_render, mock_get_templates, mock_details, mock_get_item, client):
    mock_get_templates.return_value = [{"id": 1, "Filename": "test.docx", "Valid": True}]
    mock_exists.side_effect = lambda path: not path.endswith('.json')
    mock_get_item.return_value = {"Part Number": "123", "Revision": "A", "Description": "Test"}
    mock_details.return_value = {"steps": []}
    mock_render.return_value = {"pn": "123", "revision": "A"}
    mock_send_file.return_value = "file_content"

    response = client.post('/api/bom/items/1/instruction-sets/0/export-wi', json={"template_id": 1})
    if response.status_code != 200:
        print(response.json)
    assert response.status_code == 200
