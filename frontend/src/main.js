import { fetchBomTree, fetchItem, updateItem, fetchScanStatus, getHealth, fetchRules, fetchManufacturers, uploadDatasheet, fetchFlatItems, createAssembly, updateAssembly, deleteAssembly, createItem } from './api.js';

let rawTree = [];
let filteredTree = [];
let searchQuery = '';
let expandedNodes = new Set();
let autoExpandedNodes = new Set();

let currentItemId = null;
let originalData = {
  description: '',
  source: '',
  externalPn: '',
  state: 'Unknown',
  manufacturerId: '',
  price: null,
  sourcedBy: 'TBD',
  notes: '',
  datasheets: [],
  images: [],
  relatedItems: []
};
let currentDatasheets = [];
let currentImages = [];
let currentRelated = [];
let allItems = [];
let manufacturers = [];

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
const inputExternalPn = document.getElementById('input-external-pn');
const inputState = document.getElementById('input-state');
const inputManufacturer = document.getElementById('input-manufacturer');
const inputPrice = document.getElementById('input-price');
const inputSourcedBy = document.getElementById('input-sourced-by');
const inputNotes = document.getElementById('input-notes');

const itemPartNumber = document.getElementById('item-part-number');
const itemPnTag = document.getElementById('item-pn-tag');
const itemRevision = document.getElementById('item-revision');
const itemCategory = document.getElementById('item-category');
const itemSourcedBy = document.getElementById('item-sourced-by');
const itemState = document.getElementById('item-state');
const itemNotes = document.getElementById('item-notes');
const titlePn = document.getElementById('title-pn');
const titleDesc = document.getElementById('title-desc');
const revisionTagsContainer = document.getElementById('revision-tags-container');
const inputPhotoFile = document.getElementById('input-photo-file');
const dragDropOverlay = document.getElementById('drag-drop-overlay');
const galleryContainer = document.getElementById('gallery-container');
const problemsAlertBox = document.getElementById('problems-alert-box');
const problemsList = document.getElementById('problems-list');

const relatedItemsContainer = document.getElementById('related-items-container');
const addRelatedSearch = document.getElementById('add-related-search');
const addRelatedModal = document.getElementById('add-related-modal');
const btnCloseAddRelated = document.getElementById('btn-close-add-related');
const addRelatedList = document.getElementById('add-related-list');

const btnFilter = document.getElementById('btn-filter');
const filterDrawer = document.getElementById('filter-drawer');
const btnCloseDrawer = document.getElementById('btn-close-drawer');
const drawerOverlay = document.getElementById('drawer-overlay');

let scanPollingInterval = null;
let categoryRules = {};
let disabledCategories = new Set();
let disabledStates = new Set();

// Add Child Modal Selectors
const addChildModal = document.getElementById('add-child-modal');
const btnCloseAddChild = document.getElementById('btn-close-add-child');
const addChildSearch = document.getElementById('add-child-search');
const addChildList = document.getElementById('add-child-list');
const addChildForm = document.getElementById('add-child-form');
const selectedChildName = document.getElementById('selected-child-name');
const addChildRevisionTags = document.getElementById('add-child-revision-tags');
const addChildQuantity = document.getElementById('add-child-quantity');
const addChildLength = document.getElementById('add-child-length');
const addChildPcb = document.getElementById('add-child-pcb');
const btnCancelAddChild = document.getElementById('btn-cancel-add-child');
const btnConfirmAddChild = document.getElementById('btn-confirm-add-child');

// Edit Assembly Modal Selectors
const editAssemblyModal = document.getElementById('edit-assembly-modal');
const btnCloseEditAssembly = document.getElementById('btn-close-edit-assembly');
const editAssemblyItemName = document.getElementById('edit-assembly-item-name');
const editAssemblyQuantity = document.getElementById('edit-assembly-quantity');
const editAssemblyLength = document.getElementById('edit-assembly-length');
const editAssemblyPcb = document.getElementById('edit-assembly-pcb');
const btnDeleteAssembly = document.getElementById('btn-delete-assembly');
const btnCancelEditAssembly = document.getElementById('btn-cancel-edit-assembly');
const btnSaveEditAssembly = document.getElementById('btn-save-edit-assembly');

// Create Item Modal Selectors
const createItemModal = document.getElementById('create-item-modal');
const btnCloseCreateItem = document.getElementById('btn-close-create-item');
const btnCancelCreateItem = document.getElementById('btn-cancel-create-item');
const btnConfirmCreateItem = document.getElementById('btn-confirm-create-item');
const createItemCategory = document.getElementById('create-item-category');
const createItemDescription = document.getElementById('create-item-description');
const btnAddItemTrigger = document.getElementById('btn-add-item-trigger');

// Add/Edit Dialog States
let addChildParentId = null;
let addChildSelectedItemId = null;
let addChildSelectedRevId = null;
let editAssemblyEdgeId = null;
let editAssemblyNode = null;

