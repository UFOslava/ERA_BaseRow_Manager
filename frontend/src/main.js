import { fetchBomTree, fetchTopLevelItems, fetchItem, updateItem, fetchScanStatus, getHealth, fetchRules, fetchManufacturers, uploadDatasheet, fetchFlatItems, searchItems, createAssembly, updateAssembly, deleteAssembly, createItem, duplicateItem, recategorizeItem, addItemRevision, fetchInstructionSets, fetchInstructionSetDetails, createInstructionStep, updateInstructionStep, deleteInstructionStep, reorderInstructionSteps, deleteInstructionSet, fetchQuickActionTemplates, fetchStates, fetchWiTemplates, exportWiDocument, checkGlobalAuthStatus } from './api.js';

let rawTree = [];
let filteredTree = [];
let searchQuery = '';
let isExplicitSearch = false;
let searchMode = 'all'; // 'all' = every token must match, 'any' = at least one token must match
let expandedNodes = new Set();
let autoExpandedNodes = new Set();
let retryCountdownInterval = null;
let isBusy = false;
let currentParentItemDetails = null;

/**
 * Show a spinner on a button while an async operation runs.
 * Returns a cleanup function that restores the original content.
 */
function setButtonLoading(btn, loadingHtml = '<i class="fa-solid fa-spinner fa-spin"></i>') {
  if (!btn) return () => {};
  const original = btn.innerHTML;
  const wasDisabled = btn.disabled;
  btn.disabled = true;
  btn.innerHTML = loadingHtml;
  return () => {
    btn.innerHTML = original;
    btn.disabled = wasDisabled;
  };
}

/**
 * Runs fn() with isBusy guard, spinner on btn, and optional global lockClass on body.
 * Returns the fn() result or undefined if already busy.
 */
async function withBusy(btn, fn, loadingHtml) {
  if (isBusy) return;
  isBusy = true;
  document.body.classList.add('ui-busy');
  const restore = setButtonLoading(btn, loadingHtml);
  try {
    return await fn();
  } finally {
    restore();
    isBusy = false;
    document.body.classList.remove('ui-busy');
  }
}

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
  blackbox: false,
  datasheets: [],
  images: []
};
let currentDatasheets = [];
let currentImages = [];
let currentGalleryIndex = 0;
let allItems = [];
let manufacturers = [];

let bomExplorerView = document.getElementById('bom-explorer-view');
let itemDetailsView = document.getElementById('item-details-view');
let treeContainer = document.getElementById('tree-container');
let searchInput = document.getElementById('search-input');
let btnRefresh = document.getElementById('btn-refresh');
let statusIndicator = document.getElementById('status-indicator');
let statusText = document.getElementById('status-text');

let btnExportExcel = null;
let btnDuplicate = null;
let duplicateItemModal = null;
let duplicateItemCategory = null;
let duplicateItemDescription = null;
let btnCloseDuplicateItem = null;
let btnCancelDuplicateItem = null;
let btnConfirmDuplicateItem = null;
let duplicateOptParents = null;
let duplicateOptChildren = null;
let duplicateOptInstructions = null;
let duplicateOptPhotos = null;

let headerDefaultBrand = document.getElementById('header-default-brand');
let headerItemReminder = document.getElementById('header-item-reminder');
let headerItemPn = document.getElementById('header-item-pn');
let headerItemDesc = document.getElementById('header-item-desc');
let headerItemActions = document.getElementById('header-item-actions');

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

const inputBlackbox = document.getElementById('input-blackbox');
const instructionSetsList = document.getElementById('instruction-sets-list');
const btnAddInstructionSet = document.getElementById('btn-add-instruction-set');

const assemblyInstructionsView = document.getElementById('assembly-instructions-view');
const btnBackFromInstructions = document.getElementById('btn-back-from-instructions');
const instructionsSetTitleBadge = document.getElementById('instructions-set-title-badge');
const btnDeleteInstructionSet = document.getElementById('btn-delete-instruction-set');
const instructionsParentPn = document.getElementById('instructions-parent-pn');
const instructionsParentDesc = document.getElementById('instructions-parent-desc');

const instructionsComparisonList = document.getElementById('instructions-comparison-list');
const instructionStepsContainer = document.getElementById('instruction-steps-container');
const btnAddStep = document.getElementById('btn-add-step');

const instructionStepModal = document.getElementById('instruction-step-modal');
const instructionStepModalTitle = document.getElementById('instruction-step-modal-title');
const btnCloseInstructionStepModal = document.getElementById('btn-close-instruction-step-modal');
const btnCancelInstructionStep = document.getElementById('btn-cancel-instruction-step');
const btnSaveInstructionStep = document.getElementById('btn-save-instruction-step');

const stepInputAction = document.getElementById('step-input-action');
const stepInputQty = document.getElementById('step-input-qty');
const stepInputChild = document.getElementById('step-input-child');
const stepInputReceiving = document.getElementById('step-input-receiving');
const stepInputTool = document.getElementById('step-input-tool');
const stepInputDescription = document.getElementById('step-input-description');
const stepTextPreview = document.getElementById('step-text-preview');
const stepInputPhotoFile = document.getElementById('step-input-photo-file');
const btnUploadStepPhoto = document.getElementById('btn-upload-step-photo');
const stepPhotoPreview = document.getElementById('step-photo-preview');
const stepInputToll = document.getElementById('step-input-toll');
const btnAddActionItem = document.getElementById('btn-add-action-item');
const actionItemsListContainer = document.getElementById('action-items-list-container');
const btnAddToolItem = document.getElementById('btn-add-tool-item');
const toolsListContainer = document.getElementById('tools-list-container');

let currentInstructionParentId = null;
let currentInstructionSetIndex = 1;
let currentInstructionSteps = [];
let currentInstructionComparison = [];
let editingStepId = null;
let stepPhotoUpload = [];
let insertStepAtIndex = null;
let currentActionItems = [];
let currentToolSlots = [];

// Item Picker Modal DOM variables
const itemPickerModal = document.getElementById('item-picker-modal');
const btnCloseItemPicker = document.getElementById('btn-close-item-picker');
const btnCancelItemPicker = document.getElementById('btn-cancel-item-picker');
const btnClearItemPicker = document.getElementById('btn-clear-item-picker');
const pickerSearchInput = document.getElementById('picker-search-input');
const pickerItemsList = document.getElementById('picker-items-list');

let itemPickerTargetSelectId = null;

let btnFilter = document.getElementById('btn-filter');
let filterDrawer = document.getElementById('filter-drawer');
let btnCloseDrawer = document.getElementById('btn-close-drawer');
let drawerOverlay = document.getElementById('drawer-overlay');

let scanPollingInterval = null;
let categoryRules = {};
let disabledCategories = new Set();
let disabledStates = new Set();

// Default view state — paginated top-level production items
const DEFAULT_STATE_FILTER = 'Production Use';
let isDefaultMode = true;  // true = showing the default paginated view
let topLevelOffset = 0;
let topLevelTotal = 0;
let topLevelBatch = 50;
let filterHasParents = null;  // null=any, true=must have parents, false=must NOT have parents
let filterHasChildren = null; // null=any, true=must have children, false=must NOT have children

// Unified Assembly Modal Selectors with fallback support for legacy tests
let assemblyModal = null;
let btnCloseAssembly = null;
let assemblyModalTitle = null;
let assemblyParentColumn = null;
let assemblyParentSearchWrapper = null;
let assemblyParentSearch = null;
let assemblyParentList = null;
let selectedParentSection = null;
let selectedParentImageBox = null;
let selectedParentPn = null;
let selectedParentDesc = null;
let selectedParentRevisions = null;

let assemblyChildColumn = null;
let assemblyChildSearchWrapper = null;
let assemblyChildSearch = null;
let assemblyChildList = null;
let selectedChildSection = null;
let selectedChildImageBox = null;
let selectedChildPn = null;
let selectedChildDesc = null;
let selectedChildRevisions = null;

let assemblyQuantity = null;
let assemblyLength = null;
let assemblyPcb = null;
let btnDeleteAssemblyRelation = null;
let btnCancelAssembly = null;
let btnConfirmAssembly = null;

// Unified Assembly Modal State & Compatibility wrappers
let assemblyMode = null; // 'create' or 'edit'
let assemblyEdgeId = null;
let assemblySelectedParentId = null;
let assemblySelectedChildId = null;
let assemblyLockedParent = false;
let assemblyLockedChild = false;

// Legacy variables for test compatibility
let addChildModal = null;
let btnCloseAddChild = null;
let addChildSearch = null;
let addChildList = null;
let addChildForm = null;
let selectedChildName = null;
let addChildRevisionTags = null;
let addChildQuantity = null;
let addChildLength = null;
let addChildPcb = null;
let btnCancelAddChild = null;
let btnConfirmAddChild = null;

let editAssemblyModal = null;
let btnCloseEditAssembly = null;
let editAssemblyItemName = null;
let editAssemblyQuantity = null;
let editAssemblyLength = null;
let editAssemblyPcb = null;
let btnDeleteAssembly = null;
let btnCancelEditAssembly = null;
let btnSaveEditAssembly = null;

let addChildParentId = null;
let addChildSelectedItemId = null;
let addChildSelectedRevId = null;
let editAssemblyEdgeId = null;
let editAssemblyNode = null;

// Create Item Modal Selectors
const createItemModal = document.getElementById('create-item-modal');
const btnCloseCreateItem = document.getElementById('btn-close-create-item');
const btnCancelCreateItem = document.getElementById('btn-cancel-create-item');
const btnConfirmCreateItem = document.getElementById('btn-confirm-create-item');
const createItemCategory = document.getElementById('create-item-category');
const createItemDescription = document.getElementById('create-item-description');
const btnAddItemTrigger = document.getElementById('btn-add-item-trigger');

