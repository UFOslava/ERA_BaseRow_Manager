"""Tests for the /api/bom/graph endpoints.

Covers both the Flask routes (mocking BaserowClient) and the BaserowClient
methods themselves (mocking requests.get).
"""
import pytest
from unittest.mock import patch, MagicMock
from app.main import create_app
from app.baserow_client import BaserowClient


# ---------------------------------------------------------------------------
# Shared mock data helpers
# ---------------------------------------------------------------------------

def _bom_resp(rows):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"results": rows, "next": None}
    m.raise_for_status.return_value = None
    return m


def _assembly_resp(edges):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"results": edges, "next": None}
    m.raise_for_status.return_value = None
    return m


# ---------------------------------------------------------------------------
# Route-level tests (mock BaserowClient entirely)
# ---------------------------------------------------------------------------

@patch('app.main.BaserowClient')
def test_get_graph_returns_nexus_nodes(mock_cls):
    """GET /api/bom/graph returns the list from get_graph_nexus_nodes()."""
    mock_instance = mock_cls.return_value
    nexus_nodes = [
        {
            "id": 1,
            "part_number": "30-00000",
            "description": "Top Assembly",
            "state": "Production Use",
            "pn_tag": {"name": "Mechanical Custom", "color": "#8b5cf6"},
            "image_url": None,
            "child_count": 2
        }
    ]
    mock_instance.get_graph_nexus_nodes.return_value = nexus_nodes

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph')
        assert response.status_code == 200
        assert response.json == nexus_nodes
        mock_instance.get_graph_nexus_nodes.assert_called_once()


@patch('app.main.BaserowClient')
def test_get_graph_returns_empty_list(mock_cls):
    """GET /api/bom/graph returns an empty list when there are no nexus nodes."""
    mock_instance = mock_cls.return_value
    mock_instance.get_graph_nexus_nodes.return_value = []

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph')
        assert response.status_code == 200
        assert response.json == []


@patch('app.main.BaserowClient')
def test_get_graph_handles_exception(mock_cls):
    """GET /api/bom/graph returns 500 when the client raises."""
    mock_instance = mock_cls.return_value
    mock_instance.get_graph_nexus_nodes.side_effect = Exception("Baserow down")

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph')
        assert response.status_code == 500
        assert "error" in response.json


@patch('app.main.BaserowClient')
def test_get_graph_children_success(mock_cls):
    """GET /api/bom/graph/<id>/children returns children list."""
    mock_instance = mock_cls.return_value
    children = [
        {
            "id": 2,
            "part_number": "40-00001",
            "description": "Capacitor",
            "state": "Engineering Use",
            "pn_tag": {"name": "Electrical COTS", "color": "#06b6d4"},
            "image_url": "https://example.com/img.jpg",
            "child_count": 0,
            "edge_id": 10,
            "quantity": 3,
            "length": 0.0
        }
    ]
    mock_instance.get_graph_children.return_value = children

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph/1/children')
        assert response.status_code == 200
        assert response.json == children
        mock_instance.get_graph_children.assert_called_once_with(1, mode='structural')


@patch('app.main.BaserowClient')
def test_get_graph_children_empty(mock_cls):
    """GET /api/bom/graph/<id>/children returns empty list for leaf nodes."""
    mock_instance = mock_cls.return_value
    mock_instance.get_graph_children.return_value = []

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph/99/children')
        assert response.status_code == 200
        assert response.json == []
        mock_instance.get_graph_children.assert_called_once_with(99, mode='structural')


@patch('app.main.BaserowClient')
def test_get_graph_children_handles_exception(mock_cls):
    """GET /api/bom/graph/<id>/children returns 500 when the client raises."""
    mock_instance = mock_cls.return_value
    mock_instance.get_graph_children.side_effect = RuntimeError("timeout")

    app = create_app()
    with app.test_client() as test_client:
        response = test_client.get('/api/bom/graph/5/children')
        assert response.status_code == 500
        assert "error" in response.json


# ---------------------------------------------------------------------------
# BaserowClient unit tests (mock requests.get)
# ---------------------------------------------------------------------------

