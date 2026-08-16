import {
  fetchManufacturers,
  fetchManufacturer,
  createManufacturer,
  updateManufacturer,
  deleteManufacturer,
  fetchSuppliers,
  fetchSupplier,
  createSupplier,
  updateSupplier,
  deleteSupplier,
  fetchContacts,
  fetchContact,
  createContact,
  updateContact,
  deleteContact,
  uploadLogo,
  fetchFlatItems,
  getHealth
} from './api.js';

// State
let allManufacturers = [];
let allSuppliers = [];
let allContacts = [];
let allBomItems = [];

let selectedMfgId = null;
let selectedSupplierId = null;
let editingContactId = null;
let pendingDeleteAction = null;

let mfgOriginalState = null;
let supplierOriginalState = null;

// DOM Elements - Navigation & Status
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const toastContainer = document.getElementById('toast-container');
const btnHamburger = document.getElementById('btn-hamburger');
const hamburgerMenu = document.getElementById('hamburger-menu');

// DOM Elements - Col 1: Manufacturers Sidebar
const mfgSearchInput = document.getElementById('mfg-search-input');
const btnClearMfgSearch = document.getElementById('btn-clear-mfg-search');
const btnAddMfgTrigger = document.getElementById('btn-add-mfg-trigger');
const mfgCountBadge = document.getElementById('mfg-count-badge');
const mfgListContainer = document.getElementById('mfg-list-container');

// DOM Elements - Col 2: Manufacturer Detail
const mfgDetailPanel = document.getElementById('mfg-detail-panel');
const mfgEmptyState = document.getElementById('mfg-empty-state');
const mfgDetailContent = document.getElementById('mfg-detail-content');
const btnMfgSave = document.getElementById('btn-mfg-save');
const btnMfgRevert = document.getElementById('btn-mfg-revert');
const btnMfgDelete = document.getElementById('btn-mfg-delete');
const mfgLogoDropzone = document.getElementById('mfg-logo-dropzone');
const mfgLogoImg = document.getElementById('mfg-logo-img');
const mfgLogoPlaceholder = document.getElementById('mfg-logo-placeholder');
const mfgLogoFileInput = document.getElementById('mfg-logo-file-input');
const btnMfgBrowseLogo = document.getElementById('btn-mfg-browse-logo');
const btnMfgRemoveLogo = document.getElementById('btn-mfg-remove-logo');
const mfgCenterpieceName = document.getElementById('mfg-centerpiece-name');
const mfgWebsiteBadge = document.getElementById('mfg-website-badge');
const mfgWebsiteAnchor = document.getElementById('mfg-website-anchor');
const inputMfgName = document.getElementById('input-mfg-name');
const inputMfgWebsite = document.getElementById('input-mfg-website');
const btnOpenMfgWebsite = document.getElementById('btn-open-mfg-website');
const inputMfgNotes = document.getElementById('input-mfg-notes');
const btnMfgOwnSupplier = document.getElementById('btn-mfg-own-supplier');
const btnOpenSupplierPicker = document.getElementById('btn-open-supplier-picker');
const mfgSupplierCountBadge = document.getElementById('mfg-supplier-count-badge');
const mfgLinkedSuppliersList = document.getElementById('mfg-linked-suppliers-list');
const mfgItemsCountBadge = document.getElementById('mfg-items-count-badge');
const mfgItemsContainer = document.getElementById('mfg-items-container');

// DOM Elements - Col 3: Supplier Detail
const supplierDetailPanel = document.getElementById('supplier-detail-panel');
const supplierEmptyState = document.getElementById('supplier-empty-state');
const supplierDetailContent = document.getElementById('supplier-detail-content');
const btnSupplierSave = document.getElementById('btn-supplier-save');
const btnSupplierRevert = document.getElementById('btn-supplier-revert');
const btnSupplierUnlink = document.getElementById('btn-supplier-unlink');
const btnSupplierDelete = document.getElementById('btn-supplier-delete');
const supplierLogoDropzone = document.getElementById('supplier-logo-dropzone');
const supplierLogoImg = document.getElementById('supplier-logo-img');
const supplierLogoPlaceholder = document.getElementById('supplier-logo-placeholder');
const supplierLogoFileInput = document.getElementById('supplier-logo-file-input');
const btnSupplierBrowseLogo = document.getElementById('btn-supplier-browse-logo');
const btnSupplierRemoveLogo = document.getElementById('btn-supplier-remove-logo');
const supplierCenterpieceName = document.getElementById('supplier-centerpiece-name');
const supplierUrlBadge = document.getElementById('supplier-url-badge');
const supplierUrlAnchor = document.getElementById('supplier-url-anchor');
const inputSupplierName = document.getElementById('input-supplier-name');
const inputSupplierUrl = document.getElementById('input-supplier-url');
const btnOpenSupplierUrl = document.getElementById('btn-open-supplier-url');
const inputSupplierOnlineStore = document.getElementById('input-supplier-online-store');
const inputSupplierNotes = document.getElementById('input-supplier-notes');
const supplierMfgCountBadge = document.getElementById('supplier-mfg-count-badge');
const supplierMfgList = document.getElementById('supplier-mfg-list');
const supplierContactsCountBadge = document.getElementById('supplier-contacts-count-badge');
const btnAddContactTrigger = document.getElementById('btn-add-contact-trigger');
const supplierContactsList = document.getElementById('supplier-contacts-list');

// Modals
const modalCreateMfg = document.getElementById('modal-create-mfg');
const modalInputMfgName = document.getElementById('modal-input-mfg-name');
const modalInputMfgWebsite = document.getElementById('modal-input-mfg-website');
const modalInputMfgNotes = document.getElementById('modal-input-mfg-notes');
const btnCloseCreateMfgModal = document.getElementById('btn-close-create-mfg-modal');
const btnCancelCreateMfg = document.getElementById('btn-cancel-create-mfg');
const btnConfirmCreateMfg = document.getElementById('btn-confirm-create-mfg');

const modalSupplierPicker = document.getElementById('modal-supplier-picker');
const modalPickerMfgName = document.getElementById('modal-picker-mfg-name');
const pickerSupplierSearch = document.getElementById('picker-supplier-search');
const btnCreateSupplierInPicker = document.getElementById('btn-create-supplier-in-picker');
const pickerSuppliersList = document.getElementById('picker-suppliers-list');
const btnCloseSupplierPickerModal = document.getElementById('btn-close-supplier-picker-modal');
const btnCancelSupplierPicker = document.getElementById('btn-cancel-supplier-picker');
const btnApplySupplierPicker = document.getElementById('btn-apply-supplier-picker');

