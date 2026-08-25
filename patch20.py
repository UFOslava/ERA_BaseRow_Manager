import sys

with open('frontend/src/api.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
'''export async function createAssembly(parentId, childId, quantity, length, pcbSymbol) {
  const res = await fetch(${API_BASE_URL}/api/bom/assembly, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_id: parentId, child_id: childId, quantity, length, pcb_symbol: pcbSymbol })
  });''',
'''export async function createAssembly(parentId, childId, quantity, length, pcbSymbol, uomId) {
  const res = await fetch(${API_BASE_URL}/api/bom/assembly, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_id: parentId, child_id: childId, quantity, length, pcb_symbol: pcbSymbol, uom_id: uomId })
  });'''
)

content = content.replace(
'''export async function updateAssembly(edgeId, quantity, length, pcbSymbol, parentId, childId) {
  const res = await fetch(${API_BASE_URL}/api/bom/assembly/, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity, length, pcb_symbol: pcbSymbol, parent_id: parentId, child_id: childId })
  });''',
'''export async function updateAssembly(edgeId, quantity, length, pcbSymbol, parentId, childId, uomId) {
  const res = await fetch(${API_BASE_URL}/api/bom/assembly/, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity, length, pcb_symbol: pcbSymbol, parent_id: parentId, child_id: childId, uom_id: uomId })
  });'''
)

with open('frontend/src/api.js', 'w', encoding='utf-8') as f:
    f.write(content)
