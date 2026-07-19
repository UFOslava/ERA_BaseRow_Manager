import os
import shutil
import pytest
from app.main import create_app

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
