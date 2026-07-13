import { fetchBomTree, fetchItem, updateItem, fetchScanStatus, getHealth } from './api.js';

let rawTree = [];
let filteredTree = [];
let searchQuery = '';
let expandedNodes = new Set();
let autoExpandedNodes = new Set();

let currentItemId = null;
let originalData = { description: '', source: '' };

const bomExplorerView = document.getElementById('bom-explorer-view');
const itemDetailsView = document.getElementById('item-details-view');
const treeContainer = document.getElementById('tree-container');
const searchInput = document.getElementById('search-input');
const btnRefresh = document.getElementById('btn-refresh');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

const btnBack = document.getElementById('btn-back');
const btnSave = document.getElementById('btn-save');
const btnRevert = document.getElementById('btn-revert');
const inputDescription = document.getElementById('input-description');
const inputSource = document.getElementById('input-source');

const itemPartNumber = document.getElementById('item-part-number');
const itemPnTag = document.getElementById('item-pn-tag');
const itemRevision = document.getElementById('item-revision');
const itemCategory = document.getElementById('item-category');
const itemSourcedBy = document.getElementById('item-sourced-by');
const itemState = document.getElementById('item-state');
const itemNotes = document.getElementById('item-notes');
const galleryContainer = document.getElementById('gallery-container');
const problemsAlertBox = document.getElementById('problems-alert-box');
const problemsList = document.getElementById('problems-list');

let scanPollingInterval = null;

async function init() {
  checkBackendHealth();
  
  if (btnRefresh) btnRefresh.addEventListener('click', refreshData);
  if (searchInput) searchInput.addEventListener('input', handleSearch);
  
  if (btnBack) btnBack.addEventListener('click', handleBackNavigation);
  if (btnRevert) btnRevert.addEventListener('click', revertChanges);
  if (btnSave) btnSave.addEventListener('click', saveChanges);
  
  if (inputDescription) inputDescription.addEventListener('input', checkChanges);
  if (inputSource) inputSource.addEventListener('input', checkChanges);
  
  window.addEventListener('hashchange', handleRouting);
  
  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedChanges()) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.tree-row')) {
      const openRows = document.querySelectorAll('.tree-row.menu-open');
      openRows.forEach(r => r.classList.remove('menu-open'));
    }
  });

  await handleRouting();

  setInterval(checkBackendHealth, 15000);
}

async function handleRouting() {
  const hash = window.location.hash;
  
  if (hash.startsWith('#/item/')) {
    const idStr = hash.replace('#/item/', '');
    const itemId = parseInt(idStr, 10);
    
    if (!isNaN(itemId)) {
      await showItemPage(itemId);
      return;
    }
  }
  
  showExplorerPage();
}

function handleBackNavigation() {
  if (hasUnsavedChanges()) {
    if (!confirm("You have unsaved changes. Discard them and return to BOM explorer?")) {
      return;
    }
  }
  window.location.hash = '';
}

function hasUnsavedChanges() {
  if (!currentItemId) return false;
  const descVal = inputDescription ? inputDescription.value.trim() : '';
  const srcVal = inputSource ? inputSource.value.trim() : '';
  return descVal !== originalData.description || srcVal !== originalData.source;
}

function checkChanges() {
  const changed = hasUnsavedChanges();
  if (btnSave) btnSave.disabled = !changed;
  if (btnRevert) btnRevert.disabled = !changed;
}

function showExplorerPage() {
  currentItemId = null;
  if (itemDetailsView) itemDetailsView.style.display = 'none';
  if (bomExplorerView) bomExplorerView.style.display = 'block';
  refreshData();
}

