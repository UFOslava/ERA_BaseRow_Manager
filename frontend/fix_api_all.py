import os

file_path = "frontend/src/api.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import re
content = re.sub(r'fetch\(\${API_BASE_URL}([^)]*)\)', r'fetch(`${API_BASE_URL}\1`)', content)
content = re.sub(r'fetch\(\${API_BASE_URL}([^,]*),\s*{', r'fetch(`${API_BASE_URL}\1`, {', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("api.js backticks fully fixed.")
