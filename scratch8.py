import re

with open('frontend/src/api.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("await fetch(${API_BASE}/bom/uom);", "await fetch(`${API_BASE_URL}/api/bom/uom`);")
content = content.replace("await fetch(${API_BASE_URL}/api/bom/uom);", "await fetch(`${API_BASE_URL}/api/bom/uom`);")

with open('frontend/src/api.js', 'w', encoding='utf-8') as f:
    f.write(content)

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("opt.textContent = ${uom.Name} ();", "opt.textContent = uom.Name ? `${uom.Name} (${uom.id})` : `UoM ${uom.id}`;")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
