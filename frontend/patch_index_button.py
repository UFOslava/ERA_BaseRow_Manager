import os

file_path = "frontend/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = '<button id="btn-delete-instruction-set"'
replacement = '<button id="btn-export-instruction-set" class="btn btn-primary btn-sm"><i class="fa-solid fa-file-word"></i> Export WI</button>\n            <button id="btn-delete-instruction-set"'

if '<button id="btn-export-instruction-set"' not in content:
    content = content.replace(target, replacement)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("index.html patched with export button in action bar.")
else:
    print("Button already exists.")
