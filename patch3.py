import sys

with open('frontend/src/api.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("export async function fetchStates()", "export async function fetchUoMs() {\n  const response = await fetch(${API_BASE}/bom/uom);\n  if (!response.ok) throw new Error('Failed to fetch UoMs');\n  return response.json();\n}\n\nexport async function fetchStates()")

with open('frontend/src/api.js', 'w', encoding='utf-8') as f:
    f.write(content)