async function init() {
  bomExplorerView = document.getElementById('bom-explorer-view') || bomExplorerView;
  itemDetailsView = document.getElementById('item-details-view') || itemDetailsView;
  treeContainer = document.getElementById('tree-container') || treeContainer;
  searchInput = document.getElementById('search-input') || searchInput;
  btnRefresh = document.getElementById('btn-refresh') || btnRefresh;
  statusIndicator = document.getElementById('status-indicator') || statusIndicator;
  statusText = document.getElementById('status-text') || statusText;
  btnFilter = document.getElementById('btn-filter') || btnFilter;
  filterDrawer = document.getElementById('filter-drawer') || filterDrawer;
  btnCloseDrawer = document.getElementById('btn-close-drawer') || btnCloseDrawer;
  drawerOverlay = document.getElementById('drawer-overlay') || drawerOverlay;
  btnExportExcel = document.getElementById('btn-export-excel') || btnExportExcel;
  btnDuplicate = document.getElementById('btn-duplicate') || btnDuplicate;
  duplicateItemModal = document.getElementById('duplicate-item-modal') || duplicateItemModal;
  duplicateItemCategory = document.getElementById('duplicate-item-category') || duplicateItemCategory;
  duplicateItemDescription = document.getElementById('duplicate-item-description') || duplicateItemDescription;
  btnCloseDuplicateItem = document.getElementById('btn-close-duplicate-item') || btnCloseDuplicateItem;
  btnCancelDuplicateItem = document.getElementById('btn-cancel-duplicate-item') || btnCancelDuplicateItem;
  btnConfirmDuplicateItem = document.getElementById('btn-confirm-duplicate-item') || btnConfirmDuplicateItem;
  duplicateOptParents = document.getElementById('duplicate-opt-parents') || duplicateOptParents;
  duplicateOptChildren = document.getElementById('duplicate-opt-children') || duplicateOptChildren;
  duplicateOptInstructions = document.getElementById('duplicate-opt-instructions') || duplicateOptInstructions;
  duplicateOptPhotos = document.getElementById('duplicate-opt-photos') || duplicateOptPhotos;

  headerDefaultBrand = document.getElementById('header-default-brand') || headerDefaultBrand;
  headerItemReminder = document.getElementById('header-item-reminder') || headerItemReminder;
  headerItemPn = document.getElementById('header-item-pn') || headerItemPn;
  headerItemDesc = document.getElementById('header-item-desc') || headerItemDesc;
  headerItemActions = document.getElementById('header-item-actions') || headerItemActions;

  if (typeof window !== 'undefined') {
    window.addEventListener('scroll', updateHeaderScrollState, { passive: true });
  }

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
  
  // Unified Assembly Modal Event Listeners (with legacy support)
  const closeAssemblyBtns = [
    document.getElementById('btn-close-assembly'),
    document.getElementById('btn-close-add-child'),
    document.getElementById('btn-close-edit-assembly')
  ];
  closeAssemblyBtns.forEach(btn => {
    if (btn) btn.addEventListener('click', closeAssemblyModal);
  });

  const cancelAssemblyBtns = [
    document.getElementById('btn-cancel-assembly'),
    document.getElementById('btn-cancel-add-child'),
    document.getElementById('btn-cancel-edit-assembly')
  ];
  cancelAssemblyBtns.forEach(btn => {
    if (btn) btn.addEventListener('click', closeAssemblyModal);
  });

  const confirmAssemblyBtns = [
    document.getElementById('btn-confirm-assembly'),
    document.getElementById('btn-confirm-add-child'),
    document.getElementById('btn-save-edit-assembly')
  ];
  confirmAssemblyBtns.forEach(btn => {
    if (btn) btn.addEventListener('click', handleConfirmAssembly);
  });

  const deleteAssemblyBtns = [
    document.getElementById('btn-delete-assembly-relation'),
    document.getElementById('btn-delete-assembly')
  ];
  deleteAssemblyBtns.forEach(btn => {
    if (btn) btn.addEventListener('click', handleDeleteAssemblyRelation);
  });

  const parentAssemblySearches = [
    document.getElementById('assembly-parent-search')
  ];
  parentAssemblySearches.forEach(search => {
    if (search) search.addEventListener('input', renderAssemblyParentList);
  });

  const childAssemblySearches = [
    document.getElementById('assembly-child-search'),
    document.getElementById('add-child-search')
  ];
  childAssemblySearches.forEach(search => {
    if (search) search.addEventListener('input', renderAssemblyChildList);
  });

  const assemblyModals = [
    document.getElementById('assembly-modal'),
    document.getElementById('add-child-modal'),
    document.getElementById('edit-assembly-modal')
  ];
  assemblyModals.forEach(m => {
    if (m) {
      m.addEventListener('click', (e) => {
        if (e.target === m) closeAssemblyModal();
      });
    }
  });

  const btnChangeParent = document.getElementById('btn-change-parent');
  if (btnChangeParent) {
    btnChangeParent.addEventListener('click', () => {
      assemblySelectedParentId = null;
      updateSelectedParentDisplay();
      checkAssemblyConfirmState();
      if (assemblyParentSearch) {
        assemblyParentSearch.value = '';
        renderAssemblyParentList();
        assemblyParentSearch.focus();
      }
    });
  }

  const btnChangeChild = document.getElementById('btn-change-child');
  if (btnChangeChild) {
    btnChangeChild.addEventListener('click', () => {
      assemblySelectedChildId = null;
      updateSelectedChildDisplay();
      checkAssemblyConfirmState();
      if (assemblyChildSearch) {
        assemblyChildSearch.value = '';
        renderAssemblyChildList();
        assemblyChildSearch.focus();
      }
    });
  }

  // Relations Add Buttons inside Details View
  const btnAddContained = document.getElementById('btn-add-contained');
  const btnAddContaining = document.getElementById('btn-add-containing');
  if (btnAddContained) btnAddContained.addEventListener('click', () => openAssemblyModal({ parentId: currentItemId }));
  if (btnAddContaining) btnAddContaining.addEventListener('click', () => openAssemblyModal({ childId: currentItemId }));
  if (searchInput) {
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = searchInput.value.toLowerCase().trim();
        searchQuery = val;
        if (val.length > 0) {
          isExplicitSearch = true;
          refreshData();
        } else {
          // Cleared — reset tree
          isExplicitSearch = false;
          const isFilterActive = disabledCategories.size > 0 || disabledStates.size > 0;
          if (!isFilterActive) {
            rawTree = [];
            allItems = [];
            filteredTree = [];
            renderTreeTable();
          } else {
            applyFilterAndRender();
          }
        }
      }
    });
  }

  // Search mode toggle (ALL / ANY)
  const btnSearchMode = document.getElementById('btn-search-mode');
  if (btnSearchMode) {
    btnSearchMode.textContent = 'ALL';
    btnSearchMode.addEventListener('click', () => {
      searchMode = searchMode === 'all' ? 'any' : 'all';
      btnSearchMode.textContent = searchMode.toUpperCase();
      btnSearchMode.classList.toggle('active', searchMode === 'any');
      // Re-apply filter on the currently loaded tree without re-fetching
      if (searchQuery || disabledCategories.size > 0 || disabledStates.size > 0) {
        applyFilterAndRender();
      }
    });
  }
  
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
  
  // Duplicate Item Modal Event Listeners
  if (btnDuplicate) btnDuplicate.addEventListener('click', openDuplicateItemModal);
  if (btnCloseDuplicateItem) btnCloseDuplicateItem.addEventListener('click', closeDuplicateItemModal);
  if (btnCancelDuplicateItem) btnCancelDuplicateItem.addEventListener('click', closeDuplicateItemModal);
  if (btnConfirmDuplicateItem) btnConfirmDuplicateItem.addEventListener('click', handleConfirmDuplicateItem);
  if (duplicateItemModal) {
    duplicateItemModal.addEventListener('click', (e) => {
      if (e.target === duplicateItemModal) closeDuplicateItemModal();
    });
  }
  
  // Gallery Overlay event listeners
  const galleryOverlay = document.getElementById('gallery-overlay');
  const btnCloseGalleryOverlay = document.getElementById('btn-close-gallery-overlay');
  const btnGalleryPrev = document.getElementById('btn-gallery-prev');
  const btnGalleryNext = document.getElementById('btn-gallery-next');

  if (btnCloseGalleryOverlay) {
    btnCloseGalleryOverlay.addEventListener('click', closeGalleryOverlay);
  }
  if (btnGalleryPrev) {
    btnGalleryPrev.addEventListener('click', () => navigateGallery(-1));
  }
  if (btnGalleryNext) {
    btnGalleryNext.addEventListener('click', () => navigateGallery(1));
  }
  if (galleryOverlay) {
    galleryOverlay.addEventListener('click', (e) => {
      if (e.target === galleryOverlay) closeGalleryOverlay();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (galleryOverlay && galleryOverlay.style.display === 'flex') {
      if (e.key === 'ArrowRight') {
        navigateGallery(1);
      } else if (e.key === 'ArrowLeft') {
        navigateGallery(-1);
      } else if (e.key === 'Escape') {
        closeGalleryOverlay();
      }
    }
  });

  if (btnBack) btnBack.addEventListener('click', handleBackNavigation);
  if (btnRevert) btnRevert.addEventListener('click', revertChanges);
  if (btnSave) btnSave.addEventListener('click', saveChanges);
  
  if (btnExportExcel) {
    btnExportExcel.addEventListener('click', () => {
      if (currentItemId) {
        const url = `${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/bom/items/${currentItemId}/export`;
        window.open(url, '_blank');
      }
    });
  }
  
  if (inputDescription) {
    inputDescription.addEventListener('input', () => {
      checkChanges();
      const descVal = inputDescription.value.trim() || 'No description';
      const pnVal = titlePn ? titlePn.textContent : '';
      if (titleDesc) titleDesc.textContent = descVal;
      if (headerItemDesc) headerItemDesc.textContent = descVal;
      document.title = `${pnVal} - ${descVal}`;
    });
  }
  if (inputSource) inputSource.addEventListener('input', checkChanges);
  if (inputExternalPn) inputExternalPn.addEventListener('input', checkChanges);
  if (inputState) inputState.addEventListener('change', checkChanges);
  if (inputManufacturer) inputManufacturer.addEventListener('change', checkChanges);
  const btnEditManufacturer = document.getElementById('btn-edit-manufacturer');
  if (btnEditManufacturer) {
    btnEditManufacturer.addEventListener('click', () => {
      const mfgId = inputManufacturer ? inputManufacturer.value : '';
      if (mfgId) {
        window.location.href = `/manufacturers.html?id=${mfgId}`;
      } else {
        window.location.href = '/manufacturers.html';
      }
    });
  }
  if (inputPrice) inputPrice.addEventListener('input', checkChanges);
  if (inputSourcedBy) inputSourcedBy.addEventListener('change', checkChanges);
  if (inputNotes) inputNotes.addEventListener('input', checkChanges);
  if (inputBlackbox) inputBlackbox.addEventListener('change', checkChanges);
  
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


  // Recategorize modal event listeners
  const btnEditCategory = document.getElementById('btn-edit-category');
  const recategorizeModal = document.getElementById('recategorize-modal');
  const btnCloseRecategorize = document.getElementById('btn-close-recategorize');
  const btnCancelRecategorize = document.getElementById('btn-cancel-recategorize');
  const btnConfirmRecategorize = document.getElementById('btn-confirm-recategorize');
  const recategorizeCategorySelect = document.getElementById('recategorize-category');

  if (btnEditCategory) {
    btnEditCategory.addEventListener('click', openRecategorizeModal);
  }
  const closeRecategorizeModal = () => {
    if (recategorizeModal) {
      recategorizeModal.classList.remove('open');
      setTimeout(() => { recategorizeModal.style.display = 'none'; }, 300);
    }
  };
  if (btnCloseRecategorize) btnCloseRecategorize.addEventListener('click', closeRecategorizeModal);
  if (btnCancelRecategorize) btnCancelRecategorize.addEventListener('click', closeRecategorizeModal);
  if (recategorizeModal) {
    recategorizeModal.addEventListener('click', (e) => {
      if (e.target === recategorizeModal) closeRecategorizeModal();
    });
  }
  if (recategorizeCategorySelect) {
    recategorizeCategorySelect.addEventListener('change', () => {
      updateRecategorizePreview();
    });
  }
  if (btnConfirmRecategorize) {
    btnConfirmRecategorize.addEventListener('click', handleConfirmRecategorize);
  }

  ensureManufacturersLoaded();
  
  if (btnFilter) {
    btnFilter.addEventListener('click', () => {
      if (filterDrawer) filterDrawer.classList.add('open');
    });
  }
  
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener('click', () => {
      if (filterDrawer) {
        filterDrawer.classList.remove('open');
        refreshData();
      }
    });
  }
  
  if (drawerOverlay) {
    drawerOverlay.addEventListener('click', () => {
      if (filterDrawer) {
        filterDrawer.classList.remove('open');
        refreshData();
      }
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
  const blackboxVal = inputBlackbox ? inputBlackbox.checked : false;
  
  const datasheetsChanged = JSON.stringify(currentDatasheets.map(d => d.name)) !== JSON.stringify((originalData.datasheets || []).map(d => d.name));
  const imagesChanged = JSON.stringify(currentImages.map(img => img.name)) !== JSON.stringify((originalData.images || []).map(img => img.name));
  
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
         blackboxVal !== !!originalData.blackbox ||
         datasheetsChanged ||
         imagesChanged;
}

function checkChanges() {
  const changed = hasUnsavedChanges();
  if (btnSave) btnSave.disabled = !changed;
  if (btnRevert) btnRevert.disabled = !changed;
}

export function updateHeaderItemReminder(pn, desc) {
  if (headerItemPn) headerItemPn.textContent = pn || '';
  if (headerItemDesc) headerItemDesc.textContent = desc || '';
}

export function updateHeaderScrollState() {
  if (itemDetailsView && itemDetailsView.style.display !== 'none') {
    const scrollPos = typeof window !== 'undefined' ? window.scrollY : 0;
    const isScrolled = scrollPos > 80;
    if (headerDefaultBrand) headerDefaultBrand.style.display = isScrolled ? 'none' : 'flex';
    if (headerItemReminder) headerItemReminder.style.display = isScrolled ? 'flex' : 'none';
    if (headerItemActions) headerItemActions.style.display = 'flex';
  } else {
    if (headerDefaultBrand) headerDefaultBrand.style.display = 'flex';
    if (headerItemReminder) headerItemReminder.style.display = 'none';
    if (headerItemActions) headerItemActions.style.display = 'none';
  }
}

function showExplorerPage() {
  currentItemId = null;
  if (itemDetailsView) itemDetailsView.style.display = 'none';
  if (bomExplorerView) bomExplorerView.style.display = 'block';
  document.title = 'ERA BOM Explorer';
  updateHeaderScrollState();
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

  updateHeaderScrollState();

  const loadingToast = showLoadingToast('Loading item data from Baserow...', 25);

  try {
    const item = await fetchItem(itemId);
    if (loadingToast) loadingToast.updateProgress(50, 'Loading manufacturers...');
    
    const fullPnStr = item["Full PN"] || item["Part Number"] || 'N/A';
    const descStr = item["Item description"] || 'No description';
    
    if (titlePn) titlePn.textContent = fullPnStr;
    if (titleDesc) titleDesc.textContent = descStr;
    document.title = `${fullPnStr} - ${descStr}`;
    updateHeaderItemReminder(fullPnStr, descStr);
    updateHeaderScrollState();
    
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
    
    const sourcedByObj = item["Sourced By"];
    if (itemSourcedBy) itemSourcedBy.textContent = sourcedByObj ? sourcedByObj.value : 'N/A';
    
    const stateObj = item["State"];
    if (itemState) {
      let displayState = 'N/A';
      if (stateObj) {
        if (Array.isArray(stateObj)) {
          displayState = (stateObj[0] && stateObj[0].value) ? stateObj[0].value : 'N/A';
        } else if (typeof stateObj === 'object') {
          displayState = stateObj.value || 'N/A';
        } else {
          displayState = String(stateObj);
        }
      }
      itemState.textContent = displayState;
    }
    
    if (itemNotes) itemNotes.textContent = item["Notes"] || 'No notes available.';
    
    await ensureManufacturersLoaded();
    if (loadingToast) loadingToast.updateProgress(75, 'Loading related items...');

    await ensureAllItemsLoaded();
    await ensureRulesLoaded();

    if (itemCategory) {
      const pnCatList = item["PN Category"] || [];
      if (pnCatList && pnCatList.length > 0) {
        const prefix = pnCatList[0].value;
        const rule = categoryRules[prefix];
        if (rule) {
          itemCategory.textContent = `${prefix} - ${rule.name || 'Unknown'}`;
        } else {
          itemCategory.textContent = prefix || 'N/A';
        }
      } else {
        itemCategory.textContent = 'N/A';
      }
    }
    
    let originalState = 'Unknown';
    if (stateObj) {
      if (Array.isArray(stateObj)) {
        originalState = (stateObj[0] && stateObj[0].value) ? stateObj[0].value : 'Unknown';
      } else if (typeof stateObj === 'object') {
        originalState = stateObj.value || 'Unknown';
      } else {
        originalState = String(stateObj);
      }
    }

    originalData = {
      fullPn: item["Full PN"] || item["Part Number"] || 'N/A',
      description: item["Item description"] || '',
      source: item["Source URL"] || '',
      externalPn: item["External Part Number"] || '',
      state: originalState,
      manufacturerId: (item["Manufacturer"] && item["Manufacturer"].length > 0) ? item["Manufacturer"][0].id : '',
      price: item["Price per unit"] !== null ? parseFloat(item["Price per unit"]) : null,
      sourcedBy: item["Sourced By"] ? item["Sourced By"].value : 'TBD',
      notes: item["Notes"] || '',
      blackbox: !!item["Blackbox"],
      datasheets: item["Datasheet"] || [],
      images: item["Image"] || []
    };
    
    if (inputDescription) inputDescription.value = originalData.description;
    if (inputSource) inputSource.value = originalData.source;
    if (inputExternalPn) inputExternalPn.value = originalData.externalPn;
    if (inputState) inputState.value = originalData.state;
    if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
    if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';
    if (inputSourcedBy) inputSourcedBy.value = originalData.sourcedBy;
    if (inputNotes) inputNotes.value = originalData.notes;
    if (inputBlackbox) inputBlackbox.checked = originalData.blackbox;
    
    currentDatasheets = [...(originalData.datasheets || [])];
    renderDatasheetsList();
    
    currentImages = [...(originalData.images || [])];
    renderGallery();
    
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
    
    renderItemRelations(item);
    if (inputBlackbox) inputBlackbox.checked = !!item.Blackbox;
    await loadInstructionSetsForItem(itemId);

    if (loadingToast) loadingToast.complete('Item data loaded.');
  } catch (error) {
    if (loadingToast) loadingToast.dismiss();
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
  if (inputBlackbox) inputBlackbox.checked = originalData.blackbox;
  
  if (titleDesc) titleDesc.textContent = originalData.description || 'No description';
  if (headerItemDesc) headerItemDesc.textContent = originalData.description || 'No description';
  document.title = `${originalData.fullPn || 'N/A'} - ${originalData.description || 'No description'}`;

  currentDatasheets = [...(originalData.datasheets || [])];
  renderDatasheetsList();
  
  currentImages = [...(originalData.images || [])];
  renderGallery();
  
  checkChanges();
  showToast('Changes reverted to original values.');
}

async function saveChanges() {
  if (!currentItemId) return;
  await withBusy(btnSave, async () => {
    const descVal = inputDescription ? inputDescription.value.trim() : '';
    const srcVal = inputSource ? inputSource.value.trim() : '';
    const extPnVal = inputExternalPn ? inputExternalPn.value.trim() : '';
    const stateVal = inputState ? inputState.value : 'Unknown';
    const mfgVal = inputManufacturer && inputManufacturer.value ? [parseInt(inputManufacturer.value, 10)] : [];
    const priceVal = inputPrice && inputPrice.value.trim() !== '' ? parseFloat(inputPrice.value) : null;
    const sourcedByVal = inputSourcedBy ? inputSourcedBy.value : 'TBD';
    const notesVal = inputNotes ? inputNotes.value.trim() : '';

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
        "Blackbox": inputBlackbox ? inputBlackbox.checked : false
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
        blackbox: inputBlackbox ? inputBlackbox.checked : false,
        datasheets: [...currentDatasheets],
        images: [...currentImages]
      };

      checkChanges();
      showToast('Item saved successfully.');

      await showItemPage(currentItemId);
    } catch (error) {
      showToast(error.message, 'error');
    }
  }, '<i class="fa-solid fa-spinner fa-spin"></i> Saving...');
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
    const authState = await checkGlobalAuthStatus();
    if (authState.isComplete) {
      if (statusIndicator) statusIndicator.className = 'status-indicator healthy';
      if (statusText) statusText.textContent = 'Baserow Online';
    }
  } catch (error) {
    if (statusIndicator) statusIndicator.className = 'status-indicator error';
    if (statusText) statusText.textContent = 'Baserow Offline';
  }
}

async function loadDefaultView(reset = false) {
  if (reset) {
    topLevelOffset = 0;
    topLevelTotal = 0;
    rawTree = [];
    filteredTree = [];
  }

  const activeTreeContainer = document.getElementById('tree-container') || treeContainer;

  // Check authentication completeness before attempting queries
  const authState = await checkGlobalAuthStatus();
  if (!authState.isComplete) {
    if (activeTreeContainer) {
      activeTreeContainer.innerHTML = `
        <div class="auth-empty-state">
          <i class="fa-solid fa-triangle-exclamation main-icon"></i>
          <h2>Baserow Authentication Incomplete</h2>
          <p>Baserow API Token or database table IDs are missing or unverified. Please configure your Baserow connection in Settings to load BOM data.</p>
          <a href="/settings.html#auth" class="btn btn-primary"><i class="fa-solid fa-key"></i> Configure Authentication</a>
        </div>
      `;
    }
    return;
  }

  const loadingToast = reset ? showLoadingToast('Loading production items...', 15) : null;

  try {
    // Ensure rules + states are loaded for the drawer
    if (Object.keys(categoryRules).length === 0) {
      const [rulesData, statesData] = await Promise.all([
        fetchRules().catch(() => ({})),
        fetchStates().catch(() => null)
      ]);
      categoryRules = rulesData || {};
      if (statesData && Object.keys(statesData).length > 0) {
        Object.keys(STATE_COLORS).forEach(k => delete STATE_COLORS[k]);
        Object.entries(statesData).forEach(([name, info]) => {
          STATE_COLORS[name] = info.color || '#8e9095';
        });
        // Sync disabledStates to match default filter (all except Production Use)
        disabledStates.clear();
        Object.keys(STATE_COLORS).forEach(name => {
          if (name !== DEFAULT_STATE_FILTER) disabledStates.add(name);
        });
      } else {
        // Fallback — disable all states except the default
        disabledStates.clear();
        Object.keys(STATE_COLORS).forEach(name => {
          if (name !== DEFAULT_STATE_FILTER) disabledStates.add(name);
        });
      }
    }

    renderDrawerCategories();
    renderDrawerStates();
    renderDrawerStructural();
    updateFilterBadge();



    const data = await fetchTopLevelItems(DEFAULT_STATE_FILTER, topLevelOffset, topLevelBatch);
    topLevelTotal = data.total || 0;
    const newNodes = (data.items || []).map(item => ({ ...item, quantity_label: 'Root', pcb_symbol: 'N/A', children: [] }));

    // Append the new batch to rawTree
    rawTree = [...rawTree, ...newNodes];
    filteredTree = applyStructuralFilter(rawTree);
    topLevelOffset += newNodes.length;

    renderTreeTable();
    renderBatchButton();
    if (loadingToast) loadingToast.complete(`Loaded ${topLevelTotal} production items.`);
  } catch (err) {
    if (loadingToast) loadingToast.dismiss();
    showToast(err.message, 'error');
    if (activeTreeContainer && reset) {
      activeTreeContainer.innerHTML = `<div class="loading-spinner" style="color:var(--color-danger)">Failed to load items. <button id="btn-retry-refresh" class="btn btn-secondary" style="margin-left:0.5rem">Retry</button></div>`;
      const retryBtn = document.getElementById('btn-retry-refresh');
      if (retryBtn) retryBtn.addEventListener('click', () => loadDefaultView(true));
    }
  }
}

function applyStructuralFilter(nodes) {
  if (filterHasParents === null && filterHasChildren === null) return nodes;
  return nodes.filter(node => {
    if (filterHasParents !== null && Boolean(node.has_parents) !== filterHasParents) return false;
    if (filterHasChildren !== null && Boolean(node.has_children) !== filterHasChildren) return false;
    return true;
  });
}

function renderBatchButton() {
  const activeTreeContainer = document.getElementById('tree-container') || treeContainer;
  if (!activeTreeContainer) return;
  // Remove existing batch button if any
  const old = document.getElementById('btn-fetch-next-batch');
  if (old) old.remove();
  if (!isDefaultMode || topLevelOffset >= topLevelTotal) return;

  const remaining = topLevelTotal - topLevelOffset;
  const btn = document.createElement('button');
  btn.id = 'btn-fetch-next-batch';
  btn.className = 'btn btn-secondary';
  btn.style.cssText = 'display:flex; align-items:center; gap:0.5rem; margin: 1rem auto; padding: 0.6rem 1.4rem;';
  btn.innerHTML = `<i class="fa-solid fa-chevron-down"></i> Load next ${Math.min(topLevelBatch, remaining)} of ${remaining} remaining`;
  btn.addEventListener('click', () => loadDefaultView(false));
  activeTreeContainer.appendChild(btn);
}

async function refreshData() {
  if (retryCountdownInterval) {
    clearInterval(retryCountdownInterval);
    retryCountdownInterval = null;
  }

  const isFilterActive = disabledCategories.size > 0 || disabledStates.size > 0;
  const isSearchActive = searchQuery.length >= 4 || isExplicitSearch;

  // Default mode: only the Production Use state filter is active (no category filter, no search)
  const isOnlyDefaultStateActive = disabledCategories.size === 0 &&
    disabledStates.size === Object.keys(STATE_COLORS).length - 1 &&
    !disabledStates.has(DEFAULT_STATE_FILTER) &&
    !isSearchActive;

  if (!isFilterActive && !isSearchActive) {
    // No filter at all — switch to default mode and load first batch
    isDefaultMode = true;
    await loadDefaultView(true);
    return;
  }

  if (isOnlyDefaultStateActive && filterHasParents === null && filterHasChildren === null) {
    // Pure default mode — use paginated top-level endpoint
    isDefaultMode = true;
    await loadDefaultView(true);
    return;
  }

  // Any other active filter/search — use full tree
  isDefaultMode = false;

  const loadingToast = showLoadingToast('Loading BOM data from Baserow...', 20);
  const activeTreeContainer = document.getElementById('tree-container') || treeContainer;
  try {
    const spinner = activeTreeContainer ? activeTreeContainer.querySelector('.loading-spinner') : null;
    if (!spinner && activeTreeContainer) {
      activeTreeContainer.innerHTML = '<div class="loading-spinner">Loading BOM data from Baserow...</div>';
    }
    
    const [treeData, rulesData, flatData, statesData] = await Promise.all([
      fetchBomTree(),
      fetchRules().catch(err => {
        console.error("Failed to fetch rules", err);
        return {};
      }),
      fetchFlatItems().catch(err => {
        console.error("Failed to fetch flat items", err);
        return [];
      }),
      fetchStates().catch(err => {
        console.error("Failed to fetch states", err);
        return null;
      })
    ]);

    if (loadingToast) loadingToast.updateProgress(75, 'Rendering BOM tree...');

    allItems = flatData || [];
    categoryRules = rulesData;
    if (statesData && Object.keys(statesData).length > 0) {
      Object.keys(STATE_COLORS).forEach(k => delete STATE_COLORS[k]);
      Object.entries(statesData).forEach(([name, info]) => {
        STATE_COLORS[name] = info.color || "#8e9095";
      });
    }
    
    rawTree = sortTreeNodesRecursively(treeData);
    
    if (expandedNodes.size === 0) {
      rawTree.forEach(node => {
        expandedNodes.add(String(node.id));
      });
    }
    
    renderDrawerCategories();
    renderDrawerStates();
    renderDrawerStructural();
    applyFilterAndRender();
    startPollingIfScanning();

    if (loadingToast) loadingToast.complete('BOM data loaded.');
  } catch (error) {
    if (loadingToast) loadingToast.dismiss();
    showToast(error.message, 'error');
    if (activeTreeContainer) {
      activeTreeContainer.innerHTML = `
        <div class="loading-spinner" style="color: var(--color-danger); display: flex; flex-direction: column; align-items: center; gap: 1rem;">
          <div>Error: failed to fetch BOM tree</div>
          <button id="btn-retry-refresh" class="btn btn-secondary" style="margin-top: 0.5rem; display: inline-flex; align-items: center; gap: 0.5rem;">
            <i class="fa-solid fa-arrows-rotate"></i>
            <span>Refresh (10s)</span>
          </button>
        </div>
      `;
      
      const retryBtn = document.getElementById('btn-retry-refresh');
      if (retryBtn) {
        let count = 10;
        const btnText = retryBtn.querySelector('span');
        
        retryCountdownInterval = setInterval(() => {
          count--;
          if (count <= 0) {
            clearInterval(retryCountdownInterval);
            retryCountdownInterval = null;
            refreshData();
          } else {
            if (btnText) btnText.textContent = `Refresh (${count}s)`;
          }
        }, 1000);
        
        retryBtn.addEventListener('click', () => {
          if (retryCountdownInterval) {
            clearInterval(retryCountdownInterval);
            retryCountdownInterval = null;
          }
          refreshData();
        });
      }
    }
  }
}

