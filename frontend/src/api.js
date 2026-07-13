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