const modalContactEdit = document.getElementById('modal-contact-edit');
const modalContactTitle = document.getElementById('modal-contact-title');
const modalInputContactName = document.getElementById('modal-input-contact-name');
const modalInputContactEmail = document.getElementById('modal-input-contact-email');
const modalInputContactPhone = document.getElementById('modal-input-contact-phone');
const modalInputContactActive = document.getElementById('modal-input-contact-active');
const modalInputContactNotes = document.getElementById('modal-input-contact-notes');
const btnCloseContactModal = document.getElementById('btn-close-contact-modal');
const btnCancelContactModal = document.getElementById('btn-cancel-contact-modal');
const btnConfirmSaveContact = document.getElementById('btn-confirm-save-contact');

const modalConfirmDelete = document.getElementById('modal-confirm-delete');
const modalConfirmTitle = document.getElementById('modal-confirm-title');
const modalConfirmMessage = document.getElementById('modal-confirm-message');
const btnCloseConfirmModal = document.getElementById('btn-close-confirm-modal');
const btnCancelConfirm = document.getElementById('btn-cancel-confirm');
const btnConfirmDeleteAction = document.getElementById('btn-confirm-delete-action');

// --- Initialization ---

export async function init() {
  bindEventListeners();
  checkHealth();
  await loadInitialData();

  // Read URL params (e.g. ?id=1 or ?supplier=2)
  const urlParams = new URLSearchParams(window.location.search);
  const mfgParam = urlParams.get('id');
  const supplierParam = urlParams.get('supplier');

  if (mfgParam) {
    const targetMfg = allManufacturers.find(m => String(m.id) === String(mfgParam));
    if (targetMfg) {
      selectManufacturer(targetMfg.id);
    }
  } else if (allManufacturers.length > 0) {
    selectManufacturer(allManufacturers[0].id);
  }

  if (supplierParam) {
    const targetSupp = allSuppliers.find(s => String(s.id) === String(supplierParam));
    if (targetSupp) {
      selectSupplier(targetSupp.id);
    }
  }
}

async function checkHealth() {
  try {
    await getHealth();
    if (statusIndicator) {
      statusIndicator.className = 'status-indicator connected';
    }
    if (statusText) statusText.textContent = 'Connected';
  } catch (err) {
    if (statusIndicator) {
      statusIndicator.className = 'status-indicator disconnected';
    }
    if (statusText) statusText.textContent = 'Offline';
  }
}

async function loadInitialData() {
  try {
    const [mfgs, supps, contacts, items] = await Promise.all([
      fetchManufacturers(true).catch(() => []),
      fetchSuppliers().catch(() => []),
      fetchContacts().catch(() => []),
      fetchFlatItems().catch(() => [])
    ]);

    allManufacturers = mfgs || [];
    allSuppliers = supps || [];
    allContacts = contacts || [];
    allBomItems = items || [];

    renderManufacturersList();
  } catch (err) {
    showToast(`Failed to load directory data: ${err.message}`, 'error');
  }
}

// --- Event Listeners Binding ---

function bindEventListeners() {
  // Hamburger Menu
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
  }

  // Search & Filter
  if (mfgSearchInput) {
    mfgSearchInput.addEventListener('input', () => {
      const query = mfgSearchInput.value.trim();
      if (btnClearMfgSearch) {
        btnClearMfgSearch.style.display = query ? 'flex' : 'none';
      }
      renderManufacturersList(query);
    });
  }

  if (btnClearMfgSearch) {
    btnClearMfgSearch.addEventListener('click', () => {
      mfgSearchInput.value = '';
      btnClearMfgSearch.style.display = 'none';
      renderManufacturersList();
      mfgSearchInput.focus();
    });
  }

  // Manufacturer CRUD buttons
  if (btnAddMfgTrigger) {
    btnAddMfgTrigger.addEventListener('click', openCreateMfgModal);
  }
  if (btnMfgSave) btnMfgSave.addEventListener('click', handleSaveManufacturer);
  if (btnMfgRevert) btnMfgRevert.addEventListener('click', handleRevertManufacturer);
  if (btnMfgDelete) btnMfgDelete.addEventListener('click', handleDeleteManufacturerClick);
  if (btnMfgOwnSupplier) btnMfgOwnSupplier.addEventListener('click', handleCreateOwnSupplier);

  // Manufacturer Form Inputs
  if (inputMfgName) inputMfgName.addEventListener('input', checkMfgChanges);
  if (inputMfgWebsite) inputMfgWebsite.addEventListener('input', checkMfgChanges);
  if (inputMfgNotes) inputMfgNotes.addEventListener('input', checkMfgChanges);

  if (btnOpenMfgWebsite) {
    btnOpenMfgWebsite.addEventListener('click', () => {
      let url = inputMfgWebsite ? inputMfgWebsite.value.trim() : '';
      if (url) {
        if (!url.startsWith('http://') && !url.startsWith('https://')) url = 'https://' + url;
        window.open(url, '_blank', 'noopener,noreferrer');
      }
    });
  }

  // Supplier Picker
  if (btnOpenSupplierPicker) {
    btnOpenSupplierPicker.addEventListener('click', openSupplierPickerModal);
  }

  // Supplier CRUD buttons
  if (btnSupplierSave) btnSupplierSave.addEventListener('click', handleSaveSupplier);
  if (btnSupplierRevert) btnSupplierRevert.addEventListener('click', handleRevertSupplier);
  if (btnSupplierUnlink) btnSupplierUnlink.addEventListener('click', handleUnlinkSupplier);
  if (btnSupplierDelete) btnSupplierDelete.addEventListener('click', handleDeleteSupplierClick);

  // Supplier Form Inputs
  if (inputSupplierName) inputSupplierName.addEventListener('input', checkSupplierChanges);
  if (inputSupplierUrl) inputSupplierUrl.addEventListener('input', checkSupplierChanges);
  if (inputSupplierOnlineStore) inputSupplierOnlineStore.addEventListener('change', checkSupplierChanges);
  if (inputSupplierNotes) inputSupplierNotes.addEventListener('input', checkSupplierChanges);

  if (btnOpenSupplierUrl) {
    btnOpenSupplierUrl.addEventListener('click', () => {
      let url = inputSupplierUrl ? inputSupplierUrl.value.trim() : '';
      if (url) {
        if (!url.startsWith('http://') && !url.startsWith('https://')) url = 'https://' + url;
        window.open(url, '_blank', 'noopener,noreferrer');
      }
    });
  }

  // Contacts
  if (btnAddContactTrigger) {
    btnAddContactTrigger.addEventListener('click', () => openContactModal(null));
  }

  // Logo Setup (Drag & Drop + File input for Manufacturer)
  setupLogoHandlers(
    mfgLogoDropzone,
    mfgLogoFileInput,
    btnMfgBrowseLogo,
    btnMfgRemoveLogo,
    async (file) => {
      await handleUploadMfgLogo(file);
    },
    async () => {
      await handleRemoveMfgLogo();
    }
  );

  // Logo Setup (Drag & Drop + File input for Supplier)
  setupLogoHandlers(
    supplierLogoDropzone,
    supplierLogoFileInput,
    btnSupplierBrowseLogo,
    btnSupplierRemoveLogo,
    async (file) => {
      await handleUploadSupplierLogo(file);
    },
    async () => {
      await handleRemoveSupplierLogo();
    }
  );

  // Modals close buttons
  setupModalClose(modalCreateMfg, [btnCloseCreateMfgModal, btnCancelCreateMfg]);
  setupModalClose(modalSupplierPicker, [btnCloseSupplierPickerModal, btnCancelSupplierPicker]);
  setupModalClose(modalContactEdit, [btnCloseContactModal, btnCancelContactModal]);
  setupModalClose(modalConfirmDelete, [btnCloseConfirmModal, btnCancelConfirm]);

  if (btnConfirmCreateMfg) btnConfirmCreateMfg.addEventListener('click', handleConfirmCreateMfg);
  if (btnApplySupplierPicker) btnApplySupplierPicker.addEventListener('click', handleApplySupplierPicker);
  if (btnCreateSupplierInPicker) btnCreateSupplierInPicker.addEventListener('click', handleCreateSupplierInPicker);
  if (btnConfirmSaveContact) btnConfirmSaveContact.addEventListener('click', handleConfirmSaveContact);
  if (btnConfirmDeleteAction) {
    btnConfirmDeleteAction.addEventListener('click', () => {
      if (typeof pendingDeleteAction === 'function') {
        pendingDeleteAction();
      }
      closeModal(modalConfirmDelete);
    });
  }
}

