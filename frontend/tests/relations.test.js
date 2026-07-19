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

    <!-- Modals -->
    <div id="create-item-modal" class="modal-overlay">
      <button id="btn-close-create-item"></button>
      <select id="create-item-category"></select>
      <input type="text" id="create-item-description" />
      <button id="btn-cancel-create-item"></button>
      <button id="btn-confirm-create-item"></button>
    </div>
    <button id="btn-add-item-trigger"></button>

    <!-- Item Details View Elements -->
    <div id="item-details-view">
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

      <!-- Relations Lists -->
      <button id="btn-add-contained"></button>
      <button id="btn-add-containing"></button>
      <div id="contained-items-list" class="relations-list-container"></div>
      <div id="containing-items-list" class="relations-list-container"></div>
    </div>
  `;

  mainModule = await import('../src/main.js');
  await mainModule.init();
});

describe('Item Relations Lists Bottom Section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.location.hash = '';
    
    // Clear list containers
    document.getElementById('contained-items-list').innerHTML = '';
    document.getElementById('containing-items-list').innerHTML = '';
  });

  it('renders placeholders when contained_items and containing_items are empty', () => {
    const item = {
      contained_items: [],
      containing_items: []
    };

    mainModule.renderItemRelations(item);

    const containedEl = document.getElementById('contained-items-list');
    const containingEl = document.getElementById('containing-items-list');

    expect(containedEl.textContent).toContain('No contained items');
    expect(containingEl.textContent).toContain('No parent assemblies contain this item');
  });

  it('renders contained items correctly with side buttons drawer and properties', () => {
    const item = {
      contained_items: [
        {
          edge_id: 101,
          id: 42,
          part_number: '10-00042',
          description: 'Resistor 10k',
          revision: 'B',
          amount_label: '5 pcs'
        }
      ],
      containing_items: []
    };

    mainModule.renderItemRelations(item);

    const container = document.getElementById('contained-items-list');
    const rows = container.querySelectorAll('.tree-row');
    expect(rows.length).toBe(1);

    const row = rows[0];
    expect(row.textContent).toContain('Resistor 10k');
    expect(row.textContent).toContain('10-00042');
    expect(row.textContent).toContain('B');
    expect(row.textContent).toContain('5 pcs');

    const actionMenu = row.querySelector('.row-action-menu');
    expect(actionMenu).not.toBeNull();
    
    const buttons = actionMenu.querySelectorAll('button');
    expect(buttons.length).toBe(3); // Go to Item, Edit, and Sever

    // Mock needed DOM for assembly modal
    const modal = document.createElement('div');
    modal.id = 'assembly-modal';
    modal.style.display = 'none';
    const title = document.createElement('h2');
    title.id = 'assembly-modal-title';
    document.body.appendChild(modal);
    document.body.appendChild(title);

    buttons[1].click();
    
    expect(modal.style.display).toBe('flex');
    expect(title.textContent).toBe('Edit Assembly Properties');

    modal.remove();
    title.remove();
  });

  it('toggles menu-open class when clicking on a relation row', () => {
    const item = {
      contained_items: [
        {
          edge_id: 101,
          id: 42,
          part_number: '10-00042',
          description: 'Resistor 10k',
          revision: 'B',
          amount_label: '5 pcs'
        }
      ],
      containing_items: []
    };

    mainModule.renderItemRelations(item);

    const container = document.getElementById('contained-items-list');
    const row = container.querySelector('.tree-row');

    expect(row.classList.contains('menu-open')).toBe(false);
    row.click();
    expect(row.classList.contains('menu-open')).toBe(true);
    row.click();
    expect(row.classList.contains('menu-open')).toBe(false);
  });

  it('calls deleteAssembly and refreshes page when severing relation is confirmed', async () => {
    const { deleteAssembly } = await import('../src/api.js');
    deleteAssembly.mockResolvedValueOnce({ status: 'success' });
    
    // Stub window.confirm
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    mainModule.setCurrentItemId(99);
    await mainModule.handleSeverRelation(101);

    expect(confirmSpy).toHaveBeenCalled();
    expect(deleteAssembly).toHaveBeenCalledWith(101);
  });

  it('triggers openAssemblyModal when btn-add-contained or btn-add-containing is clicked', () => {
    const modal = document.createElement('div');
    modal.id = 'assembly-modal';
    modal.style.display = 'none';
    
    const parentPn = document.createElement('div');
    parentPn.id = 'selected-parent-pn';
    const childPn = document.createElement('div');
    childPn.id = 'selected-child-pn';

    const parentDesc = document.createElement('div');
    parentDesc.id = 'selected-parent-desc';
    const childDesc = document.createElement('div');
    childDesc.id = 'selected-child-desc';

    document.body.appendChild(modal);
    document.body.appendChild(parentPn);
    document.body.appendChild(childPn);
    document.body.appendChild(parentDesc);
    document.body.appendChild(childDesc);

    mainModule.setCurrentItemId(351);
    
    const btnAddContained = document.getElementById('btn-add-contained');
    expect(btnAddContained).not.toBeNull();
    btnAddContained.click();
    
    expect(modal.style.display).toBe('flex');
    
    modal.style.display = 'none';
    const btnAddContaining = document.getElementById('btn-add-containing');
    expect(btnAddContaining).not.toBeNull();
    btnAddContaining.click();
    
    expect(modal.style.display).toBe('flex');
    
    modal.remove();
    parentPn.remove();
    childPn.remove();
    parentDesc.remove();
    childDesc.remove();
  });
});
