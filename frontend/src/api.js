const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchBomTree() {
  const res = await fetch(`${API_BASE_URL}/api/bom/tree`);
  if (!res.ok) throw new Error('Failed to fetch BOM tree');
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error('Backend is offline');
  return res.json();
}