@patch('app.baserow_client.requests.get')
def test_get_graph_nexus_nodes_basic(mock_get):
    """get_graph_nexus_nodes returns only items not referenced as children."""
    bom_rows = [
        {
            "id": 1,
            "Part Number": "30-00001",
            "Item description": "Assembly A",
            "State": [{"value": "Production Use"}],
            "Image": []
        },
        {
            "id": 2,
            "Part Number": "40-00010",
            "Item description": "Capacitor",
            "State": [{"value": "Engineering Use"}],
            "Image": []
        },
    ]
    # Edge: item 1 contains item 2 -> item 2 is a child, item 1 is the nexus
    assembly_edges = [
        {
            "id": 10,
            "Item": [{"id": 1}],
            "Contains": [{"id": 2}],
            "Amount of Times": 2,
            "Measurement": None
        }
    ]

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    result = client.get_graph_nexus_nodes()

    assert len(result) == 1
    node = result[0]
    assert node["id"] == 1
    assert node["part_number"] == "30-00001"
    assert node["description"] == "Assembly A"
    assert node["state"] == "Production Use"
    assert node["child_count"] == 1   # item 2 is its direct child
    assert node["image_url"] is None


@patch('app.baserow_client.requests.get')
def test_get_graph_nexus_nodes_with_image(mock_get):
    """get_graph_nexus_nodes picks up the first image url."""
    bom_rows = [
        {
            "id": 5,
            "Part Number": "55-00001",
            "Item description": "Kit",
            "State": [],
            "Image": [
                {"url": "https://cdn.example.com/photo.jpg"},
                {"url": "https://cdn.example.com/other.jpg"}
            ]
        }
    ]
    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp([])]

    client = BaserowClient()
    result = client.get_graph_nexus_nodes()

    assert len(result) == 1
    assert result[0]["image_url"] == "https://cdn.example.com/photo.jpg"


@patch('app.baserow_client.requests.get')
def test_get_graph_nexus_nodes_empty_tables(mock_get):
    """get_graph_nexus_nodes returns empty list when BOM is empty."""
    mock_get.side_effect = [_bom_resp([]), _assembly_resp([])]

    client = BaserowClient()
    result = client.get_graph_nexus_nodes()
    assert result == []


@patch('app.baserow_client.requests.get')
def test_get_graph_nexus_nodes_sorted_by_id(mock_get):
    """get_graph_nexus_nodes result is sorted ascending by id."""
    bom_rows = [
        {"id": 10, "Part Number": "30-00010", "Item description": "Z Item", "State": [], "Image": []},
        {"id": 3,  "Part Number": "30-00003", "Item description": "A Item", "State": [], "Image": []},
        {"id": 7,  "Part Number": "30-00007", "Item description": "M Item", "State": [], "Image": []},
    ]
    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp([])]

    client = BaserowClient()
    result = client.get_graph_nexus_nodes()

    ids = [r["id"] for r in result]
    assert ids == sorted(ids)


@patch('app.baserow_client.requests.get')
def test_get_graph_children_basic(mock_get):
    """get_graph_children returns the correct children for a given item_id."""
    bom_rows = [
        {
            "id": 1,
            "Part Number": "30-00001",
            "Item description": "Assembly",
            "State": [{"value": "Production Use"}],
            "Image": []
        },
        {
            "id": 2,
            "Part Number": "40-00002",
            "Item description": "Resistor",
            "State": [{"value": "Engineering Use"}],
            "Image": [{"url": "https://cdn.example.com/res.jpg"}]
        },
        {
            "id": 3,
            "Part Number": "40-00003",
            "Item description": "Capacitor",
            "State": [],
            "Image": []
        }
    ]
    assembly_edges = [
        {
            "id": 10,
            "Item": [{"id": 1}],
            "Contains": [{"id": 2}],
            "Amount of Times": 4,
            "Measurement": None
        },
        {
            "id": 11,
            "Item": [{"id": 1}],
            "Contains": [{"id": 3}],
            "Amount of Times": 1,
            "Measurement": 150.0
        }
    ]

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    result = client.get_graph_children(1)

    assert len(result) == 2
    # Sorted by id: child 2 first, then child 3
    c2 = result[0]
    assert c2["id"] == 2
    assert c2["part_number"] == "40-00002"
    assert c2["quantity"] == 4
    assert c2["length"] == 0.0
    assert c2["edge_id"] == 10
    assert c2["image_url"] == "https://cdn.example.com/res.jpg"
    assert c2["child_count"] == 0
    assert c2["state"] == "Engineering Use"

    c3 = result[1]
    assert c3["id"] == 3
    assert c3["quantity"] == 1
    assert c3["length"] == 150.0
    assert c3["edge_id"] == 11
    assert c3["image_url"] is None