async function startPollingIfScanning() {
  if (scanPollingInterval) return;
  
  try {
    const statusObj = await fetchScanStatus();
    if (statusObj && (statusObj.status === 'running' || statusObj.status === 'pending')) {
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
  if (isDefaultMode) {
    // Re-run default view silently (reload from scratch)
    await loadDefaultView(true);
    return;
  }
  const isFilterActive = disabledCategories.size > 0 || disabledStates.size > 0;
  const isSearchActive = searchQuery.length >= 4 || isExplicitSearch;
  if (!isFilterActive && !isSearchActive) {
    return;
  }
  try {
    const [treeData, rulesData, flatData, statesData] = await Promise.all([
      fetchBomTree(),
      fetchRules().catch(err => {
        console.error("Failed to fetch rules", err);
        return {};
      }),
      fetchFlatItems().catch(err => {
        console.error("Failed to fetch flat items", err);
        return [];
      }),
      fetchStates().catch(err => {
        console.error("Failed to fetch states", err);
        return null;
      })
    ]);
    allItems = flatData || [];
    categoryRules = rulesData;
    if (statesData && Object.keys(statesData).length > 0) {
      Object.keys(STATE_COLORS).forEach(k => delete STATE_COLORS[k]);
      Object.entries(statesData).forEach(([name, info]) => {
        STATE_COLORS[name] = info.color || "#8e9095";
      });
    }
    rawTree = sortTreeNodesRecursively(treeData);
    renderDrawerCategories();
    renderDrawerStates();
    renderDrawerStructural();
    applyFilterAndRender();
  } catch (err) {
    console.error('Silent refresh failed:', err);
  }
}

function handleSearch(e) {
  // No-op: search is now triggered only on Enter key press (see init() keydown listener).
}

function getSearchMode() { return searchMode; }
function setSearchMode(mode) { searchMode = mode; }

function getFilterHasParents() { return filterHasParents; }
function setFilterHasParents(val) { filterHasParents = val; }

function getFilterHasChildren() { return filterHasChildren; }
function setFilterHasChildren(val) { filterHasChildren = val; }

function applyFilterAndRender() {
  autoExpandedNodes.clear();
  const result = [];
  
  rawTree.forEach(node => {
    const filtered = filterNode(node, searchQuery, String(node.id), []);
    if (filtered) {
      result.push(filtered);
    }
  });
  filteredTree = sortTreeNodesRecursively(applyStructuralFilter(result));
  
  renderTreeTable();
}

function itemMatchesQuery(item, query, mode = searchMode) {
  if (!query || typeof query !== 'string' || !query.trim()) return true;
  if (!item || typeof item !== 'object') return false;

  let mfgStr = '';
  const mfg = item.Manufacturer || item.manufacturer;
  if (Array.isArray(mfg)) {
    mfgStr = mfg.map(m => (m && typeof m === 'object' ? (m.value || m.name || '') : String(m || ''))).join(' ');
  } else if (mfg && typeof mfg === 'object') {
    mfgStr = mfg.value || mfg.name || '';
  } else if (typeof mfg === 'string') {
    mfgStr = mfg;
  }

  // Build a single combined searchable string from all relevant fields
  const combined = [
    item.part_number || item["Part Number"] || item.pn || item.pn_number || '',
    item["Full PN"] || item.full_pn || item["Full Part Number"] || '',
    item.description || item["Item description"] || item["Description"] || item.desc || '',
    item.search_helper || item["Search helper"] || item["Search Helper"] || '',
    item.external_pn || item["External PN"] || item["External Part Number"] || item["Ext PN"] || item["Manufacturer PN"] || item["Supplier PN"] || item.external_part_number || '',
    item.notes || item["Notes"] || item["Comments"] || item["Remarks"] || '',
    item.revision || item["Revision"] || item["Rev"] || '',
    item.pcb_symbol || item["PCB Symbol"] || item["Designator"] || item["RefDes"] || '',
    mfgStr
  ].join(' ').toLowerCase();

  // Tokenise on whitespace — every non-empty token counts
  const tokens = query.toLowerCase().split(/\s+/).filter(t => t.length > 0);
  if (tokens.length === 0) return true;

  const currentMode = mode || searchMode || 'all';
  if (currentMode === 'any') {
    return tokens.some(token => combined.includes(token));
  } else {
    // default: 'all' — every token must appear somewhere in the combined string
    return tokens.every(token => combined.includes(token));
  }
}

function nodeMatchesQuery(node, query) {
  return itemMatchesQuery(node, query, searchMode);
}

function filterNode(node, query, currentPath, parentPaths, ancestorMatched = false) {
  const categoryName = (node.pn_tag && node.pn_tag.name) || 'Unknown';
  const isDisabledCategory = disabledCategories.has(categoryName);
  const isDisabledState = disabledStates.has(node.state || 'Unknown');
  const isDisabled = isDisabledCategory || isDisabledState;

  const isSelfMatch = nodeMatchesQuery(node, query);
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

let fullTreeCache = null;

async function ensureNodeChildrenLoaded(node) {
  if (node.children && node.children.length > 0) {
    return;
  }
  if (!fullTreeCache) {
    fullTreeCache = await fetchBomTree();
  }
  
  const foundNode = findNodeInTree(fullTreeCache, node.id);
  if (foundNode && foundNode.children) {
    node.children = foundNode.children;
  }
}

function findNodeInTree(nodes, id) {
  for (const n of nodes) {
    if (n.id === id) return n;
    if (n.children && n.children.length > 0) {
      const found = findNodeInTree(n.children, id);
      if (found) return found;
    }
  }
  return null;
}

function renderTreeTable() {
  const activeTreeContainer = document.getElementById('tree-container') || treeContainer;
  if (!activeTreeContainer) return;
  activeTreeContainer.innerHTML = '';
  
  if (filteredTree.length === 0) {
    const isFilterActive = disabledCategories.size > 0 || disabledStates.size > 0;
    const isSearchActive = searchQuery.length >= 4 || isExplicitSearch;
    if (!isFilterActive && !isSearchActive && !isDefaultMode) {
      activeTreeContainer.innerHTML = '<div class="loading-spinner">Please apply a filter or search to load BOM.</div>';
    } else {
      activeTreeContainer.innerHTML = '<div class="loading-spinner">No matching parts found.</div>';
    }
    return;
  }

  const fragment = document.createDocumentFragment();
  
  function traverseAndRender(node, level, path) {
    const hasChildren = (node.children && node.children.length > 0) || Boolean(node.has_children);
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
    toggleSpan.textContent = isExpanded ? '▼' : '▶';
    
    if (hasChildren) {
      toggleSpan.addEventListener('click', async (e) => {
        e.stopPropagation();
        if ((!node.children || node.children.length === 0) && node.has_children) {
          toggleSpan.textContent = '⏳';
          try {
            await ensureNodeChildrenLoaded(node);
          } catch (err) {
            toggleSpan.textContent = '▶';
            return;
          }
        }
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
    textSpan.textContent = node.description || '';
    
    const stateName = node.state || 'Unknown';
    const stateColor = STATE_COLORS[stateName] || STATE_COLORS['Unknown'];
    const stateDot = document.createElement('span');
    stateDot.className = 'category-color-dot';
    stateDot.style.backgroundColor = stateColor;
    stateDot.style.flexShrink = '0';
    stateDot.title = `Status: ${stateName === 'Engineerig Use' ? 'Engineering Use' : stateName}`;
    
    descCol.appendChild(toggleSpan);
    descCol.appendChild(stateDot);
    descCol.appendChild(textSpan);
    
    const pnCol = document.createElement('div');
    pnCol.className = 'col-pn';
    
    const pnSpan = document.createElement('span');
    pnSpan.className = 'pn-number';
    pnSpan.textContent = node.part_number || '';
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
  
  activeTreeContainer.appendChild(fragment);
}

function highlightText(text, query) {
  if (!text) return '';
  if (!query) return text;
  
  const escapedQuery = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
  const regex = new RegExp(`(${escapedQuery})`, 'gi');
  return text.replace(regex, '<mark>$1</mark>');
}



function showToast(message, type = 'success', progress = null) {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return null;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconHtml = '✓';
  if (type === 'error') iconHtml = '✗';
  else if (type === 'loading') iconHtml = '<span class="toast-hourglass">⏳</span>';

  let progressBarHtml = '';
  if (type === 'loading') {
    const isIndeterminate = progress === null || progress === undefined;
    const progressWidth = isIndeterminate ? 30 : Math.min(100, Math.max(0, progress));
    const barClass = isIndeterminate ? 'toast-progress-bar indeterminate' : 'toast-progress-bar';
    progressBarHtml = `
      <div class="toast-progress-track">
        <div class="${barClass}" style="width: ${progressWidth}%;"></div>
      </div>
    `;
  }
  
  toast.innerHTML = `
    <span class="toast-icon">${iconHtml}</span>
    <span class="toast-text">${message}</span>
    ${progressBarHtml}
  `;
  toastContainer.appendChild(toast);
  
  const textSpan = toast.querySelector('.toast-text');
  const progressBar = toast.querySelector('.toast-progress-bar');
  
  let timeoutId = null;
  if (type !== 'loading') {
    timeoutId = setTimeout(() => {
      toast.remove();
    }, 4000);
  }
  
  const toastHandle = {
    element: toast,
    updateProgress(percent, newText) {
      if (newText && textSpan) {
        textSpan.textContent = newText;
      }
      if (progressBar) {
        if (percent === null || percent === undefined) {
          progressBar.classList.add('indeterminate');
          progressBar.style.width = '30%';
        } else {
          progressBar.classList.remove('indeterminate');
          const clamped = Math.min(100, Math.max(0, percent));
          progressBar.style.width = `${clamped}%`;
        }
      }
    },
    dismiss() {
      if (timeoutId) clearTimeout(timeoutId);
      toast.remove();
    },
    complete(finalMessage) {
      this.updateProgress(100, finalMessage || 'Done');
      setTimeout(() => {
        this.dismiss();
      }, 600);
    }
  };

  return toastHandle;
}

function showLoadingToast(message, initialProgress = null) {
  return showToast(message, 'loading', initialProgress);
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
    
    const pnA = a.part_number || '';
    const pnB = b.part_number || '';
    if (!pnA) return 1;
    if (!pnB) return -1;
    return pnA.localeCompare(pnB, undefined, { numeric: true });
  });
}

function renderDrawerCategories() {
  const container = document.getElementById('categories-filter-list');
  if (!container) return;
  container.innerHTML = '';
  
  const categoriesList = [];
  Object.entries(categoryRules).forEach(([prefix, rule]) => {
    if (rule.name) {
      categoriesList.push({
        prefix: prefix,
        name: rule.name,
        displayName: `${prefix} - ${rule.name}`,
        color: rule.color || '#8e9095'
      });
    }
  });
  
  // Add Unknown category
  categoriesList.push({
    prefix: '999',
    name: 'Unknown',
    displayName: 'Unknown',
    color: '#8e9095'
  });
  
  const sortedCategories = categoriesList.sort((a, b) => a.prefix.localeCompare(b.prefix, undefined, { numeric: true }));
  
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
      sortedCategories.forEach(cat => {
        disabledCategories.add(cat.name);
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
  
  sortedCategories.forEach(({ name, displayName, color }) => {
    const isEnabled = !disabledCategories.has(name);
    
    const itemEl = document.createElement('div');
    itemEl.className = 'category-filter-item';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'category-filter-checkbox';
    checkbox.checked = isEnabled;
    checkbox.id = `filter-cat-${name.replace(/\s+/g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'category-filter-label';
    label.htmlFor = checkbox.id;
    
    const colorDot = document.createElement('span');
    colorDot.className = 'category-color-dot';
    colorDot.style.backgroundColor = color;
    
    const nameText = document.createTextNode(displayName);
    
    label.appendChild(colorDot);
    label.appendChild(nameText);
    
    itemEl.appendChild(checkbox);
    itemEl.appendChild(label);
    
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        disabledCategories.delete(name);
      } else {
        disabledCategories.add(name);
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

let STATE_COLORS = {
  "Production Use": "#00FF00",
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

function renderDrawerStructural() {
  const container = document.getElementById('structural-filter-list');
  if (!container) return;
  container.innerHTML = '';

  const options = [
    { label: 'Has Children', key: 'filterHasChildren', getter: () => filterHasChildren, setter: v => { filterHasChildren = v; } },
    { label: 'Has Parents',  key: 'filterHasParents',  getter: () => filterHasParents,  setter: v => { filterHasParents = v; } }
  ];

  options.forEach(({ label, getter, setter }) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'structural-filter-item';
    wrapper.style.cssText = 'display:flex; align-items:center; gap:0.6rem; padding:0.35rem 0;';

    const labelEl = document.createElement('span');
    labelEl.className = 'category-filter-label';
    labelEl.style.minWidth = '9rem';
    labelEl.textContent = label + ':';

    const btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display:flex; gap:0.3rem;';

    const toggleStates = [
      { value: null,  text: 'Any' },
      { value: true,  text: 'Yes' },
      { value: false, text: 'No'  }
    ];

    function refresh() {
      const cur = getter();
      Array.from(btnGroup.children).forEach((btn, i) => {
        btn.classList.toggle('active', toggleStates[i].value === cur);
      });
    }

    toggleStates.forEach(({ value, text }) => {
      const btn = document.createElement('button');
      btn.className = 'btn btn-xs btn-secondary';
      btn.style.cssText = 'padding:0.2rem 0.55rem; font-size:0.75rem; border-radius:0.35rem;';
      btn.textContent = text;
      btn.addEventListener('click', () => {
        setter(value);
        refresh();
        updateFilterBadge();
        if (isDefaultMode) {
          filteredTree = applyStructuralFilter(rawTree);
          renderTreeTable();
          renderBatchButton();
        } else {
          applyFilterAndRender();
        }
      });
      btnGroup.appendChild(btn);
    });

    refresh();
    wrapper.appendChild(labelEl);
    wrapper.appendChild(btnGroup);
    container.appendChild(wrapper);
  });
}

function updateFilterBadge() {
  const badge = document.getElementById('filter-badge');
  const btnFilterElement = document.getElementById('btn-filter');
  if (!badge || !btnFilterElement) return;
  
  const structuralCount = (filterHasParents !== null ? 1 : 0) + (filterHasChildren !== null ? 1 : 0);
  const count = disabledCategories.size + disabledStates.size + structuralCount;
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
      imgCard.style.cursor = 'pointer';
      imgCard.innerHTML = `<img src="${img.url}" alt="Item image" />`;
      
      imgCard.addEventListener('click', () => {
        openGalleryOverlay(index);
      });
      
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

function openGalleryOverlay(index) {
  if (currentImages.length === 0) return;
  currentGalleryIndex = index;
  const overlay = document.getElementById('gallery-overlay');
  const img = document.getElementById('gallery-overlay-img');
  if (!overlay || !img) return;
  
  img.src = currentImages[currentGalleryIndex].url;
  overlay.style.display = 'flex';
  overlay.offsetHeight;
  overlay.classList.add('open');
}

function closeGalleryOverlay() {
  const overlay = document.getElementById('gallery-overlay');
  if (!overlay) return;
  overlay.classList.remove('open');
  setTimeout(() => { overlay.style.display = 'none'; }, 300);
}

function navigateGallery(direction) {
  if (currentImages.length === 0) return;
  currentGalleryIndex = (currentGalleryIndex + direction + currentImages.length) % currentImages.length;
  const img = document.getElementById('gallery-overlay-img');
  if (img) {
    img.src = currentImages[currentGalleryIndex].url;
  }
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

async function ensureRulesLoaded() {
  if (Object.keys(categoryRules).length > 0) return;
  try {
    const rules = await fetchRules();
    categoryRules = rules || {};
  } catch (err) {
    console.error("Failed to load category rules:", err);
  }
}


function renderItemRelations(item) {
  const containedContainer = document.getElementById('contained-items-list');
  const containingContainer = document.getElementById('containing-items-list');
  
  if (containedContainer) {
    containedContainer.innerHTML = '';
    const containedList = item.contained_items || [];
    if (containedList.length === 0) {
      containedContainer.innerHTML = '<div style="color: var(--text-secondary); font-style: italic; text-align: center; padding: 1rem 0;">No contained items</div>';
    } else {
      containedList.forEach(rel => {
        containedContainer.appendChild(createRelationRowElement(rel));
      });
    }
  }
  
  if (containingContainer) {
    containingContainer.innerHTML = '';
    const containingList = item.containing_items || [];
    if (containingList.length === 0) {
      containingContainer.innerHTML = '<div style="color: var(--text-secondary); font-style: italic; text-align: center; padding: 1rem 0;">No parent assemblies contain this item</div>';
    } else {
      containingList.forEach(rel => {
        containingContainer.appendChild(createRelationRowElement(rel));
      });
    }
  }
}

function createRelationRowElement(rel) {
  const rowEl = document.createElement('div');
  rowEl.className = 'tree-row';
  rowEl.style.position = 'relative';
  rowEl.style.overflow = 'hidden';
  rowEl.style.display = 'block';
  
  const menuEl = document.createElement('div');
  menuEl.className = 'row-action-menu';
  
  const goBtn = document.createElement('button');
  goBtn.className = 'row-menu-btn enabled';
  goBtn.innerHTML = '<i class="fa-solid fa-up-right-from-square"></i>';
  goBtn.title = 'Go to Item';
  goBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    navigateToItem(rel.id);
  });
  
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'row-menu-btn enabled';
  deleteBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
  deleteBtn.title = 'Sever Assembly Relation';
  deleteBtn.style.color = 'var(--color-danger)';
  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    handleSeverRelation(rel.edge_id);
  });
  
  const editBtn = document.createElement('button');
  editBtn.className = 'row-menu-btn enabled';
  editBtn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i>';
  editBtn.title = 'Edit Assembly Properties';
  editBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    openAssemblyModal({
      edgeId: rel.edge_id,
      parentId: rel.parent_id,
      childId: rel.child_id,
      quantity: rel.quantity,
      length: rel.length,
      pcb_symbol: rel.pcb_symbol
    });
  });
  
  menuEl.appendChild(goBtn);
  menuEl.appendChild(editBtn);
  menuEl.appendChild(deleteBtn);
  rowEl.appendChild(menuEl);
  
  const contentWrapper = document.createElement('div');
  contentWrapper.className = 'row-content-wrapper';
  contentWrapper.style.gridTemplateColumns = '2fr 1.5fr 1fr';
  contentWrapper.style.padding = '0.75rem 1rem';
  
  const descCol = document.createElement('div');
  descCol.className = 'col-desc';
  descCol.style.fontWeight = '500';
  descCol.textContent = rel.description || 'Unknown description';
  
  const pnCol = document.createElement('div');
  pnCol.className = 'col-pn';
  
  const pnSpan = document.createElement('span');
  pnSpan.className = 'pn-number';
  pnSpan.textContent = rel.part_number;
  pnCol.appendChild(pnSpan);
  
  if (rel.revision) {
    const revTag = document.createElement('span');
    revTag.className = 'revision-tag active';
    revTag.style.fontSize = '0.65rem';
    revTag.style.padding = '0.05rem 0.25rem';
    revTag.style.marginLeft = '0.5rem';
    revTag.textContent = rel.revision;
    pnCol.appendChild(revTag);
  }
  
  const qtyCol = document.createElement('div');
  qtyCol.className = 'col-qty';
  qtyCol.style.textAlign = 'right';
  qtyCol.style.color = 'var(--color-gold)';
  qtyCol.style.fontSize = '0.85rem';
  qtyCol.textContent = rel.amount_label || '';
  
  contentWrapper.appendChild(descCol);
  contentWrapper.appendChild(pnCol);
  contentWrapper.appendChild(qtyCol);
  rowEl.appendChild(contentWrapper);
  
  rowEl.addEventListener('click', (e) => {
    if (e.target.closest('.row-menu-btn')) return;
    
    const isCurrentlyOpen = rowEl.classList.contains('menu-open');
    
    const container = rowEl.closest('.relations-list-container');
    if (container) {
      container.querySelectorAll('.tree-row.menu-open').forEach(r => {
        if (r !== rowEl) r.classList.remove('menu-open');
      });
    }
    
    if (isCurrentlyOpen) {
      rowEl.classList.remove('menu-open');
    } else {
      rowEl.classList.add('menu-open');
    }
  });
  
  rowEl.addEventListener('dblclick', (e) => {
    if (e.target.closest('.row-menu-btn')) return;
    navigateToItem(rel.id);
  });
  
  return rowEl;
}

async function handleSeverRelation(edgeId) {
  if (!confirm("Are you sure you want to sever this assembly relation?")) {
    return;
  }
  
  try {
    showToast('Severing relation...');
    await deleteAssembly(edgeId);
    showToast('Assembly relation severed.');
    if (currentItemId) {
      await showItemPage(currentItemId);
    }
  } catch (err) {
    showToast(`Failed to sever relation: ${err.message}`, 'error');
  }
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

  const addTag = document.createElement('a');
  addTag.className = 'revision-tag';
  addTag.textContent = '+ Add';
  addTag.title = 'Add New Revision';
  addTag.style.cursor = 'pointer';
  addTag.addEventListener('click', async (e) => {
    e.preventDefault();
    if (isBusy) return;
    const restoreTag = setButtonLoading(addTag, '⏳');
    isBusy = true;
    document.body.classList.add('ui-busy');
    try {
      showToast('Creating new revision...');
      const newItem = await addItemRevision(currentItem.id);
      showToast(`Revision ${newItem.Revision || ''} created!`);
      allItems = [];
      navigateToItem(newItem.id);
    } catch (err) {
      showToast(`Failed to create revision: ${err.message}`, 'error');
      restoreTag();
    } finally {
      isBusy = false;
      document.body.classList.remove('ui-busy');
    }
  });
  revisionTagsContainer.appendChild(addTag);
}

// Create Item Dialog Logic
async function openCreateItemModal() {
  if (!createItemModal) return;
  if (createItemDescription) createItemDescription.value = '';
  
  await ensureRulesLoaded();
  
  if (createItemCategory) {
    createItemCategory.innerHTML = '';
    const categories = Object.entries(categoryRules)
      .map(([prefix, rule]) => ({ prefix, name: rule.name || 'Unknown' }))
      .sort((a, b) => a.prefix.localeCompare(b.prefix, undefined, { numeric: true }));
      
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

  await withBusy(btnConfirmCreateItem, async () => {
    try {
      const newItem = await createItem(prefix, description);
      showToast('Item created successfully!');
      closeCreateItemModal();
      window.location.hash = `#/item/${newItem.id}`;
    } catch (err) {
      showToast(`Failed to create item: ${err.message}`, 'error');
    }
  }, '<i class="fa-solid fa-spinner fa-spin"></i> Creating...');
}

async function openDuplicateItemModal() {
  if (!duplicateItemModal) return;
  if (!currentItemId) return;

  await ensureRulesLoaded();

  // Prefill fields
  const sourcePartNumber = itemPartNumber ? itemPartNumber.textContent.trim() : '';
  const sourcePrefix = sourcePartNumber ? sourcePartNumber.substring(0, 2) : '';
  const sourceDesc = inputDescription ? inputDescription.value.trim() : '';

  if (duplicateItemDescription) {
    duplicateItemDescription.value = sourceDesc ? `${sourceDesc} - copy` : '';
  }

  if (duplicateItemCategory) {
    duplicateItemCategory.innerHTML = '';
    const categories = Object.entries(categoryRules)
      .map(([prefix, rule]) => ({ prefix, name: rule.name || 'Unknown' }))
      .sort((a, b) => a.prefix.localeCompare(b.prefix, undefined, { numeric: true }));
      
    categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat.prefix;
      opt.textContent = `${cat.prefix} - ${cat.name}`;
      if (cat.prefix === sourcePrefix) {
        opt.selected = true;
      }
      duplicateItemCategory.appendChild(opt);
    });
  }

  if (duplicateOptParents) duplicateOptParents.checked = true;
  if (duplicateOptChildren) duplicateOptChildren.checked = true;
  if (duplicateOptInstructions) duplicateOptInstructions.checked = true;
  if (duplicateOptPhotos) duplicateOptPhotos.checked = true;

  if (btnConfirmDuplicateItem) btnConfirmDuplicateItem.disabled = false;

  duplicateItemModal.style.display = 'flex';
  duplicateItemModal.offsetHeight;
  duplicateItemModal.classList.add('open');
  if (duplicateItemDescription) duplicateItemDescription.focus();
}

function closeDuplicateItemModal() {
  if (!duplicateItemModal) return;
  duplicateItemModal.classList.remove('open');
  setTimeout(() => { duplicateItemModal.style.display = 'none'; }, 300);
}

async function handleConfirmDuplicateItem() {
  if (!duplicateItemCategory || !duplicateItemDescription || !currentItemId) return;
  const prefix = duplicateItemCategory.value;
  const description = duplicateItemDescription.value.trim();

  if (!description) {
    showToast('Description is required.', 'error');
    if (duplicateItemDescription) duplicateItemDescription.focus();
    return;
  }

  const options = {
    duplicate_parents: duplicateOptParents ? duplicateOptParents.checked : true,
    duplicate_children: duplicateOptChildren ? duplicateOptChildren.checked : true,
    duplicate_instructions: duplicateOptInstructions ? duplicateOptInstructions.checked : true,
    duplicate_photos: duplicateOptPhotos ? duplicateOptPhotos.checked : true
  };

  await withBusy(btnConfirmDuplicateItem, async () => {
    try {
      const newItem = await duplicateItem(currentItemId, prefix, description, options);
      showToast('Item duplicated successfully!');
      closeDuplicateItemModal();
      window.location.hash = `#/item/${newItem.id}`;
    } catch (err) {
      showToast(`Failed to duplicate item: ${err.message}`, 'error');
    }
  }, '<i class="fa-solid fa-spinner fa-spin"></i> Duplicating...');
}

// Recategorize Item Dialog Logic
async function openRecategorizeModal() {
  const modal = document.getElementById('recategorize-modal');
  if (!modal) return;

  await Promise.all([
    ensureRulesLoaded(),
    ensureAllItemsLoaded()
  ]);

  const catSelect = document.getElementById('recategorize-category');
  if (catSelect) {
    catSelect.innerHTML = '';
    const categories = Object.entries(categoryRules)
      .map(([prefix, rule]) => ({ prefix, name: rule.name || 'Unknown' }))
      .sort((a, b) => a.prefix.localeCompare(b.prefix, undefined, { numeric: true }));

    categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat.prefix;
      opt.textContent = `${cat.prefix} - ${cat.name}`;
      catSelect.appendChild(opt);
    });
  }

  const preview = document.getElementById('recategorize-preview');
  if (preview) preview.style.display = 'none';

  modal.style.display = 'flex';
  modal.offsetHeight;
  modal.classList.add('open');

  updateRecategorizePreview();
}

function updateRecategorizePreview() {
  const catSelect = document.getElementById('recategorize-category');
  const preview = document.getElementById('recategorize-preview');
  const newPnEl = document.getElementById('recategorize-new-pn');
  if (!catSelect || !preview || !newPnEl) return;

  const newPrefix = catSelect.value;
  if (!newPrefix || !allItems.length) {
    preview.style.display = 'none';
    return;
  }

  const prefixDash = `${newPrefix}-`;
  const existingSuffixes = allItems
    .map(item => item['Part Number'] || '')
    .filter(pn => pn.startsWith(prefixDash))
    .map(pn => {
      const suffix = pn.slice(prefixDash.length);
      return /^\d+$/.test(suffix) ? parseInt(suffix, 10) : -1;
    })
    .filter(n => n >= 0);

  const nextNum = existingSuffixes.length > 0 ? Math.max(...existingSuffixes) + 1 : 0;
  const previewPn = `${newPrefix}-${String(nextNum).padStart(5, '0')}`;
  newPnEl.textContent = previewPn;
  preview.style.display = 'block';
}

async function handleConfirmRecategorize() {
  const catSelect = document.getElementById('recategorize-category');
  const btn = document.getElementById('btn-confirm-recategorize');
  if (!catSelect || !currentItemId) return;

  const newPrefix = catSelect.value;
  if (!newPrefix) {
    showToast('Please select a new category.', 'error');
    return;
  }

  await withBusy(btn, async () => {
    try {
      showToast('Recategorizing item, please wait...');
      const result = await recategorizeItem(currentItemId, newPrefix);
      showToast(`Item recategorized as ${result['Part Number']}!`);

      const modal = document.getElementById('recategorize-modal');
      if (modal) {
        modal.classList.remove('open');
        setTimeout(() => { modal.style.display = 'none'; }, 300);
      }

      allItems = [];
      window.location.hash = `#/item/${result.id}`;
    } catch (err) {
      showToast(`Recategorize failed: ${err.message}`, 'error');
    }
  }, '<i class="fa-solid fa-spinner fa-spin"></i> Recategorizing...');
}

// Unified Assembly Modal Logic
function openAssemblyModal(options = {}) {
  // Re-evaluate modal and sub-element variables dynamically to support legacy fallback modes
  assemblyModal = document.getElementById('assembly-modal') || 
                  (options.edgeId ? document.getElementById('edit-assembly-modal') : document.getElementById('add-child-modal'));
  btnCloseAssembly = document.getElementById('btn-close-assembly') || 
                     (options.edgeId ? document.getElementById('btn-close-edit-assembly') : document.getElementById('btn-close-add-child'));
  btnCancelAssembly = document.getElementById('btn-cancel-assembly') || 
                      (options.edgeId ? document.getElementById('btn-cancel-edit-assembly') : document.getElementById('btn-cancel-add-child'));
  btnConfirmAssembly = document.getElementById('btn-confirm-assembly') || 
                       (options.edgeId ? document.getElementById('btn-save-edit-assembly') : document.getElementById('btn-confirm-add-child'));
  btnDeleteAssemblyRelation = document.getElementById('btn-delete-assembly-relation') || document.getElementById('btn-delete-assembly');
  
  assemblyModalTitle = document.getElementById('assembly-modal-title');
  assemblyParentColumn = document.getElementById('assembly-parent-column');
  assemblyParentSearchWrapper = document.getElementById('assembly-parent-search-wrapper');
  assemblyParentSearch = document.getElementById('assembly-parent-search');
  assemblyParentList = document.getElementById('assembly-parent-list');
  selectedParentSection = document.getElementById('selected-parent-section');
  selectedParentImageBox = document.getElementById('selected-parent-image-box');
  selectedParentPn = document.getElementById('selected-parent-pn');
  selectedParentDesc = document.getElementById('selected-parent-desc');
  selectedParentRevisions = document.getElementById('selected-parent-revisions');

  assemblyChildColumn = document.getElementById('assembly-child-column');
  assemblyChildSearchWrapper = document.getElementById('assembly-child-search-wrapper');
  assemblyChildSearch = document.getElementById('assembly-child-search') || document.getElementById('add-child-search');
  assemblyChildList = document.getElementById('assembly-child-list') || document.getElementById('add-child-list');
  selectedChildSection = document.getElementById('selected-child-section') || document.getElementById('add-child-form');
  selectedChildImageBox = document.getElementById('selected-child-image-box');
  selectedChildPn = document.getElementById('selected-child-pn') || document.getElementById('selected-child-name');
  selectedChildDesc = document.getElementById('selected-child-desc') || document.getElementById('edit-assembly-item-name');
  selectedChildRevisions = document.getElementById('selected-child-revisions') || document.getElementById('add-child-revision-tags');

  assemblyQuantity = document.getElementById('assembly-quantity') || 
                     (options.edgeId ? document.getElementById('edit-assembly-quantity') : document.getElementById('add-child-quantity'));
  assemblyLength = document.getElementById('assembly-length') || 
                   (options.edgeId ? document.getElementById('edit-assembly-length') : document.getElementById('add-child-length'));
  assemblyPcb = document.getElementById('assembly-pcb') || 
                (options.edgeId ? document.getElementById('edit-assembly-pcb') : document.getElementById('add-child-pcb'));

  // Legacy variables for test compatibility
  addChildModal = assemblyModal;
  btnCloseAddChild = btnCloseAssembly;
  addChildSearch = assemblyChildSearch;
  addChildList = assemblyChildList;
  addChildForm = selectedChildSection;
  selectedChildName = selectedChildPn;
  addChildRevisionTags = selectedChildRevisions;
  addChildQuantity = assemblyQuantity;
  addChildLength = assemblyLength;
  addChildPcb = assemblyPcb;
  btnCancelAddChild = btnCancelAssembly;
  btnConfirmAddChild = btnConfirmAssembly;

  editAssemblyModal = assemblyModal;
  btnCloseEditAssembly = btnCloseAssembly;
  editAssemblyItemName = selectedChildDesc;
  editAssemblyQuantity = assemblyQuantity;
  editAssemblyLength = assemblyLength;
  editAssemblyPcb = assemblyPcb;
  btnDeleteAssembly = btnDeleteAssemblyRelation;
  btnCancelEditAssembly = btnCancelAssembly;
  btnSaveEditAssembly = btnConfirmAssembly;

  if (!assemblyModal) return;

  assemblySelectedParentId = options.parentId || null;
  assemblySelectedChildId = options.childId || null;
  assemblyLockedParent = !!options.parentId;
  assemblyLockedChild = !!options.childId;
  
  if (options.edgeId) {
    assemblyMode = 'edit';
    assemblyEdgeId = options.edgeId;
    assemblyLockedParent = true;
    assemblyLockedChild = true;
    
    if (assemblyModalTitle) assemblyModalTitle.textContent = "Edit Assembly Properties";
    if (btnDeleteAssemblyRelation) btnDeleteAssemblyRelation.style.display = 'block';
    
    if (assemblyQuantity) assemblyQuantity.value = options.quantity !== null && options.quantity !== undefined ? options.quantity : 1;
    if (assemblyLength) assemblyLength.value = options.length !== null && options.length !== undefined ? options.length : 0;
    if (assemblyPcb) assemblyPcb.value = options.pcb_symbol || '';
    
    if (options.node) {
      if (!assemblySelectedParentId) assemblySelectedParentId = options.node.parent_id;
      if (!assemblySelectedChildId) assemblySelectedChildId = options.node.id;
    }
  } else {
    assemblyMode = 'create';
    assemblyEdgeId = null;
    
    if (assemblyModalTitle) assemblyModalTitle.textContent = "Add Assembly Relation";
    if (btnDeleteAssemblyRelation) btnDeleteAssemblyRelation.style.display = 'none';
    
    if (assemblyQuantity) assemblyQuantity.value = 1;
    if (assemblyLength) assemblyLength.value = 0;
    if (assemblyPcb) assemblyPcb.value = '';
  }

  if (assemblyParentSearch) {
    assemblyParentSearch.value = '';
    if (assemblyParentList) {
      assemblyParentList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a parent item...</div>';
    }
  }

  if (assemblyChildSearch) {
    assemblyChildSearch.value = '';
    if (assemblyChildList) {
      assemblyChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a child item...</div>';
    }
  }

  // Open modal synchronously
  assemblyModal.style.display = 'flex';
  assemblyModal.offsetHeight;
  assemblyModal.classList.add('open');

  updateSelectedParentDisplay();
  updateSelectedChildDisplay();
  checkAssemblyConfirmState();

  // Load items data asynchronously in the background
  ensureAllItemsLoaded().then(() => {
    updateSelectedParentDisplay();
    updateSelectedChildDisplay();
    checkAssemblyConfirmState();
    if (!assemblyLockedParent && assemblyParentSearch) {
      assemblyParentSearch.focus();
    } else if (!assemblyLockedChild && assemblyChildSearch) {
      assemblyChildSearch.focus();
    }
  });
}

function closeAssemblyModal() {
  if (!assemblyModal) return;
  assemblyModal.classList.remove('open');
  setTimeout(() => { assemblyModal.style.display = 'none'; }, 300);
}

function updateSelectedParentDisplay() {
  if (!selectedParentSection) return;
  if (!assemblySelectedParentId) {
    selectedParentSection.style.display = 'none';
    if (assemblyParentSearchWrapper) assemblyParentSearchWrapper.style.display = 'flex';
    return;
  }

  const parentItem = allItems.find(item => item.id === assemblySelectedParentId);
  if (!parentItem) {
    selectedParentSection.style.display = 'none';
    if (assemblyParentSearchWrapper) assemblyParentSearchWrapper.style.display = 'flex';
    return;
  }

  selectedParentSection.style.display = 'flex';
  if (assemblyParentSearchWrapper) assemblyParentSearchWrapper.style.display = 'none';
  
  const btnChange = document.getElementById('btn-change-parent');
  if (btnChange) {
    btnChange.style.display = assemblyLockedParent ? 'none' : 'flex';
  }
  
  const parentTitleEl = document.getElementById('selected-parent-title');
  if (parentTitleEl) {
    parentTitleEl.innerHTML = 'Selected Parent' + (assemblyLockedParent ? ' <i class="fa-solid fa-lock" style="margin-left: 0.35rem; color: var(--color-gold-bright); font-size: 0.8rem;" title="Locked"></i>' : '');
  }
  
  const legacyParentNameEl = document.getElementById('selected-parent-name');
  if (legacyParentNameEl) {
    legacyParentNameEl.textContent = `${parentItem["Part Number"]} - ${parentItem["Item description"] || 'No description'}`;
  }
  
  if (selectedParentPn && selectedParentPn !== legacyParentNameEl) selectedParentPn.textContent = parentItem["Part Number"] || 'N/A';
  if (selectedParentDesc) {
    selectedParentDesc.textContent = parentItem["Item description"] || 'No description';
    selectedParentDesc.title = parentItem["Item description"] || 'No description';
  }

  if (selectedParentImageBox) {
    selectedParentImageBox.innerHTML = '';
    const images = parentItem["Image"] || [];
    if (images.length > 0) {
      const img = document.createElement('img');
      img.src = images[0].url;
      img.style.width = '100%';
      img.style.height = '100%';
      img.style.objectFit = 'cover';
      selectedParentImageBox.appendChild(img);
    } else {
      selectedParentImageBox.innerHTML = '<span style="font-size: 1.25rem;">📦</span>';
    }
  }

  if (selectedParentRevisions) {
    selectedParentRevisions.innerHTML = '';
    const revs = getRevisionsForPN(parentItem["Part Number"]);
    if (revs.length > 0) {
      revs.forEach(revItem => {
        const tag = document.createElement('span');
        tag.className = 'revision-tag';
        tag.textContent = revItem.revision || 'N/A';
        if (revItem.id === assemblySelectedParentId) {
          tag.classList.add('active');
        }
        tag.style.cursor = 'pointer';
        tag.addEventListener('click', (e) => {
          e.stopPropagation();
          assemblySelectedParentId = revItem.id;
          updateSelectedParentDisplay();
          checkAssemblyConfirmState();
        });
        selectedParentRevisions.appendChild(tag);
      });
      const wrapper = document.getElementById('selected-parent-revisions-wrapper');
      if (wrapper) wrapper.style.display = 'flex';
    } else {
      const wrapper = document.getElementById('selected-parent-revisions-wrapper');
      if (wrapper) wrapper.style.display = 'none';
    }
  }
}

function updateSelectedChildDisplay() {
  if (!selectedChildSection) return;
  if (!assemblySelectedChildId) {
    selectedChildSection.style.display = 'none';
    if (assemblyChildSearchWrapper) assemblyChildSearchWrapper.style.display = 'flex';
    return;
  }

  const childItem = allItems.find(item => item.id === assemblySelectedChildId);
  if (!childItem) {
    selectedChildSection.style.display = 'none';
    if (assemblyChildSearchWrapper) assemblyChildSearchWrapper.style.display = 'flex';
    return;
  }

  selectedChildSection.style.display = 'flex';
  if (assemblyChildSearchWrapper) assemblyChildSearchWrapper.style.display = 'none';
  
  const btnChange = document.getElementById('btn-change-child');
  if (btnChange) {
    btnChange.style.display = assemblyLockedChild ? 'none' : 'flex';
  }
  
  const childTitleEl = document.getElementById('selected-child-title');
  if (childTitleEl) {
    childTitleEl.innerHTML = 'Selected Child' + (assemblyLockedChild ? ' <i class="fa-solid fa-lock" style="margin-left: 0.35rem; color: var(--color-gold-bright); font-size: 0.8rem;" title="Locked"></i>' : '');
  }
  
  const legacyNameEl = document.getElementById('selected-child-name');
  if (legacyNameEl) {
    legacyNameEl.textContent = `${childItem["Part Number"]} - ${childItem["Item description"] || 'No description'}`;
  }
  
  if (selectedChildPn && selectedChildPn !== legacyNameEl) selectedChildPn.textContent = childItem["Part Number"] || 'N/A';
  if (selectedChildDesc) {
    selectedChildDesc.textContent = childItem["Item description"] || 'No description';
    selectedChildDesc.title = childItem["Item description"] || 'No description';
  }

  if (selectedChildImageBox) {
    selectedChildImageBox.innerHTML = '';
    const images = childItem["Image"] || [];
    if (images.length > 0) {
      const img = document.createElement('img');
      img.src = images[0].url;
      img.style.width = '100%';
      img.style.height = '100%';
      img.style.objectFit = 'cover';
      selectedChildImageBox.appendChild(img);
    } else {
      selectedChildImageBox.innerHTML = '<span style="font-size: 1.25rem;">📦</span>';
    }
  }

  if (selectedChildRevisions) {
    selectedChildRevisions.innerHTML = '';
    const revs = getRevisionsForPN(childItem["Part Number"]);
    if (revs.length > 0) {
      revs.forEach(revItem => {
        const tag = document.createElement('span');
        tag.className = 'revision-tag';
        tag.textContent = revItem.revision || 'N/A';
        if (revItem.id === assemblySelectedChildId) {
          tag.classList.add('active');
        }
        tag.style.cursor = 'pointer';
        tag.addEventListener('click', (e) => {
          e.stopPropagation();
          assemblySelectedChildId = revItem.id;
          updateSelectedChildDisplay();
          checkAssemblyConfirmState();
        });
        selectedChildRevisions.appendChild(tag);
      });
      const wrapper = document.getElementById('selected-child-revisions-wrapper');
      if (wrapper) wrapper.style.display = 'flex';
    } else {
      const wrapper = document.getElementById('selected-child-revisions-wrapper');
      if (wrapper) wrapper.style.display = 'none';
    }
  }
}

function checkAssemblyConfirmState() {
  if (btnConfirmAssembly) {
    btnConfirmAssembly.disabled = !(assemblySelectedParentId && assemblySelectedChildId);
  }
}

function isItemEolOrDeprecated(item) {
  if (!item) return false;
  const stateObj = item["State"] !== undefined ? item["State"] : item.state;
  let stateStr = '';
  if (stateObj) {
    if (Array.isArray(stateObj)) {
      stateStr = (stateObj[0] && stateObj[0].value) ? stateObj[0].value : (typeof stateObj[0] === 'string' ? stateObj[0] : '');
    } else if (typeof stateObj === 'object') {
      stateStr = stateObj.value || '';
    } else {
      stateStr = String(stateObj);
    }
  }
  const s = stateStr.trim().toLowerCase();
  if (!s) return false;
  return (
    s.includes('eol') ||
    s.includes('discard') ||
    s.includes('do not use') ||
    s.includes('use up') ||
    s.includes('finish stock')
  );
}

function renderAssemblyParentList() {
  if (!assemblyParentList) return;
  assemblyParentList.innerHTML = '';
  const query = assemblyParentSearch ? assemblyParentSearch.value.toLowerCase().trim() : '';
  if (!query) {
    assemblyParentList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a parent item...</div>';
    return;
  }

  const matches = allItems.filter(item => {
    if (item.id === assemblySelectedChildId) return false;
    return itemMatchesQuery(item, query, 'all');
  });

  if (matches.length === 0) {
    assemblyParentList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">No matching items found.</div>';
    return;
  }

  const uniqueItems = [];
  const pnsSeen = new Set();
  matches.forEach(item => {
    if (item["Part Number"] && !pnsSeen.has(item["Part Number"])) {
      pnsSeen.add(item["Part Number"]);
      const latest = getLatestRevisionId(item["Part Number"], item.id);
      const latestItem = allItems.find(i => i.id === latest) || item;
      uniqueItems.push(latestItem);
    }
  });

  uniqueItems.forEach(item => {
    const isEol = isItemEolOrDeprecated(item);
    const row = document.createElement('div');
    row.className = `add-related-item-row${isEol ? ' is-eol' : ''}`;
    row.style.cursor = 'pointer';
    
    let pnStyle = 'font-weight: 500; font-family: monospace;';
    let descStyle = 'font-size: 0.8rem; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;';
    if (isEol) {
      pnStyle += ' color: #ef4444;';
      descStyle = 'font-size: 0.8rem; color: rgba(239, 68, 68, 0.85); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;';
    }

    const stateObj = item["State"] !== undefined ? item["State"] : item.state;
    let displayState = '';
    if (stateObj) {
      if (Array.isArray(stateObj)) displayState = (stateObj[0] && stateObj[0].value) ? stateObj[0].value : (typeof stateObj[0] === 'string' ? stateObj[0] : '');
      else if (typeof stateObj === 'object') displayState = stateObj.value || '';
      else displayState = String(stateObj);
    }
    const eolTag = isEol && displayState ? `<span class="badge badge-eol-warning">${displayState}</span>` : '';

    row.innerHTML = `
      <div class="row-pn" style="${pnStyle}">${item["Part Number"]}${eolTag}</div>
      <div class="row-desc" style="${descStyle}">${item["Item description"] || 'No description'}</div>
    `;
    row.addEventListener('click', () => {
      assemblySelectedParentId = item.id;
      updateSelectedParentDisplay();
      checkAssemblyConfirmState();
    });
    assemblyParentList.appendChild(row);
  });
}

function renderAssemblyChildList() {
  if (!assemblyChildList) return;
  assemblyChildList.innerHTML = '';
  const query = assemblyChildSearch ? assemblyChildSearch.value.toLowerCase().trim() : '';
  if (!query) {
    assemblyChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">Type to search for a child item...</div>';
    return;
  }

  const matches = allItems.filter(item => {
    if (item.id === assemblySelectedParentId) return false;
    return itemMatchesQuery(item, query, 'all');
  });

  if (matches.length === 0) {
    assemblyChildList.innerHTML = '<div class="tab-description" style="margin: 0; font-style: italic; text-align: center;">No matching items found.</div>';
    return;
  }

  const uniqueItems = [];
  const pnsSeen = new Set();
  matches.forEach(item => {
    if (item["Part Number"] && !pnsSeen.has(item["Part Number"])) {
      pnsSeen.add(item["Part Number"]);
      const latest = getLatestRevisionId(item["Part Number"], item.id);
      const latestItem = allItems.find(i => i.id === latest) || item;
      uniqueItems.push(latestItem);
    }
  });

  uniqueItems.forEach(item => {
    const isEol = isItemEolOrDeprecated(item);
    const row = document.createElement('div');
    row.className = `add-related-item-row${isEol ? ' is-eol' : ''}`;
    row.style.cursor = 'pointer';
    
    let pnStyle = 'font-weight: 500; font-family: monospace;';
    let descStyle = 'font-size: 0.8rem; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;';
    if (isEol) {
      pnStyle += ' color: #ef4444;';
      descStyle = 'font-size: 0.8rem; color: rgba(239, 68, 68, 0.85); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;';
    }

    const stateObj = item["State"] !== undefined ? item["State"] : item.state;
    let displayState = '';
    if (stateObj) {
      if (Array.isArray(stateObj)) displayState = (stateObj[0] && stateObj[0].value) ? stateObj[0].value : (typeof stateObj[0] === 'string' ? stateObj[0] : '');
      else if (typeof stateObj === 'object') displayState = stateObj.value || '';
      else displayState = String(stateObj);
    }
    const eolTag = isEol && displayState ? `<span class="badge badge-eol-warning">${displayState}</span>` : '';

    row.innerHTML = `
      <div class="row-pn" style="${pnStyle}">${item["Part Number"]}${eolTag}</div>
      <div class="row-desc" style="${descStyle}">${item["Item description"] || 'No description'}</div>
    `;
    row.addEventListener('click', () => {
      assemblySelectedChildId = item.id;
      updateSelectedChildDisplay();
      checkAssemblyConfirmState();
    });
    assemblyChildList.appendChild(row);
  });
}

async function handleConfirmAssembly() {
  if (assemblyMode !== 'edit') {
    if (!assemblySelectedParentId || !assemblySelectedChildId) return;
  }

  const qty = parseInt(assemblyQuantity ? assemblyQuantity.value : 1) || 1;
  const len = parseFloat(assemblyLength ? assemblyLength.value : 0) || 0;
  const pcb = assemblyPcb ? assemblyPcb.value.trim() : '';

  try {
    if (btnConfirmAssembly) {
      btnConfirmAssembly.disabled = true;
      btnConfirmAssembly.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
    }

    if (assemblyMode === 'edit') {
      await updateAssembly(assemblyEdgeId, qty, len, pcb, assemblySelectedParentId, assemblySelectedChildId);
      showToast('Assembly properties saved.');
    } else {
      await createAssembly(assemblySelectedParentId, assemblySelectedChildId, qty, len, pcb);
      showToast('Assembly updated successfully.');
    }

    closeAssemblyModal();
    await refreshData();
    if (assemblyInstructionsView && assemblyInstructionsView.style.display !== 'none' && currentInstructionParentId) {
      await renderInstructionSetDetailsView();
    } else if (currentItemId) {
      await showItemPage(currentItemId);
    }
  } catch (err) {
    showToast(`Failed to save: ${err.message}`, 'error');
  } finally {
    if (btnConfirmAssembly) {
      btnConfirmAssembly.disabled = false;
      btnConfirmAssembly.innerHTML = 'Save';
    }
  }
}

async function handleDeleteAssemblyRelation() {
  if (!assemblyEdgeId) return;
  
  if (!confirm("Are you sure you want to remove this item from the assembly relation?")) {
    return;
  }
  
  try {
    showToast('Removing from assembly...');
    if (btnDeleteAssemblyRelation) btnDeleteAssemblyRelation.disabled = true;
    
    await deleteAssembly(assemblyEdgeId);
    
    showToast('Item removed from assembly.');
    closeAssemblyModal();
    await refreshData();
    if (currentItemId) {
      await showItemPage(currentItemId);
    }
  } catch (err) {
    showToast(`Failed to remove: ${err.message}`, 'error');
  } finally {
    if (btnDeleteAssemblyRelation) {
      btnDeleteAssemblyRelation.disabled = false;
    }
  }
}

// Legacy wrappers for test and backward compatibility
function openAddChildModal(parentId) {
  openAssemblyModal({ parentId });
}
function closeAddChildModal() {
  closeAssemblyModal();
}
function renderAddChildList() {
  renderAssemblyChildList();
}
function selectChildItem(item) {
  assemblySelectedChildId = item.id;
  updateSelectedChildDisplay();
  checkAssemblyConfirmState();
}
function handleConfirmAddChild() {
  handleConfirmAssembly();
}
function openEditAssemblyModal(node) {
  openAssemblyModal({
    edgeId: node.edge_id,
    parentId: node.parent_id,
    childId: node.id,
    quantity: node.quantity,
    length: node.length,
    pcb_symbol: node.pcb_symbol,
    node: node
  });
}
function closeEditAssemblyModal() {
  closeAssemblyModal();
}
function handleSaveEditAssembly() {
  handleConfirmAssembly();
}
function handleDeleteAssembly() {
  handleDeleteAssemblyRelation();
}

function getFullPn(item) {
  if (!item) return '';
  if (item["Full PN"]) return item["Full PN"];
  const pn = item["Part Number"] || item["part_number"] || item["pn_number"] || '';
  const rev = item["Revision"] || item["revision"] || '';
  if (rev) {
    if (pn.includes('Rev.')) return pn;
    return `${pn} Rev.${rev}`;
  }
  return pn;
}

function insertTextAtCursor(textarea, text) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const val = textarea.value;
  textarea.value = val.substring(0, start) + text + val.substring(end);
  textarea.selectionStart = textarea.selectionEnd = start + text.length;
  textarea.focus();
  textarea.dispatchEvent(new Event('input'));
}

function evaluateInstructionText(template, options = {}) {
  let str = template;

  let partSlots = options.partSlots;
  let toolSlots = options.toolSlots;
  const action = options.action;

  // Fallback to legacy single arguments if slots are not provided
  if (!partSlots) {
    if (options.childNames && options.childNames.length > 0) {
      partSlots = options.childNames.map(name => {
        return { id: 1, quantity: 1, toll: true, part_number: '', description: name };
      });
    } else if (options.childName) {
      const qtyVal = parseInt(options.qty, 10) || 1;
      partSlots = [{ id: 1, quantity: qtyVal, toll: true, part_number: '', description: options.childName }];
    } else {
      partSlots = [];
    }
  }

  if (!toolSlots) {
    if (options.toolName) {
      toolSlots = [{ id: 1, quantity: 1, part_number: '', description: options.toolName }];
    } else {
      toolSlots = [];
    }
  }

  const formatSlot = (slot) => {
    if (!slot || slot.id === null || slot.id === undefined) return null;
    const qty = slot.quantity || 1;
    const prefix = (qty > 1) ? `${qty}x ` : '';
    const desc = slot.description || 'No description';
    let pn = slot.full_pn || slot.part_number || slot.pn || '';
    const rev = slot.revision || slot.rev || '';
    if (pn) {
      if (rev && !pn.includes('Rev.')) {
        pn = `${pn} Rev.${rev}`;
      }
      return `${prefix}"${desc}" (${pn})`;
    }
    return `${prefix}${desc}`;
  };

  const filledParts = partSlots.map(formatSlot).filter(Boolean);
  const filledTools = toolSlots.map(formatSlot).filter(Boolean);

  const defaultPart = filledParts.length > 0 ? filledParts.join(', ') : '[Action Item A]';
  const defaultTool = filledTools.length > 0 ? filledTools.join(', ') : '[Tool]';

  if (!str) {
    let base = `${action || 'Assemble'} ${defaultPart}`;
    if (filledTools.length > 0) base += ` using ${defaultTool}`;
    return base;
  }

  for (let i = 0; i < 20; i++) {
    const token = `{a.${i + 1}}`;
    if (str.includes(token)) {
      const slot = partSlots[i];
      const val = slot ? (formatSlot(slot) || `[Empty Slot ${token}]`) : `[Slot ${token} not found]`;
      str = str.replaceAll(token, val);
    }
  }

  for (let i = 0; i < 20; i++) {
    const token = `{t.${i + 1}}`;
    if (str.includes(token)) {
      const slot = toolSlots[i];
      const val = slot ? (formatSlot(slot) || `[Empty Slot ${token}]`) : `[Slot ${token} not found]`;
      str = str.replaceAll(token, val);
    }
  }

  return str.replaceAll('{action}', action || 'Assemble');
}

function updateStepTextPreview() {
  if (!stepTextPreview) return;
  const tpl = stepInputDescription ? stepInputDescription.value : '';
  const action = stepInputAction ? stepInputAction.value.trim() : '';

  const preview = evaluateInstructionText(tpl, { 
    partSlots: currentActionItems, 
    toolSlots: currentToolSlots, 
    action 
  });
  stepTextPreview.textContent = preview;
}

async function loadInstructionSetsForItem(parentId) {
  if (!instructionSetsList) return;
  instructionSetsList.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem;">Loading instruction sets...</div>';
  try {
    const sets = await fetchInstructionSets(parentId);
    if (!sets || sets.length === 0) {
      instructionSetsList.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.6rem; background: rgba(0,0,0,0.3); border: 1px dashed var(--card-border);">
          <span style="color: var(--text-secondary); font-size: 0.85rem;">No instruction sets created yet.</span>
        </div>`;
      return;
    }
    instructionSetsList.innerHTML = '';
    sets.forEach(s => {
      const setRow = document.createElement('div');
      setRow.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0.8rem; background: rgba(0,0,0,0.4); border: 1px solid var(--card-border); border-radius: 4px;';
      
      const isBalanced = s.is_balanced === true;
      const scaleIconHtml = isBalanced
        ? `<i class="fa-solid fa-scale-balanced scale-status-icon" style="color: #4ade80; font-size: 1.1rem; margin-right: 0.6rem;" title="Balanced: all component quantities match the assembly hierarchy"></i>`
        : `<i class="fa-solid fa-scale-unbalanced scale-status-icon" style="color: #f87171; font-size: 1.1rem; margin-right: 0.6rem;" title="Unbalanced: discrepancies exist between instructed items and assembly hierarchy"></i>`;

      setRow.innerHTML = `
        <div style="display: flex; align-items: center;">
          ${scaleIconHtml}
          <div>
            <span style="font-weight: 600; color: var(--color-gold-bright);">Instruction Set #${s.set_index}</span>
            <span style="margin-left: 0.5rem; font-size: 0.8rem; color: var(--text-secondary);">(${s.step_count} step${s.step_count === 1 ? '' : 's'})</span>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm btn-open-set" data-set-index="${s.set_index}"><i class="fa-solid fa-pen-to-square"></i> Open Editor</button>
          <button class="btn btn-primary btn-sm btn-export-set" data-set-index="${s.set_index}"><i class="fa-solid fa-file-word"></i> Export WI</button>
        </div>
      `;
      setRow.querySelector('.btn-open-set').addEventListener('click', () => {
        openAssemblyInstructionsView(parentId, s.set_index);
      });
      setRow.querySelector('.btn-export-set').addEventListener('click', () => {
        openWiExportModal(parentId, s.set_index);
      });
      instructionSetsList.appendChild(setRow);
    });
  } catch (err) {
    instructionSetsList.innerHTML = `<div style="color: var(--color-danger); font-size: 0.85rem;">Failed to load sets: ${err.message}</div>`;
  }
}

async function openAssemblyInstructionsView(parentId, setIndex) {
  currentInstructionParentId = parentId;
  currentInstructionSetIndex = setIndex;

  if (bomExplorerView) bomExplorerView.style.display = 'none';
  if (itemDetailsView) itemDetailsView.style.display = 'none';
  if (assemblyInstructionsView) assemblyInstructionsView.style.display = 'block';
  updateHeaderScrollState();

  if (instructionsSetTitleBadge) instructionsSetTitleBadge.textContent = `Set ${setIndex}`;

  try {
    currentParentItemDetails = await fetchItem(parentId);
  } catch (err) {
    console.error("Failed to preload parent item details", err);
  }

  await ensureAllItemsLoaded();
  const parentItem = allItems.find(i => i.id === parentId);
  if (parentItem) {
    if (instructionsParentPn) instructionsParentPn.textContent = getFullPn(parentItem);
    if (instructionsParentDesc) instructionsParentDesc.textContent = parentItem["Item description"] || '';
  }

  await renderInstructionSetDetailsView();
}

async function renderInstructionSetDetailsView() {
  if (!currentInstructionParentId) return;

  if (instructionsComparisonList) instructionsComparisonList.innerHTML = '<div style="padding: 1rem; color: var(--text-secondary);">Calculating items count comparison...</div>';
  if (instructionStepsContainer) instructionStepsContainer.innerHTML = '<div style="padding: 1rem; color: var(--text-secondary);">Loading steps...</div>';

  try {
    const details = await fetchInstructionSetDetails(currentInstructionParentId, currentInstructionSetIndex);
    currentInstructionSteps = details.steps || [];
    currentInstructionComparison = details.comparison || [];

    if (instructionsComparisonList) {
      if (currentInstructionComparison.length === 0) {
        instructionsComparisonList.innerHTML = '<div style="padding: 1rem; color: var(--text-secondary);">No hierarchy or instructed items for this set.</div>';
      } else {
        instructionsComparisonList.innerHTML = '';

        const allSubAssemblies = details.sub_assemblies || [];

        // Separate direct items from derived sub-assembly items
        const directItems = [];
        const derivedGroups = {}; // parent_id -> { parent_id, parent_pn, parent_description, parent_blackbox, items: [] }

        currentInstructionComparison.forEach(c => {
          // If this item has origins in sub-assemblies, add entries to the sub-assembly groups
          if (c.origins && c.origins.length > 0) {
            c.origins.forEach(o => {
              if (o.is_derived && o.parent_id && o.parent_id !== currentInstructionParentId) {
                if (!derivedGroups[o.parent_id]) {
                  derivedGroups[o.parent_id] = {
                    parent_id: o.parent_id,
                    parent_pn: o.parent_pn || `Sub-assembly #${o.parent_id}`,
                    parent_description: o.parent_description || '',
                    parent_blackbox: o.parent_blackbox || false,
                    items: []
                  };
                }
                derivedGroups[o.parent_id].items.push({
                  ...c,
                  parent_id: o.parent_id,
                  parent_pn: o.parent_pn,
                  parent_description: o.parent_description,
                  parent_blackbox: o.parent_blackbox,
                  edge_id: o.edge_id,
                  unit_qty: o.unit_qty,
                  required_qty: o.total_qty || o.unit_qty,
                  length: o.length,
                  pcb_symbol: o.pcb_symbol,
                  is_derived: true
                });
              }
            });
          } else if (c.is_derived && c.parent_id && c.parent_id !== currentInstructionParentId) {
            if (!derivedGroups[c.parent_id]) {
              derivedGroups[c.parent_id] = {
                parent_id: c.parent_id,
                parent_pn: c.parent_pn || `Sub-assembly #${c.parent_id}`,
                parent_description: c.parent_description || '',
                parent_blackbox: c.parent_blackbox || false,
                items: []
              };
            }
            derivedGroups[c.parent_id].items.push(c);
          }

          // If this item is not in hierarchy, OR has direct requirements under the main parent:
          const hasDirectOrigin = c.origins && c.origins.length > 0
            ? c.origins.some(o => !o.is_derived)
            : !c.is_derived;

          if (!c.in_hierarchy || hasDirectOrigin) {
            directItems.push(c);
          }
        });

        // Helper to render a single comparison row
        const createComparisonRow = (c, isDerived = false) => {
          const row = document.createElement('div');
          row.className = 'tree-table-header comparison-row';
          row.style.cssText = 'grid-template-columns: 2fr 1fr 1fr 1.5fr 1.5fr; border-bottom: 1px solid var(--card-border); align-items: center; font-weight: normal; font-size: 0.9rem; overflow: hidden;';
          
          let badgeClass = 'badge-discrepancy-ok';
          if (c.discrepancy === 'Missing Instruction') badgeClass = 'badge-discrepancy-missing';
          else if (c.discrepancy === 'Under-instructed') badgeClass = 'badge-discrepancy-under';
          else if (c.discrepancy === 'Over-instructed') badgeClass = 'badge-discrepancy-over';
          else if (c.discrepancy === 'Not in Hierarchy') badgeClass = 'badge-discrepancy-notin';

          let quickAction = '';
          if (c.discrepancy === 'Not in Hierarchy') {
            let optionsHtml = `<option value="${currentInstructionParentId}">Direct (Main Assembly)</option>`;
            if (allSubAssemblies && allSubAssemblies.length > 0) {
              allSubAssemblies.forEach(sa => {
                optionsHtml += `<option value="${sa.id}">${sa.part_number}</option>`;
              });
            }
            quickAction = `
              <div style="display: flex; gap: 0.35rem; align-items: center; justify-content: flex-end;">
                <select class="form-input target-parent-select" style="max-width: 140px; padding: 0.2rem 0.4rem; font-size: 0.75rem; height: auto;">
                  ${optionsHtml}
                </select>
                <button class="btn btn-secondary btn-sm btn-quick-link" data-child-id="${c.item_id}" data-qty="${c.instructed_qty}" title="Add to chosen hierarchy"><i class="fa-solid fa-plus"></i> Add</button>
              </div>
            `;
          } else if (isDerived) {
            if (c.discrepancy !== 'OK') {
              quickAction = `<button class="btn btn-secondary btn-sm btn-edit-derived-relation" data-edge-id="${c.edge_id}" title="Edit properties in sub-assembly"><i class="fa-solid fa-pen-to-square"></i> Edit in Sub-assembly</button>`;
            } else {
              quickAction = `<div style="display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem;"><span style="color: #4ade80; font-size: 0.8rem;"><i class="fa-solid fa-check"></i> Balanced</span> <button class="btn btn-secondary btn-sm btn-edit-derived-relation" data-edge-id="${c.edge_id}" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;" title="Edit properties in sub-assembly"><i class="fa-solid fa-pen"></i></button></div>`;
            }
          } else {
            if (c.discrepancy !== 'OK') {
              const derivedQty = Number(c.derived_required_qty || 0);
              const targetDirectQty = Math.max(0, Number(c.instructed_qty) - derivedQty);
              if (targetDirectQty === 0) {
                quickAction = `<button class="btn btn-secondary btn-sm btn-quick-update" data-child-id="${c.item_id}" data-qty="0"><i class="fa-solid fa-trash-can"></i> Remove Dependency</button>`;
              } else {
                quickAction = `<button class="btn btn-secondary btn-sm btn-quick-update" data-child-id="${c.item_id}" data-qty="${targetDirectQty}"><i class="fa-solid fa-pen"></i> Set Hierarchy Qty to ${targetDirectQty}</button>`;
              }
            } else {
              quickAction = `<span style="color: #4ade80; font-size: 0.8rem;"><i class="fa-solid fa-check"></i> Balanced</span>`;
            }
          }

          row.innerHTML = `
            <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: var(--color-gold-bright);">${c.part_number}</strong> <span style="color: var(--text-secondary); margin-left: 0.4rem;" title="${c.description}">${c.description}</span></div>
            <div>${c.required_qty} pcs</div>
            <div>${c.instructed_qty} pcs</div>
            <div><span class="badge ${badgeClass}">${c.discrepancy}</span></div>
            <div style="text-align: right;">${quickAction}</div>
          `;

          const btnLink = row.querySelector('.btn-quick-link');
          if (btnLink) {
            btnLink.addEventListener('click', async () => {
              const selectEl = row.querySelector('.target-parent-select');
              const targetParentId = selectEl ? parseInt(selectEl.value) : currentInstructionParentId;
              await withBusy(btnLink, async () => {
                try {
                  showToast('Adding item to hierarchy...');
                  await createAssembly(targetParentId, c.item_id, c.instructed_qty, 0, 'N/A');
                  showToast('Added to hierarchy!');
                  await renderInstructionSetDetailsView();
                } catch (e) {
                  showToast(e.message, 'error');
                }
              }, '<i class="fa-solid fa-spinner fa-spin"></i>');
            });
          }

          const btnEditDerived = row.querySelector('.btn-edit-derived-relation');
          if (btnEditDerived) {
            btnEditDerived.addEventListener('click', () => {
              openAssemblyModal({
                edgeId: c.edge_id,
                parentId: c.parent_id,
                childId: c.item_id,
                quantity: c.unit_qty,
                length: c.length,
                pcb_symbol: c.pcb_symbol
              });
            });
          }

          const btnUpdate = row.querySelector('.btn-quick-update');
          if (btnUpdate) {
            btnUpdate.addEventListener('click', async () => {
              await withBusy(btnUpdate, async () => {
                try {
                  const bomItem = await fetchItem(currentInstructionParentId);
                  const rel = (bomItem.contained_items || []).find(r => r.child_id === c.item_id);
                  const derivedQty = Number(c.derived_required_qty || 0);
                  const targetDirectQty = Math.max(0, Number(c.instructed_qty) - derivedQty);

                  if (rel) {
                    if (targetDirectQty === 0) {
                      showToast('Removing dependency from hierarchy...');
                      await deleteAssembly(rel.edge_id);
                      showToast('Dependency removed!');
                    } else {
                      showToast('Updating hierarchy quantity...');
                      await updateAssembly(rel.edge_id, targetDirectQty, rel.length, rel.pcb_symbol, currentInstructionParentId, c.item_id);
                      showToast('Hierarchy quantity updated!');
                    }
                  } else {
                    if (targetDirectQty > 0) {
                      await createAssembly(currentInstructionParentId, c.item_id, targetDirectQty, 0, 'N/A');
                      showToast('Hierarchy quantity updated!');
                    }
                  }
                  await renderInstructionSetDetailsView();
                } catch (e) {
                  showToast(e.message, 'error');
                }
              }, '<i class="fa-solid fa-spinner fa-spin"></i>');
            });
          }

          return row;
        };

        // Render direct items
        if (directItems.length > 0) {
          if (Object.keys(derivedGroups).length > 0) {
            const directHeader = document.createElement('div');
            directHeader.className = 'direct-items-header';
            directHeader.style.cssText = 'padding: 0.4rem 0.8rem; background: rgba(255,255,255,0.02); border-bottom: 1px solid var(--card-border); font-size: 0.8rem; font-weight: 600; color: var(--color-gold); display: flex; align-items: center; gap: 0.5rem;';
            directHeader.innerHTML = `<i class="fa-solid fa-folder-tree"></i> Direct Items (${directItems.length})`;
            instructionsComparisonList.appendChild(directHeader);
          }
          directItems.forEach(c => {
            instructionsComparisonList.appendChild(createComparisonRow(c, false));
          });
        }

        // Render derived sub-assembly groups
        for (const [pId, group] of Object.entries(derivedGroups)) {
          const groupContainer = document.createElement('div');
          groupContainer.className = 'subassembly-comparison-group';
          groupContainer.style.cssText = 'margin-top: 0.75rem; border-top: 2px solid var(--card-border); background: rgba(0,0,0,0.15);';

          const groupHeader = document.createElement('div');
          groupHeader.className = 'subassembly-group-header';
          groupHeader.style.cssText = 'display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0.8rem; background: rgba(255,255,255,0.03); border-bottom: 1px solid var(--card-border);';
          
          groupHeader.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.5rem; min-width: 0;">
              <i class="fa-solid fa-layer-group" style="color: var(--color-gold-bright);"></i>
              <span style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary);">Sub-assembly:</span>
              <strong style="color: var(--color-gold-bright);">${group.parent_pn}</strong>
              <span style="font-size: 0.8rem; color: var(--text-secondary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${group.parent_description || ''}</span>
              <span class="badge" style="font-size: 0.75rem; background: rgba(197, 160, 89, 0.15); color: var(--color-gold);">${group.items.length} derived item${group.items.length === 1 ? '' : 's'}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm btn-toggle-blackbox" data-parent-id="${group.parent_id}" title="Toggle Blackbox flag on this sub-assembly">
                <i class="fa-solid fa-cube"></i> Set Blackbox
              </button>
            </div>
          `;

          const btnBlackbox = groupHeader.querySelector('.btn-toggle-blackbox');
          if (btnBlackbox) {
            btnBlackbox.addEventListener('click', () => {
              const newBlackboxState = !group.parent_blackbox;
              const actionText = newBlackboxState ? "enable Blackbox" : "disable Blackbox";
              showConfirmModal(
                "Toggle Blackbox Flag",
                `Are you sure you want to ${actionText} on "${group.parent_pn}"? This will ${newBlackboxState ? 'collapse its sub-components into a single requirement' : 'expand its sub-components'} in this comparison.`,
                `<div style="font-size: 0.9rem; color: var(--text-secondary);"><strong>${group.parent_pn}</strong><br>${group.parent_description || ''}</div>`,
                async () => {
                  try {
                    showToast(`Updating Blackbox flag for ${group.parent_pn}...`);
                    await updateItem(group.parent_id, { "Blackbox": newBlackboxState });
                    showToast(`Blackbox flag ${newBlackboxState ? 'enabled' : 'disabled'}!`);
                    await renderInstructionSetDetailsView();
                  } catch (err) {
                    showToast(`Failed to update Blackbox: ${err.message}`, 'error');
                  }
                }
              );
            });
          }

          groupContainer.appendChild(groupHeader);

          group.items.forEach(c => {
            groupContainer.appendChild(createComparisonRow(c, true));
          });

          instructionsComparisonList.appendChild(groupContainer);
        }
      }
    }

    if (instructionStepsContainer) {
      if (currentInstructionSteps.length === 0) {
        instructionStepsContainer.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: var(--text-secondary); border: 1px dashed var(--card-border);">No instruction steps in this set yet. Click "+ Add Step" to create the first step.</div>';
      } else {
        instructionStepsContainer.innerHTML = '';

        // Add the top-most divider (index 0)
        const topDivider = document.createElement('div');
        topDivider.className = 'add-step-divider-wrapper';
        topDivider.innerHTML = `
          <button class="btn btn-secondary btn-sm btn-insert-step" data-index="0">
            <i class="fa-solid fa-plus"></i> Insert Step Here
          </button>
        `;
        topDivider.querySelector('.btn-insert-step').addEventListener('click', () => {
          openInstructionStepModal(null, 0);
        });
        instructionStepsContainer.appendChild(topDivider);

        currentInstructionSteps.forEach((step, idx) => {
          const card = document.createElement('div');
          card.className = 'instruction-step-card';

          if (!step.part_slots) {
            const childItems = step.child_items && step.child_items.length > 0
              ? step.child_items
              : (step.child_item ? [step.child_item] : []);
            step.part_slots = childItems.map(c => ({
              id: c.id,
              part_number: c.part_number,
              description: c.description || '',
              toll: step.toll !== false,
              quantity: c.quantity || step.quantity || 1
            }));
          }
          if (!step.tool_slots) {
            step.tool_slots = step.tool ? [{
              id: step.tool.id,
              part_number: step.tool.part_number,
              description: step.tool.description || '',
              quantity: 1
            }] : [];
          }

          const filledPartSlots = (step.part_slots || []).filter(s => s.id !== null && s.id !== undefined);
          const childPn = filledPartSlots.map(c => {
            const qty = c.quantity || 1;
            return qty > 1 ? `${qty}x ${c.part_number}` : c.part_number;
          }).join(', ') || 'None';

          const filledToolSlots = (step.tool_slots || []).filter(s => s.id !== null && s.id !== undefined);
          const toolPn = filledToolSlots.map(t => {
            const qty = t.quantity || 1;
            return qty > 1 ? `${qty}x ${t.part_number}` : t.part_number;
          }).join(', ') || '';

          const recPn = step.receiving_item ? step.receiving_item.part_number : 'Parent';

          const evalText = evaluateInstructionText(step.description, {
            partSlots: step.part_slots,
            toolSlots: step.tool_slots,
            action: step.action,
            qty: step.quantity,
            receivingName: step.receiving_item ? (step.receiving_item.description ? `"${step.receiving_item.description}" (${step.receiving_item.part_number})` : step.receiving_item.part_number) : ''
          });

          const allPrep = filledPartSlots.length > 0 && filledPartSlots.every(c => c.toll === false);
          const anyPrep = filledPartSlots.length > 0 && filledPartSlots.some(c => c.toll === false) && !allPrep;

          let tollBadgeHtml = '';
          if (allPrep) {
            tollBadgeHtml = '<span class="badge" style="background: rgba(239,68,68,0.15); border: 1px solid rgb(239,68,68); color: rgb(239,68,68);"><i class="fa-solid fa-ban"></i> Prep Only</span>';
          } else if (anyPrep) {
            tollBadgeHtml = '<span class="badge" style="background: rgba(234,179,8,0.15); border: 1px solid rgb(234,179,8); color: rgb(234,179,8);"><i class="fa-solid fa-triangle-exclamation"></i> Mixed Toll</span>';
          }

          let photoHtml = '';
          if (step.photo && step.photo.length > 0) {
            photoHtml = '<div style="margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 0.5rem;">';
            step.photo.forEach(p => {
              photoHtml += `<img src="${p.url}" style="max-height: 120px; border-radius: 4px; border: 1px solid var(--card-border);" alt="Step Photo"/>`;
            });
            photoHtml += '</div>';
          }

          card.innerHTML = `
            <div class="step-card-header">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <span class="step-drag-handle" title="Step ${idx + 1}"><i class="fa-solid fa-grip-vertical"></i></span>
                <span style="font-weight: 700; font-size: 1.1rem; color: var(--color-gold-bright);">Step ${idx + 1}</span>
                <div class="step-card-badges">
                  <span class="badge" style="background: rgba(197,160,89,0.15); border: 1px solid var(--color-gold); color: var(--color-gold);">${step.action || 'Action'}</span>
                  <span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-primary);"><i class="fa-solid fa-cube"></i> ${childPn}</span>
                  ${step.receiving_item ? `<span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-secondary);"><i class="fa-solid fa-arrow-right"></i> onto ${recPn}</span>` : ''}
                  ${toolPn ? `<span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-secondary);"><i class="fa-solid fa-wrench"></i> ${toolPn}</span>` : ''}
                  ${tollBadgeHtml}
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 0.4rem;">
                <button class="btn btn-secondary btn-sm btn-move-up" title="Move Up" ${idx === 0 ? 'disabled' : ''}><i class="fa-solid fa-arrow-up"></i></button>
                <button class="btn btn-secondary btn-sm btn-move-down" title="Move Down" ${idx === currentInstructionSteps.length - 1 ? 'disabled' : ''}><i class="fa-solid fa-arrow-down"></i></button>
                <button class="btn btn-secondary btn-sm btn-edit-step" title="Edit Step"><i class="fa-solid fa-pen"></i> Edit</button>
                <button class="btn btn-secondary btn-sm btn-duplicate-step" title="Duplicate Step"><i class="fa-solid fa-copy"></i> Duplicate</button>
                <button class="btn btn-danger btn-sm btn-delete-step" title="Delete Step"><i class="fa-solid fa-trash"></i></button>
              </div>
            </div>
            <div style="font-size: 0.95rem; color: var(--text-primary); line-height: 1.5; background: rgba(0,0,0,0.3); padding: 0.75rem; border-radius: 4px; border-left: 3px solid var(--color-gold-bright); white-space: pre-wrap; word-break: break-word;">
              ${evalText}
            </div>
            ${photoHtml}
          `;

          card.querySelector('.btn-edit-step').addEventListener('click', () => openInstructionStepModal(step));

          const btnDuplicateStep = card.querySelector('.btn-duplicate-step');
          btnDuplicateStep?.addEventListener('click', async () => {
            await withBusy(btnDuplicateStep, async () => {
              try {
                showToast('Duplicating step...');
                const payload = {
                  action: step.action,
                  child_item_ids: filledPartSlots.map(c => c.id),
                  tool_ids: (step.tool_slots || []).map(t => t.id).filter(id => id !== null && id !== undefined),
                  receiving_item_id: step.receiving_item ? step.receiving_item.id : null,
                  description: step.description,
                  toll_map: step.toll_map,
                  tool_map: step.tool_map,
                  photo: step.photo || []
                };
                
                const newStep = await createInstructionStep(currentInstructionParentId, currentInstructionSetIndex, payload);
                const stepIds = currentInstructionSteps.map(s => s.id);
                stepIds.splice(idx + 1, 0, newStep.id);
                await reorderInstructionSteps(currentInstructionParentId, currentInstructionSetIndex, stepIds);
                await renderInstructionSetDetailsView();
                showToast('Step duplicated!');
              } catch (e) {
                showToast(e.message, 'error');
              }
            }, '<i class="fa-solid fa-spinner fa-spin"></i>');
          });

          const btnDeleteStep = card.querySelector('.btn-delete-step');
          btnDeleteStep.addEventListener('click', () => {
            showConfirmModal(
              'Delete Step',
              'Are you sure you want to delete this instruction step?',
              '',
              async () => {
                const restoreDelete = setButtonLoading(btnDeleteStep, '<i class="fa-solid fa-spinner fa-spin"></i>');
                try {
                  showToast('Deleting step...');
                  await deleteInstructionStep(step.id);
                  await renderInstructionSetDetailsView();
                } catch (e) {
                  showToast(e.message, 'error');
                  restoreDelete();
                }
              }
            );
          });

          const btnMoveUp = card.querySelector('.btn-move-up');
          btnMoveUp?.addEventListener('click', async () => {
            if (idx === 0) return;
            await withBusy(btnMoveUp, async () => {
              const newOrder = [...currentInstructionSteps];
              const temp = newOrder[idx];
              newOrder[idx] = newOrder[idx - 1];
              newOrder[idx - 1] = temp;
              showToast('Reordering steps...');
              await reorderInstructionSteps(currentInstructionParentId, currentInstructionSetIndex, newOrder.map(s => s.id));
              await renderInstructionSetDetailsView();
            }, '<i class="fa-solid fa-spinner fa-spin"></i>');
          });

          const btnMoveDown = card.querySelector('.btn-move-down');
          btnMoveDown?.addEventListener('click', async () => {
            if (idx === currentInstructionSteps.length - 1) return;
            await withBusy(btnMoveDown, async () => {
              const newOrder = [...currentInstructionSteps];
              const temp = newOrder[idx];
              newOrder[idx] = newOrder[idx + 1];
              newOrder[idx + 1] = temp;
              showToast('Reordering steps...');
              await reorderInstructionSteps(currentInstructionParentId, currentInstructionSetIndex, newOrder.map(s => s.id));
              await renderInstructionSetDetailsView();
            }, '<i class="fa-solid fa-spinner fa-spin"></i>');
          });

          instructionStepsContainer.appendChild(card);

          // Add a divider after this step (index idx + 1)
          const divider = document.createElement('div');
          divider.className = 'add-step-divider-wrapper';
          divider.innerHTML = `
            <button class="btn btn-secondary btn-sm btn-insert-step" data-index="${idx + 1}">
              <i class="fa-solid fa-plus"></i> Insert Step Here
            </button>
          `;
          divider.querySelector('.btn-insert-step').addEventListener('click', () => {
            openInstructionStepModal(null, idx + 1);
          });
          instructionStepsContainer.appendChild(divider);
        });
      }
    }
  } catch (err) {
    showToast(`Error rendering instructions: ${err.message}`, 'error');
  }
}

function renderActionItemsList() {
  const container = document.getElementById('action-items-list-container');
  if (!container) return;
  container.innerHTML = '';
  
  if (currentActionItems.length === 0) {
    container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center; padding: 0.5rem; width: 100%;">No action item slots. Click "+ Add Slot".</div>';
    return;
  }
  
  currentActionItems.forEach((slot, idx) => {
    const row = document.createElement('div');
    row.className = 'action-item-row';
    row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.4rem 0.6rem; background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 4px; overflow: hidden;';
    
    // Slot label
    const label = document.createElement('div');
    label.style.cssText = 'font-size: 0.82rem; flex: 1; min-width: 0; display: flex; align-items: center; gap: 0.5rem;';
    
    const indexBadge = document.createElement('span');
    indexBadge.style.cssText = 'font-weight: 700; color: var(--color-gold-bright); flex-shrink: 0;';
    indexBadge.textContent = `{a.${idx + 1}}`;
    
    const details = document.createElement('span');
    details.style.cssText = 'color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;';
    
    if (slot.id !== null && slot.id !== undefined) {
      details.textContent = `${slot.part_number} - ${slot.description || 'No description'}`;
      details.title = details.textContent;
    } else {
      details.textContent = 'Empty Slot';
      details.style.color = 'var(--text-secondary)';
      details.style.fontStyle = 'italic';
    }
    
    label.appendChild(indexBadge);
    label.appendChild(details);
    
    // Control buttons and inputs
    const controls = document.createElement('div');
    controls.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0;';
    
    // Insert token button
    const insertBtn = document.createElement('button');
    insertBtn.type = 'button';
    insertBtn.className = 'btn btn-secondary btn-xs';
    insertBtn.style.cssText = 'font-size: 0.7rem; padding: 0.1rem 0.35rem;';
    insertBtn.textContent = `Insert`;
    insertBtn.addEventListener('click', (e) => {
      e.preventDefault();
      insertTextAtCursor(stepInputDescription, `{a.${idx + 1}}`);
      updateStepTextPreview();
    });
    controls.appendChild(insertBtn);

    if (slot.id !== null && slot.id !== undefined) {
      // Qty Input
      const qtyWrapper = document.createElement('div');
      qtyWrapper.style.cssText = 'display: flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; color: var(--text-secondary);';
      
      const qtyInput = document.createElement('input');
      qtyInput.type = 'number';
      qtyInput.min = '1';
      qtyInput.value = slot.quantity || 1;
      qtyInput.style.cssText = 'width: 3rem; height: 1.5rem; border-radius: 4px; border: 1px solid var(--card-border); background: rgba(0,0,0,0.2); color: var(--text-primary); text-align: center; font-size: 0.75rem;';
      qtyInput.addEventListener('input', () => {
        let val = parseInt(qtyInput.value, 10);
        if (isNaN(val) || val < 1) val = 1;
        slot.quantity = val;
        updateStepTextPreview();
      });
      qtyWrapper.appendChild(document.createTextNode('Qty:'));
      qtyWrapper.appendChild(qtyInput);
      controls.appendChild(qtyWrapper);

      // Toll Checkbox
      const tollLabel = document.createElement('label');
      tollLabel.style.cssText = 'display: flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; color: var(--text-secondary); cursor: pointer; user-select: none; margin: 0;';
      
      const tollCheckbox = document.createElement('input');
      tollCheckbox.type = 'checkbox';
      tollCheckbox.checked = slot.toll !== false;
      tollCheckbox.style.cssText = 'width: 0.95rem; height: 0.95rem; cursor: pointer;';
      tollCheckbox.addEventListener('change', () => {
        slot.toll = tollCheckbox.checked;
        updateStepTextPreview();
      });
      tollLabel.appendChild(tollCheckbox);
      tollLabel.appendChild(document.createTextNode('Toll'));
      controls.appendChild(tollLabel);

      // Clear button (make slot empty)
      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'btn btn-secondary btn-xs';
      clearBtn.title = 'Clear Part';
      clearBtn.innerHTML = '<i class="fa-solid fa-eraser"></i>';
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        slot.id = null;
        slot.part_number = null;
        slot.description = null;
        renderActionItemsList();
        updateStepTextPreview();
      });
      controls.appendChild(clearBtn);
    } else {
      // Choose Part button
      const chooseBtn = document.createElement('button');
      chooseBtn.type = 'button';
      chooseBtn.className = 'btn btn-primary btn-xs';
      chooseBtn.textContent = 'Choose Part';
      chooseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openItemPicker(`fill-action-item-slot-${idx}`);
      });
      controls.appendChild(chooseBtn);
    }

    // Rearrange buttons
    const moveUpBtn = document.createElement('button');
    moveUpBtn.type = 'button';
    moveUpBtn.className = 'btn btn-secondary btn-xs';
    moveUpBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
    moveUpBtn.disabled = idx === 0;
    moveUpBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const temp = currentActionItems[idx];
      currentActionItems[idx] = currentActionItems[idx - 1];
      currentActionItems[idx - 1] = temp;
      renderActionItemsList();
      updateStepTextPreview();
    });
    controls.appendChild(moveUpBtn);

    const moveDownBtn = document.createElement('button');
    moveDownBtn.type = 'button';
    moveDownBtn.className = 'btn btn-secondary btn-xs';
    moveDownBtn.innerHTML = '<i class="fa-solid fa-arrow-down"></i>';
    moveDownBtn.disabled = idx === currentActionItems.length - 1;
    moveDownBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const temp = currentActionItems[idx];
      currentActionItems[idx] = currentActionItems[idx + 1];
      currentActionItems[idx + 1] = temp;
      renderActionItemsList();
      updateStepTextPreview();
    });
    controls.appendChild(moveDownBtn);

    // Delete Slot button
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'btn btn-danger btn-xs';
    deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
    deleteBtn.addEventListener('click', (e) => {
      e.preventDefault();
      currentActionItems.splice(idx, 1);
      renderActionItemsList();
      updateStepTextPreview();
    });
    controls.appendChild(deleteBtn);
    
    row.appendChild(label);
    row.appendChild(controls);
    container.appendChild(row);
  });
}

function renderToolsList() {
  const container = document.getElementById('tools-list-container');
  if (!container) return;
  container.innerHTML = '';
  
  if (currentToolSlots.length === 0) {
    container.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; text-align: center; padding: 0.5rem; width: 100%;">No tool slots. Click "+ Add Slot".</div>';
    return;
  }
  
  currentToolSlots.forEach((slot, idx) => {
    const row = document.createElement('div');
    row.className = 'tool-item-row';
    row.style.cssText = 'display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.4rem 0.6rem; background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 4px; overflow: hidden;';
    
    // Slot label
    const label = document.createElement('div');
    label.style.cssText = 'font-size: 0.82rem; flex: 1; min-width: 0; display: flex; align-items: center; gap: 0.5rem;';
    
    const indexBadge = document.createElement('span');
    indexBadge.style.cssText = 'font-weight: 700; color: var(--color-gold-bright); flex-shrink: 0;';
    indexBadge.textContent = `{t.${idx + 1}}`;
    
    const details = document.createElement('span');
    details.style.cssText = 'color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;';
    
    if (slot.id !== null && slot.id !== undefined) {
      details.textContent = `${slot.part_number} - ${slot.description || 'No description'}`;
      details.title = details.textContent;
    } else {
      details.textContent = 'Empty Slot';
      details.style.color = 'var(--text-secondary)';
      details.style.fontStyle = 'italic';
    }
    
    label.appendChild(indexBadge);
    label.appendChild(details);
    
    // Control buttons and inputs
    const controls = document.createElement('div');
    controls.style.cssText = 'display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0;';
    
    // Insert token button
    const insertBtn = document.createElement('button');
    insertBtn.type = 'button';
    insertBtn.className = 'btn btn-secondary btn-xs';
    insertBtn.style.cssText = 'font-size: 0.7rem; padding: 0.1rem 0.35rem;';
    insertBtn.textContent = `Insert`;
    insertBtn.addEventListener('click', (e) => {
      e.preventDefault();
      insertTextAtCursor(stepInputDescription, `{t.${idx + 1}}`);
      updateStepTextPreview();
    });
    controls.appendChild(insertBtn);

    if (slot.id !== null && slot.id !== undefined) {
      // Qty Input
      const qtyWrapper = document.createElement('div');
      qtyWrapper.style.cssText = 'display: flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; color: var(--text-secondary);';
      
      const qtyInput = document.createElement('input');
      qtyInput.type = 'number';
      qtyInput.min = '1';
      qtyInput.value = slot.quantity || 1;
      qtyInput.style.cssText = 'width: 3rem; height: 1.5rem; border-radius: 4px; border: 1px solid var(--card-border); background: rgba(0,0,0,0.2); color: var(--text-primary); text-align: center; font-size: 0.75rem;';
      qtyInput.addEventListener('input', () => {
        let val = parseInt(qtyInput.value, 10);
        if (isNaN(val) || val < 1) val = 1;
        slot.quantity = val;
        updateStepTextPreview();
      });
      qtyWrapper.appendChild(document.createTextNode('Qty:'));
      qtyWrapper.appendChild(qtyInput);
      controls.appendChild(qtyWrapper);

      // Clear button (make slot empty)
      const clearBtn = document.createElement('button');
      clearBtn.type = 'button';
      clearBtn.className = 'btn btn-secondary btn-xs';
      clearBtn.title = 'Clear Tool';
      clearBtn.innerHTML = '<i class="fa-solid fa-eraser"></i>';
      clearBtn.addEventListener('click', (e) => {
        e.preventDefault();
        slot.id = null;
        slot.part_number = null;
        slot.description = null;
        renderToolsList();
        updateStepTextPreview();
      });
      controls.appendChild(clearBtn);
    } else {
      // Choose Tool button
      const chooseBtn = document.createElement('button');
      chooseBtn.type = 'button';
      chooseBtn.className = 'btn btn-primary btn-xs';
      chooseBtn.textContent = 'Choose Tool';
      chooseBtn.addEventListener('click', (e) => {
        e.preventDefault();
        openItemPicker(`fill-tool-item-slot-${idx}`);
      });
      controls.appendChild(chooseBtn);
    }

    // Rearrange buttons
    const moveUpBtn = document.createElement('button');
    moveUpBtn.type = 'button';
    moveUpBtn.className = 'btn btn-secondary btn-xs';
    moveUpBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
    moveUpBtn.disabled = idx === 0;
    moveUpBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const temp = currentToolSlots[idx];
      currentToolSlots[idx] = currentToolSlots[idx - 1];
      currentToolSlots[idx - 1] = temp;
      renderToolsList();
      updateStepTextPreview();
    });
    controls.appendChild(moveUpBtn);

    const moveDownBtn = document.createElement('button');
    moveDownBtn.type = 'button';
    moveDownBtn.className = 'btn btn-secondary btn-xs';
    moveDownBtn.innerHTML = '<i class="fa-solid fa-arrow-down"></i>';
    moveDownBtn.disabled = idx === currentToolSlots.length - 1;
    moveDownBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const temp = currentToolSlots[idx];
      currentToolSlots[idx] = currentToolSlots[idx + 1];
      currentToolSlots[idx + 1] = temp;
      renderToolsList();
      updateStepTextPreview();
    });
    controls.appendChild(moveDownBtn);

    // Delete Slot button
    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'btn btn-danger btn-xs';
    deleteBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
    deleteBtn.addEventListener('click', (e) => {
      e.preventDefault();
      currentToolSlots.splice(idx, 1);
      renderToolsList();
      updateStepTextPreview();
    });
    controls.appendChild(deleteBtn);
    
    row.appendChild(label);
    row.appendChild(controls);
    container.appendChild(row);
  });
}

async function openInstructionStepModal(editingStep = null, insertIndex = null) {
  editingStepId = editingStep ? editingStep.id : null;
  insertStepAtIndex = (editingStep === null) ? (insertIndex !== null ? insertIndex : currentInstructionSteps.length) : null;
  stepPhotoUpload = editingStep && editingStep.photo ? [...editingStep.photo] : [];

  if (instructionStepModalTitle) {
    instructionStepModalTitle.textContent = editingStep ? 'Edit Instruction Step' : 'Add Instruction Step';
  }

  // Load prefabs dynamically from the backend settings
  let templates = [];
  try {
    templates = await fetchQuickActionTemplates();
  } catch (e) {
    console.error("Failed to fetch templates, falling back to default", e);
    templates = [
      {"action": "Solder", "template": "{action} {a.1} onto {a.2} using {t.1}"},
      {"action": "Fasten", "template": "{action} {a.1} to {a.2} using {t.1}"},
      {"action": "Mount", "template": "{action} {a.1} onto {a.2}"},
      {"action": "Glue", "template": "{action} {a.1} to {a.2} with {t.1}"},
      {"action": "Inspect", "template": "{action} {a.1} on {a.2}"}
    ];
  }

  const prefabsContainer = document.getElementById('prefabs-container');
  if (prefabsContainer) {
    prefabsContainer.innerHTML = '';
    templates.forEach(t => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'btn btn-secondary btn-sm btn-prefab';
      btn.setAttribute('data-action', t.action);
      btn.setAttribute('data-template', t.template);
      btn.textContent = t.action;
      btn.addEventListener('click', () => {
        if (stepInputAction) stepInputAction.value = t.action;
        if (stepInputDescription) stepInputDescription.value = t.template;
        updateStepTextPreview();
      });
      prefabsContainer.appendChild(btn);
    });
  }

  await ensureAllItemsLoaded();

  if (editingStep) {
    if (stepInputAction) stepInputAction.value = editingStep.action || '';
    if (stepInputDescription) stepInputDescription.value = editingStep.description || '';

    if (editingStep.part_slots && editingStep.part_slots.length > 0) {
      currentActionItems = editingStep.part_slots.map(slot => ({ ...slot }));
    } else {
      let legacyItems = editingStep.child_items && editingStep.child_items.length > 0
        ? editingStep.child_items
        : (editingStep.child_item ? [editingStep.child_item] : []);

      let tollMap = {};
      if (editingStep.toll_map) {
        try {
          tollMap = JSON.parse(editingStep.toll_map);
        } catch (e) {}
      }

      currentActionItems = legacyItems.map(child => {
        let isTolled = true;
        let qtyVal = child.quantity || editingStep.quantity || 1;
        if (tollMap && tollMap[child.id] !== undefined) {
          const entry = tollMap[child.id];
          if (typeof entry === 'object' && entry !== null) {
            isTolled = entry.toll !== false;
            qtyVal = entry.qty !== undefined ? entry.qty : qtyVal;
          } else {
            isTolled = entry !== false;
          }
        } else {
          isTolled = editingStep.toll !== undefined ? editingStep.toll : true;
        }
        return {
          id: child.id,
          part_number: child.part_number,
          description: child.description || '',
          toll: isTolled,
          quantity: qtyVal
        };
      });
    }

    if (editingStep.tool_slots && editingStep.tool_slots.length > 0) {
      currentToolSlots = editingStep.tool_slots.map(slot => ({ ...slot }));
    } else if (editingStep.tool) {
      currentToolSlots = [{
        id: editingStep.tool.id,
        part_number: editingStep.tool.part_number,
        description: editingStep.tool.description || '',
        quantity: 1
      }];
    } else {
      currentToolSlots = [];
    }
  } else {
    if (stepInputAction) stepInputAction.value = 'Assemble';
    if (stepInputDescription) stepInputDescription.value = '{action} {a.1} using {t.1}';
    currentActionItems = [];
    currentToolSlots = [];
  }

  renderActionItemsList();
  renderToolsList();
  renderStepPhotoPreview();
  updateStepTextPreview();

  if (instructionStepModal) {
    instructionStepModal.style.display = 'flex';
    instructionStepModal.classList.add('open');
  }
}

function renderStepPhotoPreview() {
  if (!stepPhotoPreview) return;
  stepPhotoPreview.innerHTML = '';
  if (!stepPhotoUpload || stepPhotoUpload.length === 0) {
    stepPhotoPreview.innerHTML = '<span style="color: var(--text-secondary); font-size: 0.85rem;">No photos attached.</span>';
  } else {
    stepPhotoUpload.forEach((img, idx) => {
      const card = document.createElement('div');
      card.style.cssText = 'position: relative; display: inline-block; width: 60px; height: 60px; border-radius: 4px; border: 1px solid var(--card-border); overflow: hidden;';
      
      const image = document.createElement('img');
      image.src = img.url;
      image.style.cssText = 'width: 100%; height: 100%; object-fit: cover;';
      
      const delBtn = document.createElement('button');
      delBtn.type = 'button';
      delBtn.innerHTML = '<i class="fa-solid fa-trash-can"></i>';
      delBtn.style.cssText = 'position: absolute; top: 2px; right: 2px; background: rgba(0,0,0,0.6); color: var(--color-danger); border: none; border-radius: 3px; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 0.65rem; cursor: pointer; padding: 0;';
      
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showConfirmModal(
          'Remove Photo',
          'Are you sure you want to remove this photo?',
          `<img src="${img.url}" style="max-height: 200px; border-radius: 4px;" alt="Preview" />`,
          () => {
            stepPhotoUpload.splice(idx, 1);
            renderStepPhotoPreview();
            showToast('Photo removed.');
          }
        );
      });
      
      card.appendChild(image);
      card.appendChild(delBtn);
      stepPhotoPreview.appendChild(card);
    });
  }
}

function setPickerValue(targetSelectId, itemId) {
  const selectElem = document.getElementById(targetSelectId);
  const displayElem = document.getElementById(`${targetSelectId}-display`);
  
  if (selectElem) {
    selectElem.value = itemId || '';
    selectElem.dispatchEvent(new Event('change'));
  }
  
  if (displayElem) {
    if (itemId) {
      const item = allItems.find(i => i.id == itemId);
      if (item) {
        const fullPn = getFullPn(item);
        const desc = item["Item description"] || item["Description"] || '';
        displayElem.value = `${fullPn} - ${desc}`;
      } else {
        displayElem.value = `ID: ${itemId}`;
      }
    } else {
      displayElem.value = '';
    }
  }
}

let _pickerSearchDebounceTimer = null;
let _pickerLastSearchResults = [];

function initItemPicker() {
  document.querySelectorAll('.btn-choose-item, .item-display-trigger').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetSelectId = btn.getAttribute('data-target');
      openItemPicker(targetSelectId);
    });
  });

  if (btnAddActionItem) {
    btnAddActionItem.addEventListener('click', (e) => {
      e.preventDefault();
      openItemPicker('add-action-item-slot');
    });
  }

  if (btnAddToolItem) {
    btnAddToolItem.addEventListener('click', (e) => {
      e.preventDefault();
      openItemPicker('add-tool-item-slot');
    });
  }

  if (btnCloseItemPicker) {
    btnCloseItemPicker.addEventListener('click', closeItemPicker);
  }
  if (btnCancelItemPicker) {
    btnCancelItemPicker.addEventListener('click', closeItemPicker);
  }

  if (btnClearItemPicker) {
    btnClearItemPicker.addEventListener('click', (e) => {
      e.preventDefault();
      if (itemPickerTargetSelectId) {
        if (itemPickerTargetSelectId !== 'add-action-item' && 
            itemPickerTargetSelectId !== 'add-action-item-slot' &&
            itemPickerTargetSelectId !== 'add-tool-item-slot') {
          setPickerValue(itemPickerTargetSelectId, null);
        }
      }
      closeItemPicker();
      updateStepTextPreview();
    });
  }

  if (pickerSearchInput) {
    pickerSearchInput.addEventListener('input', () => {
      const query = pickerSearchInput.value.trim();
      clearTimeout(_pickerSearchDebounceTimer);

      if (query.length < 3) {
        _renderPickerPrompt(query.length === 0
          ? 'Type at least 3 characters to search...'
          : `Type ${3 - query.length} more character${3 - query.length > 1 ? 's' : ''}...`);
        return;
      }

      _renderPickerPrompt('Searching Baserow...');
      _pickerSearchDebounceTimer = setTimeout(() => {
        _doPickerSearch(query);
      }, 300);
    });
  }
}

async function openItemPicker(targetSelectId) {
  itemPickerTargetSelectId = targetSelectId;

  if (pickerSearchInput) {
    pickerSearchInput.value = '';
  }

  const pickerChildrenGrid = document.getElementById('picker-children-grid');
  if (pickerChildrenGrid) {
    pickerChildrenGrid.innerHTML = '';
    let availableItems = [];
    if (currentInstructionComparison && currentInstructionComparison.length > 0) {
      availableItems = currentInstructionComparison.filter(c => c.in_hierarchy !== false);
    } else if (currentParentItemDetails && currentParentItemDetails.contained_items) {
      availableItems = currentParentItemDetails.contained_items;
    }

    if (availableItems.length === 0) {
      pickerChildrenGrid.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem; padding: 0.5rem; grid-column: 1 / -1; text-align: center;">No assembly items available.</div>';
    } else {
      availableItems.forEach(child => {
        const card = document.createElement('div');
        card.className = 'picker-child-card';

        const itemId = child.item_id !== undefined ? child.item_id : child.id;
        const fullPn = child.part_number || getFullPn(child) || `Item #${itemId}`;
        const desc = child.description || child["Item description"] || 'No description';

        let imgUrl = child.image_url || '';
        if (!imgUrl) {
          const imgList = child.Image || child.image || [];
          if (Array.isArray(imgList) && imgList.length > 0) {
            imgUrl = imgList[0].url || '';
          }
        }

        card.innerHTML = `
          ${imgUrl ? `<img src="${imgUrl}" alt="${fullPn}" />` : `<div style="width: 100%; height: 60px; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; border-radius: 4px; color: var(--text-secondary); font-size: 1.25rem;"><i class="fa-solid fa-cube"></i></div>`}
          <div class="card-pn" title="${fullPn}">${fullPn}</div>
          <div class="card-desc" title="${desc}">${desc}</div>
        `;

        card.addEventListener('click', () => {
          selectItemInPicker(itemId);
        });

        pickerChildrenGrid.appendChild(card);
      });
    }
  }

  // Show prompt — no automatic full BOM load
  _renderPickerPrompt('Type at least 3 characters to search...');

  if (itemPickerModal) {
    itemPickerModal.style.display = 'flex';
    itemPickerModal.classList.add('open');
    if (pickerSearchInput) pickerSearchInput.focus();
  }
}