async function init() {
  checkBackendHealth();
  
  const btnHamburger = document.getElementById('btn-hamburger');
  const hamburgerMenu = document.getElementById('hamburger-menu');
  if (btnHamburger && hamburgerMenu) {
    btnHamburger.addEventListener('click', (e) => {
      e.stopPropagation();
      hamburgerMenu.classList.toggle('open');
    });
    
    document.addEventListener('click', (e) => {
      if (!hamburgerMenu.contains(e.target) && e.target !== btnHamburger) {
        hamburgerMenu.classList.remove('open');
      }
    });
    
    const menuItemNested = document.getElementById('menu-item-nested');
    if (menuItemNested) {
      menuItemNested.addEventListener('click', (e) => {
        const path = window.location.pathname;
        if (path === '/' || path.endsWith('index.html') || path === '') {
          e.preventDefault();
          hamburgerMenu.classList.remove('open');
        }
      });
    }
  }
  
  if (btnRefresh) btnRefresh.addEventListener('click', refreshData);
  
  // Add Child Modal Event Listeners
  if (btnCloseAddChild) btnCloseAddChild.addEventListener('click', closeAddChildModal);
  if (btnCancelAddChild) btnCancelAddChild.addEventListener('click', closeAddChildModal);
  if (addChildSearch) addChildSearch.addEventListener('input', renderAddChildList);
  if (btnConfirmAddChild) btnConfirmAddChild.addEventListener('click', handleConfirmAddChild);
  if (addChildModal) {
    addChildModal.addEventListener('click', (e) => {
      if (e.target === addChildModal) closeAddChildModal();
    });
  }

  // Edit Assembly Modal Event Listeners
  if (btnCloseEditAssembly) btnCloseEditAssembly.addEventListener('click', closeEditAssemblyModal);
  if (btnCancelEditAssembly) btnCancelEditAssembly.addEventListener('click', closeEditAssemblyModal);
  if (btnSaveEditAssembly) btnSaveEditAssembly.addEventListener('click', handleSaveEditAssembly);
  if (btnDeleteAssembly) btnDeleteAssembly.addEventListener('click', handleDeleteAssembly);
  if (editAssemblyModal) {
    editAssemblyModal.addEventListener('click', (e) => {
      if (e.target === editAssemblyModal) closeEditAssemblyModal();
    });
  }
  if (searchInput) searchInput.addEventListener('input', handleSearch);
  
  // Create Item Modal Event Listeners
  if (btnAddItemTrigger) btnAddItemTrigger.addEventListener('click', openCreateItemModal);
  if (btnCloseCreateItem) btnCloseCreateItem.addEventListener('click', closeCreateItemModal);
  if (btnCancelCreateItem) btnCancelCreateItem.addEventListener('click', closeCreateItemModal);
  if (btnConfirmCreateItem) btnConfirmCreateItem.addEventListener('click', handleConfirmCreateItem);
  if (createItemModal) {
    createItemModal.addEventListener('click', (e) => {
      if (e.target === createItemModal) closeCreateItemModal();
    });
  }
  
  if (btnBack) btnBack.addEventListener('click', handleBackNavigation);
  if (btnRevert) btnRevert.addEventListener('click', revertChanges);
  if (btnSave) btnSave.addEventListener('click', saveChanges);
  
  if (inputDescription) {
    inputDescription.addEventListener('input', () => {
      checkChanges();
      const descVal = inputDescription.value.trim() || 'No description';
      const pnVal = titlePn ? titlePn.textContent : '';
      if (titleDesc) titleDesc.textContent = descVal;
      document.title = `${pnVal} - ${descVal}`;
    });
  }
  if (inputSource) inputSource.addEventListener('input', checkChanges);
  if (inputExternalPn) inputExternalPn.addEventListener('input', checkChanges);
  if (inputState) inputState.addEventListener('change', checkChanges);
  if (inputManufacturer) inputManufacturer.addEventListener('change', checkChanges);
  if (inputPrice) inputPrice.addEventListener('input', checkChanges);
  if (inputSourcedBy) inputSourcedBy.addEventListener('change', checkChanges);
  if (inputNotes) inputNotes.addEventListener('input', checkChanges);
  
  const btnUploadDatasheet = document.getElementById('btn-upload-datasheet');
  const inputDatasheetFile = document.getElementById('input-datasheet-file');
  if (btnUploadDatasheet && inputDatasheetFile) {
    btnUploadDatasheet.addEventListener('click', () => {
      inputDatasheetFile.click();
    });
    inputDatasheetFile.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        showToast('Uploading PDF...');
        const uploadedFile = await uploadDatasheet(file);
        currentDatasheets.push(uploadedFile);
        renderDatasheetsList();
        checkChanges();
        showToast('Datasheet uploaded successfully.');
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        inputDatasheetFile.value = '';
      }
    });
  }

  if (inputPhotoFile) {
    inputPhotoFile.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        showToast('Uploading photo...');
        const uploadedFile = await uploadDatasheet(file);
        currentImages.push(uploadedFile);
        renderGallery();
        checkChanges();
        showToast('Photo uploaded successfully.');
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        inputPhotoFile.value = '';
      }
    });
  }

  let dragCounter = 0;
  window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    if (!currentItemId) return;
    dragCounter++;
    if (dragCounter === 1) {
      if (dragDropOverlay) {
        dragDropOverlay.style.display = 'flex';
        dragDropOverlay.offsetHeight; // force reflow
        dragDropOverlay.classList.add('active');
      }
    }
  });

  window.addEventListener('dragover', (e) => {
    e.preventDefault();
  });

  window.addEventListener('dragleave', (e) => {
    e.preventDefault();
    if (!currentItemId) return;
    dragCounter--;
    if (dragCounter === 0) {
      if (dragDropOverlay) {
        dragDropOverlay.classList.remove('active');
        setTimeout(() => {
          if (dragCounter === 0) {
            dragDropOverlay.style.display = 'none';
          }
        }, 300);
      }
    }
  });

  window.addEventListener('drop', async (e) => {
    e.preventDefault();
    if (!currentItemId) return;
    dragCounter = 0;
    if (dragDropOverlay) {
      dragDropOverlay.classList.remove('active');
      dragDropOverlay.style.display = 'none';
    }
    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;
    await handleDroppedFiles(files);
  });

  if (addRelatedSearch) {
    addRelatedSearch.addEventListener('input', renderAddRelatedList);
  }
  if (btnCloseAddRelated && addRelatedModal) {
    btnCloseAddRelated.addEventListener('click', () => {
      addRelatedModal.classList.remove('open');
      setTimeout(() => { addRelatedModal.style.display = 'none'; }, 300);
    });
    addRelatedModal.addEventListener('click', (e) => {
      if (e.target === addRelatedModal) {
        addRelatedModal.classList.remove('open');
        setTimeout(() => { addRelatedModal.style.display = 'none'; }, 300);
      }
    });
  }

  ensureManufacturersLoaded();
  
  if (btnFilter) {
    btnFilter.addEventListener('click', () => {
      if (filterDrawer) filterDrawer.classList.add('open');
    });
  }
  
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener('click', () => {
      if (filterDrawer) filterDrawer.classList.remove('open');
    });
  }
  
  if (drawerOverlay) {
    drawerOverlay.addEventListener('click', () => {
      if (filterDrawer) filterDrawer.classList.remove('open');
    });
  }
  

  
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
  } else if (hash === '#/settings') {
    await showSettingsPage();
    return;
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
  const extPnVal = inputExternalPn ? inputExternalPn.value.trim() : '';
  const stateVal = inputState ? inputState.value : 'Unknown';
  const mfgVal = inputManufacturer ? inputManufacturer.value : '';
  const priceVal = inputPrice ? inputPrice.value.trim() : '';
  const sourcedByVal = inputSourcedBy ? inputSourcedBy.value : 'TBD';
  const notesVal = inputNotes ? inputNotes.value.trim() : '';
  
  const datasheetsChanged = JSON.stringify(currentDatasheets.map(d => d.name)) !== JSON.stringify((originalData.datasheets || []).map(d => d.name));
  const imagesChanged = JSON.stringify(currentImages.map(img => img.name)) !== JSON.stringify((originalData.images || []).map(img => img.name));
  
  const originalRelatedIds = (originalData.relatedItems || []).map(r => r.id).sort();
  const currentRelatedIds = currentRelated.map(r => r.id).sort();
  const relatedChanged = JSON.stringify(originalRelatedIds) !== JSON.stringify(currentRelatedIds);
  
  const priceDiff = parseFloat(priceVal) !== parseFloat(originalData.price);
  const priceChanged = (isNaN(parseFloat(priceVal)) && isNaN(parseFloat(originalData.price))) ? false : priceDiff;

  return descVal !== originalData.description ||
         srcVal !== originalData.source ||
         extPnVal !== originalData.externalPn ||
         stateVal !== originalData.state ||
         String(mfgVal) !== String(originalData.manufacturerId) ||
         priceChanged ||
         sourcedByVal !== originalData.sourcedBy ||
         notesVal !== originalData.notes ||
         datasheetsChanged ||
         imagesChanged ||
         relatedChanged;
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
  document.title = 'ERA BOM Explorer';
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
    
    const fullPnStr = item["Full PN"] || item["Part Number"] || 'N/A';
    const descStr = item["Item description"] || 'No description';
    
    if (titlePn) titlePn.textContent = fullPnStr;
    if (titleDesc) titleDesc.textContent = descStr;
    document.title = `${fullPnStr} - ${descStr}`;
    
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
    
    await ensureManufacturersLoaded();
    await ensureAllItemsLoaded();
    
    const setList = item["Part of a set"] || [];
    const relatedMapped = setList
      .filter(x => x.id !== itemId)
      .map(x => {
        const matched = allItems.find(i => i.id === x.id);
        return matched ? {
          id: x.id,
          fullPn: x.value,
          description: matched["Item description"] || 'No description',
          image: matched["Image"] || []
        } : {
          id: x.id,
          fullPn: x.value,
          description: 'Unknown description',
          image: []
        };
      });

    originalData = {
      fullPn: item["Full PN"] || item["Part Number"] || 'N/A',
      description: item["Item description"] || '',
      source: item["Source URL"] || '',
      externalPn: item["External Part Number"] || '',
      state: item["State"] ? item["State"].value : 'Unknown',
      manufacturerId: (item["Manufacturer"] && item["Manufacturer"].length > 0) ? item["Manufacturer"][0].id : '',
      price: item["Price per unit"] !== null ? parseFloat(item["Price per unit"]) : null,
      sourcedBy: item["Sourced By"] ? item["Sourced By"].value : 'TBD',
      notes: item["Notes"] || '',
      datasheets: item["Datasheet"] || [],
      images: item["Image"] || [],
      relatedItems: relatedMapped
    };
    
    if (inputDescription) inputDescription.value = originalData.description;
    if (inputSource) inputSource.value = originalData.source;
    if (inputExternalPn) inputExternalPn.value = originalData.externalPn;
    if (inputState) inputState.value = originalData.state;
    if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
    if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';
    if (inputSourcedBy) inputSourcedBy.value = originalData.sourcedBy;
    if (inputNotes) inputNotes.value = originalData.notes;
    
    currentDatasheets = [...(originalData.datasheets || [])];
    renderDatasheetsList();
    
    currentImages = [...(originalData.images || [])];
    renderGallery();
    
    currentRelated = [...(originalData.relatedItems || [])];
    renderRelatedItems();
    renderRevisionTags(item);
    
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
  if (inputExternalPn) inputExternalPn.value = originalData.externalPn;
  if (inputState) inputState.value = originalData.state;
  if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
  if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';
  if (inputSourcedBy) inputSourcedBy.value = originalData.sourcedBy;
  if (inputNotes) inputNotes.value = originalData.notes;
  
  if (titleDesc) titleDesc.textContent = originalData.description || 'No description';
  document.title = `${originalData.fullPn || 'N/A'} - ${originalData.description || 'No description'}`;

  currentDatasheets = [...(originalData.datasheets || [])];
  renderDatasheetsList();
  
  currentImages = [...(originalData.images || [])];
  renderGallery();
  
  currentRelated = [...(originalData.relatedItems || [])];
  renderRelatedItems();
  
  checkChanges();
  showToast('Changes reverted to original values.');
}