// --- Logo Handling (Drag & Drop + Click) ---

function setupLogoHandlers(dropzone, fileInput, btnBrowse, btnRemove, onUpload, onRemove) {
  if (!dropzone) return;

  dropzone.addEventListener('click', () => {
    if (fileInput) fileInput.click();
  });

  if (btnBrowse && fileInput) {
    btnBrowse.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (btnRemove) {
    btnRemove.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm('Are you sure you want to remove the logo?')) {
        await onRemove();
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (file) {
        await onUpload(file);
        fileInput.value = '';
      }
    });
  }

  // Drag & Drop events
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', async (e) => {
    const dt = e.dataTransfer;
    const file = dt && dt.files && dt.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        showToast('Please drop an image file (PNG, JPG, SVG, WebP)', 'error');
        return;
      }
      await onUpload(file);
    }
  });
}

// --- Column 1: Manufacturers List Rendering ---

function renderManufacturersList(filterQuery = '') {
  if (!mfgListContainer) return;

  const query = (filterQuery || '').toLowerCase().trim();
  const filtered = allManufacturers.filter(m => {
    if (!query) return true;
    const name = (m.Name || m.name || '').toLowerCase();
    const website = (m.Website || m.website || '').toLowerCase();
    const notes = (m.Notes || m.notes || '').toLowerCase();
    return name.includes(query) || website.includes(query) || notes.includes(query);
  });

  if (mfgCountBadge) mfgCountBadge.textContent = String(filtered.length);

  if (filtered.length === 0) {
    mfgListContainer.innerHTML = `
      <div class="empty-selection-state" style="padding: 2rem 1rem;">
        <p style="font-size: 0.85rem;">No manufacturers found${query ? ` matching "${query}"` : ''}.</p>
      </div>
    `;
    return;
  }

  mfgListContainer.innerHTML = filtered.map(mfg => {
    const isSelected = mfg.id === selectedMfgId;
    const suppCount = (mfg.Suppliers || []).length;
    const itemCount = getManufacturerItemsCount(mfg.id);

    return `
      <div class="mfg-card-item ${isSelected ? 'active' : ''}" data-mfg-id="${mfg.id}">
        <div class="mfg-card-header">
          <span class="mfg-card-name">${escapeHtml(mfg.Name || 'Unnamed Manufacturer')}</span>
        </div>
        <div class="mfg-card-meta">
          <span class="mfg-meta-pill" title="Linked Suppliers">
            <i class="fa-solid fa-truck"></i> ${suppCount}
          </span>
          <span class="mfg-meta-pill" title="Manufactured Items">
            <i class="fa-solid fa-cubes"></i> ${itemCount}
          </span>
        </div>
      </div>
    `;
  }).join('');

  // Add click listeners to cards
  mfgListContainer.querySelectorAll('.mfg-card-item').forEach(card => {
    card.addEventListener('click', () => {
      const id = parseInt(card.getAttribute('data-mfg-id'), 10);
      selectManufacturer(id);
    });
  });
}

function getManufacturerItems(mfgId) {
  const mfg = allManufacturers.find(m => m.id === mfgId);
  const mfgBomLinks = mfg && Array.isArray(mfg.BOM) ? mfg.BOM : [];

  const itemMap = new Map();

  // 1. Populate from manufacturer's BOM link field directly
  mfgBomLinks.forEach(b => {
    const itemId = (b && typeof b === 'object') ? b.id : b;
    if (itemId) {
      itemMap.set(itemId, {
        id: itemId,
        'Part Number': (b && b.value) ? b.value : `Item #${itemId}`,
        'Item description': ''
      });
    }
  });

  // 2. Populate and enrich from allBomItems
  allBomItems.forEach(item => {
    const mLinks = item.Manufacturer || [];
    const isLinked = mLinks.some(m => {
      const id = (m && typeof m === 'object') ? m.id : m;
      return id === mfgId;
    });

    if (isLinked) {
      itemMap.set(item.id, {
        ...(itemMap.get(item.id) || {}),
        ...item
      });
    } else if (itemMap.has(item.id)) {
      // Enrich existing item from BOM table
      itemMap.set(item.id, {
        ...itemMap.get(item.id),
        ...item
      });
    }
  });

  return Array.from(itemMap.values());
}

function getManufacturerItemsCount(mfgId) {
  return getManufacturerItems(mfgId).length;
}

// --- Column 2: Select & Display Manufacturer ---

