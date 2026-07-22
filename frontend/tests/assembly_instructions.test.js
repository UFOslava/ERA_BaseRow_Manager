import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

vi.mock('../src/api.js', () => {
  return {
    fetchBomTree: vi.fn(),
    fetchItem: vi.fn().mockResolvedValue({ id: 10, "Part Number": "10-00010", "Item description": "Parent Unit", contained_items: [{ id: 20, part_number: "20-00020", description: "Child Item" }] }),
    updateItem: vi.fn().mockResolvedValue({ id: 10 }),
    fetchScanStatus: vi.fn(),
    getHealth: vi.fn(),
    fetchRules: vi.fn(),
    fetchManufacturers: vi.fn().mockResolvedValue([]),
    uploadDatasheet: vi.fn().mockResolvedValue({ url: 'http://example.com/photo.jpg' }),
    fetchFlatItems: vi.fn().mockResolvedValue([
      { id: 10, "Part Number": "10-00010", "Item description": "Parent Unit" },
      { id: 20, "Part Number": "20-00020", "Item description": "Child Item" },
      { id: 30, "Part Number": "30-00030", "Item description": "Tool Item" }
    ]),
    createAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    updateAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    deleteAssembly: vi.fn().mockResolvedValue({ status: 'success' }),
    createItem: vi.fn(),
    recategorizeItem: vi.fn(),
    fetchInstructionSets: vi.fn().mockResolvedValue([
      { set_index: 1, step_count: 2 },
      { set_index: 2, step_count: 0 }
    ]),
    fetchInstructionSetDetails: vi.fn().mockResolvedValue({
      steps: [
        {
          id: 101,
          set_index: 1,
          step_order: 1,
          action: 'Solder',
          quantity: 2,
          description: 'Solder {qty}x {child} onto {receiving_item} using {tool}',
          photo: [],
          receiving_item: { id: 10, part_number: '10-00010', description: 'Parent Unit' },
          child_item: { id: 20, part_number: '20-00020', description: 'Child Item' },
          tool: { id: 30, part_number: '30-00030', description: 'Tool Item' }
        }
      ],
      comparison: [
        {
          item_id: 20,
          part_number: '20-00020',
          description: 'Child Item',
          required_qty: 2,
          instructed_qty: 2,
          discrepancy: 'OK',
          in_hierarchy: true
        },
        {
          item_id: 40,
          part_number: '40-00040',
          description: 'Uninstructed Screw',
          required_qty: 4,
          instructed_qty: 0,
          discrepancy: 'Missing Instruction',
          in_hierarchy: true
        }
      ]
    }),
    createInstructionStep: vi.fn().mockResolvedValue({ id: 102 }),
    updateInstructionStep: vi.fn().mockResolvedValue({ id: 101 }),
    deleteInstructionStep: vi.fn().mockResolvedValue({ status: 'success' }),
    reorderInstructionSteps: vi.fn().mockResolvedValue({ status: 'success' }),
    deleteInstructionSet: vi.fn().mockResolvedValue({ status: 'success' })
  };
});

let mainModule;

