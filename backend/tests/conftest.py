import os
import shutil
import pytest
from flask.testing import FlaskClient
from app.main import create_app

DEFAULT_TEST_ERA_API_TOKEN = "test-era-api-token"
os.environ.setdefault("ERA_API_TOKEN", DEFAULT_TEST_ERA_API_TOKEN)

_orig_client_open = FlaskClient.open

def _auth_client_open(self, *args, **kwargs):
    if "headers" not in kwargs:
        token = os.getenv("ERA_API_TOKEN", "")
        if token:
            kwargs["headers"] = {"Authorization": f"Bearer {token}"}
    return _orig_client_open(self, *args, **kwargs)

FlaskClient.open = _auth_client_open

@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_logs():
    yield
    from app.logger import _global_handler
    if _global_handler:
        import logging
        logging.getLogger().removeHandler(_global_handler)
        _global_handler.close()
    
    test_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "test"))
    if os.path.exists(test_log_dir):
        try:
            shutil.rmtree(test_log_dir)
        except Exception:
            pass