export function selectManufacturer(mfgId) {
  selectedMfgId = mfgId;
  const mfg = allManufacturers.find(m => m.id === mfgId);

  // Update selection in list
  if (mfgListContainer) {
    mfgListContainer.querySelectorAll('.mfg-card-item').forEach(card => {
      const cardId = parseInt(card.getAttribute('data-mfg-id'), 10);
      card.classList.toggle('active', cardId === mfgId);
    });
  }

  if (!mfg) {
    if (mfgEmptyState) mfgEmptyState.style.display = 'flex';
    if (mfgDetailContent) mfgDetailContent.style.display = 'none';
    clearSupplierSelection();
    return;
  }

  if (mfgEmptyState) mfgEmptyState.style.display = 'none';
  if (mfgDetailContent) mfgDetailContent.style.display = 'block';

  // Populate Centerpiece & Form
  const name = mfg.Name || '';
  const website = mfg.Website || '';
  const notes = mfg.Notes || '';

  if (mfgCenterpieceName) mfgCenterpieceName.textContent = name || 'Unnamed Manufacturer';
  if (inputMfgName) inputMfgName.value = name;
  if (inputMfgWebsite) inputMfgWebsite.value = website;
  if (inputMfgNotes) inputMfgNotes.value = notes;

  if (mfgWebsiteBadge && mfgWebsiteAnchor) {
    if (website) {
      let href = website;
      if (!href.startsWith('http://') && !href.startsWith('https://')) href = 'https://' + href;
      mfgWebsiteAnchor.href = href;
      mfgWebsiteBadge.style.display = 'inline-flex';
    } else {
      mfgWebsiteBadge.style.display = 'none';
    }
  }

  // Populate Logo in White Box
  renderLogo(mfg.Logo, mfgLogoImg, mfgLogoPlaceholder, btnMfgRemoveLogo);

  // Snapshot original state for dirty checking
  mfgOriginalState = {
    Name: name,
    Website: website,
    Notes: notes
  };
  checkMfgChanges();

  // Render Linked Suppliers
  renderLinkedSuppliers(mfg);

  // Render Manufactured BOM Items
  renderManufacturedItems(mfg.id);

  // Select Supplier if one was selected or auto-select first linked supplier
  const linkedSuppliers = mfg.Suppliers || [];
  if (selectedSupplierId && linkedSuppliers.some(s => (s.id || s) === selectedSupplierId)) {
    selectSupplier(selectedSupplierId);
  } else if (linkedSuppliers.length > 0) {
    const firstSuppId = linkedSuppliers[0].id || linkedSuppliers[0];
    selectSupplier(firstSuppId);
  } else {
    clearSupplierSelection();
  }
}

function renderLogo(logoArray, imgEl, placeholderEl, removeBtn) {
  const hasLogo = Array.isArray(logoArray) && logoArray.length > 0 && logoArray[0].url;
  if (hasLogo) {
    const url = logoArray[0].url;
    if (imgEl) {
      imgEl.src = url;
      imgEl.style.display = 'block';
    }
    if (placeholderEl) placeholderEl.style.display = 'none';
    if (removeBtn) removeBtn.style.display = 'inline-flex';
  } else {
    if (imgEl) {
      imgEl.src = '';
      imgEl.style.display = 'none';
    }
    if (placeholderEl) placeholderEl.style.display = 'flex';
    if (removeBtn) removeBtn.style.display = 'none';
  }
}

function renderLinkedSuppliers(mfg) {
  if (!mfgLinkedSuppliersList) return;

  const linked = mfg.Suppliers || [];
  if (mfgSupplierCountBadge) mfgSupplierCountBadge.textContent = `${linked.length} linked`;

  if (linked.length === 0) {
    mfgLinkedSuppliersList.innerHTML = `
      <div style="font-size: 0.85rem; color: var(--text-secondary); padding: 0.5rem 0;">
        No suppliers linked yet. Click "Manage / Link Suppliers" to associate suppliers or use "Manufacturer is Own Supplier".
      </div>
    `;
    return;
  }

  mfgLinkedSuppliersList.innerHTML = linked.map(link => {
    const sId = link.id || link;
    const suppObj = allSuppliers.find(s => s.id === sId);
    const sName = suppObj ? (suppObj['Company Name'] || suppObj.name) : (link.value || `Supplier #${sId}`);
    const isSelected = sId === selectedSupplierId;

    return `
      <div class="linked-supplier-card ${isSelected ? 'active' : ''}" data-supp-id="${sId}">
        <i class="fa-solid fa-truck" style="color: var(--color-gold);"></i>
        <span class="supp-name">${escapeHtml(sName)}</span>
        <i class="fa-solid fa-arrow-right supp-arrow"></i>
      </div>
    `;
  }).join('');

  mfgLinkedSuppliersList.querySelectorAll('.linked-supplier-card').forEach(card => {
    card.addEventListener('click', () => {
      const suppId = parseInt(card.getAttribute('data-supp-id'), 10);
      selectSupplier(suppId);
    });
  });
}

function renderManufacturedItems(mfgId) {
  if (!mfgItemsContainer) return;

  const items = getManufacturerItems(mfgId);
  if (mfgItemsCountBadge) mfgItemsCountBadge.textContent = `${items.length} items`;

  if (items.length === 0) {
    mfgItemsContainer.innerHTML = `
      <div style="font-size: 0.85rem; color: var(--text-secondary); padding: 0.5rem 0;">
        No BOM items linked to this manufacturer.
      </div>
    `;
    return;
  }

  mfgItemsContainer.innerHTML = items.map(item => {
    const pn = item['Part Number'] || item['Full PN'] || 'No PN';
    const desc = item['Item description'] || 'No description';
    const stateVal = item.State ? (item.State.value || item.State) : '';

    return `
      <div class="mfg-item-row" data-item-id="${item.id}" title="Click to view in BOM Explorer">
        <div class="mfg-item-pn-desc">
          <span class="mfg-item-pn">${escapeHtml(pn)}</span>
          <span class="mfg-item-desc">${escapeHtml(desc)}</span>
        </div>
        <a href="/?item=${item.id}" class="btn btn-secondary btn-sm" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">
          View <i class="fa-solid fa-arrow-up-right-from-square"></i>
        </a>
      </div>
    `;
  }).join('');
}

// Dirty checking for Manufacturer form
function checkMfgChanges() {
  if (!mfgOriginalState || !btnMfgSave || !btnMfgRevert) return;

  const currentName = inputMfgName ? inputMfgName.value.trim() : '';
  const currentWebsite = inputMfgWebsite ? inputMfgWebsite.value.trim() : '';
  const currentNotes = inputMfgNotes ? inputMfgNotes.value.trim() : '';

  const isDirty = (
    currentName !== (mfgOriginalState.Name || '') ||
    currentWebsite !== (mfgOriginalState.Website || '') ||
    currentNotes !== (mfgOriginalState.Notes || '')
  );

  btnMfgSave.disabled = !isDirty || !currentName;
  btnMfgRevert.disabled = !isDirty;

  if (mfgCenterpieceName && currentName) {
    mfgCenterpieceName.textContent = currentName;
  }
}

async function handleSaveManufacturer() {
  if (!selectedMfgId) return;

  const name = inputMfgName ? inputMfgName.value.trim() : '';
  if (!name) {
    showToast('Manufacturer Name is required.', 'error');
    return;
  }

  const website = inputMfgWebsite ? inputMfgWebsite.value.trim() : '';
  const notes = inputMfgNotes ? inputMfgNotes.value.trim() : '';

  try {
    btnMfgSave.disabled = true;
    showToast('Saving manufacturer...');
    const updated = await updateManufacturer(selectedMfgId, {
      Name: name,
      Website: website,
      Notes: notes
    });

    // Update in local cache
    const idx = allManufacturers.findIndex(m => m.id === selectedMfgId);
    if (idx !== -1) {
      allManufacturers[idx] = { ...allManufacturers[idx], ...updated, Name: name, Website: website, Notes: notes };
    }

    renderManufacturersList(mfgSearchInput ? mfgSearchInput.value : '');
    selectManufacturer(selectedMfgId);
    showToast('Manufacturer saved successfully!', 'success');
  } catch (err) {
    showToast(`Failed to save manufacturer: ${err.message}`, 'error');
    checkMfgChanges();
  }
}