function _renderPickerPrompt(message) {
  if (!pickerItemsList) return;
  pickerItemsList.innerHTML = `<div style="color: var(--text-secondary); text-align: center; padding: 0.75rem; font-style: italic; font-size: 0.85rem;">${message}</div>`;
}

async function _doPickerSearch(query) {
  if (!pickerItemsList) return;
  try {
    const items = await searchItems(query, 200);
    _pickerLastSearchResults = items;
    _renderPickerItems(items, query);
  } catch (err) {
    pickerItemsList.innerHTML = `<div style="color: var(--color-danger); text-align: center; padding: 0.5rem; font-size: 0.85rem;">Search failed: ${err.message}</div>`;
  }
}

function _renderPickerItems(items, query = '') {
  if (!pickerItemsList) return;
  pickerItemsList.innerHTML = '';

  if (items.length === 0) {
    pickerItemsList.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 0.5rem;">No matching items found.</div>';
    return;
  }

  items.forEach(item => {
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.justifyContent = 'space-between';
    row.style.alignItems = 'center';
    row.style.padding = '0.4rem 0.6rem';
    row.style.borderBottom = '1px solid var(--card-border)';
    row.style.gap = '0.5rem';

    const textSpan = document.createElement('span');
    textSpan.style.fontSize = '0.85rem';
    textSpan.style.color = 'var(--text-primary)';
    textSpan.style.whiteSpace = 'nowrap';
    textSpan.style.overflow = 'hidden';
    textSpan.style.textOverflow = 'ellipsis';
    textSpan.style.flex = '1';

    const fullPn = getFullPn(item);
    const desc = item["Item description"] || item["Description"] || '';
    textSpan.textContent = `${fullPn} - ${desc}`;
    textSpan.title = textSpan.textContent;

    const selectBtn = document.createElement('button');
    selectBtn.type = 'button';
    selectBtn.className = 'btn btn-primary btn-sm';
    selectBtn.style.padding = '0.2rem 0.5rem';
    selectBtn.textContent = 'Select';
    selectBtn.addEventListener('click', () => {
      selectItemInPicker(item.id);
    });

    row.appendChild(textSpan);
    row.appendChild(selectBtn);
    pickerItemsList.appendChild(row);
  });

  if (items.length >= 200) {
    const note = document.createElement('div');
    note.style.fontSize = '0.75rem';
    note.style.color = 'var(--text-secondary)';
    note.style.textAlign = 'center';
    note.style.padding = '0.3rem';
    note.textContent = 'Showing up to 200 results. Refine your search for more specific results.';
    pickerItemsList.appendChild(note);
  }
}