@patch('app.baserow_client.requests.get')
def test_get_graph_children_counts_grandchildren(mock_get):
    """child_count reflects how many direct children the child itself has."""
    bom_rows = [
        {"id": 1, "Part Number": "30-00001", "Item description": "Root", "State": [], "Image": []},
        {"id": 2, "Part Number": "30-00002", "Item description": "Sub-assembly", "State": [], "Image": []},
        {"id": 3, "Part Number": "40-00003", "Item description": "Part A", "State": [], "Image": []},
        {"id": 4, "Part Number": "40-00004", "Item description": "Part B", "State": [], "Image": []},
    ]
    assembly_edges = [
        # Root -> Sub-assembly
        {"id": 10, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 1, "Measurement": None},
        # Sub-assembly -> Part A
        {"id": 11, "Item": [{"id": 2}], "Contains": [{"id": 3}], "Amount of Times": 2, "Measurement": None},
        # Sub-assembly -> Part B
        {"id": 12, "Item": [{"id": 2}], "Contains": [{"id": 4}], "Amount of Times": 3, "Measurement": None},
    ]

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    result = client.get_graph_children(1)  # children of Root

    assert len(result) == 1
    sub = result[0]
    assert sub["id"] == 2
    assert sub["child_count"] == 2  # Sub-assembly has 2 children


@patch('app.baserow_client.requests.get')
def test_get_graph_children_no_children(mock_get):
    """get_graph_children returns empty list for a leaf item."""
    bom_rows = [
        {"id": 5, "Part Number": "40-00005", "Item description": "Leaf", "State": [], "Image": []}
    ]
    assembly_edges = []

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    result = client.get_graph_children(5)
    assert result == []


@patch('app.baserow_client.requests.get')
def test_get_graph_children_skips_unknown_bom_ids(mock_get):
    """get_graph_children silently skips edges referencing missing BOM rows."""
    bom_rows = [
        {"id": 1, "Part Number": "30-00001", "Item description": "Root", "State": [], "Image": []}
        # child id 999 is NOT in bom_rows intentionally
    ]
    assembly_edges = [
        {"id": 20, "Item": [{"id": 1}], "Contains": [{"id": 999}], "Amount of Times": 1, "Measurement": None}
    ]

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    result = client.get_graph_children(1)
    # The child references a BOM id not in bom_map -- must be skipped
    assert result == []


@patch('app.baserow_client.requests.get')
def test_get_graph_nexus_nodes_procurement_mode(mock_get):
    """In procurement mode, only items inside Purchase Kits are children; other items join top level."""
    bom_rows = [
        {"id": 1, "Part Number": "30-00001", "Item description": "Root Assembly", "State": [], "Image": [], "Purchase Kit": False},
        {"id": 2, "Part Number": "50-00001", "Item description": "Cable Kit", "State": [], "Image": [], "Purchase Kit": True},
        {"id": 3, "Part Number": "40-00001", "Item description": "Kit Component", "State": [], "Image": [], "Purchase Kit": False},
        {"id": 4, "Part Number": "40-00002", "Item description": "Assembly Component", "State": [], "Image": [], "Purchase Kit": False},
    ]
    assembly_edges = [
        # Root Assembly contains Assembly Component and Cable Kit
        {"id": 10, "Item": [{"id": 1}], "Contains": [{"id": 4}], "Amount of Times": 1},
        {"id": 11, "Item": [{"id": 1}], "Contains": [{"id": 2}], "Amount of Times": 1},
        # Cable Kit contains Kit Component
        {"id": 12, "Item": [{"id": 2}], "Contains": [{"id": 3}], "Amount of Times": 2},
    ]

    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]

    client = BaserowClient()
    # In procurement mode: only item 3 (inside kit 2) is a child. Items 1, 2, 4 are top-level nexus nodes!
    proc_nodes = client.get_graph_nexus_nodes(mode="procurement")
    proc_ids = [n["id"] for n in proc_nodes]
    assert 1 in proc_ids
    assert 2 in proc_ids
    assert 4 in proc_ids
    assert 3 not in proc_ids

    # Kit node (2) has child_count = 1 in procurement mode; non-kit nodes (1, 4) have child_count = 0
    kit_node = next(n for n in proc_nodes if n["id"] == 2)
    assert kit_node["child_count"] == 1
    root_node = next(n for n in proc_nodes if n["id"] == 1)
    assert root_node["child_count"] == 0

    # In structural mode: items 2, 4 (inside assembly 1) are children. Items 1 (assembly) and 3 (kit component without regular parent) are root nexus.
    mock_get.side_effect = [_bom_resp(bom_rows), _assembly_resp(assembly_edges)]
    struct_nodes = client.get_graph_nexus_nodes(mode="structural")
    struct_ids = [n["id"] for n in struct_nodes]
    assert set(struct_ids) == {1, 3}
    assert next(n for n in struct_nodes if n["id"] == 1)["child_count"] == 2  # Root assembly has 2 structural children
