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
    fetchStates: vi.fn().mockResolvedValue({}),
    fetchTopLevelItems: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    fetchUoMs: vi.fn().mockResolvedValue([]),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

import { createAssembly, updateAssembly, deleteAssembly as apiDeleteAssembly } from '../src/api';

let mainModule;

describe('Assembly Modals Logic', () => {
  beforeAll(async () => {
    document.body.innerHTML = `
      <div id="add-child-modal" class="modal-overlay">
        <div id="assembly-parent-search-wrapper">
          <input type="text" id="assembly-parent-search" />
          <div id="assembly-parent-list"></div>
        </div>
        <div id="selected-parent-section" style="display: none;">
          <div id="selected-parent-title">Selected Parent</div>
          <button id="btn-change-parent" class="btn-change-item" style="display: flex;">Change</button>
          <span id="selected-parent-pn"></span>
          <span id="selected-parent-desc"></span>
          <span id="selected-parent-name"></span>
          <div id="selected-parent-revisions-wrapper">
            <div id="selected-parent-revisions"></div>
          </div>
        </div>

        <input type="text" id="add-child-search" />
        <div id="add-child-list"></div>
        <div id="add-child-form" style="display: none;">
          <div id="selected-child-title">Selected Child</div>
          <button id="btn-change-child" class="btn-change-item" style="display: flex;">Change</button>
          <span id="selected-child-name"></span>
          <div id="add-child-revision-tags"></div>
          <input type="number" id="add-child-quantity" value="1" />
          <div class="form-group">
            <input type="number" id="add-child-length" value="0" />
            <select id="assembly-measurement-uom"></select>
          </div>
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

  it('renderAssemblyParentList and renderAssemblyChildList support multi-token search matching Search helper', () => {
    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 1, "Part Number": "30-00059", "Item description": "Nova Handle Lower", "External PN": "EXT-3059", "Notes": "Black color", "Search helper": "30 59" },
      { id: 2, "Part Number": "40-00049", "Item description": "100pF Capacitor", "External PN": "EXT-4049", "Notes": "SMD 0603", "Search helper": "40 49" }
    );

    // Test Parent List multi-token search
    const parentInput = document.getElementById('assembly-parent-search');
    if (parentInput) {
      parentInput.value = '30 59';
      mainModule.renderAssemblyParentList();
      const parentList = document.getElementById('assembly-parent-list');
      expect(parentList.children.length).toBe(1);
      expect(parentList.textContent).toContain('30-00059');
      expect(parentList.textContent).toContain('Nova Handle Lower');
    }

    // Test Child List multi-token search
    const childInput = document.getElementById('assembly-child-search') || document.getElementById('add-child-search');
    childInput.value = '40 49';
    mainModule.renderAssemblyChildList();
    const childList = document.getElementById('assembly-child-list') || document.getElementById('add-child-list');
    expect(childList.children.length).toBe(1);
    expect(childList.textContent).toContain('40-00049');
    expect(childList.textContent).toContain('100pF Capacitor');
  });

  it('renderAssemblyParentList and renderAssemblyChildList match Molex PNs ignoring dividers', () => {
    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 1, "Part Number": "40-00050", "Item description": "Molex Crimp Terminal", "External PN": "39-00-00-39" },
      { id: 2, "Part Number": "40-00051", "Item description": "Molex Receptacle 2 Pos", "External PN": "39-01-2020" }
    );

    // Search 39000039 without dividers in child search
    const childInput = document.getElementById('assembly-child-search') || document.getElementById('add-child-search');
    childInput.value = '39000039';
    mainModule.renderAssemblyChildList();
    const childList = document.getElementById('assembly-child-list') || document.getElementById('add-child-list');
    expect(childList.children.length).toBe(1);
    expect(childList.textContent).toContain('40-00050');
    expect(childList.textContent).toContain('Molex Crimp Terminal');

    // Search 39012020 without dividers in parent search
    const parentInput = document.getElementById('assembly-parent-search');
    if (parentInput) {
      parentInput.value = '39012020';
      mainModule.renderAssemblyParentList();
      const parentList = document.getElementById('assembly-parent-list');
      expect(parentList.children.length).toBe(1);
      expect(parentList.textContent).toContain('40-00051');
      expect(parentList.textContent).toContain('Molex Receptacle 2 Pos');
    }
  });

  it('selectChildItem sets revision selection', () => {
    const item = { id: 1, "Part Number": "10-00001", "Item description": "Child Item A" };
    mainModule.allItems.length = 0;
    mainModule.allItems.push(item);
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

    expect(updateAssembly).toHaveBeenCalledWith(200, 10, 250, "R3", undefined, 5);
  });

  it('handleDeleteAssembly calls deleteAssembly API after confirm', async () => {
    const node = { id: 5, edge_id: 200 };
    mainModule.openEditAssemblyModal(node);

    window.confirm = vi.fn().mockReturnValue(true);

    await mainModule.handleDeleteAssembly();

    expect(apiDeleteAssembly).toHaveBeenCalledWith(200);
  });

  it('preserves change button when updateSelectedParentDisplay and updateSelectedChildDisplay are called', () => {
    // Inject parent & child items in allItems
    mainModule.allItems.push(
      { id: 10, "Part Number": "10-00010", "Item description": "Parent Item X" },
      { id: 20, "Part Number": "10-00020", "Item description": "Child Item Y" }
    );

    // 1. Parent display update:
    // Set unlocked parent
    document.getElementById('add-child-modal').style.display = 'none';
    mainModule.openAssemblyModal({ childId: 20 }); // A is locked child, parent is unlocked

    // Select B (id 10) as parent
    document.getElementById('assembly-parent-search').value = 'Parent Item';
    mainModule.renderAssemblyParentList();
    const parentRow = document.getElementById('assembly-parent-list').children[0];
    parentRow.click(); // Select parent 10

    // Assert that the title was updated AND the button was NOT wiped out and is displayed as flex
    const titleEl = document.getElementById('selected-parent-title');
    const changeBtn = document.getElementById('btn-change-parent');
    expect(titleEl).not.toBeNull();
    expect(titleEl.textContent).toContain('Selected Parent');
    expect(changeBtn).not.toBeNull();
    expect(changeBtn.style.display).toBe('flex');

    // 2. Child display update:
    // Set unlocked child
    mainModule.openAssemblyModal({ parentId: 10 }); // Parent is locked, child is unlocked

    // Select B (id 20) as child
    document.getElementById('add-child-search').value = 'Child Item';
    mainModule.renderAssemblyChildList();
    const childRow = document.getElementById('add-child-list').children[0];
    childRow.click(); // Select child 20

    // Assert that the title was updated AND the button was NOT wiped out and is displayed as flex
    const childTitleEl = document.getElementById('selected-child-title');
    const childChangeBtn = document.getElementById('btn-change-child');
    expect(childTitleEl).not.toBeNull();
    expect(childTitleEl.textContent).toContain('Selected Child');
    expect(childChangeBtn).not.toBeNull();
    expect(childChangeBtn.style.display).toBe('flex');
  });

  it('allows clicking revision tags in edit mode and saves the updated revision ID', async () => {
    // Clear and populate allItems
    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 10, "Part Number": "10-00010", revision: "A", "Item description": "Parent Item X" },
      { id: 11, "Part Number": "10-00010", revision: "B", "Item description": "Parent Item X RevB" },
      { id: 20, "Part Number": "10-00020", revision: "A", "Item description": "Child Item Y" },
      { id: 21, "Part Number": "10-00020", revision: "B", "Item description": "Child Item Y RevB" }
    );

    // Open in edit mode
    mainModule.openAssemblyModal({
      edgeId: 200,
      parentId: 10,
      childId: 20,
      quantity: 3,
      length: 150,
      pcb_symbol: "C1"
    });

    // Verify parent & child revision tags are populated
    const childRevsContainer = document.getElementById('add-child-revision-tags');
    expect(childRevsContainer.children.length).toBe(2);

    // The first revision tag is "A" (ID 20), second is "B" (ID 21)
    // Click revision "B"
    const revBTag = childRevsContainer.children[1];
    revBTag.click();

    // Verify that assemblySelectedChildId updated to 21
    // And handleConfirmAssembly calls updateAssembly with child ID 21
    await mainModule.handleConfirmAddChild();

    expect(updateAssembly).toHaveBeenCalledWith(200, 3, 150, "C1", 10, 21);
  });

  it('correctly identifies EOL, discard, and use up states with isItemEolOrDeprecated', () => {
    const { isItemEolOrDeprecated } = mainModule;
    expect(isItemEolOrDeprecated({ State: 'EOL' })).toBe(true);
    expect(isItemEolOrDeprecated({ State: { value: 'Do Not Use (Discard)' } })).toBe(true);
    expect(isItemEolOrDeprecated({ State: [{ value: 'Finish Stock (Use Up)' }] })).toBe(true);
    expect(isItemEolOrDeprecated({ State: 'Discard' })).toBe(true);
    expect(isItemEolOrDeprecated({ State: 'Production Use' })).toBe(false);
    expect(isItemEolOrDeprecated({ State: 'Engineering Use' })).toBe(false);
    expect(isItemEolOrDeprecated({ State: null })).toBe(false);
  });

  it('renders EOL, discard, and use up items with red tint and warning badge in assembly search list', () => {
    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 101, "Part Number": "10-00101", "Item description": "Production Item Active", State: "Production Use" },
      { id: 102, "Part Number": "10-00102", "Item description": "EOL Item Legacy", State: "EOL" },
      { id: 103, "Part Number": "10-00103", "Item description": "Discarded Component", State: "Do Not Use (Discard)" },
      { id: 104, "Part Number": "10-00104", "Item description": "Finish Stock Resistor", State: "Finish Stock (Use Up)" }
    );

    mainModule.openAssemblyModal({ parentId: null, childId: null });

    // Test Parent search
    const parentSearchInput = document.getElementById('assembly-parent-search');
    parentSearchInput.value = '10-';
    mainModule.renderAssemblyParentList();

    const parentList = document.getElementById('assembly-parent-list');
    expect(parentList.children.length).toBe(4);

    const activeRow = parentList.children[0];
    expect(activeRow.classList.contains('is-eol')).toBe(false);
    expect(activeRow.querySelector('.badge-eol-warning')).toBeNull();

    const eolRow = parentList.children[1];
    expect(eolRow.classList.contains('is-eol')).toBe(true);
    expect(eolRow.querySelector('.row-pn').style.color).toBe('rgb(239, 68, 68)');
    const eolBadge = eolRow.querySelector('.badge-eol-warning');
    expect(eolBadge).not.toBeNull();
    expect(eolBadge.textContent).toBe('EOL');

    const discardRow = parentList.children[2];
    expect(discardRow.classList.contains('is-eol')).toBe(true);
    expect(discardRow.querySelector('.badge-eol-warning').textContent).toBe('Do Not Use (Discard)');

    const useUpRow = parentList.children[3];
    expect(useUpRow.classList.contains('is-eol')).toBe(true);
    expect(useUpRow.querySelector('.badge-eol-warning').textContent).toBe('Finish Stock (Use Up)');

    // Test Child search
    const childSearchInput = document.getElementById('add-child-search');
    childSearchInput.value = '10-';
    mainModule.renderAssemblyChildList();

    const childList = document.getElementById('add-child-list');
    expect(childList.children.length).toBe(4);
    expect(childList.children[1].classList.contains('is-eol')).toBe(true);
  });

  it('displays Parent Item properly when opening modal for freshly created item not yet in allItems', async () => {
    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 10, "Part Number": "10-00010", "Item description": "Existing Item" }
    );

    const { fetchItem } = await import('../src/api.js');
    fetchItem.mockResolvedValueOnce({
      id: 999,
      "Part Number": "55-00999",
      "Item description": "Freshly Created Parent",
      contained_items: []
    });

    await mainModule.showItemPage(999);

    mainModule.openAssemblyModal({ parentId: 999 });

    const parentSection = document.getElementById('selected-parent-section');
    const parentSearchWrapper = document.getElementById('assembly-parent-search-wrapper');
    const parentPn = document.getElementById('selected-parent-pn');
    const parentDesc = document.getElementById('selected-parent-desc');

    expect(parentSection.style.display).toBe('flex');
    expect(parentSearchWrapper.style.display).toBe('none');
    expect(parentPn.textContent).toBe('55-00999');
    expect(parentDesc.textContent).toBe('Freshly Created Parent');
  });

  it('automatically triggers ensureAllItemsLoaded and renders results when searching child item with unloaded allItems', async () => {
    mainModule.allItems.length = 0;
    mainModule.setIsFlatItemsLoaded(false);
    mainModule.allItems.push(
      { id: 999, "Part Number": "55-00999", "Item description": "Parent Unit" }
    );

    const { fetchFlatItems } = await import('../src/api.js');
    fetchFlatItems.mockResolvedValueOnce([
      { id: 999, "Part Number": "55-00999", "Item description": "Parent Unit" },
      { id: 101, "Part Number": "10-00101", "Item description": "Child Resistor" },
      { id: 102, "Part Number": "10-00102", "Item description": "Child Capacitor" }
    ]);

    mainModule.openAssemblyModal({ parentId: 999 });

    const childSearchInput = document.getElementById('assembly-child-search') || document.getElementById('add-child-search');
    childSearchInput.value = 'Resistor';
    mainModule.renderAssemblyChildList();

    const childList = document.getElementById('assembly-child-list') || document.getElementById('add-child-list');
    expect(childList.textContent).toContain('Loading item directory...');

    // Wait for the async ensureAllItemsLoaded to resolve
    await new Promise(resolve => setTimeout(resolve, 50));

    expect(childList.textContent).toContain('10-00101');
    expect(childList.textContent).toContain('Child Resistor');
  });

  it('updates assembly measurement UOM and visibility in respect to selected child item consumption UOM', async () => {
    const { fetchUoMs } = await import('../src/api.js');
    fetchUoMs.mockResolvedValue([
      { id: 1, Name: 'Piece', Symbol: 'pcs', 'Multiplier to Base': '1.0' },
      { id: 4, Name: 'Millimeter', Symbol: 'mm', 'Multiplier to Base': '0.001' },
      { id: 5, Name: 'Centimeter', Symbol: 'cm', 'Multiplier to Base': '0.01' }
    ]);

    mainModule.allItems.length = 0;
    mainModule.allItems.push(
      { id: 999, "Part Number": "55-00999", "Item description": "Parent Unit" },
      { id: 501, "Part Number": "10-00016", "Item description": "Cable Wire", "Consumption UoM": [{ id: 5, value: "Centimeter" }] },
      { id: 502, "Part Number": "20-00001", "Item description": "Screw M3", "Consumption UoM": [{ id: 1, value: "Piece" }] }
    );

    // Open modal with parent only
    mainModule.openAssemblyModal({ parentId: 999 });
    await new Promise(resolve => setTimeout(resolve, 50));

    const uomSelect = document.getElementById('assembly-measurement-uom');
    const lengthInput = document.getElementById('add-child-length') || document.getElementById('assembly-length');
    const lengthGroup = lengthInput.closest('.form-group') || lengthInput.parentElement;

    // Search and select child item 501 (Cable Wire with cm)
    const childSearchInput = document.getElementById('assembly-child-search') || document.getElementById('add-child-search');
    childSearchInput.value = 'Wire';
    mainModule.renderAssemblyChildList();

    const childList = document.getElementById('assembly-child-list') || document.getElementById('add-child-list');
    const wireRow = childList.querySelector('.add-related-item-row');
    expect(wireRow).not.toBeNull();
    wireRow.click();

    // The modal must update UOM to 5 (Centimeter) and display the measurement field
    expect(uomSelect.value).toBe('5');
    expect(lengthGroup.style.display).not.toBe('none');

    // Change child to discrete piece item (502)
    const btnChangeChild = document.getElementById('btn-change-child');
    btnChangeChild.click();

    childSearchInput.value = 'Screw';
    mainModule.renderAssemblyChildList();

    const screwRow = childList.querySelector('.add-related-item-row');
    expect(screwRow).not.toBeNull();
    screwRow.click();

    // The modal must update UOM to 1 (Piece) and hide the measurement field
    expect(uomSelect.value).toBe('1');
    expect(lengthGroup.style.display).toBe('none');
  });
});