function closeItemPicker() {
  if (itemPickerModal) {
    itemPickerModal.style.display = 'none';
    itemPickerModal.classList.remove('open');
  }
  clearTimeout(_pickerSearchDebounceTimer);
}

function selectItemInPicker(itemId) {
  if (itemPickerTargetSelectId) {
    const compPool = (currentInstructionComparison || []).map(c => ({
      id: c.item_id !== undefined ? c.item_id : c.id,
      'Part Number': c.part_number,
      'Item description': c.description,
      'Full PN': c.part_number
    }));
    const pool = [...compPool, ...allItems, ..._pickerLastSearchResults];
    const found = pool.find(i => i.id == itemId);
    const itemData = found ? {
      id: found.id,
      part_number: found['Full PN'] || getFullPn(found) || found['Part Number'] || `Item #${found.id}`,
      description: found["Item description"] || found["Description"] || ''
    } : {
      id: itemId,
      part_number: `Item #${itemId}`,
      description: ''
    };

    if (itemPickerTargetSelectId === 'add-action-item' || itemPickerTargetSelectId === 'add-action-item-slot') {
      currentActionItems.push({
        ...itemData,
        toll: true,
        quantity: 1
      });
      renderActionItemsList();
      updateStepTextPreview();
    } else if (itemPickerTargetSelectId.startsWith('fill-action-item-slot-')) {
      const slotIdx = parseInt(itemPickerTargetSelectId.split('-').pop(), 10);
      if (!isNaN(slotIdx) && currentActionItems[slotIdx]) {
        currentActionItems[slotIdx] = {
          ...currentActionItems[slotIdx],
          ...itemData,
          toll: true,
          quantity: 1
        };
        renderActionItemsList();
        updateStepTextPreview();
      }
    } else if (itemPickerTargetSelectId === 'add-tool-item' || itemPickerTargetSelectId === 'add-tool-item-slot') {
      currentToolSlots.push({
        ...itemData,
        quantity: 1
      });
      renderToolsList();
      updateStepTextPreview();
    } else if (itemPickerTargetSelectId.startsWith('fill-tool-item-slot-')) {
      const slotIdx = parseInt(itemPickerTargetSelectId.split('-').pop(), 10);
      if (!isNaN(slotIdx) && currentToolSlots[slotIdx]) {
        currentToolSlots[slotIdx] = {
          ...currentToolSlots[slotIdx],
          ...itemData,
          quantity: 1
        };
        renderToolsList();
        updateStepTextPreview();
      }
    } else {
      if (found) {
        setPickerValue(itemPickerTargetSelectId, found.id);
        const displayElem = document.getElementById(`${itemPickerTargetSelectId}-display`);
        if (displayElem) {
          const fullPn = getFullPn(found);
          const desc = found["Item description"] || found["Description"] || '';
          displayElem.value = desc ? `${fullPn} - ${desc}` : fullPn;
        }
      } else {
        const selectElem = document.getElementById(itemPickerTargetSelectId);
        if (selectElem) {
          selectElem.value = itemId;
          selectElem.dispatchEvent(new Event('change'));
        }
      }
    }
  }
  closeItemPicker();
}