async function saveChanges() {
  if (!currentItemId) return;
  
  const descVal = inputDescription ? inputDescription.value.trim() : '';
  const srcVal = inputSource ? inputSource.value.trim() : '';
  const extPnVal = inputExternalPn ? inputExternalPn.value.trim() : '';
  const stateVal = inputState ? inputState.value : 'Unknown';
  const mfgVal = inputManufacturer && inputManufacturer.value ? [parseInt(inputManufacturer.value, 10)] : [];
  const priceVal = inputPrice && inputPrice.value.trim() !== '' ? parseFloat(inputPrice.value) : null;
  const sourcedByVal = inputSourcedBy ? inputSourcedBy.value : 'TBD';
  const notesVal = inputNotes ? inputNotes.value.trim() : '';
  
  const relatedIds = [currentItemId, ...currentRelated.map(r => r.id)];
  
  try {
    showToast('Saving changes to Baserow...');
    
    await updateItem(currentItemId, {
      "Item description": descVal,
      "Source URL": srcVal,
      "External Part Number": extPnVal,
      "State": stateVal,
      "Manufacturer": mfgVal,
      "Price per unit": priceVal,
      "Sourced By": sourcedByVal,
      "Notes": notesVal,
      "Datasheet": currentDatasheets,
      "Image": currentImages,
      "Part of a set": relatedIds
    });
    
    originalData = {
      description: descVal,
      source: srcVal,
      externalPn: extPnVal,
      state: stateVal,
      manufacturerId: inputManufacturer ? inputManufacturer.value : '',
      price: priceVal,
      sourcedBy: sourcedByVal,
      notes: notesVal,
      datasheets: [...currentDatasheets],
      images: [...currentImages],
      relatedItems: [...currentRelated]
    };
    
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
    
    const [treeData, rulesData, flatData] = await Promise.all([
      fetchBomTree(),
      fetchRules().catch(err => {
        console.error("Failed to fetch rules", err);
        return {};
      }),
      fetchFlatItems().catch(err => {
        console.error("Failed to fetch flat items", err);
        return [];
      })
    ]);
    allItems = flatData || [];
    categoryRules = rulesData;
    
    rawTree = sortTreeNodesRecursively(treeData);
    
    if (expandedNodes.size === 0) {
      rawTree.forEach(node => {
        expandedNodes.add(String(node.id));
      });
    }
    
    renderDrawerCategories();
    renderDrawerStates();
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
    const [treeData, rulesData, flatData] = await Promise.all([
      fetchBomTree(),
      fetchRules().catch(err => {
        console.error("Failed to fetch rules", err);
        return {};
      }),
      fetchFlatItems().catch(err => {
        console.error("Failed to fetch flat items", err);
        return [];
      })
    ]);
    allItems = flatData || [];
    categoryRules = rulesData;
    rawTree = sortTreeNodesRecursively(treeData);
    renderDrawerCategories();
    renderDrawerStates();
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
  autoExpandedNodes.clear();
  const result = [];
  
  rawTree.forEach(node => {
    const filtered = filterNode(node, searchQuery, String(node.id), []);
    if (filtered) {
      result.push(filtered);
    }
  });
  filteredTree = sortTreeNodesRecursively(result);
  
  renderTreeTable();
}

function filterNode(node, query, currentPath, parentPaths, ancestorMatched = false) {
  const categoryName = (node.pn_tag && node.pn_tag.name) || 'Unknown';
  const isDisabledCategory = disabledCategories.has(categoryName);
  const isDisabledState = disabledStates.has(node.state || 'Unknown');
  const isDisabled = isDisabledCategory || isDisabledState;
  
  const matchesPN = node.part_number && node.part_number.toLowerCase().includes(query);
  const matchesDesc = node.description && node.description.toLowerCase().includes(query);
  const matchesHelper = node.search_helper && node.search_helper.toLowerCase().includes(query);
  const matchesExtPN = node.external_pn && node.external_pn.toLowerCase().includes(query);
  const matchesNotes = node.notes && node.notes.toLowerCase().includes(query);
  
  const isSelfMatch = !query ? true : (matchesPN || matchesDesc || matchesHelper || matchesExtPN || matchesNotes);
  const isMatch = isSelfMatch || ancestorMatched;
  const filteredChildren = [];
  
  if (node.children && node.children.length > 0) {
    node.children.forEach(child => {
      const childPath = `${currentPath}/${child.id}`;
      const filteredChild = filterNode(child, query, childPath, [...parentPaths, currentPath], isMatch);
      if (filteredChild) {
        filteredChildren.push(filteredChild);
      }
    });
  }
  
  const hasMatchingChildren = filteredChildren.length > 0;
  
  if (isMatch || hasMatchingChildren) {
    if (hasMatchingChildren && query && isSelfMatch) {
      parentPaths.forEach(p => autoExpandedNodes.add(p));
      autoExpandedNodes.add(currentPath);
    }
    return {
      ...node,
      children: filteredChildren,
      isMatch: isMatch,
      isDisabledCategory: isDisabled
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
    if (node.isDisabledCategory) {
      rowEl.classList.add('disabled-row');
    }
    
    // Slide menu element
    const menuEl = document.createElement('div');
    menuEl.className = 'row-action-menu';
    
    const plusBtn = document.createElement('button');
    plusBtn.className = 'row-menu-btn enabled';
    plusBtn.textContent = '+';
    plusBtn.title = 'Add Child to Assembly';
    plusBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openAddChildModal(node.id);
    });
    
    menuEl.appendChild(plusBtn);

    if (level > 0 && node.edge_id) {
      const editBtn = document.createElement('button');
      editBtn.className = 'row-menu-btn enabled';
      editBtn.innerHTML = '<i class="fa-solid fa-pencil"></i>';
      editBtn.title = 'Edit Assembly Properties';
      editBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        openEditAssemblyModal(node);
      });
      menuEl.appendChild(editBtn);
    }
    
    const openBtn = document.createElement('button');
    openBtn.className = 'row-menu-btn enabled';
    openBtn.innerHTML = '<i class="fa-solid fa-up-right-from-square"></i>';
    openBtn.title = 'Open Item Details';
    
    openBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      navigateToItem(getLatestRevisionId(node.part_number, node.id));
    });
    
    menuEl.appendChild(openBtn);
    rowEl.appendChild(menuEl);
    
    // Single click handler to toggle menu open/close
    rowEl.addEventListener('click', (e) => {
      if (e.target.closest('.node-toggle') || e.target.closest('.row-menu-btn') || e.target.closest('.revision-tag')) return;
      
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
      if (e.target.closest('.node-toggle') || e.target.closest('.row-menu-btn') || e.target.closest('.revision-tag')) return;
      navigateToItem(getLatestRevisionId(node.part_number, node.id));
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
    
    const pnSpan = document.createElement('span');
    pnSpan.className = 'pn-number';
    pnSpan.innerHTML = highlightText(node.part_number, searchQuery);
    pnCol.appendChild(pnSpan);
    
    const revs = getRevisionsForPN(node.part_number);
    if (revs.length > 0) {
      const revsContainer = document.createElement('span');
      revsContainer.className = 'pn-revisions-container';
      revsContainer.style.marginLeft = '0.5rem';
      revsContainer.style.display = 'inline-flex';
      revsContainer.style.gap = '0.25rem';
      revsContainer.style.alignItems = 'center';
      
      const maxToShow = 3;
      const totalRevs = revs.length;
      
      if (totalRevs > maxToShow) {
        const dots = document.createElement('span');
        dots.className = 'pn-rev-dots';
        dots.textContent = '...';
        dots.style.color = 'var(--text-secondary)';
        dots.style.marginRight = '0.1rem';
        revsContainer.appendChild(dots);
      }
      
      const startIdx = Math.max(0, totalRevs - maxToShow);
      const latestRevs = revs.slice(startIdx);
      
      latestRevs.forEach(revItem => {
        const tag = document.createElement('span');
        tag.className = 'revision-tag';
        tag.textContent = revItem.revision || 'N/A';
        tag.style.padding = '0.05rem 0.25rem';
        tag.style.fontSize = '0.65rem';
        tag.style.lineHeight = '1';
        
        if (revItem.id === node.id) {
          tag.classList.add('active');
        }
        
        tag.style.cursor = 'pointer';
        tag.addEventListener('click', (e) => {
          e.stopPropagation();
          navigateToItem(revItem.id);
        });
        
        revsContainer.appendChild(tag);
      });
      
      pnCol.appendChild(revsContainer);
    }
    
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

function getItemRevision(id) {
  const item = allItems.find(i => i.id === id);
  return item ? (item["Revision"] || '') : '';
}

function getRevisionsForPN(partNumber) {
  if (!partNumber) return [];
  const revs = allItems
    .filter(item => item["Part Number"] === partNumber)
    .map(item => ({
      id: item.id,
      revision: item["Revision"] || ''
    }));

  revs.sort((a, b) => {
    const revA = a.revision;
    const revB = b.revision;
    if (revA.length !== revB.length) {
      return revA.length - revB.length;
    }
    return revA.localeCompare(revB);
  });
  return revs;
}

function getLatestRevisionId(partNumber, fallbackId) {
  const revs = getRevisionsForPN(partNumber);
  if (revs.length > 0) {
    return revs[revs.length - 1].id;
  }
  return fallbackId;
}

function filterDuplicateRevisions(nodes) {
  if (!nodes || nodes.length === 0) return [];
  
  const groups = {};
  nodes.forEach(node => {
    const pn = node.part_number;
    if (!pn) {
      const uniqueKey = `unique_${node.id}`;
      groups[uniqueKey] = [node];
    } else {
      if (!groups[pn]) {
        groups[pn] = [];
      }
      groups[pn].push(node);
    }
  });
  
  const result = [];
  for (const pn in groups) {
    const groupNodes = groups[pn];
    if (groupNodes.length === 1) {
      result.push(groupNodes[0]);
    } else {
      groupNodes.sort((a, b) => {
        const revA = getItemRevision(a.id);
        const revB = getItemRevision(b.id);
        if (revA.length !== revB.length) {
          return revA.length - revB.length;
        }
        return revA.localeCompare(revB);
      });
      result.push(groupNodes[groupNodes.length - 1]);
    }
  }
  return result;
}

function sortTreeNodesRecursively(nodes) {
  if (!nodes || nodes.length === 0) return [];
  
  const filteredNodes = filterDuplicateRevisions(nodes);
  
  filteredNodes.forEach(node => {
    if (node.children && node.children.length > 0) {
      node.children = sortTreeNodesRecursively(node.children);
    }
  });
  
  return [...filteredNodes].sort((a, b) => {
    const actA = a.isDisabledCategory ? 1 : 0;
    const actB = b.isDisabledCategory ? 1 : 0;
    if (actA !== actB) return actA - actB;
    
    const catA = (a.pn_tag && a.pn_tag.name) || 'Unknown';
    const catB = (b.pn_tag && b.pn_tag.name) || 'Unknown';
    const catComp = catA.localeCompare(catB);
    if (catComp !== 0) return catComp;
    
    const pnA = a.part_number || '';
    const pnB = b.part_number || '';
    return pnA.localeCompare(pnB);
  });
}

function renderDrawerCategories() {
  const container = document.getElementById('categories-filter-list');
  if (!container) return;
  container.innerHTML = '';
  
  const categoriesMap = new Map();
  Object.values(categoryRules).forEach(rule => {
    if (rule.name) {
      categoriesMap.set(rule.name, rule.color || '#8e9095');
    }
  });
  if (!categoriesMap.has('Unknown')) {
    categoriesMap.set('Unknown', '#8e9095');
  }
  
  const sortedCategories = Array.from(categoriesMap.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  
  // Create Select All categories checkbox item
  const selectAllEl = document.createElement('div');
  selectAllEl.className = 'category-filter-item select-all-item';
  selectAllEl.style.fontWeight = '600';
  selectAllEl.style.borderBottom = '1px solid var(--card-border)';
  selectAllEl.style.paddingBottom = '0.5rem';
  selectAllEl.style.marginBottom = '0.5rem';
  
  const selectAllCheckbox = document.createElement('input');
  selectAllCheckbox.type = 'checkbox';
  selectAllCheckbox.className = 'category-filter-checkbox';
  selectAllCheckbox.checked = disabledCategories.size === 0;
  selectAllCheckbox.id = 'filter-cat-select-all';
  
  const selectAllLabel = document.createElement('label');
  selectAllLabel.className = 'category-filter-label';
  selectAllLabel.htmlFor = selectAllCheckbox.id;
  selectAllLabel.textContent = 'Select All';
  
  selectAllEl.appendChild(selectAllCheckbox);
  selectAllEl.appendChild(selectAllLabel);
  
  selectAllCheckbox.addEventListener('change', () => {
    if (selectAllCheckbox.checked) {
      disabledCategories.clear();
    } else {
      sortedCategories.forEach(([catName]) => {
        disabledCategories.add(catName);
      });
    }
    renderDrawerCategories();
    applyFilterAndRender();
  });
  
  selectAllEl.addEventListener('click', (e) => {
    if (e.target !== selectAllCheckbox && e.target !== selectAllLabel && !selectAllLabel.contains(e.target)) {
      selectAllCheckbox.checked = !selectAllCheckbox.checked;
      selectAllCheckbox.dispatchEvent(new Event('change'));
    }
  });
  
  container.appendChild(selectAllEl);
  
  sortedCategories.forEach(([catName, color]) => {
    const isEnabled = !disabledCategories.has(catName);
    
    const itemEl = document.createElement('div');
    itemEl.className = 'category-filter-item';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'category-filter-checkbox';
    checkbox.checked = isEnabled;
    checkbox.id = `filter-cat-${catName.replace(/\s+/g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'category-filter-label';
    label.htmlFor = checkbox.id;
    
    const colorDot = document.createElement('span');
    colorDot.className = 'category-color-dot';
    colorDot.style.backgroundColor = color;
    
    const nameText = document.createTextNode(catName);
    
    label.appendChild(colorDot);
    label.appendChild(nameText);
    
    itemEl.appendChild(checkbox);
    itemEl.appendChild(label);
    
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        disabledCategories.delete(catName);
      } else {
        disabledCategories.add(catName);
      }
      updateFilterBadge();
      applyFilterAndRender();
    });
    
    itemEl.addEventListener('click', (e) => {
      if (e.target !== checkbox && e.target !== label && !label.contains(e.target)) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    container.appendChild(itemEl);
  });
  
  updateFilterBadge();
}

const STATE_COLORS = {
  "Production Use": "hsl(170, 75%, 45%)",
  "Engineerig Use": "hsl(210, 75%, 50%)",
  "Unknown": "hsl(0, 0%, 60%)",
  "Finish Stock (Use Up)": "hsl(38, 95%, 50%)",
  "EOL": "hsl(25, 75%, 45%)",
  "Do Not Use (Discard)": "hsl(355, 80%, 50%)"
};

function renderDrawerStates() {
  const container = document.getElementById('states-filter-list');
  if (!container) return;
  container.innerHTML = '';
  
  const states = Object.keys(STATE_COLORS);
  
  // Create Select All states checkbox item
  const selectAllEl = document.createElement('div');
  selectAllEl.className = 'category-filter-item select-all-item';
  selectAllEl.style.fontWeight = '600';
  selectAllEl.style.borderBottom = '1px solid var(--card-border)';
  selectAllEl.style.paddingBottom = '0.5rem';
  selectAllEl.style.marginBottom = '0.5rem';
  
  const selectAllCheckbox = document.createElement('input');
  selectAllCheckbox.type = 'checkbox';
  selectAllCheckbox.className = 'category-filter-checkbox';
  selectAllCheckbox.checked = disabledStates.size === 0;
  selectAllCheckbox.id = 'filter-state-select-all';
  
  const selectAllLabel = document.createElement('label');
  selectAllLabel.className = 'category-filter-label';
  selectAllLabel.htmlFor = selectAllCheckbox.id;
  selectAllLabel.textContent = 'Select All';
  
  selectAllEl.appendChild(selectAllCheckbox);
  selectAllEl.appendChild(selectAllLabel);
  
  selectAllCheckbox.addEventListener('change', () => {
    if (selectAllCheckbox.checked) {
      disabledStates.clear();
    } else {
      states.forEach(s => {
        disabledStates.add(s);
      });
    }
    renderDrawerStates();
    applyFilterAndRender();
  });
  
  selectAllEl.addEventListener('click', (e) => {
    if (e.target !== selectAllCheckbox && e.target !== selectAllLabel && !selectAllLabel.contains(e.target)) {
      selectAllCheckbox.checked = !selectAllCheckbox.checked;
      selectAllCheckbox.dispatchEvent(new Event('change'));
    }
  });
  
  container.appendChild(selectAllEl);
  
  states.forEach(stateName => {
    const isEnabled = !disabledStates.has(stateName);
    const color = STATE_COLORS[stateName];
    
    const itemEl = document.createElement('div');
    itemEl.className = 'category-filter-item';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'category-filter-checkbox';
    checkbox.checked = isEnabled;
    checkbox.id = `filter-state-${stateName.replace(/\s+/g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'category-filter-label';
    label.htmlFor = checkbox.id;
    
    const colorDot = document.createElement('span');
    colorDot.className = 'category-color-dot';
    colorDot.style.backgroundColor = color;
    
    const nameText = document.createTextNode(stateName === 'Engineerig Use' ? 'Engineering Use' : stateName);
    
    label.appendChild(colorDot);
    label.appendChild(nameText);
    
    itemEl.appendChild(checkbox);
    itemEl.appendChild(label);
    
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        disabledStates.delete(stateName);
      } else {
        disabledStates.add(stateName);
      }
      updateFilterBadge();
      applyFilterAndRender();
    });
    
    itemEl.addEventListener('click', (e) => {
      if (e.target !== checkbox && e.target !== label && !label.contains(e.target)) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    container.appendChild(itemEl);
  });
  
  updateFilterBadge();
}

function updateFilterBadge() {
  const badge = document.getElementById('filter-badge');
  const btnFilterElement = document.getElementById('btn-filter');
  if (!badge || !btnFilterElement) return;
  
  const count = disabledCategories.size + disabledStates.size;
  if (count > 0) {
    badge.textContent = count;
    badge.style.display = 'grid';
    btnFilterElement.classList.add('active-filter');
  } else {
    badge.style.display = 'none';
    btnFilterElement.classList.remove('active-filter');
  }
}

async function ensureManufacturersLoaded() {
  if (manufacturers.length > 0) return;
  try {
    manufacturers = await fetchManufacturers();
    populateManufacturersDropdown();
  } catch (err) {
    console.error("Failed to load manufacturers:", err);
  }
}

function populateManufacturersDropdown() {
  const select = document.getElementById('input-manufacturer');
  if (!select) return;
  select.innerHTML = '<option value="">None</option>';
  manufacturers.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.name;
    select.appendChild(opt);
  });
}

function renderDatasheetsList() {
  const container = document.getElementById('datasheets-list');
  if (!container) return;
  container.innerHTML = '';
  
  if (currentDatasheets.length === 0) {
    container.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic;">No datasheet PDFs available.</div>';
    return;
  }
  
  currentDatasheets.forEach((file, index) => {
    const btn = document.createElement('a');
    btn.href = file.url;
    btn.target = '_blank';
    btn.className = 'datasheet-btn';
    btn.title = `Open ${file.visible_name || file.name}`;
    
    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-file-pdf pdf-icon';
    
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn-delete-datasheet';
    deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
    deleteBtn.title = 'Remove datasheet';
    deleteBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      showConfirmModal(
        'Remove Datasheet',
        'Are you sure you want to remove this datasheet?',
        '<i class="fa-solid fa-file-pdf pdf-icon"></i>',
        () => {
          currentDatasheets.splice(index, 1);
          renderDatasheetsList();
          checkChanges();
          showToast('Datasheet removed.');
        }
      );
    });
    
    btn.appendChild(deleteBtn);
    btn.appendChild(icon);
    container.appendChild(btn);
  });
}

