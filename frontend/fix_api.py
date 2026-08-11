import os
import re

file_path = "frontend/src/api.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("fetch(${API_BASE_URL}/api/wi-templates)", "fetch(`${API_BASE_URL}/api/wi-templates`)")
content = content.replace("fetch(${API_BASE_URL}/api/wi-templates, {", "fetch(`${API_BASE_URL}/api/wi-templates`, {")
content = content.replace("fetch(${API_BASE_URL}/api/wi-templates/${templateId}, {", "fetch(`${API_BASE_URL}/api/wi-templates/${templateId}`, {")
content = content.replace("fetch(${API_BASE_URL}/api/wi-templates/config)", "fetch(`${API_BASE_URL}/api/wi-templates/config`)")
content = content.replace("fetch(${API_BASE_URL}/api/wi-templates/config, {", "fetch(`${API_BASE_URL}/api/wi-templates/config`, {")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("api.js backticks fixed.")