function renderPickerItemsList(query = '') {
  // Legacy shim kept for test compatibility — delegates to the new search-driven flow
  if (query.length >= 3) {
    _doPickerSearch(query);
  } else {
    _renderPickerPrompt(query.length === 0
      ? 'Type at least 3 characters to search...'
      : `Type ${3 - query.length} more character${3 - query.length > 1 ? 's' : ''}...`);
  }
}

function initInstructionEventListeners() {
  initItemPicker();
  if (btnAddInstructionSet) {
    btnAddInstructionSet.addEventListener('click', async () => {
      if (!currentItemId) return;
      await withBusy(btnAddInstructionSet, async () => {
        const sets = await fetchInstructionSets(currentItemId);
        const setIndices = sets.map(s => s.set_index);
        const nextIdx = setIndices.length > 0 ? Math.max(...setIndices) + 1 : 1;
        openAssemblyInstructionsView(currentItemId, nextIdx);
      }, '<i class="fa-solid fa-spinner fa-spin"></i> Loading...');
    });
  }

  if (btnBackFromInstructions) {
    btnBackFromInstructions.addEventListener('click', () => {
      if (assemblyInstructionsView) assemblyInstructionsView.style.display = 'none';
      if (currentItemId) {
        showItemPage(currentItemId);
      } else {
        showExplorerPage();
      }
    });
  }

  if (btnDeleteInstructionSet) {
    btnDeleteInstructionSet.addEventListener('click', () => {
      if (!currentInstructionParentId || !currentInstructionSetIndex) return;
      // Pass '' as previewHtml (3rd arg), async handler as onAccept (4th arg)
      showConfirmModal(
        'Delete Instruction Set',
        `Are you sure you want to delete entire Instruction Set #${currentInstructionSetIndex}?`,
        '',
        async () => {
          const restoreBtn = setButtonLoading(btnDeleteInstructionSet, '<i class="fa-solid fa-spinner fa-spin"></i>');
          try {
            showToast('Deleting instruction set...');
            await deleteInstructionSet(currentInstructionParentId, currentInstructionSetIndex);
            showItemPage(currentInstructionParentId);
          } catch (e) {
            showToast(e.message, 'error');
            restoreBtn();
          }
        }
      );
    });
  }

  if (btnAddStep) {
    btnAddStep.addEventListener('click', () => openInstructionStepModal());
  }

  const closeStepModal = () => {
    if (instructionStepModal) {
      instructionStepModal.style.display = 'none';
      instructionStepModal.classList.remove('open');
    }
  };

  if (btnCloseInstructionStepModal) btnCloseInstructionStepModal.addEventListener('click', closeStepModal);
  if (btnCancelInstructionStep) btnCancelInstructionStep.addEventListener('click', closeStepModal);

  // Handle variables button insertions
  document.querySelectorAll('.btn-var-insert').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const variable = btn.getAttribute('data-var');
      if (stepInputDescription && variable) {
        insertTextAtCursor(stepInputDescription, variable);
        updateStepTextPreview();
      }
    });
  });

  document.querySelectorAll('.btn-prefab').forEach(btn => {
    btn.addEventListener('click', () => {
      const act = btn.getAttribute('data-action');
      const tpl = btn.getAttribute('data-template');
      if (stepInputAction && act) stepInputAction.value = act;
      if (stepInputDescription && tpl) stepInputDescription.value = tpl;
      updateStepTextPreview();
    });
  });

  [stepInputAction, stepInputQty, stepInputTool, stepInputDescription].forEach(input => {
    if (input) {
      input.addEventListener('input', updateStepTextPreview);
      input.addEventListener('change', updateStepTextPreview);
    }
  });

  if (btnUploadStepPhoto && stepInputPhotoFile) {
    btnUploadStepPhoto.addEventListener('click', () => stepInputPhotoFile.click());
    stepInputPhotoFile.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files);
      if (files.length === 0) return;
      try {
        showToast(`Uploading ${files.length} photo(s)...`);
        for (const file of files) {
          const uploaded = await uploadDatasheet(file);
          stepPhotoUpload.push(uploaded);
        }
        renderStepPhotoPreview();
        showToast('Photo(s) uploaded successfully!');
      } catch (err) {
        showToast(err.message, 'error');
      }
      stepInputPhotoFile.value = '';
    });
  }

  if (btnSaveInstructionStep) {
    btnSaveInstructionStep.addEventListener('click', async () => {
      if (!currentInstructionParentId || !currentInstructionSetIndex) return;

      const action = stepInputAction ? stepInputAction.value.trim() : '';
      const description = stepInputDescription ? stepInputDescription.value.trim() : '';

      const filledPartSlots = currentActionItems.filter(s => s.id !== null && s.id !== undefined);
      if (filledPartSlots.length === 0) {
        showToast('Please add and select at least one Action Item.', 'error');
        return;
      }

      const child_item_ids = filledPartSlots.map(item => item.id);
      const child_item_id = child_item_ids[0] || null;

      const filledToolSlots = currentToolSlots.filter(s => s.id !== null && s.id !== undefined);
      const tool_ids = filledToolSlots.map(item => item.id);
      const tool_id = tool_ids[0] || null;

      const toll_map = JSON.stringify(currentActionItems.map(slot => ({
        id: slot.id,
        quantity: slot.quantity || 1,
        toll: slot.toll !== false
      })));

      const tool_map = JSON.stringify(currentToolSlots.map(slot => ({
        id: slot.id,
        quantity: slot.quantity || 1
      })));

      const payload = {
        action,
        description,
        child_item_id,
        child_item_ids,
        tool_id,
        tool_ids,
        toll_map,
        tool_map,
        photo: stepPhotoUpload
      };

      await withBusy(btnSaveInstructionStep, async () => {
        try {
          showToast('Saving step...');
          if (editingStepId) {
            await updateInstructionStep(editingStepId, payload);
          } else {
            const newStep = await createInstructionStep(currentInstructionParentId, currentInstructionSetIndex, payload);
            if (insertStepAtIndex !== null && insertStepAtIndex !== undefined && insertStepAtIndex < currentInstructionSteps.length) {
              const stepIds = currentInstructionSteps.map(s => s.id);
              stepIds.splice(insertStepAtIndex, 0, newStep.id);
              await reorderInstructionSteps(currentInstructionParentId, currentInstructionSetIndex, stepIds);
            }
          }
          closeStepModal();
          await renderInstructionSetDetailsView();
          showToast('Step saved!');
        } catch (err) {
          showToast(err.message, 'error');
        }
      }, '<i class="fa-solid fa-spinner fa-spin"></i> Saving...');
    });
  }
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', () => {
    init();
    initInstructionEventListeners();
  });
}

