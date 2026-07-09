import { fetchParts, createPart, updatePart, deletePart, movePart, getHealth } from './api.js';

let parts = [];
let expandedNodes = new Set([1]);

const treeContainer = document.getElementById('tree-container');
const partForm = document.getElementById('part-form');
const partNameInput = document.getElementById('part-name');
const partDescInput = document.getElementById('part-description');
const partParentSelect = document.getElementById('part-parent');

const editModal = document.getElementById('edit-modal');
const editForm = document.getElementById('edit-form');
const editPartIdInput = document.getElementById('edit-part-id');
const editPartNameInput = document.getElementById('edit-part-name');
const editPartDescInput = document.getElementById('edit-part-description');
const editPartParentSelect = document.getElementById('edit-part-parent');
const btnCloseModal = document.getElementById('btn-close-modal');

const btnRefresh = document.getElementById('btn-refresh');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

const statTotal = document.getElementById('stat-total');
const statRoots = document.getElementById('stat-roots');

async function init() {
  checkBackendHealth();
  await refreshData();
  
  partForm.addEventListener('submit', handleCreatePart);
  editForm.addEventListener('submit', handleEditPart);
  btnRefresh.addEventListener('click', refreshData);
  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', () => editModal.classList.remove('active'));
  }
  
  setInterval(checkBackendHealth, 15000);
}

async function checkBackendHealth() {
  try {
    await getHealth();
    if (statusIndicator) statusIndicator.className = 'status-indicator healthy';
    if (statusText) statusText.textContent = 'Backend Online';
  } catch (error) {
    if (statusIndicator) statusIndicator.className = 'status-indicator error';
    if (statusText) statusText.textContent = 'Backend Offline';
  }
}

async function refreshData() {
  try {
    parts = await fetchParts();
    updateSelectors();
    updateStats();
    renderTree();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function updateStats() {
  if (statTotal) statTotal.textContent = parts.length;
  if (statRoots) statRoots.textContent = parts.filter(p => p.parent_id === null).length;
}

function updateSelectors() {
  if (!partParentSelect) return;
  const optionsHtml = '<option value="">None (Root Part)</option>' +
    parts.map(p => `<option value="${p.id}">${p.name} (ID: ${p.id})</option>`).join('');
  
  partParentSelect.innerHTML = optionsHtml;
}

function renderTree() {
  if (!treeContainer) return;
  treeContainer.innerHTML = '';
  
  const rootParts = parts.filter(p => p.parent_id === null);
  const childrenMap = {};
  
  parts.forEach(p => {
    if (p.parent_id !== null) {
      if (!childrenMap[p.parent_id]) childrenMap[p.parent_id] = [];
      childrenMap[p.parent_id].push(p);
    }
  });

  if (rootParts.length === 0) {
    treeContainer.innerHTML = '<div class="loading-spinner">No parts found. Create one to begin.</div>';
    return;
  }

  function buildNodeHtml(node) {
    const children = childrenMap[node.id] || [];
    const hasChildren = children.length > 0;
    const isExpanded = expandedNodes.has(node.id);
    
    const nodeEl = document.createElement('div');
    nodeEl.className = 'tree-node-wrapper';
    
    const nodeHeaderHtml = `
      <div class="tree-node" data-id="${node.id}">
        <div class="node-header">
          <div class="node-title-wrapper">
            ${hasChildren ? `
              <span class="node-toggle ${isExpanded ? 'expanded' : ''}" data-id="${node.id}">▶</span>
            ` : '<span style="width: 16px;"></span>'}
            <span class="node-name">${node.name}</span>
            <span class="node-id">ID: ${node.id}</span>
          </div>
          <div class="node-actions">
            <button class="action-btn btn-edit-node" data-id="${node.id}">Edit</button>
            <button class="action-btn btn-delete-node" data-id="${node.id}">Delete</button>
          </div>
        </div>
        ${node.description ? `<div class="node-desc">${node.description}</div>` : ''}
      </div>
    `;
    
    nodeEl.innerHTML = nodeHeaderHtml;
    
    const toggleBtn = nodeEl.querySelector('.node-toggle');
    const editBtn = nodeEl.querySelector('.btn-edit-node');
    const deleteBtn = nodeEl.querySelector('.btn-delete-node');
    
    if (toggleBtn) {
      toggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (expandedNodes.has(node.id)) {
          expandedNodes.delete(node.id);
        } else {
          expandedNodes.add(node.id);
        }
        renderTree();
      });
    }
    
    if (editBtn) {
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openEditModal(node);
      });
    }
    
    if (deleteBtn) {
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        handleDeletePart(node.id);
      });
    }

    if (hasChildren && isExpanded) {
      const branchEl = document.createElement('div');
      branchEl.className = 'tree-branch';
      children.forEach(child => {
        branchEl.appendChild(buildNodeHtml(child));
      });
      nodeEl.appendChild(branchEl);
    }
    
    return nodeEl;
  }

  rootParts.forEach(root => {
    treeContainer.appendChild(buildNodeHtml(root));
  });
}

async function handleCreatePart(e) {
  e.preventDefault();
  if (!partNameInput || !partDescInput || !partParentSelect) return;
  const name = partNameInput.value.trim();
  const description = partDescInput.value.trim();
  const parentIdVal = partParentSelect.value;
  const parent_id = parentIdVal ? parseInt(parentIdVal, 10) : null;

  try {
    await createPart({ name, description, parent_id });
    showToast(`Created part: ${name}`, 'success');
    partForm.reset();
    await refreshData();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function openEditModal(part) {
  if (!editPartIdInput || !editPartNameInput || !editPartDescInput || !editPartParentSelect || !editModal) return;
  editPartIdInput.value = part.id;
  editPartNameInput.value = part.name;
  editPartDescInput.value = part.description || '';
  
  const availableParents = parts.filter(p => p.id !== part.id);
  const optionsHtml = '<option value="">None (Root Part)</option>' +
    availableParents.map(p => `<option value="${p.id}">${p.name} (ID: ${p.id})</option>`).join('');
  
  editPartParentSelect.innerHTML = optionsHtml;
  editPartParentSelect.value = part.parent_id || '';
  editModal.classList.add('active');
}

async function handleEditPart(e) {
  e.preventDefault();
  if (!editPartIdInput || !editPartNameInput || !editPartDescInput || !editPartParentSelect || !editModal) return;
  const id = parseInt(editPartIdInput.value, 10);
  const name = editPartNameInput.value.trim();
  const description = editPartDescInput.value.trim();
  const parentIdVal = editPartParentSelect.value;
  const parent_id = parentIdVal ? parseInt(parentIdVal, 10) : null;

  try {
    const originalPart = parts.find(p => p.id === id);
    if (originalPart && originalPart.parent_id !== parent_id) {
      await movePart(id, parent_id);
    }
    await updatePart(id, { name, description });
    showToast(`Updated part: ${name}`, 'success');
    editModal.classList.remove('active');
    await refreshData();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function handleDeletePart(id) {
  if (!confirm(`Are you sure you want to delete part ID ${id}? Children parts will be set to root.`)) {
    return;
  }
  try {
    await deletePart(id);
    showToast(`Deleted part ID ${id}`, 'success');
    await refreshData();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function showToast(message, type = 'success') {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : '✗'}</span>
    <span>${message}</span>
  `;
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

// Support browser environment vs testing environment
if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