function renderGallery() {
  if (!galleryContainer) return;
  galleryContainer.innerHTML = '';
  
  if (currentImages.length === 0) {
    galleryContainer.innerHTML = `
      <div class="gallery-placeholder">
        <span>📷</span>
        <span>No images available for this item</span>
      </div>
    `;
  } else {
    currentImages.forEach((img, index) => {
      const imgCard = document.createElement('div');
      imgCard.className = 'gallery-image-card';
      imgCard.innerHTML = `<img src="${img.url}" alt="Item image" />`;
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn-delete-image';
      deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
      deleteBtn.title = 'Remove photo';
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showConfirmModal(
          'Remove Photo',
          'Are you sure you want to remove this photo?',
          `<img src="${img.url}" alt="Preview" />`,
          () => {
            currentImages.splice(index, 1);
            renderGallery();
            checkChanges();
            showToast('Photo removed.');
          }
        );
      });
      imgCard.appendChild(deleteBtn);
      galleryContainer.appendChild(imgCard);
    });
  }
  
  // Append the Add Photo card
  const addCard = document.createElement('div');
  addCard.className = 'gallery-image-card add-image-card';
  addCard.id = 'btn-add-photo';
  addCard.innerHTML = `
    <i class="fa-solid fa-plus add-icon"></i>
    <span>Add Photo</span>
  `;
  addCard.addEventListener('click', () => {
    const input = document.getElementById('input-photo-file');
    if (input) input.click();
  });
  galleryContainer.appendChild(addCard);
}

