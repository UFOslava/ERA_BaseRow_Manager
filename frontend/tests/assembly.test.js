import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

// Mock the API calls
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
    createAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    updateAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    deleteAssembly: vi.fn().mockResolvedValue({ status: 'success' }),
    fetchStates: vi.fn().mockResolvedValue({})
  };
});

import { createAssembly, updateAssembly, deleteAssembly as apiDeleteAssembly } from '../src/api';

let mainModule;

describe('Assembly Modals Logic', () => {
  beforeAll(async () => {
    document.body.innerHTML = `
      <div id="add-child-modal" class="modal-overlay">
        <input type="text" id="add-child-search" />
        <div id="add-child-list"></div>
        <div id="add-child-form" style="display: none;">
          <span id="selected-child-name"></span>
          <div id="add-child-revision-tags"></div>
          <input type="number" id="add-child-quantity" value="1" />
          <input type="number" id="add-child-length" value="0" />
          <input type="text" id="add-child-pcb" />
        </div>
        <button id="btn-close-add-child"></button>
        <button id="btn-cancel-add-child"></button>
        <button id="btn-confirm-add-child" disabled></button>
      </div>

      <div id="edit-assembly-modal" class="modal-overlay">
        <span id="edit-assembly-item-name"></span>
        <input type="number" id="edit-assembly-quantity" value="1" />
        <input type="number" id="edit-assembly-length" value="0" />
        <input type="text" id="edit-assembly-pcb" />
        <button id="btn-close-edit-assembly"></button>
        <button id="btn-cancel-edit-assembly"></button>
        <button id="btn-save-edit-assembly"></button>
        <button id="btn-delete-assembly"></button>
      </div>
      
      <!-- Stub other required main.js selectors so import doesn't fail -->
      <span id="title-pn"></span>
      <span id="title-desc"></span>
      <div id="revision-tags-container"></div>
      <select id="input-manufacturer"></select>
      <input type="file" id="input-photo-file" />
      <div id="drag-drop-overlay"></div>
      <div id="gallery-container"></div>
      <div id="related-items-container"></div>
      <div id="add-related-modal">
        <input type="text" id="add-related-search" />
        <button id="btn-close-add-related"></button>
        <div id="add-related-list"></div>
      </div>
      <div id="confirm-modal">
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
      <input type="text" id="input-notes" />
    `;
    
    // Dynamically import main.js after setting up DOM
    mainModule = await import('../src/main.js');
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('openAddChildModal resets states and opens modal', () => {
    mainModule.openAddChildModal(10);
    const modal = document.getElementById('add-child-modal');
    expect(modal.style.display).toBe('flex');
    expect(modal.classList.contains('open')).toBe(true);
    expect(document.getElementById('btn-confirm-add-child').disabled).toBe(true);
  });

  it('renderAddChildList filters and lists items by query', () => {
    mainModule.allItems.push(
      { id: 1, "Part Number": "10-00001", "Item description": "Child Item A", "External PN": "EXT-A", "Notes": "Notes A", "Search helper": "helper A" },
      { id: 2, "Part Number": "10-00002", "Item description": "Other Item", "External PN": "EXT-B", "Notes": "Notes B", "Search helper": "helper B" }
    );

    mainModule.openAddChildModal(10);
    
    const searchInput = document.getElementById('add-child-search');
    searchInput.value = 'Child Item';
    mainModule.renderAddChildList();

    const list = document.getElementById('add-child-list');
    expect(list.children.length).toBe(1);
    expect(list.querySelector('.row-desc').textContent).toBe('Child Item A');
  });

  it('selectChildItem sets revision selection', () => {
    const item = { id: 1, "Part Number": "10-00001", "Item description": "Child Item A" };
    mainModule.selectChildItem(item);
    
    expect(document.getElementById('selected-child-name').textContent).toContain('Child Item A');
    expect(document.getElementById('add-child-form').style.display).toBe('flex');
    expect(document.getElementById('btn-confirm-add-child').disabled).toBe(false);
  });

  it('handleConfirmAddChild calls createAssembly', async () => {
    mainModule.openAddChildModal(10);
    mainModule.selectChildItem({ id: 1, "Part Number": "10-00001" });
    
    document.getElementById('add-child-quantity').value = "5";
    document.getElementById('add-child-length').value = "100";
    document.getElementById('add-child-pcb').value = "C1";

    await mainModule.handleConfirmAddChild();

    expect(createAssembly).toHaveBeenCalledWith(10, 1, 5, 100, "C1");
  });

  it('openEditAssemblyModal opens edit modal', () => {
    const node = {
      id: 5,
      part_number: '10-00005',
      description: 'Edit Target Component',
      edge_id: 200,
      quantity: 4,
      length: 120,
      pcb_symbol: 'R2'
    };

    mainModule.openEditAssemblyModal(node);

    const modal = document.getElementById('edit-assembly-modal');
    expect(modal.style.display).toBe('flex');
    expect(modal.classList.contains('open')).toBe(true);
    expect(document.getElementById('edit-assembly-quantity').value).toBe('4');
    expect(document.getElementById('edit-assembly-length').value).toBe('120');
    expect(document.getElementById('edit-assembly-pcb').value).toBe('R2');
  });

  it('handleSaveEditAssembly calls updateAssembly API', async () => {
    const node = { id: 5, edge_id: 200 };
    mainModule.openEditAssemblyModal(node);

    document.getElementById('edit-assembly-quantity').value = "10";
    document.getElementById('edit-assembly-length').value = "250";
    document.getElementById('edit-assembly-pcb').value = "R3";

    await mainModule.handleSaveEditAssembly();

    expect(updateAssembly).toHaveBeenCalledWith(200, 10, 250, "R3");
  });

  it('handleDeleteAssembly calls deleteAssembly API after confirm', async () => {
    const node = { id: 5, edge_id: 200 };
    mainModule.openEditAssemblyModal(node);

    window.confirm = vi.fn().mockReturnValue(true);

    await mainModule.handleDeleteAssembly();

    expect(apiDeleteAssembly).toHaveBeenCalledWith(200);
  });
});