function handleRevertManufacturer() {
  if (!selectedMfgId) return;
  selectManufacturer(selectedMfgId);
}

function handleDeleteManufacturerClick() {
  if (!selectedMfgId) return;
  const mfg = allManufacturers.find(m => m.id === selectedMfgId);
  const name = mfg ? (mfg.Name || 'this manufacturer') : 'this manufacturer';

  openConfirmModal(
    'Delete Manufacturer',
    `Are you sure you want to delete "${name}"? This will remove the manufacturer record from Baserow.`,
    async () => {
      try {
        showToast('Deleting manufacturer...');
        await deleteManufacturer(selectedMfgId);
        allManufacturers = allManufacturers.filter(m => m.id !== selectedMfgId);
        showToast('Manufacturer deleted.', 'success');
        renderManufacturersList(mfgSearchInput ? mfgSearchInput.value : '');
        if (allManufacturers.length > 0) {
          selectManufacturer(allManufacturers[0].id);
        } else {
          selectManufacturer(null);
        }
      } catch (err) {
        showToast(`Failed to delete manufacturer: ${err.message}`, 'error');
      }
    }
  );
}

// Manufacturer is Own Supplier
async function handleCreateOwnSupplier() {
  if (!selectedMfgId) return;
  const mfg = allManufacturers.find(m => m.id === selectedMfgId);
  if (!mfg) return;

  const mfgName = (mfg.Name || '').trim();
  if (!mfgName) {
    showToast('Please set a manufacturer name first.', 'error');
    return;
  }

  try {
    showToast('Configuring self-supplier...');

    // Check if a supplier with the exact name already exists
    let existingSupplier = allSuppliers.find(s => {
      const sName = (s['Company Name'] || s.name || '').trim().toLowerCase();
      return sName === mfgName.toLowerCase();
    });

    let targetSupplierId = null;

    if (!existingSupplier) {
      // Create new supplier
      const created = await createSupplier({
        'Company Name': mfgName,
        URL: mfg.Website || '',
        Notes: mfg.Notes || '',
        'Online Store': false,
        'Imports From': [mfg.id],
        Logo: mfg.Logo || []
      });
      existingSupplier = created;
      allSuppliers.push(created);
      targetSupplierId = created.id;
    } else {
      targetSupplierId = existingSupplier.id;
    }

    // Link supplier to this manufacturer if not already linked
    const currentSuppliers = (mfg.Suppliers || []).map(s => s.id || s);
    if (!currentSuppliers.includes(targetSupplierId)) {
      currentSuppliers.push(targetSupplierId);
      const updatedMfg = await updateManufacturer(mfg.id, {
        Suppliers: currentSuppliers
      });
      const idx = allManufacturers.findIndex(m => m.id === mfg.id);
      if (idx !== -1) allManufacturers[idx] = updatedMfg;
    }

    renderManufacturersList(mfgSearchInput ? mfgSearchInput.value : '');
    selectManufacturer(mfg.id);
    selectSupplier(targetSupplierId);

    showToast(`Supplier "${mfgName}" linked successfully!`, 'success');
  } catch (err) {
    showToast(`Failed to create own supplier: ${err.message}`, 'error');
  }
}

// Logo upload handlers
async function handleUploadMfgLogo(file) {
  if (!selectedMfgId) return;
  try {
    showToast('Uploading logo...');
    const uploaded = await uploadLogo(file);
    const updated = await updateManufacturer(selectedMfgId, {
      Logo: [uploaded]
    });

    const idx = allManufacturers.findIndex(m => m.id === selectedMfgId);
    if (idx !== -1) allManufacturers[idx] = { ...allManufacturers[idx], Logo: [uploaded] };

    renderLogo([uploaded], mfgLogoImg, mfgLogoPlaceholder, btnMfgRemoveLogo);
    showToast('Logo updated successfully!', 'success');
  } catch (err) {
    showToast(`Failed to upload logo: ${err.message}`, 'error');
  }
}

async function handleRemoveMfgLogo() {
  if (!selectedMfgId) return;
  try {
    showToast('Removing logo...');
    await updateManufacturer(selectedMfgId, { Logo: [] });

    const idx = allManufacturers.findIndex(m => m.id === selectedMfgId);
    if (idx !== -1) allManufacturers[idx].Logo = [];

    renderLogo([], mfgLogoImg, mfgLogoPlaceholder, btnMfgRemoveLogo);
    showToast('Logo removed.', 'success');
  } catch (err) {
    showToast(`Failed to remove logo: ${err.message}`, 'error');
  }
}

// --- Column 3: Select & Display Supplier ---

export function selectSupplier(supplierId) {
  selectedSupplierId = supplierId;
  const supplier = allSuppliers.find(s => s.id === supplierId);

  // Update active state in linked suppliers list in Col 2
  if (mfgLinkedSuppliersList) {
    mfgLinkedSuppliersList.querySelectorAll('.linked-supplier-card').forEach(card => {
      const cardId = parseInt(card.getAttribute('data-supp-id'), 10);
      card.classList.toggle('active', cardId === supplierId);
    });
  }

  if (!supplier) {
    clearSupplierSelection();
    return;
  }

  if (supplierEmptyState) supplierEmptyState.style.display = 'none';
  if (supplierDetailContent) supplierDetailContent.style.display = 'block';

  const name = supplier['Company Name'] || supplier.name || '';
  const url = supplier.URL || supplier.url || '';
  const onlineStore = Boolean(supplier['Online Store'] || supplier.online_store);
  const notes = supplier.Notes || supplier.notes || '';

  if (supplierCenterpieceName) supplierCenterpieceName.textContent = name || 'Unnamed Supplier';
  if (inputSupplierName) inputSupplierName.value = name;
  if (inputSupplierUrl) inputSupplierUrl.value = url;
  if (inputSupplierOnlineStore) inputSupplierOnlineStore.checked = onlineStore;
  if (inputSupplierNotes) inputSupplierNotes.value = notes;

  if (supplierUrlBadge && supplierUrlAnchor) {
    if (url) {
      let href = url;
      if (!href.startsWith('http://') && !href.startsWith('https://')) href = 'https://' + href;
      supplierUrlAnchor.href = href;
      supplierUrlBadge.style.display = 'inline-flex';
    } else {
      supplierUrlBadge.style.display = 'none';
    }
  }

  // Supplier Logo in White Box
  renderLogo(supplier.Logo, supplierLogoImg, supplierLogoPlaceholder, btnSupplierRemoveLogo);

  // Snapshot original state
  supplierOriginalState = {
    name,
    url,
    onlineStore,
    notes
  };
  checkSupplierChanges();

  // Render Supplied Manufacturers
  renderSuppliedManufacturers(supplier);

  // Render Contacts
  renderSupplierContacts(supplier.id);
}

