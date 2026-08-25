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
    fetchStates: vi.fn().mockResolvedValue({}),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

let mainModule;

beforeAll(async () => {
  document.body.innerHTML = `
    <div id="item-details-view" style="display: block;">
      <button id="btn-export-menu"></button>
      <div id="export-menu-dropdown" class="dropdown-menu-custom">
        <a href="#" id="menu-export-direct"></a>
        <a href="#" id="menu-export-inventory"></a>
      </div>

      <!-- Inventory Report Modal -->
      <div id="inventory-report-modal" class="modal-overlay" style="display: none;">
        <input type="number" id="input-target-build-qty" value="1" />
        <button id="btn-close-inventory-report"></button>
        <button id="btn-cancel-inventory-report"></button>
        <button id="btn-confirm-inventory-report"></button>
      </div>

      <div id="contained-items-list"></div>
      <div id="containing-items-list"></div>
    </div>
  `;

  mainModule = await import('../src/main.js');
  await mainModule.init();
});

describe('Reports Menu & Inventory Requirement Report UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.open = vi.fn();
    mainModule.setCurrentItemId(539);
    const dropdown = document.getElementById('export-menu-dropdown');
    dropdown.classList.remove('open');
    const modal = document.getElementById('inventory-report-modal');
    modal.style.display = 'none';
  });

  it('toggles Reports dropdown menu on button click and closes on outside click', () => {
    const btnMenu = document.getElementById('btn-export-menu');
    const dropdown = document.getElementById('export-menu-dropdown');

    expect(dropdown.classList.contains('open')).toBe(false);

    btnMenu.click();
    expect(dropdown.classList.contains('open')).toBe(true);

    // Outside click closes dropdown
    document.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(dropdown.classList.contains('open')).toBe(false);
  });

  it('triggers direct components export on menu-export-direct click', () => {
    const btnDirect = document.getElementById('menu-export-direct');
    btnDirect.click();

    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('/api/bom/items/539/export'),
      '_blank'
    );
  });

  it('opens inventory report modal when clicking menu-export-inventory', () => {
    const btnInv = document.getElementById('menu-export-inventory');
    const modal = document.getElementById('inventory-report-modal');
    const inputQty = document.getElementById('input-target-build-qty');

    btnInv.click();
    expect(modal.style.display).toBe('flex');
    expect(inputQty.value).toBe('1');
  });

  it('closes inventory report modal on cancel or close button click', () => {
    const modal = document.getElementById('inventory-report-modal');
    modal.style.display = 'flex';

    const btnCancel = document.getElementById('btn-cancel-inventory-report');
    btnCancel.click();
    expect(modal.style.display).toBe('none');

    modal.style.display = 'flex';
    const btnClose = document.getElementById('btn-close-inventory-report');
    btnClose.click();
    expect(modal.style.display).toBe('none');
  });

  it('triggers inventory report download with custom target build quantity', () => {
    const modal = document.getElementById('inventory-report-modal');
    const inputQty = document.getElementById('input-target-build-qty');
    const btnConfirm = document.getElementById('btn-confirm-inventory-report');

    modal.style.display = 'flex';
    inputQty.value = '15';

    btnConfirm.click();

    expect(window.open).toHaveBeenCalledWith(
      expect.stringContaining('/api/bom/items/539/inventory-report?build_qty=15'),
      '_blank'
    );
    expect(modal.style.display).toBe('none');
  });
});
