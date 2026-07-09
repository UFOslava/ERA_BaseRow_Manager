const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchParts() {
  const res = await fetch(`${API_BASE_URL}/api/parts`);
  if (!res.ok) throw new Error('Failed to fetch parts');
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  if (!res.ok) throw new Error('Backend is offline');
  return res.json();
}

export async function createPart(part) {
  const res = await fetch(`${API_BASE_URL}/api/parts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(part)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || 'Failed to create part');
  }
  return res.json();
}

export async function updatePart(id, part) {
  const res = await fetch(`${API_BASE_URL}/api/parts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(part)
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || 'Failed to update part');
  }
  return res.json();
}

export async function deletePart(id) {
  const res = await fetch(`${API_BASE_URL}/api/parts/${id}`, {
    method: 'DELETE'
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || 'Failed to delete part');
  }
  return res.json();
}

export async function movePart(id, newParentId) {
  const res = await fetch(`${API_BASE_URL}/api/parts/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ part_id: id, new_parent_id: newParentId })
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || 'Failed to move part');
  }
  return res.json();
}