async function handleDroppedFiles(files) {
  const validFiles = [];
  const invalidFiles = [];

  files.forEach(file => {
    const isPDF = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|gif|webp|svg)$/i.test(file.name);

    if (isPDF || isImage) {
      validFiles.push({ file, type: isPDF ? 'pdf' : 'image' });
    } else {
      invalidFiles.push(file.name);
    }
  });

  if (invalidFiles.length > 0) {
    showToast(`Discarded unsupported files: ${invalidFiles.join(', ')}`, 'error');
  }

  if (validFiles.length === 0) return;

  const total = validFiles.length;
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < total; i++) {
    const { file, type } = validFiles[i];
    showToast(`Uploading file ${i + 1} of ${total}: ${file.name}...`);

    try {
      const uploadedFile = await uploadDatasheet(file);
      if (type === 'pdf') {
        currentDatasheets.push(uploadedFile);
      } else {
        currentImages.push(uploadedFile);
      }
      successCount++;
    } catch (err) {
      console.error(`Failed to upload ${file.name}:`, err);
      failCount++;
    }
  }

  renderDatasheetsList();
  renderGallery();
  checkChanges();

  if (successCount > 0 && failCount === 0) {
    showToast(`Successfully uploaded ${successCount} file(s).`);
  } else if (successCount > 0 && failCount > 0) {
    showToast(`Uploaded ${successCount} file(s), but ${failCount} failed.`, 'error');
  } else if (failCount > 0) {
    showToast(`Failed to upload ${failCount} file(s).`, 'error');
  }
}

