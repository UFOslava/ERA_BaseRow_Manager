import pytest
import os
from app.main import create_app

@pytest.fixture
def client():
    # Use a temporary file database for testing
    db_file = "test_parts.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass

    app = create_app(db_path=db_file)
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

    # Cleanup database file after tests
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
