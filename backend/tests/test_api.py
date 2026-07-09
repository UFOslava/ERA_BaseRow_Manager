import json

def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}

def test_get_parts(client):
    response = client.get('/api/parts')
    assert response.status_code == 200
    parts = response.json
    assert len(parts) > 0
    # Seeded data checks
    assert parts[0]["name"] == "Root Assembly"
    assert parts[0]["parent_id"] is None

def test_get_part(client):
    response = client.get('/api/parts/1')
    assert response.status_code == 200
    assert response.json["name"] == "Root Assembly"

    response = client.get('/api/parts/999')
    assert response.status_code == 404

def test_create_part(client):
    new_part = {"name": "Test Part", "description": "Test Desc", "parent_id": 1}
    response = client.post('/api/parts', json=new_part)
    assert response.status_code == 201
    assert response.json["name"] == "Test Part"
    assert response.json["parent_id"] == 1
    assert "id" in response.json

    # Bad request (missing name)
    response = client.post('/api/parts', json={"description": "No name"})
    assert response.status_code == 400

def test_update_part(client):
    update_data = {"name": "Updated Assembly", "description": "Updated Desc"}
    response = client.put('/api/parts/1', json=update_data)
    assert response.status_code == 200
    assert response.json["name"] == "Updated Assembly"
    assert response.json["description"] == "Updated Desc"

    response = client.put('/api/parts/999', json=update_data)
    assert response.status_code == 404

def test_delete_part(client):
    # First create a part to delete
    new_part = {"name": "To Delete"}
    response = client.post('/api/parts', json=new_part)
    part_id = response.json["id"]

    response = client.delete(f'/api/parts/{part_id}')
    assert response.status_code == 200
    assert "deleted successfully" in response.json["message"]

    # Delete non-existing
    response = client.delete('/api/parts/999')
    assert response.status_code == 404

def test_move_part(client):
    # Move Part A1 (id=4, parent=2) to Sub-assembly B (id=3)
    move_data = {"part_id": 4, "new_parent_id": 3}
    response = client.post('/api/parts/move', json=move_data)
    assert response.status_code == 200
    assert response.json["message"] == "Part moved successfully"

    # Verify move
    response = client.get('/api/parts/4')
    assert response.json["parent_id"] == 3

    # Error cases
    # Circular reference (Move Root Assembly (1) under Sub-assembly A (2))
    response = client.post('/api/parts/move', json={"part_id": 1, "new_parent_id": 2})
    assert response.status_code == 400
    assert "Circular reference" in response.json["error"]

    # Self parenting
    response = client.post('/api/parts/move', json={"part_id": 2, "new_parent_id": 2})
    assert response.status_code == 400

    # Missing parameters
    response = client.post('/api/parts/move', json={})
    assert response.status_code == 400
