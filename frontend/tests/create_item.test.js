import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

// Mock API
vi.mock('../src/api.js', () => {
  return {
    fetchBomTree: vi.fn(),
    fetchItem: vi.fn(),
    updateItem: vi.fn(),
    fetchScanStatus: vi.fn(),
    getHealth: vi.fn(),
    fetchRules: vi.fn(),
    fetchManufacturers: vi.fn().mockResolvedValue([]),
    uploadDatasheet: vi.fn(),
    fetchFlatItems: vi.fn().mockResolvedValue([]),
    createAssembly: vi.fn(),
    updateAssembly: vi.fn(),
    deleteAssembly: vi.fn(),
    createItem: vi.fn(),
  };
});

let mainModule;

beforeAll(async () => {
  document.body.innerHTML = `
    <!-- Mock required elements for main.js loading -->
    <button id="btn-refresh"></button>
    <div id="tree-container"></div>
    <div id="filter-drawer"></div>
    <span id="filter-badge"></span>
    <button id="btn-filter"></button>
    <div id="categories-filter-list"></div>
    <div id="states-filter-list"></div>

    <!-- Create New Item Modal Elements -->
    <div id="create-item-modal" class="modal-overlay">
      <button id="btn-close-create-item"></button>
      <select id="create-item-category"></select>
      <input type="text" id="create-item-description" />
      <button id="btn-cancel-create-item"></button>
      <button id="btn-confirm-create-item"></button>
    </div>
    <button id="btn-add-item-trigger"></button>

    <!-- Other items for main.js init -->
    <span id="title-pn"></span>
    <span id="title-desc"></span>
    <div id="revision-tags-container"></div>
    <select id="input-manufacturer"></select>
    <div id="datasheets-list"></div>
    <input type="file" id="input-photo-file" />
    <div id="drag-drop-overlay"></div>
    <div id="gallery-container"></div>
    <div id="related-items-container"></div>
    <div id="add-related-modal" class="modal-overlay">
      <input type="text" id="add-related-search" />
      <button id="btn-close-add-related"></button>
      <div id="add-related-list"></div>
    </div>
    <div id="confirm-modal" class="modal-overlay">
      <button id="btn-close-confirm"></button>
      <button id="btn-confirm-cancel"></button>
      <button id="btn-confirm-accept"></button>
    </div>
    <input type="text" id="input-description" />
    <input type="text" id="input-source" />
    <input type="text" id="input-external-pn" />
    <select id="input-state"></select>
    <input type="text" id="input-price" />
    <select id="input-sourced-by"></select>
    <textarea id="input-notes"></textarea>
  `;

  mainModule = await import('../src/main.js');
});

describe('Create Item Modal Dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.location.hash = '';
  });

  it('openCreateItemModal populates categories and shows modal', () => {
    // Setup categories in main module state
    mainModule.categoryRules['10'] = { name: 'Raw Material', color: 'red' };
    mainModule.categoryRules['20'] = { name: 'Mechanical COTS', color: 'blue' };

    mainModule.openCreateItemModal();

    const modal = document.getElementById('create-item-modal');
    expect(modal.style.display).toBe('flex');
    expect(modal.classList.contains('open')).toBe(true);

    const categorySelect = document.getElementById('create-item-category');
    const options = categorySelect.querySelectorAll('option');
    expect(options.length).toBe(2);
    // Alphabetically sorted: Mechanical COTS first (20), Raw Material second (10)
    expect(options[0].value).toBe('20');
    expect(options[0].textContent).toBe('20 - Mechanical COTS');
    expect(options[1].value).toBe('10');
    expect(options[1].textContent).toBe('10 - Raw Material');
  });

  it('closeCreateItemModal hides the modal after transition', () => {
    const modal = document.getElementById('create-item-modal');
    modal.style.display = 'flex';
    modal.classList.add('open');

    mainModule.closeCreateItemModal();
    expect(modal.classList.contains('open')).toBe(false);
  });

  it('handleConfirmCreateItem validates description and calls createItem API', async () => {
    const { createItem } = await import('../src/api.js');
    createItem.mockResolvedValue({ id: 123, 'Part Number': '10-00000' });

    const descInput = document.getElementById('create-item-description');
    const categorySelect = document.getElementById('create-item-category');
    
    categorySelect.value = '10';
    descInput.value = 'Test Part Description';

    await mainModule.handleConfirmCreateItem();

    expect(createItem).toHaveBeenCalledWith('10', 'Test Part Description');
    expect(window.location.hash).toBe('#item/123');
  });
});