function showConfirmModal(title, message, previewHtml, onAccept) {
  const modal = document.getElementById('confirm-modal');
  const titleEl = document.getElementById('confirm-modal-title');
  const messageEl = document.getElementById('confirm-modal-message');
  const previewEl = document.getElementById('confirm-modal-preview');
  const btnClose = document.getElementById('btn-close-confirm');
  const btnCancel = document.getElementById('btn-confirm-cancel');
  const btnAccept = document.getElementById('btn-confirm-accept');

  if (!modal || !titleEl || !messageEl || !btnAccept) return;

  titleEl.textContent = title;
  messageEl.textContent = message;
  
  if (previewEl) {
    previewEl.innerHTML = previewHtml || '';
  }

  modal.style.display = 'flex';
  modal.offsetHeight; // force reflow
  modal.classList.add('open');

  const closeModal = () => {
    modal.classList.remove('open');
    setTimeout(() => {
      modal.style.display = 'none';
    }, 300);
    cleanup();
  };

  const handleAccept = () => {
    onAccept();
    closeModal();
  };

  const cleanup = () => {
    btnAccept.removeEventListener('click', handleAccept);
    btnCancel?.removeEventListener('click', closeModal);
    btnClose?.removeEventListener('click', closeModal);
    modal.removeEventListener('click', handleOverlayClick);
  };

  const handleOverlayClick = (e) => {
    if (e.target === modal) {
      closeModal();
    }
  };

  btnAccept.addEventListener('click', handleAccept);
  btnCancel?.addEventListener('click', closeModal);
  btnClose?.addEventListener('click', closeModal);
  modal.addEventListener('click', handleOverlayClick);
}

async function ensureAllItemsLoaded() {
  if (allItems.length > 0) return;
  try {
    const data = await fetchFlatItems();
    allItems = data;
  } catch (err) {
    console.error("Failed to load all items:", err);
  }
}

function renderRelatedItems() {
  if (!relatedItemsContainer) return;
  relatedItemsContainer.innerHTML = '';
  
  if (currentRelated.length === 0) {
    relatedItemsContainer.classList.add('empty-set');
  } else {
    relatedItemsContainer.classList.remove('empty-set');
    currentRelated.forEach((item, index) => {
      const card = document.createElement('div');
      card.className = 'related-item-card';
      
      const photoBox = document.createElement('div');
      photoBox.className = 'related-item-photo';
      
      if (item.image && item.image.length > 0) {
        const img = document.createElement('img');
        img.src = item.image[0].url;
        photoBox.appendChild(img);
      } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'gallery-placeholder';
        placeholder.style.padding = '0';
        placeholder.innerHTML = '<span>📦</span>';
        photoBox.appendChild(placeholder);
      }
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn-delete-related';
      deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
      deleteBtn.title = 'Remove relation';
      deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const previewHtml = item.image && item.image.length > 0
          ? `<img src="${item.image[0].url}" alt="Preview" />`
          : '<span>📦</span>';
        showConfirmModal(
          'Remove Related Item',
          'Are you sure you want to remove this related item relationship?',
          `<div class="confirm-preview-box">${previewHtml}</div>`,
          () => {
            currentRelated.splice(index, 1);
            renderRelatedItems();
            checkChanges();
            showToast('Related item relationship removed.');
          }
        );
      });
      photoBox.appendChild(deleteBtn);
      
      const infoBox = document.createElement('div');
      infoBox.className = 'related-item-info';
      
      const pnTag = document.createElement('span');
      pnTag.className = 'related-item-pn';
      pnTag.textContent = item.fullPn;
      
      const descTag = document.createElement('span');
      descTag.className = 'related-item-desc';
      descTag.title = item.description;
      descTag.textContent = item.description;
      
      infoBox.appendChild(pnTag);
      infoBox.appendChild(descTag);
      
      card.appendChild(photoBox);
      card.appendChild(infoBox);
      relatedItemsContainer.appendChild(card);
    });
  }
  
  // Append the Add button card
  const addCard = document.createElement('div');
  addCard.className = 'add-related-card';
  addCard.innerHTML = `
    <i class="fa-solid fa-plus add-icon"></i>
    <span>Add Item</span>
  `;
  addCard.addEventListener('click', openAddRelatedModal);
  relatedItemsContainer.appendChild(addCard);
}