function clearSupplierSelection() {
  selectedSupplierId = null;
  supplierOriginalState = null;
  if (supplierEmptyState) supplierEmptyState.style.display = 'flex';
  if (supplierDetailContent) supplierDetailContent.style.display = 'none';
}

function renderSuppliedManufacturers(supplier) {
  if (!supplierMfgList) return;

  const importsFrom = supplier['Imports From'] || supplier.imports_from || [];
  if (supplierMfgCountBadge) supplierMfgCountBadge.textContent = String(importsFrom.length);

  if (importsFrom.length === 0) {
    supplierMfgList.innerHTML = `
      <div style="font-size: 0.8rem; color: var(--text-secondary);">No imported manufacturers recorded.</div>
    `;
    return;
  }

  supplierMfgList.innerHTML = importsFrom.map(link => {
    const mId = link.id || link;
    const mfg = allManufacturers.find(m => m.id === mId);
    const mName = mfg ? (mfg.Name || mfg.name) : (link.value || `Manufacturer #${mId}`);

    return `
      <button type="button" class="btn-subtle-link supplier-mfg-chip" data-mfg-id="${mId}" style="background: rgba(255,255,255,0.05); padding: 0.25rem 0.5rem;">
        <i class="fa-solid fa-industry"></i> ${escapeHtml(mName)}
      </button>
    `;
  }).join('');

  supplierMfgList.querySelectorAll('.supplier-mfg-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetMfgId = parseInt(btn.getAttribute('data-mfg-id'), 10);
      selectManufacturer(targetMfgId);
    });
  });
}

function renderSupplierContacts(supplierId) {
  if (!supplierContactsList) return;

  const contacts = allContacts.filter(c => {
    const suppLinks = c.Suppliers || c.suppliers || [];
    return suppLinks.some(s => (s.id || s) === supplierId);
  });

  if (supplierContactsCountBadge) supplierContactsCountBadge.textContent = String(contacts.length);

  if (contacts.length === 0) {
    supplierContactsList.innerHTML = `
      <div style="font-size: 0.85rem; color: var(--text-secondary); padding: 0.75rem 0;">
        No contacts added for this supplier. Click "+ Add Contact" to add sales reps, engineering, or support.
      </div>
    `;
    return;
  }

  supplierContactsList.innerHTML = contacts.map(contact => {
    const name = contact.Name || contact.name || 'Unnamed Contact';
    const email = contact.Email || contact.email || '';
    const phone = contact['Phone number'] || contact.phone || '';
    const active = contact.Active !== false;
    const notes = contact.Notes || contact.notes || '';

    return `
      <div class="contact-card" data-contact-id="${contact.id}">
        <div class="contact-card-top">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span class="contact-name-title">${escapeHtml(name)}</span>
            ${active ? '<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid #10b981;">Active</span>' : '<span class="badge" style="opacity: 0.6;">Inactive</span>'}
          </div>
          <div class="item-actions">
            <button type="button" class="btn-subtle-link btn-edit-contact" data-contact-id="${contact.id}" title="Edit Contact">
              <i class="fa-regular fa-pen-to-square"></i>
            </button>
            <button type="button" class="btn-subtle-link text-danger btn-delete-contact" data-contact-id="${contact.id}" title="Delete Contact">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </div>
        </div>

        <div class="contact-card-links">
          ${email ? `
            <a href="mailto:${encodeURIComponent(email)}" class="contact-uri-link" title="Send Email">
              <i class="fa-solid fa-envelope"></i> ${escapeHtml(email)}
            </a>
          ` : ''}
          ${phone ? `
            <a href="tel:${encodeURIComponent(phone)}" class="contact-uri-link" title="Call Phone">
              <i class="fa-solid fa-phone"></i> ${escapeHtml(phone)}
            </a>
          ` : ''}
        </div>

        ${notes ? `<div class="contact-card-notes">${escapeHtml(notes)}</div>` : ''}
      </div>
    `;
  }).join('');

  supplierContactsList.querySelectorAll('.btn-edit-contact').forEach(btn => {
    btn.addEventListener('click', () => {
      const cId = parseInt(btn.getAttribute('data-contact-id'), 10);
      const c = allContacts.find(item => item.id === cId);
      if (c) openContactModal(c);
    });
  });

  supplierContactsList.querySelectorAll('.btn-delete-contact').forEach(btn => {
    btn.addEventListener('click', () => {
      const cId = parseInt(btn.getAttribute('data-contact-id'), 10);
      const c = allContacts.find(item => item.id === cId);
      const cName = c ? c.Name : 'this contact';

      openConfirmModal(
        'Delete Contact',
        `Are you sure you want to remove "${cName}"?`,
        async () => {
          try {
            showToast('Deleting contact...');
            await deleteContact(cId);
            allContacts = allContacts.filter(item => item.id !== cId);
            renderSupplierContacts(selectedSupplierId);
            showToast('Contact removed.', 'success');
          } catch (err) {
            showToast(`Failed to delete contact: ${err.message}`, 'error');
          }
        }
      );
    });
  });
}

function checkSupplierChanges() {
  if (!supplierOriginalState || !btnSupplierSave || !btnSupplierRevert) return;

  const currentName = inputSupplierName ? inputSupplierName.value.trim() : '';
  const currentUrl = inputSupplierUrl ? inputSupplierUrl.value.trim() : '';
  const currentOnlineStore = inputSupplierOnlineStore ? inputSupplierOnlineStore.checked : false;
  const currentNotes = inputSupplierNotes ? inputSupplierNotes.value.trim() : '';

  const isDirty = (
    currentName !== (supplierOriginalState.name || '') ||
    currentUrl !== (supplierOriginalState.url || '') ||
    currentOnlineStore !== Boolean(supplierOriginalState.onlineStore) ||
    currentNotes !== (supplierOriginalState.notes || '')
  );

  btnSupplierSave.disabled = !isDirty || !currentName;
  btnSupplierRevert.disabled = !isDirty;

  if (supplierCenterpieceName && currentName) {
    supplierCenterpieceName.textContent = currentName;
  }
}

async function handleSaveSupplier() {
  if (!selectedSupplierId) return;

  const name = inputSupplierName ? inputSupplierName.value.trim() : '';
  if (!name) {
    showToast('Supplier Name is required.', 'error');
    return;
  }

  const url = inputSupplierUrl ? inputSupplierUrl.value.trim() : '';
  const onlineStore = inputSupplierOnlineStore ? inputSupplierOnlineStore.checked : false;
  const notes = inputSupplierNotes ? inputSupplierNotes.value.trim() : '';

  try {
    btnSupplierSave.disabled = true;
    showToast('Saving supplier...');
    const updated = await updateSupplier(selectedSupplierId, {
      'Company Name': name,
      URL: url,
      'Online Store': onlineStore,
      Notes: notes
    });

    const idx = allSuppliers.findIndex(s => s.id === selectedSupplierId);
    if (idx !== -1) {
      allSuppliers[idx] = { ...allSuppliers[idx], ...updated, 'Company Name': name, URL: url, 'Online Store': onlineStore, Notes: notes };
    }

    if (selectedMfgId) {
      const mfg = allManufacturers.find(m => m.id === selectedMfgId);
      if (mfg) renderLinkedSuppliers(mfg);
    }

    selectSupplier(selectedSupplierId);
    showToast('Supplier saved successfully!', 'success');
  } catch (err) {
    showToast(`Failed to save supplier: ${err.message}`, 'error');
    checkSupplierChanges();
  }
}