function resetSearchState() {
  searchQuery = '';
  isExplicitSearch = false;
}

function setCurrentItemId(id) {
  currentItemId = id;
}

export {
  resetSearchState,
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
  currentInstructionSteps,
  currentActionItems,
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
  ensureAllItemsLoaded,
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
  renderDrawerStructural,
  openCreateItemModal,
  closeCreateItemModal,
  handleConfirmCreateItem,
  renderItemRelations,
  createRelationRowElement,
  handleSeverRelation,
  openAssemblyModal,
  closeAssemblyModal,
  updateSelectedParentDisplay,
  updateSelectedChildDisplay,
  checkAssemblyConfirmState,
  renderAssemblyParentList,
  renderAssemblyChildList,
  isItemEolOrDeprecated,
  handleConfirmAssembly,
  handleDeleteAssemblyRelation,
  openGalleryOverlay,
  closeGalleryOverlay,
  navigateGallery,
  openRecategorizeModal,
  updateRecategorizePreview,
  handleConfirmRecategorize,
  evaluateInstructionText,
  updateStepTextPreview,
  loadInstructionSetsForItem,
  openAssemblyInstructionsView,
  renderInstructionSetDetailsView,
  openInstructionStepModal,
  initInstructionEventListeners,
  addItemRevision,
  showToast,
  showLoadingToast,
  refreshData,
  loadDefaultView,
  applyStructuralFilter,
  renderBatchButton,
  renderDrawerCategories,
  initItemPicker,
  openItemPicker,
  closeItemPicker,
  selectItemInPicker,
  renderPickerItemsList,
  setButtonLoading,
  withBusy,
  itemMatchesQuery,
  nodeMatchesQuery,
  getSearchMode,
  setSearchMode,
  getFilterHasParents,
  setFilterHasParents,
  getFilterHasChildren,
  setFilterHasChildren,
  openDuplicateItemModal,
  closeDuplicateItemModal,
  handleConfirmDuplicateItem
};

