const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchBomTree() {
  const res = await fetch(`${API_BASE_URL}/api/bom/tree`);
  if (!res.ok) throw new Error('Failed to fetch BOM tree');
  return res.json();
}

export async function fetchItem(itemId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}`);
  if (!res.ok) throw new Error(`Failed to fetch item details for ${itemId}`);
  return res.json();
}

export async function updateItem(itemId, data) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error(`Failed to update item ${itemId}`);
  return res.json();
}

export async function fetchScanStatus() {
  const res = await fetch(`${API_BASE_URL}/api/bom/scan-status`);
  if (!res.ok) throw new Error('Failed to fetch scan status');
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error('Backend is offline');
  return res.json();
}

export async function fetchRules() {
  const res = await fetch(`${API_BASE_URL}/api/bom/rules`);
  if (!res.ok) throw new Error('Failed to fetch category rules');
  return res.json();
}

export async function saveRules(rules) {
  const res = await fetch(`${API_BASE_URL}/api/bom/rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rules)
  });
  if (!res.ok) throw new Error('Failed to save category rules');
  return res.json();
}

export async function fetchProblemDefinitions() {
  const res = await fetch(`${API_BASE_URL}/api/bom/problem-definitions`);
  if (!res.ok) throw new Error('Failed to fetch problem definitions');
  return res.json();
}

export async function saveProblemDefinitions(definitions) {
  const res = await fetch(`${API_BASE_URL}/api/bom/problem-definitions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(definitions)
  });
  if (!res.ok) throw new Error('Failed to save problem definitions');
  return res.json();
}

export async function fetchProblemDefinitionCount(definitionId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/problem-definitions/${definitionId}/count`);
  if (!res.ok) {
    if (res.status === 404) return { id: definitionId, count: null, status: 'unsaved' };
    throw new Error(`Failed to fetch count for definition ${definitionId}`);
  }
  return res.json();
}

export async function triggerRescan() {
  const res = await fetch(`${API_BASE_URL}/api/bom/scan/rescan`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to trigger rescan');
  return res.json();
}

export async function fetchManufacturers() {
  const res = await fetch(`${API_BASE_URL}/api/manufacturers`);
  if (!res.ok) throw new Error('Failed to fetch manufacturers');
  return res.json();
}

export async function uploadDatasheet(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await fetch(`${API_BASE_URL}/api/bom/upload-file`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) throw new Error('Failed to upload datasheet PDF');
  return res.json();
}

export async function fetchFlatItems() {
  const res = await fetch(`${API_BASE_URL}/api/bom/items`);
  if (!res.ok) throw new Error('Failed to fetch flat BOM items');
  return res.json();
}
