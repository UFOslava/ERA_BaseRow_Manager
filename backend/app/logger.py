import os
import glob
import json
import logging
from datetime import datetime, timedelta

TRACE_LEVEL_NUM = 5
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")

def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)
logging.Logger.trace = trace

# Global reference to handler
_global_handler = None
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "log_config.json")
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

LEVELS_MAP = {
    "TRACE": TRACE_LEVEL_NUM,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}

class CustomRotatingFileHandler(logging.Handler):
    terminator = "\n"

    def __init__(self, log_dir, level=logging.NOTSET, now_func=None):
        super().__init__(level)
        self.log_dir = os.path.abspath(log_dir)
        os.makedirs(self.log_dir, exist_ok=True)
        self.now_func = now_func if now_func else datetime.now
        self.current_date = self.now_func().date()
        self.log_file = None
        self.stream = None
        self._init_new_file()

    def _init_new_file(self):
        if self.stream:
            self.stream.close()
        
        # Clean up files first
        self.cleanup_logs()
        
        # Current local time
        now = self.now_func()
        self.current_date = now.date()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        filename = f"log_{timestamp}.log"
        self.log_file = os.path.join(self.log_dir, filename)
        
        self.stream = open(self.log_file, "a", encoding="utf-8")

    def cleanup_logs(self):
        try:
            # 1. Remove older files if over a year old
            now = self.now_func()
            one_year_ago = now - timedelta(days=365)
            log_pattern = os.path.join(self.log_dir, "log_*.log")
            files = glob.glob(log_pattern)
            
            for f in files:
                try:
                    fname = os.path.basename(f)
                    if fname.startswith("log_") and fname.endswith(".log"):
                        parts = fname[4:-4].split("_")
                        if len(parts) >= 1:
                            dt = datetime.strptime(parts[0], "%Y%m%d")
                            if dt < one_year_ago:
                                os.remove(f)
                                continue
                except Exception:
                    pass
                
                # Fallback to file mtime
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(f))
                    if mtime < one_year_ago:
                        os.remove(f)
                except Exception:
                    pass

            # 2. Remove oldest files if total logs amount to over 100 MB
            files = glob.glob(log_pattern)
            files.sort(key=os.path.getmtime)
            max_bytes = 100 * 1024 * 1024
            total_size = sum(os.path.getsize(f) for f in files if os.path.exists(f))
            
            for f in files:
                if total_size <= max_bytes:
                    break
                try:
                    size = os.path.getsize(f)
                    os.remove(f)
                    total_size -= size
                except Exception:
                    pass
        except Exception:
            pass

    def emit(self, record):
        try:
            # Check if date has changed mid-run
            if self.now_func().date() != self.current_date:
                self._init_new_file()
                
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    def flush(self):
        if self.stream:
            self.stream.flush()

    def close(self):
        if self.stream:
            self.stream.close()
        super().close()

def setup_logging(log_dir=None, default_level="INFO", now_func=None):
    global _global_handler
    
    # Load level from config
    level_str = default_level
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                level_str = config.get("level", default_level)
        except Exception:
            pass
            
    level = LEVELS_MAP.get(level_str, logging.INFO)
    
    # If handler already exists, close it
    if _global_handler:
        logging.getLogger().removeHandler(_global_handler)
        _global_handler.close()
        
    actual_log_dir = log_dir if log_dir else LOG_DIR
    import sys
    if "pytest" in sys.modules and not log_dir:
        actual_log_dir = os.path.join(actual_log_dir, "test")
    _global_handler = CustomRotatingFileHandler(actual_log_dir, now_func=now_func)
    
    # Create standard formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    _global_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Remove existing custom handlers if any
    for h in list(root_logger.handlers):
        if isinstance(h, CustomRotatingFileHandler):
            root_logger.removeHandler(h)
            h.close()
            
    root_logger.setLevel(level)
    root_logger.addHandler(_global_handler)
    
    # Also set level of the global handler
    _global_handler.setLevel(level)
    
    return _global_handler

def get_log_level():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("level", "INFO")
        except Exception:
            pass
    return "INFO"

def set_log_level(level_str):
    if level_str not in LEVELS_MAP:
        raise ValueError(f"Invalid level name: {level_str}")
        
    # Save to config file
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"level": level_str}, f)
    except Exception:
        pass
        
    # Update logger dynamically
    level = LEVELS_MAP[level_str]
    logging.getLogger().setLevel(level)
    if _global_handler:
        _global_handler.setLevel(level)

def get_active_log_info():
    if not _global_handler or not _global_handler.log_file:
        return {"filename": "", "content": ""}
    
    filename = os.path.basename(_global_handler.log_file)
    content = ""
    if os.path.exists(_global_handler.log_file):
        try:
            with open(_global_handler.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) > 1000:
                    lines = lines[-1000:]
                content = "".join(lines)
        except Exception as e:
            content = f"Error reading log file: {str(e)}"
            
    return {"filename": filename, "content": content}