async function openAddRelatedModal() {
  if (!addRelatedModal) return;

  addRelatedModal.style.display = 'flex';
  addRelatedModal.offsetHeight;
  addRelatedModal.classList.add('open');

  if (addRelatedSearch) {
    addRelatedSearch.value = '';
    addRelatedSearch.focus();
  }

  await ensureAllItemsLoaded();
  renderAddRelatedList();
}

function renderAddRelatedList() {
  if (!addRelatedList) return;
  
  addRelatedList.innerHTML = '';
  const query = addRelatedSearch ? addRelatedSearch.value.toLowerCase().trim() : '';

  const currentSetIds = [currentItemId, ...currentRelated.map(r => r.id)];
  
  const filtered = allItems.filter(item => {
    if (currentSetIds.includes(item.id)) return false;
    
    const pn = (item["Part Number"] || '').toLowerCase();
    const desc = (item["Item description"] || '').toLowerCase();
    
    return pn.includes(query) || desc.includes(query);
  });

  if (filtered.length === 0) {
    addRelatedList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">No matching items found.</div>';
    return;
  }

  filtered.forEach(item => {
    const row = document.createElement('div');
    row.className = 'add-related-item-row';
    row.addEventListener('click', () => {
      const revStr = item["Revision"] ? ` Rev.${item["Revision"]}` : '';
      currentRelated.push({
        id: item.id,
        fullPn: `${item["Part Number"]}${revStr}`,
        description: item["Item description"] || 'No description',
        image: item["Image"] || []
      });
      renderRelatedItems();
      checkChanges();
      
      if (addRelatedModal) {
        addRelatedModal.classList.remove('open');
        setTimeout(() => { addRelatedModal.style.display = 'none'; }, 300);
      }
      showToast('Related item added.');
    });

    const photoBox = document.createElement('div');
    photoBox.className = 'row-photo';
    if (item["Image"] && item["Image"].length > 0) {
      const img = document.createElement('img');
      img.src = item["Image"][0].url;
      photoBox.appendChild(img);
    } else {
      photoBox.innerHTML = '<span>📦</span>';
    }

    const infoBox = document.createElement('div');
    infoBox.className = 'row-info';

    const pnLabel = document.createElement('span');
    pnLabel.className = 'row-pn';
    const revStr = item["Revision"] ? ` Rev.${item["Revision"]}` : '';
    pnLabel.textContent = `${item["Part Number"]}${revStr}`;

    const descLabel = document.createElement('span');
    descLabel.className = 'row-desc';
    descLabel.textContent = item["Item description"] || 'No description';

    infoBox.appendChild(pnLabel);
    infoBox.appendChild(descLabel);

    row.appendChild(photoBox);
    row.appendChild(infoBox);
    addRelatedList.appendChild(row);
  });
}

function renderRevisionTags(currentItem) {
  if (!revisionTagsContainer) return;
  revisionTagsContainer.innerHTML = '';

  const partNumber = currentItem["Part Number"];
  if (!partNumber) return;

  const revisions = allItems
    .filter(item => item["Part Number"] === partNumber)
    .map(item => ({
      id: item.id,
      revision: item["Revision"] || ''
    }));

  revisions.sort((a, b) => {
    const revA = a.revision;
    const revB = b.revision;
    if (revA.length !== revB.length) {
      return revA.length - revB.length;
    }
    return revA.localeCompare(revB);
  });

  revisions.forEach(revItem => {
    const tag = document.createElement('a');
    tag.className = 'revision-tag';
    tag.textContent = revItem.revision || 'N/A';
    
    if (revItem.id === currentItemId) {
      tag.classList.add('active');
    } else {
      tag.addEventListener('click', (e) => {
        e.preventDefault();
        navigateToItem(revItem.id);
      });
    }
    revisionTagsContainer.appendChild(tag);
  });

  const addTag = document.createElement('span');
  addTag.className = 'revision-tag disabled';
  addTag.textContent = '+ Add';
  revisionTagsContainer.appendChild(addTag);
}

// Create Item Dialog Logic
function openCreateItemModal() {
  if (!createItemModal) return;
  if (createItemDescription) createItemDescription.value = '';
  
  if (createItemCategory) {
    createItemCategory.innerHTML = '';
    const categories = Object.entries(categoryRules)
      .map(([prefix, rule]) => ({ prefix, name: rule.name || 'Unknown' }))
      .sort((a, b) => a.name.localeCompare(b.name));
      
    categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat.prefix;
      opt.textContent = `${cat.prefix} - ${cat.name}`;
      createItemCategory.appendChild(opt);
    });
  }
  
  if (btnConfirmCreateItem) btnConfirmCreateItem.disabled = false;
  
  createItemModal.style.display = 'flex';
  createItemModal.offsetHeight;
  createItemModal.classList.add('open');
  if (createItemDescription) createItemDescription.focus();
}

function closeCreateItemModal() {
  if (!createItemModal) return;
  createItemModal.classList.remove('open');
  setTimeout(() => { createItemModal.style.display = 'none'; }, 300);
}

async function handleConfirmCreateItem() {
  if (!createItemCategory || !createItemDescription) return;
  const prefix = createItemCategory.value;
  const description = createItemDescription.value.trim();
  
  if (!description) {
    showToast('Description is required.', 'error');
    if (createItemDescription) createItemDescription.focus();
    return;
  }
  
  if (btnConfirmCreateItem) btnConfirmCreateItem.disabled = true;
  
  try {
    const newItem = await createItem(prefix, description);
    showToast('Item created successfully!');
    closeCreateItemModal();
    window.location.hash = `#item/${newItem.id}`;
  } catch (err) {
    showToast(`Failed to create item: ${err.message}`, 'error');
    if (btnConfirmCreateItem) btnConfirmCreateItem.disabled = false;
  }
}

// Add Child Dialog Logic
function openAddChildModal(parentId) {
  if (!addChildModal) return;
  addChildParentId = parentId;
  addChildSelectedItemId = null;
  addChildSelectedRevId = null;
  
  if (addChildSearch) addChildSearch.value = '';
  if (addChildList) addChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a child item...</div>';
  if (addChildForm) addChildForm.style.display = 'none';
  if (btnConfirmAddChild) btnConfirmAddChild.disabled = true;
  
  addChildModal.style.display = 'flex';
  addChildModal.offsetHeight;
  addChildModal.classList.add('open');
  if (addChildSearch) addChildSearch.focus();
}

function closeAddChildModal() {
  if (!addChildModal) return;
  addChildModal.classList.remove('open');
  setTimeout(() => { addChildModal.style.display = 'none'; }, 300);
}