// --- WI Export Logic ---
let wiExportParentId = null;
let wiExportSetIndex = null;

async function openWiExportModal(parentId, setIndex) {
  wiExportParentId = parentId;
  wiExportSetIndex = setIndex;
  
  const modal = document.getElementById('wi-export-modal');
  const select = document.getElementById('wi-template-select');
  if (!modal || !select) return;
  
  select.innerHTML = '<option value="">Loading...</option>';
  modal.style.display = 'flex';
  setTimeout(() => { modal.classList.add('open'); }, 10);
  
  try {
    const templates = await fetchWiTemplates();
    const validTemplates = (templates || []).filter(t => t.Valid || t.Approved);
    
    if (validTemplates.length === 0) {
      select.innerHTML = '<option value="">No valid templates found</option>';
      document.getElementById('btn-wi-export-confirm').disabled = true;
    } else {
      select.innerHTML = validTemplates.map(t => `<option value="${t.id}">${t.Name}</option>`).join('');
      document.getElementById('btn-wi-export-confirm').disabled = false;
    }
  } catch (err) {
    select.innerHTML = '<option value="">Failed to load templates</option>';
    document.getElementById('btn-wi-export-confirm').disabled = true;
  }
}

document.getElementById('btn-close-wi-export')?.addEventListener('click', () => {
  const modal = document.getElementById('wi-export-modal');
  if (modal) {
    modal.classList.remove('open');
    setTimeout(() => { modal.style.display = 'none'; }, 300);
  }
});

document.getElementById('btn-wi-export-cancel')?.addEventListener('click', () => {
  const modal = document.getElementById('wi-export-modal');
  if (modal) {
    modal.classList.remove('open');
    setTimeout(() => { modal.style.display = 'none'; }, 300);
  }
});

document.getElementById('btn-wi-export-confirm')?.addEventListener('click', async () => {
  const templateId = document.getElementById('wi-template-select').value;
  if (!templateId) return;
  
  const btn = document.getElementById('btn-wi-export-confirm');
  const origText = btn.textContent;
  btn.textContent = 'Exporting...';
  btn.disabled = true;
  
  try {
    const res = await exportWiDocument(wiExportParentId, wiExportSetIndex, templateId);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    const contentDisposition = res.headers.get('Content-Disposition');
    let fileName = 'Export.docx';
    if (contentDisposition && contentDisposition.indexOf('filename=') !== -1) {
        const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
        if (matches != null && matches[1]) {
            fileName = matches[1].replace(/['"]/g, '');
        }
    }
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
    
    const modal = document.getElementById('wi-export-modal');
    if (modal) {
      modal.classList.remove('open');
      setTimeout(() => { modal.style.display = 'none'; }, 300);
    }
    showToast('Export successful!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.textContent = origText;
    btn.disabled = false;
  }
});

document.getElementById('btn-export-instruction-set')?.addEventListener('click', () => {
  if (currentInstructionParentId && currentInstructionSetIndex !== null) {
    openWiExportModal(currentInstructionParentId, currentInstructionSetIndex);
  }
});