async function showItemPage(itemId) {
  currentItemId = itemId;
  if (bomExplorerView) bomExplorerView.style.display = 'none';
  if (itemDetailsView) itemDetailsView.style.display = 'block';
  
  if (inputDescription) inputDescription.value = '';
  if (inputSource) inputSource.value = '';
  if (galleryContainer) galleryContainer.innerHTML = '<div class="gallery-placeholder">Loading item details...</div>';
  if (problemsAlertBox) problemsAlertBox.style.display = 'none';
  if (btnSave) btnSave.disabled = true;
  if (btnRevert) btnRevert.disabled = true;

  try {
    const item = await fetchItem(itemId);
    
    if (itemPartNumber) itemPartNumber.textContent = item["Part Number"] || 'N/A';
    if (itemPnTag) {
      const pnTag = item["pn_tag"];
      if (pnTag && pnTag.name) {
        itemPnTag.textContent = pnTag.name;
        itemPnTag.style.borderColor = pnTag.color;
        itemPnTag.style.color = pnTag.color;
        itemPnTag.style.backgroundColor = `${pnTag.color}15`;
        itemPnTag.style.display = 'inline-block';
      } else {
        itemPnTag.style.display = 'none';
      }
    }
    if (itemRevision) itemRevision.textContent = item["Revision"] || 'N/A';
    if (itemCategory) itemCategory.textContent = item["Category"] || 'N/A';
    
    const sourcedByObj = item["Sourced By"];
    if (itemSourcedBy) itemSourcedBy.textContent = sourcedByObj ? sourcedByObj.value : 'N/A';
    
    const stateObj = item["State"];
    if (itemState) itemState.textContent = stateObj ? stateObj.value : 'N/A';
    
    if (itemNotes) itemNotes.textContent = item["Notes"] || 'No notes available.';
    
    originalData = {
      description: item["Item description"] || '',
      source: item["Source"] || ''
    };
    
    if (inputDescription) inputDescription.value = originalData.description;
    if (inputSource) inputSource.value = originalData.source;
    
    if (galleryContainer) {
      galleryContainer.innerHTML = '';
      const images = item["Image"] || [];
      
      if (images.length === 0) {
        galleryContainer.innerHTML = `
          <div class="gallery-placeholder">
            <span>📷</span>
            <span>No images available for this item</span>
          </div>
        `;
      } else {
        images.forEach(img => {
          const imgCard = document.createElement('div');
          imgCard.className = 'gallery-image-card';
          imgCard.innerHTML = `<img src="${img.url}" alt="Item image" />`;
          galleryContainer.appendChild(imgCard);
        });
      }
    }
    
    if (problemsAlertBox && problemsList) {
      problemsList.innerHTML = '';
      const problems = item["problems"] || [];
      if (problems.length > 0) {
        problems.forEach(prob => {
          const li = document.createElement('li');
          li.textContent = prob;
          problemsList.appendChild(li);
        });
        problemsAlertBox.style.display = 'flex';
      } else {
        problemsAlertBox.style.display = 'none';
      }
    }
    
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function revertChanges() {
  if (inputDescription) inputDescription.value = originalData.description;
  if (inputSource) inputSource.value = originalData.source;
  checkChanges();
  showToast('Changes reverted to original values.');
}

async function saveChanges() {
  if (!currentItemId) return;
  
  const descVal = inputDescription ? inputDescription.value.trim() : '';
  const srcVal = inputSource ? inputSource.value.trim() : '';
  
  try {
    showToast('Saving changes to Baserow...');
    
    await updateItem(currentItemId, {
      "Item description": descVal,
      "Source": srcVal
    });
    
    originalData = { description: descVal, source: srcVal };
    checkChanges();
    showToast('Item saved successfully.');
    
    await showItemPage(currentItemId);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function navigateToItem(itemId) {
  if (hasUnsavedChanges()) {
    if (!confirm("You have unsaved changes. Discard them and open item details?")) {
      return;
    }
  }
  window.location.hash = `#/item/${itemId}`;
}

async function checkBackendHealth() {
  try {
    await getHealth();
    if (statusIndicator) statusIndicator.className = 'status-indicator healthy';
    if (statusText) statusText.textContent = 'Baserow Online';
  } catch (error) {
    if (statusIndicator) statusIndicator.className = 'status-indicator error';
    if (statusText) statusText.textContent = 'Baserow Offline';
  }
}

async function refreshData() {
  try {
    const spinner = treeContainer ? treeContainer.querySelector('.loading-spinner') : null;
    if (!spinner && treeContainer) {
      treeContainer.innerHTML = '<div class="loading-spinner">Loading BOM data from Baserow...</div>';
    }
    
    rawTree = await fetchBomTree();
    
    if (expandedNodes.size === 0) {
      rawTree.forEach(node => {
        expandedNodes.add(String(node.id));
      });
    }
    
    applyFilterAndRender();
    startPollingIfScanning();
  } catch (error) {
    showToast(error.message, 'error');
    if (treeContainer) treeContainer.innerHTML = `<div class="loading-spinner" style="color: var(--color-danger)">Error: ${error.message}</div>`;
  }
}

async function startPollingIfScanning() {
  if (scanPollingInterval) return;
  
  try {
    const statusObj = await fetchScanStatus();
    if (statusObj.status === 'running' || statusObj.status === 'pending') {
      scanPollingInterval = setInterval(async () => {
        const checkStatus = await fetchScanStatus();
        if (checkStatus.status === 'completed' || checkStatus.status === 'failed') {
          clearInterval(scanPollingInterval);
          scanPollingInterval = null;
          refreshDataSilent();
        }
      }, 3000);
    }
  } catch (err) {
    console.error('Error starting scanner polling:', err);
  }
}

async function refreshDataSilent() {
  try {
    rawTree = await fetchBomTree();
    applyFilterAndRender();
  } catch (err) {
    console.error('Silent refresh failed:', err);
  }
}

function handleSearch(e) {
  searchQuery = e.target.value.toLowerCase().trim();
  applyFilterAndRender();
}

function applyFilterAndRender() {
  if (!searchQuery) {
    filteredTree = rawTree;
    autoExpandedNodes.clear();
  } else {
    autoExpandedNodes.clear();
    const result = [];
    
    rawTree.forEach(node => {
      const filtered = filterNode(node, searchQuery, String(node.id), []);
      if (filtered) {
        result.push(filtered);
      }
    });
    filteredTree = result;
  }
  
  renderTreeTable();
}

function filterNode(node, query, currentPath, parentPaths) {
  const matchesPN = node.part_number && node.part_number.toLowerCase().includes(query);
  const matchesDesc = node.description && node.description.toLowerCase().includes(query);
  const matchesHelper = node.search_helper && node.search_helper.toLowerCase().includes(query);
  
  const isMatch = matchesPN || matchesDesc || matchesHelper;
  const filteredChildren = [];
  
  if (node.children && node.children.length > 0) {
    node.children.forEach(child => {
      const childPath = `${currentPath}/${child.id}`;
      const filteredChild = filterNode(child, query, childPath, [...parentPaths, currentPath]);
      if (filteredChild) {
        filteredChildren.push(filteredChild);
      }
    });
  }
  
  const hasMatchingChildren = filteredChildren.length > 0;
  
  if (isMatch || hasMatchingChildren) {
    if (hasMatchingChildren) {
      parentPaths.forEach(p => autoExpandedNodes.add(p));
      autoExpandedNodes.add(currentPath);
    }
    return {
      ...node,
      children: filteredChildren,
      isMatch: isMatch
    };
  }
  
  return null;
}

function renderTreeTable() {
  if (!treeContainer) return;
  treeContainer.innerHTML = '';
  
  if (filteredTree.length === 0) {
    treeContainer.innerHTML = '<div class="loading-spinner">No matching parts found.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  
  function traverseAndRender(node, level, path) {
    const hasChildren = node.children && node.children.length > 0;
    const isExpanded = expandedNodes.has(path) || autoExpandedNodes.has(path);
    
    const rowEl = document.createElement('div');
    rowEl.className = 'tree-row';
    
    // Slide menu element
    const menuEl = document.createElement('div');
    menuEl.className = 'row-action-menu';
    
    const plusBtn = document.createElement('button');
    plusBtn.className = 'row-menu-btn';
    plusBtn.textContent = '+';
    plusBtn.disabled = true;
    
    const openBtn = document.createElement('button');
    openBtn.className = 'row-menu-btn enabled';
    openBtn.innerHTML = '<i class="fa-solid fa-up-right-from-square"></i>';
    openBtn.title = 'Open Item Details';
    
    openBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      navigateToItem(node.id);
    });
    
    menuEl.appendChild(plusBtn);
    menuEl.appendChild(openBtn);
    rowEl.appendChild(menuEl);
    
    // Single click handler to toggle menu open/close
    rowEl.addEventListener('click', (e) => {
      if (e.target.closest('.node-toggle') || e.target.closest('.row-menu-btn')) return;
      
      const isCurrentlyOpen = rowEl.classList.contains('menu-open');
      
      const openRows = treeContainer.querySelectorAll('.tree-row.menu-open');
      openRows.forEach(r => {
        if (r !== rowEl) r.classList.remove('menu-open');
      });
      
      if (isCurrentlyOpen) {
        rowEl.classList.remove('menu-open');
      } else {
        rowEl.classList.add('menu-open');
      }
    });
    
    rowEl.addEventListener('dblclick', (e) => {
      if (e.target.closest('.node-toggle') || e.target.closest('.row-menu-btn')) return;
      navigateToItem(node.id);
    });
    
    const descCol = document.createElement('div');
    descCol.className = 'col-desc';
    descCol.style.paddingLeft = `${level * 24}px`;
    
    const toggleSpan = document.createElement('span');
    toggleSpan.className = `node-toggle ${hasChildren ? '' : 'hidden-toggle'} ${isExpanded ? 'expanded' : ''}`;
    toggleSpan.textContent = '▶';
    
    if (hasChildren) {
      toggleSpan.addEventListener('click', (e) => {
        e.stopPropagation();
        if (expandedNodes.has(path)) {
          expandedNodes.delete(path);
        } else {
          expandedNodes.add(path);
        }
        renderTreeTable();
      });
    }
    
    const textSpan = document.createElement('span');
    textSpan.className = 'node-text';
    textSpan.innerHTML = highlightText(node.description, searchQuery);
    
    descCol.appendChild(toggleSpan);
    descCol.appendChild(textSpan);
    
    const pnCol = document.createElement('div');
    pnCol.className = 'col-pn';
    pnCol.innerHTML = highlightText(node.part_number, searchQuery);
    
    const qtyCol = document.createElement('div');
    qtyCol.className = 'col-qty';
    qtyCol.textContent = node.quantity_label || 'Root';
    
    const probCol = document.createElement('div');
    probCol.className = 'col-problems';
    
    const count = node.problems_count;
    if (count === null) {
      probCol.innerHTML = '<span class="prob-badge unknown">? Scanning</span>';
    } else if (count === 0) {
      probCol.innerHTML = '<span class="prob-badge ok">✓ Ok</span>';
    } else {
      probCol.innerHTML = `<span class="prob-badge error">⚠️ ${count} ${count === 1 ? 'issue' : 'issues'}</span>`;
    }
    
    // Wrap columns into content wrapper
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'row-content-wrapper';
    
    contentWrapper.appendChild(descCol);
    contentWrapper.appendChild(pnCol);
    contentWrapper.appendChild(qtyCol);
    contentWrapper.appendChild(probCol);
    
    rowEl.appendChild(contentWrapper);
    
    fragment.appendChild(rowEl);
    
    if (hasChildren && isExpanded) {
      node.children.forEach(child => {
        traverseAndRender(child, level + 1, `${path}/${child.id}`);
      });
    }
  }

  filteredTree.forEach(root => {
    traverseAndRender(root, 0, String(root.id));
  });
  
  treeContainer.appendChild(fragment);
}

function highlightText(text, query) {
  if (!text) return '';
  if (!query) return text;
  
  const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
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

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
