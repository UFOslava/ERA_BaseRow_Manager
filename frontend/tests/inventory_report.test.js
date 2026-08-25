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
    fetchTopLevelItems: vi.fn().mockResolvedValue({ total: 0, items: [] }),
    fetchUoMs: vi.fn().mockResolvedValue([]),
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
      <div id="toast-container"></div>
    </div>
  `;

  // Mock URL methods for blob downloads
  window.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
  window.URL.revokeObjectURL = vi.fn();

  mainModule = await import('../src/main.js');
  await mainModule.init();
});

describe('Reports Menu & Inventory Requirement Report UI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(new Blob(['fake_xlsx'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })),
      headers: new Headers({
        'Content-Disposition': 'attachment; filename="55-00017 Rev.A - Inventory Requirement Report.xlsx"'
      })
    });
    mainModule.setCurrentItemId(539);
    const dropdown = document.getElementById('export-menu-dropdown');
    dropdown.classList.remove('open');
    const modal = document.getElementById('inventory-report-modal');
    modal.classList.remove('open');
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

  it('triggers direct components export on menu-export-direct click', async () => {
    const btnDirect = document.getElementById('menu-export-direct');
    btnDirect.click();

    await vi.waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/bom/items/539/export')
      );
    });
  });

  it('opens inventory report modal with .open class when clicking menu-export-inventory', () => {
    const btnInv = document.getElementById('menu-export-inventory');
    const modal = document.getElementById('inventory-report-modal');
    const inputQty = document.getElementById('input-target-build-qty');

    btnInv.click();
    expect(modal.style.display).toBe('flex');
    expect(modal.classList.contains('open')).toBe(true);
    expect(inputQty.value).toBe('1');
  });

  it('closes inventory report modal on cancel or close button click', () => {
    mainModule.openInventoryReportModal();
    const modal = document.getElementById('inventory-report-modal');
    expect(modal.classList.contains('open')).toBe(true);

    const btnCancel = document.getElementById('btn-cancel-inventory-report');
    btnCancel.click();
    expect(modal.classList.contains('open')).toBe(false);

    mainModule.openInventoryReportModal();
    const btnClose = document.getElementById('btn-close-inventory-report');
    btnClose.click();
    expect(modal.classList.contains('open')).toBe(false);
  });

  it('triggers inventory report download with custom target build quantity', async () => {
    mainModule.openInventoryReportModal();
    const modal = document.getElementById('inventory-report-modal');
    const inputQty = document.getElementById('input-target-build-qty');
    const btnConfirm = document.getElementById('btn-confirm-inventory-report');

    inputQty.value = '15';
    btnConfirm.click();

    await vi.waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/bom/items/539/inventory-report?build_qty=15')
      );
      expect(modal.classList.contains('open')).toBe(false);
    });
  });
});
