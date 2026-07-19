import os
import glob
import json
import logging
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from app.logger import (
    CustomRotatingFileHandler,
    setup_logging,
    get_log_level,
    set_log_level,
    get_active_log_info,
    TRACE_LEVEL_NUM
)
from app.main import create_app

def test_logger_initialization_and_write(tmp_path):
    log_dir = tmp_path / "logs"
    handler = CustomRotatingFileHandler(log_dir=str(log_dir))
    
    # Check that a log file was created
    log_files = glob.glob(os.path.join(str(log_dir), "log_*.log"))
    assert len(log_files) == 1
    
    # Configure logging with this handler
    logger = logging.getLogger("test_logger_init")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    
    test_msg = "Hello World Log Entry"
    logger.debug(test_msg)
    handler.close()
    
    with open(log_files[0], "r", encoding="utf-8") as f:
        content = f.read()
    assert test_msg in content

def test_logger_custom_trace(tmp_path):
    log_dir = tmp_path / "logs"
    handler = CustomRotatingFileHandler(log_dir=str(log_dir))
    
    logger = logging.getLogger("test_logger_trace")
    logger.setLevel(TRACE_LEVEL_NUM)
    logger.addHandler(handler)
    
    # Should write to log
    logger.trace("This is a trace log")
    
    handler.close()
    
    log_files = glob.glob(os.path.join(str(log_dir), "log_*.log"))
    with open(log_files[0], "r", encoding="utf-8") as f:
        content = f.read()
    assert "This is a trace log" in content

def test_date_based_rotation(tmp_path):
    log_dir = tmp_path / "logs"
    
    # Mock clock
    current_time = datetime(2026, 7, 19, 12, 0, 0)
    def mock_now():
        return current_time
        
    handler = CustomRotatingFileHandler(log_dir=str(log_dir), now_func=mock_now)
    
    log_files = glob.glob(os.path.join(str(log_dir), "log_*.log"))
    assert len(log_files) == 1
    assert "log_20260719_120000.log" in os.path.basename(log_files[0])
    
    # Change date
    current_time = datetime(2026, 7, 20, 0, 1, 0)
    
    # Emit a record
    record = logging.LogRecord("test", logging.INFO, "path", 10, "Message after date change", (), None)
    handler.emit(record)
    
    # There should now be two log files
    log_files = glob.glob(os.path.join(str(log_dir), "log_*.log"))
    assert len(log_files) == 2
    
    filenames = [os.path.basename(f) for f in log_files]
    assert "log_20260719_120000.log" in filenames
    assert "log_20260720_000100.log" in filenames
    
    handler.close()

def test_cleanup_over_a_year_old(tmp_path):
    log_dir = tmp_path / "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Create an old file
    old_file_path = os.path.join(str(log_dir), "log_20240719_120000.log")
    with open(old_file_path, "w") as f:
        f.write("old log")
    
    # Set back the file modification time by 400 days to test fallback
    past_time = time.time() - (400 * 24 * 3600)
    os.utime(old_file_path, (past_time, past_time))
    
    # Create a new file
    current_time = datetime(2026, 7, 19, 12, 0, 0)
    def mock_now():
        return current_time
        
    handler = CustomRotatingFileHandler(log_dir=str(log_dir), now_func=mock_now)
    
    # Check that old file was deleted during init
    assert not os.path.exists(old_file_path)
    
    handler.close()

def test_cleanup_total_size_over_100mb(tmp_path):
    log_dir = tmp_path / "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # We will create 3 large files of 40MB each (total 120MB)
    file1 = os.path.join(str(log_dir), "log_20260719_100000.log")
    file2 = os.path.join(str(log_dir), "log_20260719_110000.log")
    
    with open(file1, "wb") as f:
        f.truncate(40 * 1024 * 1024)
    with open(file2, "wb") as f:
        f.truncate(40 * 1024 * 1024)
        
    # Adjust mtimes so file1 is oldest, file2 is next
    time1 = time.time() - 3600
    time2 = time.time() - 1800
    os.utime(file1, (time1, time1))
    os.utime(file2, (time2, time2))
    
    current_time = datetime(2026, 7, 19, 12, 0, 0)
    def mock_now():
        return current_time
        
    handler = CustomRotatingFileHandler(log_dir=str(log_dir), now_func=mock_now)
    
    # Make the active log file large
    with open(handler.log_file, "wb") as f:
        f.truncate(40 * 1024 * 1024)
        
    # Call cleanup
    handler.cleanup_logs()
    
    # Total size: 120MB. oldest (file1) should be deleted
    assert not os.path.exists(file1)
    assert os.path.exists(file2)
    assert os.path.exists(handler.log_file)
    
    handler.close()

def test_api_endpoints():
    app = create_app()
    with app.test_client() as client:
        # GET log level config
        res = client.get('/api/logs/config')
        assert res.status_code == 200
        assert "level" in res.json
        
        # POST new log level config
        res = client.post('/api/logs/config', json={"level": "DEBUG"})
        assert res.status_code == 200
        assert res.json["status"] == "success"
        assert res.json["level"] == "DEBUG"
        
        # Verify level updated
        assert get_log_level() == "DEBUG"
        
        # GET active log info
        res = client.get('/api/logs/active')
        assert res.status_code == 200
        assert "filename" in res.json
        assert "content" in res.json