describe('Assembly Instructions Logic', () => {
  beforeAll(async () => {
    document.body.innerHTML = `
      <main id="bom-explorer-view" style="display: block;"></main>
      <main id="item-details-view" style="display: none;"></main>
      <main id="assembly-instructions-view" style="display: none;">
        <span id="instructions-set-title-badge"></span>
        <span id="instructions-parent-pn"></span>
        <span id="instructions-parent-desc"></span>
        <div id="instructions-comparison-list"></div>
        <div id="instruction-steps-container"></div>
      </main>

      <div id="instruction-sets-list"></div>
      <input type="checkbox" id="input-blackbox" />

      <div id="instruction-step-modal" class="modal-overlay" style="display: none;">
        <h2 id="instruction-step-modal-title"></h2>
        <input type="text" id="step-input-action" />
        <input type="number" id="step-input-qty" value="1" />
        <select id="step-input-child"></select>
        <button type="button" class="btn-choose-item" data-target="step-input-child">Choose</button>
        <select id="step-input-receiving"></select>
        <button type="button" class="btn-choose-item" data-target="step-input-receiving">Choose</button>
        <select id="step-input-tool"></select>
        <button type="button" class="btn-choose-item" data-target="step-input-tool">Choose</button>
        <textarea id="step-input-description"></textarea>
        <div id="step-text-preview"></div>
        <div id="step-photo-preview"></div>
        <input type="file" id="step-input-photo-file" />
        <button id="btn-save-instruction-step"></button>
        <button id="btn-cancel-instruction-step"></button>
        <button id="btn-close-instruction-step-modal"></button>
      </div>

      <div id="item-picker-modal" class="modal-overlay" style="display: none;">
        <button id="btn-close-item-picker"></button>
        <select id="picker-select-children"></select>
        <input type="text" id="picker-search-input" />
        <div id="picker-items-list"></div>
        <button id="btn-cancel-item-picker"></button>
      </div>

      <div id="confirm-modal" style="display: none;">
        <h2 id="confirm-modal-title"></h2>
        <p id="confirm-modal-message"></p>
        <button id="btn-confirm-accept"></button>
        <button id="btn-confirm-cancel"></button>
      </div>
    `;

    mainModule = await import('../src/main.js');
    mainModule.initInstructionEventListeners();
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('evaluateInstructionText replaces placeholders correctly', () => {
    const template = 'Solder {qty}x {child} onto {receiving_item} with {tool}';
    const result = mainModule.evaluateInstructionText(template, {
      childName: 'Capacitor',
      qty: '5',
      toolName: 'Soldering Iron',
      receivingName: 'Main Board',
      action: 'Solder'
    });

    expect(result).toBe('Solder 5x Capacitor onto Main Board with Soldering Iron');
  });

  it('loadInstructionSetsForItem fetches and renders sets list', async () => {
    await mainModule.loadInstructionSetsForItem(10);
    const container = document.getElementById('instruction-sets-list');
    expect(container.children.length).toBe(2);
    expect(container.textContent).toContain('Instruction Set #1');
    expect(container.textContent).toContain('Instruction Set #2');
  });

  it('openAssemblyInstructionsView switches view and renders comparison table and steps', async () => {
    mainModule.allItems.push(
      { id: 10, "Part Number": "10-00010", "Item description": "Parent Unit" },
      { id: 20, "Part Number": "20-00020", "Item description": "Child Item" }
    );

    await mainModule.openAssemblyInstructionsView(10, 1);

    expect(document.getElementById('assembly-instructions-view').style.display).toBe('block');
    expect(document.getElementById('instructions-set-title-badge').textContent).toBe('Set 1');

    const compList = document.getElementById('instructions-comparison-list');
    expect(compList.children.length).toBe(2);
    expect(compList.textContent).toContain('20-00020');
    expect(compList.textContent).toContain('Missing Instruction');

    const stepsList = document.getElementById('instruction-steps-container');
    expect(stepsList.children.length).toBe(1);
    expect(stepsList.textContent).toContain('Step 1');
    expect(stepsList.textContent).toContain('Solder 2x 20-00020 (Child Item) onto 10-00010 (Parent Unit) using 30-00030 (Tool Item)');
  });

  it('openInstructionStepModal populates dropdowns and sets live preview', async () => {
    await mainModule.openInstructionStepModal();

    const modal = document.getElementById('instruction-step-modal');
    expect(modal.style.display).toBe('flex');

    const childSelect = document.getElementById('step-input-child');
    expect(childSelect.children.length).toBeGreaterThan(0);

    const preview = document.getElementById('step-text-preview');
    expect(preview.textContent).not.toBe('-- Preview --');
  });

  describe('Item Picker Modal', () => {
    beforeEach(() => {
      // Clear values and state
      document.getElementById('picker-search-input').value = '';
      document.getElementById('step-input-child').value = '';
      document.getElementById('item-picker-modal').style.display = 'none';
      mainModule.allItems.length = 0;
      mainModule.allItems.push(
        { id: 10, "Part Number": "10-00010", "Item description": "Parent Unit" },
        { id: 20, "Part Number": "20-00020", "Item description": "Child Item" },
        { id: 30, "Part Number": "30-00030", "Item description": "Tool Item" }
      );
    });

    it('openItemPicker opens modal, populates quick choice children and renders search list', async () => {
      // Simulate viewing instructions for parent item 10
      await mainModule.openAssemblyInstructionsView(10, 1);
      
      await mainModule.openItemPicker('step-input-child');

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('flex');

      const selectChildren = document.getElementById('picker-select-children');
      expect(selectChildren.children.length).toBe(2); // Option 0: placeholder, Option 1: child item 20
      expect(selectChildren.children[1].textContent).toContain('20-00020');

      const itemsList = document.getElementById('picker-items-list');
      expect(itemsList.children.length).toBeGreaterThan(0);
      expect(itemsList.textContent).toContain('10-00010');
      expect(itemsList.textContent).toContain('20-00020');
      expect(itemsList.textContent).toContain('30-00030');
    });

    it('free text search filters the BOM table list', async () => {
      await mainModule.openItemPicker('step-input-child');
      
      const searchInput = document.getElementById('picker-search-input');
      searchInput.value = 'Tool';
      
      // Dispatch input event to trigger search filtering
      searchInput.dispatchEvent(new Event('input'));

      const itemsList = document.getElementById('picker-items-list');
      expect(itemsList.textContent).toContain('30-00030');
      expect(itemsList.textContent).not.toContain('10-00010');
    });

    it('selecting an item from search updates the target select and closes picker', async () => {
      await mainModule.openItemPicker('step-input-child');

      const itemsList = document.getElementById('picker-items-list');
      const selectBtn = itemsList.querySelector('button'); // First item's select button (Parent Unit)
      expect(selectBtn).not.toBeNull();

      selectBtn.click();

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('none');

      const childSelect = document.getElementById('step-input-child');
      expect(childSelect.value).toBe('10');
    });

    it('selecting from quick choice children select dropdown updates the target select and closes picker', async () => {
      await mainModule.openAssemblyInstructionsView(10, 1);
      await mainModule.openItemPicker('step-input-child');

      const selectChildren = document.getElementById('picker-select-children');
      selectChildren.value = '20';
      selectChildren.dispatchEvent(new Event('change'));

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('none');

      const childSelect = document.getElementById('step-input-child');
      expect(childSelect.value).toBe('20');
    });
  });
});