function handleRevertSupplier() {
  if (!selectedSupplierId) return;
  selectSupplier(selectedSupplierId);
}

function handleUnlinkSupplier() {
  if (!selectedMfgId || !selectedSupplierId) return;

  const mfg = allManufacturers.find(m => m.id === selectedMfgId);
  const supp = allSuppliers.find(s => s.id === selectedSupplierId);
  const suppName = supp ? (supp['Company Name'] || 'this supplier') : 'this supplier';

  openConfirmModal(
    'Unlink Supplier',
    `Unlink "${suppName}" from ${mfg ? mfg.Name : 'this manufacturer'}? (The supplier itself will not be deleted).`,
    async () => {
      try {
        showToast('Unlinking supplier...');
        const updatedSuppliers = (mfg.Suppliers || [])
          .map(s => s.id || s)
          .filter(id => id !== selectedSupplierId);

        const updatedMfg = await updateManufacturer(selectedMfgId, {
          Suppliers: updatedSuppliers
        });

        const idx = allManufacturers.findIndex(m => m.id === selectedMfgId);
        if (idx !== -1) allManufacturers[idx] = updatedMfg;

        selectManufacturer(selectedMfgId);
        showToast('Supplier unlinked.', 'success');
      } catch (err) {
        showToast(`Failed to unlink supplier: ${err.message}`, 'error');
      }
    }
  );
}

function handleDeleteSupplierClick() {
  if (!selectedSupplierId) return;
  const supp = allSuppliers.find(s => s.id === selectedSupplierId);
  const suppName = supp ? (supp['Company Name'] || 'this supplier') : 'this supplier';

  openConfirmModal(
    'Delete Supplier Completely',
    `Are you sure you want to delete supplier "${suppName}" and all associated data from Baserow?`,
    async () => {
      try {
        showToast('Deleting supplier...');
        await deleteSupplier(selectedSupplierId);
        allSuppliers = allSuppliers.filter(s => s.id !== selectedSupplierId);

        // Update manufacturers referencing this supplier
        allManufacturers.forEach(m => {
          if (m.Suppliers) {
            m.Suppliers = m.Suppliers.filter(s => (s.id || s) !== selectedSupplierId);
          }
        });

        if (selectedMfgId) {
          selectManufacturer(selectedMfgId);
        } else {
          clearSupplierSelection();
        }
        showToast('Supplier deleted.', 'success');
      } catch (err) {
        showToast(`Failed to delete supplier: ${err.message}`, 'error');
      }
    }
  );
}

async function handleUploadSupplierLogo(file) {
  if (!selectedSupplierId) return;
  try {
    showToast('Uploading supplier logo...');
    const uploaded = await uploadLogo(file);
    const updated = await updateSupplier(selectedSupplierId, {
      Logo: [uploaded]
    });

    const idx = allSuppliers.findIndex(s => s.id === selectedSupplierId);
    if (idx !== -1) allSuppliers[idx] = { ...allSuppliers[idx], Logo: [uploaded] };

    renderLogo([uploaded], supplierLogoImg, supplierLogoPlaceholder, btnSupplierRemoveLogo);
    showToast('Supplier logo updated!', 'success');
  } catch (err) {
    showToast(`Failed to upload supplier logo: ${err.message}`, 'error');
  }
}

async function handleRemoveSupplierLogo() {
  if (!selectedSupplierId) return;
  try {
    showToast('Removing supplier logo...');
    await updateSupplier(selectedSupplierId, { Logo: [] });

    const idx = allSuppliers.findIndex(s => s.id === selectedSupplierId);
    if (idx !== -1) allSuppliers[idx].Logo = [];

    renderLogo([], supplierLogoImg, supplierLogoPlaceholder, btnSupplierRemoveLogo);
    showToast('Supplier logo removed.', 'success');
  } catch (err) {
    showToast(`Failed to remove supplier logo: ${err.message}`, 'error');
  }
}

// --- Modals Logic ---

// Modal: Create Manufacturer
function openCreateMfgModal() {
  if (modalInputMfgName) modalInputMfgName.value = '';
  if (modalInputMfgWebsite) modalInputMfgWebsite.value = '';
  if (modalInputMfgNotes) modalInputMfgNotes.value = '';
  openModal(modalCreateMfg);
  if (modalInputMfgName) modalInputMfgName.focus();
}

async function handleConfirmCreateMfg() {
  const name = modalInputMfgName ? modalInputMfgName.value.trim() : '';
  if (!name) {
    showToast('Manufacturer name is required.', 'error');
    return;
  }

  const website = modalInputMfgWebsite ? modalInputMfgWebsite.value.trim() : '';
  const notes = modalInputMfgNotes ? modalInputMfgNotes.value.trim() : '';

  try {
    showToast('Creating manufacturer...');
    const created = await createManufacturer({
      Name: name,
      Website: website,
      Notes: notes
    });

    allManufacturers.unshift(created);
    closeModal(modalCreateMfg);
    renderManufacturersList(mfgSearchInput ? mfgSearchInput.value : '');
    selectManufacturer(created.id);
    showToast(`Manufacturer "${name}" created!`, 'success');
  } catch (err) {
    showToast(`Failed to create manufacturer: ${err.message}`, 'error');
  }
}

// Modal: Supplier Picker & Multi-selection
let pickerSelectedSupplierIds = new Set();

function openSupplierPickerModal() {
  if (!selectedMfgId) return;
  const mfg = allManufacturers.find(m => m.id === selectedMfgId);
  if (!mfg) return;

  if (modalPickerMfgName) modalPickerMfgName.textContent = mfg.Name || 'Manufacturer';
  if (pickerSupplierSearch) pickerSupplierSearch.value = '';

  const currentlyLinked = (mfg.Suppliers || []).map(s => s.id || s);
  pickerSelectedSupplierIds = new Set(currentlyLinked);

  renderPickerList();
  openModal(modalSupplierPicker);

  if (pickerSupplierSearch) {
    pickerSupplierSearch.addEventListener('input', () => {
      renderPickerList(pickerSupplierSearch.value);
    });
  }
}