function renderAddChildList() {
  if (!addChildList) return;
  addChildList.innerHTML = '';
  const query = addChildSearch ? addChildSearch.value.toLowerCase().trim() : '';
  
  if (!query) {
    addChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a child item...</div>';
    return;
  }
  
  const filtered = allItems.filter(item => {
    if (item.id === addChildParentId) return false;
    
    const pn = (item["Part Number"] || '').toLowerCase();
    const desc = (item["Item description"] || '').toLowerCase();
    const extPn = (item["External PN"] || '').toLowerCase();
    const notes = (item["Notes"] || '').toLowerCase();
    const helper = (item["Search helper"] || '').toLowerCase();
    
    return pn.includes(query) || desc.includes(query) || extPn.includes(query) || notes.includes(query) || helper.includes(query);
  });
  
  const distinctParts = [];
  const pnsSeen = new Set();
  filtered.forEach(item => {
    if (item["Part Number"] && !pnsSeen.has(item["Part Number"])) {
      pnsSeen.add(item["Part Number"]);
      distinctParts.push(item);
    }
  });

  if (distinctParts.length === 0) {
    addChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">No matching items found.</div>';
    return;
  }
  
  distinctParts.forEach(item => {
    const row = document.createElement('div');
    row.className = 'add-related-item-row';
    row.addEventListener('click', () => {
      selectChildItem(item);
    });
    
    const photoBox = document.createElement('div');
    photoBox.className = 'row-photo';
    if (item["Image"] && item["Image"].length > 0) {
      const img = document.createElement('img');
      img.src = item["Image"][0].url;
      photoBox.appendChild(img);
    } else {
      photoBox.innerHTML = '<span>📦</span>';
    }
    
    const infoBox = document.createElement('div');
    infoBox.className = 'row-info';
    
    const pnLabel = document.createElement('span');
    pnLabel.className = 'row-pn';
    pnLabel.textContent = item["Part Number"] || 'Unknown PN';
    
    const descLabel = document.createElement('span');
    descLabel.className = 'row-desc';
    descLabel.textContent = item["Item description"] || 'No description';
    
    infoBox.appendChild(pnLabel);
    infoBox.appendChild(descLabel);
    
    row.appendChild(photoBox);
    row.appendChild(infoBox);
    addChildList.appendChild(row);
  });
}

function selectChildItem(item) {
  addChildSelectedItemId = item.id;
  if (selectedChildName) {
    selectedChildName.textContent = `${item["Part Number"]} - ${item["Item description"] || 'No description'}`;
  }
  
  if (addChildRevisionTags) {
    addChildRevisionTags.innerHTML = '';
    const revs = getRevisionsForPN(item["Part Number"]);
    
    if (revs.length > 0) {
      addChildSelectedRevId = revs[revs.length - 1].id;
      
      revs.forEach(revItem => {
        const tag = document.createElement('span');
        tag.className = 'revision-tag';
        tag.textContent = revItem.revision || 'N/A';
        tag.style.cursor = 'pointer';
        
        if (revItem.id === addChildSelectedRevId) {
          tag.classList.add('active');
        }
        
        tag.addEventListener('click', () => {
          addChildSelectedRevId = revItem.id;
          addChildRevisionTags.querySelectorAll('.revision-tag').forEach(t => t.classList.remove('active'));
          tag.classList.add('active');
        });
        
        addChildRevisionTags.appendChild(tag);
      });
    } else {
      addChildSelectedRevId = item.id;
    }
  }
  
  if (addChildForm) addChildForm.style.display = 'flex';
  if (btnConfirmAddChild) btnConfirmAddChild.disabled = false;
}

async function handleConfirmAddChild() {
  if (!addChildParentId || !addChildSelectedRevId) return;
  
  const quantityVal = parseInt(addChildQuantity ? addChildQuantity.value : 1) || 1;
  const lengthVal = parseFloat(addChildLength ? addChildLength.value : 0) || 0;
  const pcbVal = addChildPcb ? addChildPcb.value.trim() : 'N/A';
  
  try {
    showToast('Adding child to assembly...');
    if (btnConfirmAddChild) btnConfirmAddChild.disabled = true;
    
    await createAssembly(addChildParentId, addChildSelectedRevId, quantityVal, lengthVal, pcbVal);
    
    showToast('Assembly updated successfully.');
    closeAddChildModal();
    await refreshData();
  } catch (err) {
    showToast(`Failed to add child: ${err.message}`, 'error');
    if (btnConfirmAddChild) btnConfirmAddChild.disabled = false;
  }
}

// Edit Assembly Dialog Logic
function openEditAssemblyModal(node) {
  if (!editAssemblyModal) return;
  editAssemblyNode = node;
  editAssemblyEdgeId = node.edge_id;
  
  if (editAssemblyItemName) {
    const revStr = getItemRevision(node.id) ? ` Rev.${getItemRevision(node.id)}` : '';
    editAssemblyItemName.textContent = `${node.part_number}${revStr} - ${node.description || 'No description'}`;
  }
  
  if (editAssemblyQuantity) {
    editAssemblyQuantity.value = node.quantity !== undefined ? node.quantity : 1;
  }
  if (editAssemblyLength) {
    editAssemblyLength.value = node.length !== undefined ? node.length : 0;
  }
  if (editAssemblyPcb) {
    editAssemblyPcb.value = node.pcb_symbol || 'N/A';
  }
  
  editAssemblyModal.style.display = 'flex';
  editAssemblyModal.offsetHeight;
  editAssemblyModal.classList.add('open');
}

function closeEditAssemblyModal() {
  if (!editAssemblyModal) return;
  editAssemblyModal.classList.remove('open');
  setTimeout(() => { editAssemblyModal.style.display = 'none'; }, 300);
}

async function handleSaveEditAssembly() {
  if (!editAssemblyEdgeId) return;
  
  const qty = parseInt(editAssemblyQuantity ? editAssemblyQuantity.value : 1) || 1;
  const len = parseFloat(editAssemblyLength ? editAssemblyLength.value : 0) || 0;
  const pcb = editAssemblyPcb ? editAssemblyPcb.value.trim() : 'N/A';
  
  try {
    showToast('Saving assembly changes...');
    if (btnSaveEditAssembly) btnSaveEditAssembly.disabled = true;
    
    await updateAssembly(editAssemblyEdgeId, qty, len, pcb);
    
    showToast('Assembly properties saved.');
    closeEditAssemblyModal();
    await refreshData();
  } catch (err) {
    showToast(`Failed to save: ${err.message}`, 'error');
    if (btnSaveEditAssembly) btnSaveEditAssembly.disabled = false;
  }
}

async function handleDeleteAssembly() {
  if (!editAssemblyEdgeId) return;
  
  if (!confirm("Are you sure you want to remove this item from the assembly relation?")) {
    return;
  }
  
  try {
    showToast('Removing from assembly...');
    if (btnDeleteAssembly) btnDeleteAssembly.disabled = true;
    
    await deleteAssembly(editAssemblyEdgeId);
    
    showToast('Item removed from assembly.');
    closeEditAssemblyModal();
    await refreshData();
  } catch (err) {
    showToast(`Failed to remove: ${err.message}`, 'error');
    if (btnDeleteAssembly) btnDeleteAssembly.disabled = false;
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}

function setCurrentItemId(id) {
  currentItemId = id;
}

export {
  sortTreeNodesRecursively,
  filterNode,
  disabledCategories,
  categoryRules,
  applyFilterAndRender,
  ensureManufacturersLoaded,
  populateManufacturersDropdown,
  renderDatasheetsList,
  currentDatasheets,
  currentImages,
  currentRelated,
  allItems,
  manufacturers,
  originalData,
  hasUnsavedChanges,
  saveChanges,
  revertChanges,
  setCurrentItemId,
  renderGallery,
  handleDroppedFiles,
  showConfirmModal,
  renderRelatedItems,
  ensureAllItemsLoaded,
  openAddRelatedModal,
  renderAddRelatedList,
  showItemPage,
  init,
  renderRevisionTags,
  openAddChildModal,
  closeAddChildModal,
  renderAddChildList,
  selectChildItem,
  handleConfirmAddChild,
  openEditAssemblyModal,
  closeEditAssemblyModal,
  handleSaveEditAssembly,
  handleDeleteAssembly,
  disabledStates,
  STATE_COLORS,
  renderDrawerStates,
  openCreateItemModal,
  closeCreateItemModal,
  handleConfirmCreateItem
};
