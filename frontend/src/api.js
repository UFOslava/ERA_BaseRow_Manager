const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export async function fetchBomTree() {
  const res = await fetch(`${API_BASE_URL}/api/bom/tree`);
  if (!res.ok) throw new Error('Failed to fetch BOM tree');
  return res.json();
}

export async function fetchTopLevelItems(state = 'Production Use', offset = 0, limit = 50) {
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  if (state) params.set('state', state);
  const res = await fetch(`${API_BASE_URL}/api/bom/top-level?${params}`);
  if (!res.ok) throw new Error('Failed to fetch top-level items');
  return res.json();
}

export async function fetchItem(itemId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}`);
  if (!res.ok) throw new Error(`Failed to fetch item details for ${itemId}`);
  return res.json();
}

export async function fetchGraphNexus() {
  const res = await fetch(`${API_BASE_URL}/api/bom/graph`);
  if (!res.ok) throw new Error('Failed to fetch graph nexus nodes');
  return res.json();
}

export async function fetchGraphChildren(itemId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/graph/${itemId}/children`);
  if (!res.ok) throw new Error(`Failed to fetch children for ${itemId}`);
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

export async function searchItems(query, limit = 200) {
  const params = new URLSearchParams({ search: query, limit: String(Math.min(limit, 200)) });
  const res = await fetch(`${API_BASE_URL}/api/bom/items?${params}`);
  if (!res.ok) throw new Error('Failed to search BOM items');
  return res.json();
}

export async function createAssembly(parentId, childId, quantity, length, pcbSymbol) {
  const res = await fetch(`${API_BASE_URL}/api/bom/assembly`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parent_id: parentId, child_id: childId, quantity, length, pcb_symbol: pcbSymbol })
  });
  if (!res.ok) throw new Error('Failed to create assembly relation');
  return res.json();
}

export async function updateAssembly(edgeId, quantity, length, pcbSymbol) {
  const res = await fetch(`${API_BASE_URL}/api/bom/assembly/${edgeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity, length, pcb_symbol: pcbSymbol })
  });
  if (!res.ok) throw new Error('Failed to update assembly relation');
  return res.json();
}

export async function deleteAssembly(edgeId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/assembly/${edgeId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete assembly relation');
  return res.json();
}

export async function createItem(prefix, description) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prefix, description })
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.error || 'Failed to create item');
  }
  return res.json();
}

export async function fetchLogsConfig() {
  const res = await fetch(`${API_BASE_URL}/api/logs/config`);
  if (!res.ok) throw new Error('Failed to fetch logs configuration');
  return res.json();
}

export async function saveLogsConfig(level) {
  const res = await fetch(`${API_BASE_URL}/api/logs/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ level })
  });
  if (!res.ok) throw new Error('Failed to save logs configuration');
  return res.json();
}

export async function recategorizeItem(itemId, newPrefix) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}/recategorize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_prefix: newPrefix })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to recategorize item');
  }
  return res.json();
}

export async function duplicateItem(itemId, prefix, description, options = {}) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}/duplicate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prefix, description, ...options })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to duplicate item');
  }
  return res.json();
}

export async function addItemRevision(itemId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${itemId}/revision`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Failed to add revision');
  }
  return res.json();
}

export async function fetchActiveLog() {
  const res = await fetch(`${API_BASE_URL}/api/logs/active`);
  if (!res.ok) throw new Error('Failed to fetch active logs');
  return res.json();
}

export async function fetchInstructionSets(parentId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets`);
  if (!res.ok) throw new Error('Failed to fetch instruction sets');
  return res.json();
}

export async function fetchInstructionSetDetails(parentId, setIndex) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets/${setIndex}`);
  if (!res.ok) throw new Error('Failed to fetch instruction set details');
  return res.json();
}

export async function createInstructionStep(parentId, setIndex, stepData) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets/${setIndex}/steps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stepData)
  });
  if (!res.ok) throw new Error('Failed to create instruction step');
  return res.json();
}

export async function updateInstructionStep(stepId, stepData) {
  const res = await fetch(`${API_BASE_URL}/api/bom/instructions/${stepId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(stepData)
  });
  if (!res.ok) throw new Error('Failed to update instruction step');
  return res.json();
}

export async function deleteInstructionStep(stepId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/instructions/${stepId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete instruction step');
  return res.json();
}

export async function reorderInstructionSteps(parentId, setIndex, stepIds) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets/${setIndex}/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ step_ids: stepIds })
  });
  if (!res.ok) throw new Error('Failed to reorder instruction steps');
  return res.json();
}

export async function deleteInstructionSet(parentId, setIndex) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets/${setIndex}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete instruction set');
  return res.json();
}

export async function fetchQuickActionTemplates() {
  const res = await fetch(`${API_BASE_URL}/api/bom/templates`);
  if (!res.ok) throw new Error('Failed to fetch quick action templates');
  return res.json();
}

export async function saveQuickActionTemplates(templates) {
  const res = await fetch(`${API_BASE_URL}/api/bom/templates`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(templates)
  });
  if (!res.ok) throw new Error('Failed to save quick action templates');
  return res.json();
}

export async function fetchStates() {
  const res = await fetch(`${API_BASE_URL}/api/bom/states`);
  if (!res.ok) throw new Error('Failed to fetch states');
  return res.json();
}


export async function fetchWiTemplates() {
  const res = await fetch(`${API_BASE_URL}/api/wi-templates`);
  if (!res.ok) throw new Error('Failed to fetch WI templates');
  return res.json();
}

export async function uploadWiTemplate(file, name) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  const res = await fetch(`${API_BASE_URL}/api/wi-templates`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) throw new Error('Failed to upload template');
  return res.json();
}

export async function replaceWiTemplate(templateId, file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE_URL}/api/wi-templates/${templateId}`, {
    method: 'PUT',
    body: formData
  });
  if (!res.ok) throw new Error('Failed to replace template');
  return res.json();
}

export async function deleteWiTemplate(templateId) {
  const res = await fetch(`${API_BASE_URL}/api/wi-templates/${templateId}`, {
    method: 'DELETE'
  });
  if (!res.ok) throw new Error('Failed to delete template');
  return res.json();
}

export async function exportWiDocument(parentId, setIndex, templateId) {
  const res = await fetch(`${API_BASE_URL}/api/bom/items/${parentId}/instruction-sets/${setIndex}/export-wi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ template_id: templateId })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || 'Export failed');
  }
  return res;
}

export async function fetchWiConfig() {
  const res = await fetch(`${API_BASE_URL}/api/wi-templates/config`);
  if (!res.ok) throw new Error('Failed to fetch config');
  return res.json();
}

export async function saveWiConfig(data) {
  const res = await fetch(`${API_BASE_URL}/api/wi-templates/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to save config');
  return res.json();
}

export async function approveWiTemplate(templateId, approved) {
  const res = await fetch(`${API_BASE_URL}/api/wi-templates/${templateId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved })
  });
  if (!res.ok) throw new Error('Failed to approve template');
  return res.json();
}