function renderPickerList(searchQuery = '') {
  if (!pickerSuppliersList) return;

  const query = (searchQuery || '').toLowerCase().trim();
  const filtered = allSuppliers.filter(s => {
    if (!query) return true;
    const name = (s['Company Name'] || s.name || '').toLowerCase();
    const notes = (s.Notes || s.notes || '').toLowerCase();
    return name.includes(query) || notes.includes(query);
  });

  if (filtered.length === 0) {
    pickerSuppliersList.innerHTML = `
      <div style="font-size: 0.85rem; color: var(--text-secondary); padding: 1.5rem; text-align: center;">
        No suppliers found. Click "+ New Supplier" to create one.
      </div>
    `;
    return;
  }

  pickerSuppliersList.innerHTML = filtered.map(supp => {
    const isChecked = pickerSelectedSupplierIds.has(supp.id);
    const name = supp['Company Name'] || supp.name || 'Unnamed Supplier';
    const isOnline = supp['Online Store'] ? '<span class="badge" style="font-size: 0.65rem;">Online Store</span>' : '';

    return `
      <div class="picker-checkbox-item ${isChecked ? 'selected' : ''}" data-supp-id="${supp.id}">
        <div class="picker-supp-info">
          <span class="picker-supp-name">${escapeHtml(name)}</span>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            ${isOnline}
            ${supp.URL ? `<span class="picker-supp-meta">${escapeHtml(supp.URL)}</span>` : ''}
          </div>
        </div>
        <label class="custom-checkbox-container" style="pointer-events: none;">
          <input type="checkbox" ${isChecked ? 'checked' : ''}>
          <span class="custom-checkmark"></span>
        </label>
      </div>
    `;
  }).join('');

  pickerSuppliersList.querySelectorAll('.picker-checkbox-item').forEach(item => {
    item.addEventListener('click', () => {
      const sId = parseInt(item.getAttribute('data-supp-id'), 10);
      if (pickerSelectedSupplierIds.has(sId)) {
        pickerSelectedSupplierIds.delete(sId);
      } else {
        pickerSelectedSupplierIds.add(sId);
      }
      renderPickerList(pickerSupplierSearch ? pickerSupplierSearch.value : '');
    });
  });
}

async function handleApplySupplierPicker() {
  if (!selectedMfgId) return;

  const supplierIds = Array.from(pickerSelectedSupplierIds);
  try {
    showToast('Updating linked suppliers...');
    const updated = await updateManufacturer(selectedMfgId, {
      Suppliers: supplierIds
    });

    const idx = allManufacturers.findIndex(m => m.id === selectedMfgId);
    if (idx !== -1) allManufacturers[idx] = updated;

    closeModal(modalSupplierPicker);
    selectManufacturer(selectedMfgId);
    showToast('Suppliers updated successfully!', 'success');
  } catch (err) {
    showToast(`Failed to update linked suppliers: ${err.message}`, 'error');
  }
}

async function handleCreateSupplierInPicker() {
  const name = prompt('Enter new supplier company name:');
  if (!name || !name.trim()) return;

  try {
    showToast('Creating supplier...');
    const created = await createSupplier({
      'Company Name': name.trim(),
      'Imports From': selectedMfgId ? [selectedMfgId] : []
    });

    allSuppliers.unshift(created);
    pickerSelectedSupplierIds.add(created.id);
    renderPickerList(pickerSupplierSearch ? pickerSupplierSearch.value : '');
    showToast(`Supplier "${name}" created.`, 'success');
  } catch (err) {
    showToast(`Failed to create supplier: ${err.message}`, 'error');
  }
}

// Modal: Contact Edit / Create
function openContactModal(contactObj) {
  editingContactId = contactObj ? contactObj.id : null;
  if (modalContactTitle) {
    modalContactTitle.textContent = contactObj ? 'Edit Contact' : 'Add Supplier Contact';
  }

  if (modalInputContactName) modalInputContactName.value = contactObj ? (contactObj.Name || contactObj.name || '') : '';
  if (modalInputContactEmail) modalInputContactEmail.value = contactObj ? (contactObj.Email || contactObj.email || '') : '';
  if (modalInputContactPhone) modalInputContactPhone.value = contactObj ? (contactObj['Phone number'] || contactObj.phone || '') : '';
  if (modalInputContactActive) modalInputContactActive.checked = contactObj ? (contactObj.Active !== false) : true;
  if (modalInputContactNotes) modalInputContactNotes.value = contactObj ? (contactObj.Notes || contactObj.notes || '') : '';

  openModal(modalContactEdit);
  if (modalInputContactName) modalInputContactName.focus();
}

async function handleConfirmSaveContact() {
  const name = modalInputContactName ? modalInputContactName.value.trim() : '';
  if (!name) {
    showToast('Contact name is required.', 'error');
    return;
  }

  const email = modalInputContactEmail ? modalInputContactEmail.value.trim() : '';
  const phone = modalInputContactPhone ? modalInputContactPhone.value.trim() : '';
  const active = modalInputContactActive ? modalInputContactActive.checked : true;
  const notes = modalInputContactNotes ? modalInputContactNotes.value.trim() : '';

  try {
    if (editingContactId) {
      showToast('Updating contact...');
      const updated = await updateContact(editingContactId, {
        Name: name,
        Email: email,
        'Phone number': phone,
        Active: active,
        Notes: notes
      });

      const idx = allContacts.findIndex(c => c.id === editingContactId);
      if (idx !== -1) {
        allContacts[idx] = { ...allContacts[idx], ...updated, Name: name, Email: email, 'Phone number': phone, Active: active, Notes: notes };
      }
      showToast('Contact updated!', 'success');
    } else {
      if (!selectedSupplierId) {
        showToast('No supplier selected.', 'error');
        return;
      }
      showToast('Creating contact...');
      const created = await createContact({
        Name: name,
        Email: email,
        'Phone number': phone,
        Active: active,
        Notes: notes,
        Suppliers: [selectedSupplierId]
      });

      allContacts.push(created);
      showToast('Contact created!', 'success');
    }

    closeModal(modalContactEdit);
    renderSupplierContacts(selectedSupplierId);
  } catch (err) {
    showToast(`Failed to save contact: ${err.message}`, 'error');
  }
}

// Modal: Confirmation
function openConfirmModal(title, message, onConfirm) {
  if (modalConfirmTitle) modalConfirmTitle.textContent = title;
  if (modalConfirmMessage) modalConfirmMessage.textContent = message;
  pendingDeleteAction = onConfirm;
  openModal(modalConfirmDelete);
}

// --- Utilities ---

function openModal(modalEl) {
  if (modalEl) modalEl.style.display = 'flex';
}

function closeModal(modalEl) {
  if (modalEl) modalEl.style.display = 'none';
}

function setupModalClose(modalEl, closeButtons) {
  if (!modalEl) return;
  (closeButtons || []).forEach(btn => {
    if (btn) {
      btn.addEventListener('click', () => closeModal(modalEl));
    }
  });

  modalEl.addEventListener('click', (e) => {
    if (e.target === modalEl) {
      closeModal(modalEl);
    }
  });
}

function showToast(message, type = 'info') {
  if (!toastContainer) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${escapeHtml(message)}</span>
  `;

  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  }, 3500);
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Auto-run if running in browser
if (typeof window !== 'undefined' && document.getElementById('mfg-list-container')) {
  document.addEventListener('DOMContentLoaded', () => {
    init();
  });
}
