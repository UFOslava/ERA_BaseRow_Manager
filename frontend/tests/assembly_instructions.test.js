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
    searchItems: vi.fn().mockImplementation(async (query) => {
      // Simulate Baserow's server-side search filtering
      const all = [
        { id: 10, "Part Number": "10-00010", "Item description": "Parent Unit" },
        { id: 20, "Part Number": "20-00020", "Item description": "Child Item" },
        { id: 30, "Part Number": "30-00030", "Item description": "Tool Item" }
      ];
      const q = query.toLowerCase();
      return all.filter(i =>
        (i["Part Number"] || '').toLowerCase().includes(q) ||
        (i["Item description"] || '').toLowerCase().includes(q)
      );
    }),
    createAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    updateAssembly: vi.fn().mockResolvedValue({ id: 99 }),
    deleteAssembly: vi.fn().mockResolvedValue({ status: 'success' }),
    createItem: vi.fn(),
    recategorizeItem: vi.fn(),
    fetchInstructionSets: vi.fn().mockResolvedValue([
      { set_index: 1, step_count: 2, is_balanced: true },
      { set_index: 2, step_count: 0, is_balanced: false }
    ]),
    fetchInstructionSetDetails: vi.fn().mockResolvedValue({
      steps: [
        {
          id: 101,
          set_index: 1,
          step_order: 1,
          action: 'Solder',
          quantity: 2,
          description: '{action} {a.1} onto {a.2} using {t.1}',
          photo: [],
          part_slots: [
            { id: 20, part_number: '20-00020', description: 'Child Item', quantity: 2 },
            { id: 10, part_number: '10-00010', description: 'Parent Unit', quantity: 1 }
          ],
          tool_slots: [
            { id: 30, part_number: '30-00030', description: 'Tool Item', quantity: 1 }
          ],
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
    deleteInstructionSet: vi.fn().mockResolvedValue({ status: 'success' }),
    fetchQuickActionTemplates: vi.fn().mockResolvedValue([
      {"action": "Solder", "template": "{action} {a.1} onto {a.2} using {t.1}"},
      {"action": "Fasten", "template": "{action} {a.1} to {a.2} using {t.1}"},
      {"action": "Mount", "template": "{action} {a.1} onto {a.2}"},
      {"action": "Glue", "template": "{action} {a.1} to {a.2} with {t.1}"},
      {"action": "Inspect", "template": "{action} {a.1} on {a.2}"}
    ]),
    saveQuickActionTemplates: vi.fn().mockResolvedValue({ status: 'success' }),
    fetchStates: vi.fn().mockResolvedValue({}),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
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
        <input type="checkbox" id="step-input-toll" />
        <button type="button" id="btn-add-action-item">Add Item</button>
        <div id="action-items-list-container"></div>
        <input type="hidden" id="step-input-child" />
        <input type="text" id="step-input-child-display" class="item-display-trigger" data-target="step-input-child" />
        <button type="button" class="btn-choose-item" data-target="step-input-child">Choose</button>
        <input type="hidden" id="step-input-receiving" />
        <input type="text" id="step-input-receiving-display" class="item-display-trigger" data-target="step-input-receiving" />
        <button type="button" class="btn-choose-item" data-target="step-input-receiving">Choose</button>
        <input type="hidden" id="step-input-tool" />
        <input type="text" id="step-input-tool-display" class="item-display-trigger" data-target="step-input-tool" />
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
        <div id="picker-children-grid"></div>
        <input type="text" id="picker-search-input" />
        <div id="picker-items-list"></div>
        <button id="btn-clear-item-picker"></button>
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

  it('evaluateInstructionText replaces placeholders correctly and ignores retired tokens', () => {
    const template = '{action}\n{a.1}\nonto {a.2}\nusing {t.1}\n{qty} {a} {b} {tool}';
    const result = mainModule.evaluateInstructionText(template, {
      action: 'Solder',
      partSlots: [
        { id: 20, description: 'Nova Amplifier Outer Shell', part_number: '30-00062', revision: 'A' },
        { id: 10, description: 'Main Logic Board', part_number: '20-00014', revision: 'B' }
      ],
      toolSlots: [
        { id: 30, description: 'Soldering Station', part_number: '90-00001', revision: 'A' }
      ]
    });

    expect(result).toBe(
      'Solder\n' +
      '"Nova Amplifier Outer Shell" (30-00062 Rev.A)\n' +
      'onto "Main Logic Board" (20-00014 Rev.B)\n' +
      'using "Soldering Station" (90-00001 Rev.A)\n' +
      '{qty} {a} {b} {tool}'
    );
  });

  it('evaluateInstructionText telegraphs length when slot has length > 0', () => {
    const template = '{action} {a.1}';
    const result = mainModule.evaluateInstructionText(template, {
      action: 'Cut',
      partSlots: [
        { id: 20, description: 'Teflon Tape', part_number: '10-00007', revision: 'A', length: 100, uom_symbol: 'mm' }
      ]
    });

    expect(result).toBe('Cut "Teflon Tape" (10-00007 Rev.A (100mm))');
  });

  it('loadInstructionSetsForItem fetches and renders sets list with scale status icons', async () => {
    await mainModule.loadInstructionSetsForItem(10);
    const container = document.getElementById('instruction-sets-list');
    expect(container.children.length).toBe(2);
    expect(container.textContent).toContain('Instruction Set #1');
    expect(container.textContent).toContain('Instruction Set #2');

    const icons = container.querySelectorAll('.scale-status-icon');
    expect(icons.length).toBe(2);
    // First set is balanced -> green fa-scale-balanced
    expect(icons[0].classList.contains('fa-scale-balanced')).toBe(true);
    expect(icons[0].style.color).toBe('rgb(74, 222, 128)');
    // Second set is unbalanced -> red fa-scale-unbalanced
    expect(icons[1].classList.contains('fa-scale-unbalanced')).toBe(true);
    expect(icons[1].style.color).toBe('rgb(248, 113, 113)');
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
    expect(compList.textContent).toContain('Remove Dependency');

    const stepsList = document.getElementById('instruction-steps-container');
    expect(stepsList.children.length).toBe(3);
    expect(stepsList.textContent).toContain('Step 1');
    expect(stepsList.textContent).toContain('Solder 2x "Child Item" (20-00020) onto "Parent Unit" (10-00010) using "Tool Item" (30-00030)');
  });

  it('openInstructionStepModal sets values and display texts, and sets live preview', async () => {
    const step = {
      id: 101,
      action: 'Solder',
      quantity: 2,
      description: '{action} {a.1} onto {a.2} using {t.1}',
      child_item: { id: 20, part_number: '20-00020', description: 'Child Item' },
      receiving_item: { id: 10, part_number: '10-00010', description: 'Parent Unit' },
      tool: { id: 30, part_number: '30-00030', description: 'Tool Item' }
    };
    await mainModule.openInstructionStepModal(step);

    const modal = document.getElementById('instruction-step-modal');
    expect(modal.style.display).toBe('flex');

    expect(mainModule.currentActionItems.length).toBe(1);
    expect(mainModule.currentActionItems[0].id).toBe(20);
    expect(mainModule.currentActionItems[0].part_number).toBe('20-00020');

    const preview = document.getElementById('step-text-preview');
    expect(preview.textContent).not.toBe('-- Preview --');

    // Test with step containing length
    const stepWithLength = {
      id: 102,
      action: 'Wrap',
      quantity: 1,
      description: '{action} {a.1}',
      part_slots: [{ id: 20, part_number: '20-00020', description: 'Teflon Tape', length: 100, uom_symbol: 'mm' }]
    };
    await mainModule.openInstructionStepModal(stepWithLength);
    const actionItemsContainer = document.getElementById('action-items-list-container');
    expect(actionItemsContainer.textContent).toContain('100mm');
    expect(actionItemsContainer.textContent).toContain('(100mm)');
  });

  describe('Item Picker Modal', () => {
    beforeEach(() => {
      // Reset picker state
      document.getElementById('picker-search-input').value = '';
      document.getElementById('item-picker-modal').style.display = 'none';
      mainModule.allItems.length = 0;
      mainModule.allItems.push(
        { id: 10, "Part Number": "10-00010", "Item description": "Parent Unit" },
        { id: 20, "Part Number": "20-00020", "Item description": "Child Item" },
        { id: 30, "Part Number": "30-00030", "Item description": "Tool Item" }
      );
    });

    it('openItemPicker opens modal, populates quick choice children, and shows search prompt (no full BOM load)', async () => {
      await mainModule.openAssemblyInstructionsView(10, 1);
      await mainModule.openItemPicker('step-input-child');

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('flex');

      const pickerChildrenGrid = document.getElementById('picker-children-grid');
      expect(pickerChildrenGrid.children.length).toBe(2); // hierarchy items 20 and 40
      expect(pickerChildrenGrid.children[0].textContent).toContain('20-00020');
      expect(pickerChildrenGrid.children[1].textContent).toContain('40-00040');

      // Search prompt shown instead of full list
      const itemsList = document.getElementById('picker-items-list');
      expect(itemsList.textContent).toContain('3 characters');
    });

    it('free text search with ≥3 chars calls searchItems and renders results', async () => {
      const { searchItems } = await import('../src/api.js');
      await mainModule.openItemPicker('step-input-child');

      const searchInput = document.getElementById('picker-search-input');
      searchInput.value = 'Tool';
      searchInput.dispatchEvent(new Event('input'));

      // Wait for debounce (300ms) + async search to complete
      await new Promise(r => setTimeout(r, 400));

      expect(searchItems).toHaveBeenCalledWith('Tool', 200);

      const itemsList = document.getElementById('picker-items-list');
      expect(itemsList.textContent).toContain('30-00030');
      expect(itemsList.textContent).not.toContain('10-00010');
    });

    it('search with fewer than 3 chars shows typing hint and does not call searchItems', async () => {
      const { searchItems } = await import('../src/api.js');
      await mainModule.openItemPicker('step-input-child');

      const searchInput = document.getElementById('picker-search-input');
      searchInput.value = 'To';
      searchInput.dispatchEvent(new Event('input'));

      await new Promise(r => setTimeout(r, 400));

      expect(searchItems).not.toHaveBeenCalled();
      const itemsList = document.getElementById('picker-items-list');
      expect(itemsList.textContent).toContain('1 more character');
    });

    it('selecting an item from search results closes picker', async () => {
      await mainModule.openItemPicker('step-input-child');

      // Trigger a search to populate the list
      const searchInput = document.getElementById('picker-search-input');
      searchInput.value = 'Par';
      searchInput.dispatchEvent(new Event('input'));
      await new Promise(r => setTimeout(r, 400));

      const itemsList = document.getElementById('picker-items-list');
      const selectBtn = itemsList.querySelector('button');
      expect(selectBtn).not.toBeNull();
      selectBtn.click();

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('none');
    });

    it('selecting from quick choice children select dropdown updates the target select and closes picker', async () => {
      await mainModule.openAssemblyInstructionsView(10, 1);
      await mainModule.openItemPicker('step-input-child');

      const grid = document.getElementById('picker-children-grid');
      const card = grid.querySelector('.picker-child-card');
      expect(card).not.toBeNull();
      card.click();

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('none');

      const childSelect = document.getElementById('step-input-child');
      expect(childSelect.value).toBe('20');
    });

    it('selecting from quick choice for action item slot defaults quantity to 1 regardless of required_qty', async () => {
      await mainModule.openAssemblyInstructionsView(10, 1);
      mainModule.currentActionItems.length = 0;
      await mainModule.openItemPicker('add-action-item-slot');

      const grid = document.getElementById('picker-children-grid');
      const cards = grid.querySelectorAll('.picker-child-card');
      // Second card is 40-00040 with required_qty: 4
      expect(cards.length).toBeGreaterThanOrEqual(2);
      cards[1].click();

      expect(mainModule.currentActionItems.length).toBe(1);
      expect(mainModule.currentActionItems[0].id).toBe(40);
      expect(mainModule.currentActionItems[0].quantity).toBe(1);
    });

    it('clicking clear selection button resets target select input to empty and closes picker', async () => {
      const targetSelect = document.getElementById('step-input-tool');
      targetSelect.value = '30';

      await mainModule.openItemPicker('step-input-tool');

      const clearBtn = document.getElementById('btn-clear-item-picker');
      expect(clearBtn).not.toBeNull();
      clearBtn.click();

      const modal = document.getElementById('item-picker-modal');
      expect(modal.style.display).toBe('none');
      expect(targetSelect.value).toBe('');
      expect(document.getElementById('step-input-tool-display').value).toBe('');
    });
  });

  describe('Toll and Step Insertion in instructions set editor', () => {
    it('sets step-input-toll checked state depending on editing step properties', async () => {
      const step = {
        id: 101,
        action: 'Solder',
        quantity: 2,
        description: 'Solder step',
        child_item: { id: 20, part_number: '20-00020', description: 'Child Item' },
        receiving_item: { id: 10, part_number: '10-00010', description: 'Parent Unit' },
        toll: false
      };
      
      await mainModule.openInstructionStepModal(step);
      expect(mainModule.currentActionItems[0].toll).toBe(false);

      await mainModule.openInstructionStepModal(null); // Add mode
      expect(mainModule.currentActionItems.length).toBe(0);
    });

    it('submits toll value in payload when saving step', async () => {
      const api = await import('../src/api.js');
      api.createInstructionStep.mockReset();

      await mainModule.openAssemblyInstructionsView(10, 1);
      await mainModule.openInstructionStepModal(null); // Add mode

      // Populate current action items mock list since we overhauled input
      mainModule.currentActionItems.length = 0;
      mainModule.currentActionItems.push({
        id: 20,
        part_number: '20-00020',
        description: 'Child Item',
        toll: false
      });

      document.getElementById('step-input-action').value = 'Prepare';
      document.getElementById('step-input-qty').value = '1';
      document.getElementById('step-input-description').value = 'Prepare {child}';

      const btnSave = document.getElementById('btn-save-instruction-step');
      btnSave.click();

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(api.createInstructionStep).toHaveBeenCalledWith(10, 1, expect.objectContaining({
        action: 'Prepare',
        child_item_id: 20,
        description: 'Prepare {child}',
        toll_map: JSON.stringify([{
          edge_id: null,
          item_id: 20,
          toll: false,
          qty: 1,
          length: 0
        }])
      }));
    });

    it('correctly inserts step at specific index and calls reorderInstructionSteps', async () => {
      const api = await import('../src/api.js');
      api.createInstructionStep.mockReset();
      api.reorderInstructionSteps.mockReset();
      
      // Setup current steps
      mainModule.currentInstructionSteps.length = 0;
      mainModule.currentInstructionSteps.push(
        { id: 101, step_order: 1 },
        { id: 102, step_order: 2 }
      );

      // Trigger insert at index 1 (between step 1 and step 2)
      await mainModule.openInstructionStepModal(null, 1);

      mainModule.currentActionItems.length = 0;
      mainModule.currentActionItems.push({
        id: 20,
        part_number: '20-00020',
        description: 'Child Item',
        toll: true
      });
      
      // Mock createInstructionStep to return step 103
      api.createInstructionStep.mockResolvedValueOnce({ id: 103 });

      const btnSave = document.getElementById('btn-save-instruction-step');
      btnSave.click();

      await new Promise(resolve => setTimeout(resolve, 50));

      expect(api.createInstructionStep).toHaveBeenCalled();
      // Should reorder with 103 inserted at index 1: [101, 103, 102]
      expect(api.reorderInstructionSteps).toHaveBeenCalledWith(10, 1, [101, 103, 102]);
    });

    it('correctly duplicates step and inserts it below source step', async () => {
      const api = await import('../src/api.js');
      api.createInstructionStep.mockReset();
      api.reorderInstructionSteps.mockReset();

      mainModule.currentInstructionParentId = 10;
      mainModule.currentInstructionSetIndex = 1;
      mainModule.currentInstructionSteps.length = 0;
      mainModule.currentInstructionSteps.push(
        {
          id: 101,
          step_order: 1,
          action: 'Solder',
          quantity: 2,
          description: 'Solder step',
          child_items: [{ id: 20, part_number: '20-00020', description: 'Child' }],
          receiving_item: { id: 10 },
          tool: null,
          toll: true,
          toll_map: '{}',
          photo: []
        },
        {
          id: 102,
          step_order: 2,
          action: 'Fasten',
          quantity: 4,
          description: 'Fasten step',
          child_items: [{ id: 30, part_number: '30-00030', description: 'Child2' }],
          receiving_item: { id: 10 },
          tool: null,
          toll: true,
          toll_map: '{}',
          photo: []
        }
      );

      await mainModule.renderInstructionSetDetailsView();

      const stepCards = document.querySelectorAll('.instruction-step-card');
      expect(stepCards.length).toBe(2);

      const btnDuplicate = stepCards[0].querySelector('.btn-duplicate-step');
      expect(btnDuplicate).not.toBeNull();

      api.createInstructionStep.mockResolvedValueOnce({ id: 103 });

      btnDuplicate.click();
      await new Promise(resolve => setTimeout(resolve, 50));

      expect(api.createInstructionStep).toHaveBeenCalledWith(10, 1, expect.objectContaining({
        action: 'Solder',
        description: 'Solder step'
      }));

      expect(api.reorderInstructionSteps).toHaveBeenCalledWith(10, 1, [101, 103, 102]);
    });

    it('groups derived dependencies under sub-assembly headers and prompts Blackbox toggle', async () => {
      const api = await import('../src/api.js');
      mainModule.currentInstructionParentId = 10;
      mainModule.currentInstructionSetIndex = 1;

      api.fetchInstructionSetDetails.mockResolvedValueOnce({
        steps: [],
        sub_assemblies: [
          { id: 50, part_number: '50-00001 Rev.A', description: 'Nova Handle', blackbox: false }
        ],
        comparison: [
          {
            item_id: 20,
            part_number: '20-00020 Rev.A',
            description: 'Direct Part',
            required_qty: 2,
            instructed_qty: 2,
            discrepancy: 'OK',
            in_hierarchy: true,
            is_derived: false
          },
          {
            item_id: 60,
            part_number: '20-00031 Rev.A',
            description: 'Sub-assembly Part',
            required_qty: 4,
            instructed_qty: 2,
            discrepancy: 'Under-instructed',
            in_hierarchy: true,
            is_derived: true,
            parent_id: 50,
            parent_pn: '50-00001 Rev.A',
            parent_description: 'Nova Handle',
            parent_blackbox: false,
            edge_id: 205,
            unit_qty: 2,
            length: 0,
            pcb_symbol: 'R1'
          }
        ]
      });

      await mainModule.renderInstructionSetDetailsView();

      const comparisonList = document.getElementById('instructions-comparison-list');
      expect(comparisonList).not.toBeNull();
      
      const subAssyGroup = comparisonList.querySelector('.subassembly-comparison-group');
      expect(subAssyGroup).not.toBeNull();
      expect(subAssyGroup.textContent).toContain('50-00001 Rev.A');
      expect(subAssyGroup.textContent).toContain('Nova Handle');
      expect(subAssyGroup.textContent).toContain('20-00031 Rev.A');

      const btnBlackbox = subAssyGroup.querySelector('.btn-toggle-blackbox');
      expect(btnBlackbox).not.toBeNull();

      // Click Blackbox button
      btnBlackbox.click();

      // Confirm modal should be open
      const confirmTitle = document.getElementById('confirm-modal-title');
      expect(confirmTitle.textContent).toBe('Toggle Blackbox Flag');

      const btnAccept = document.getElementById('btn-confirm-accept');
      expect(btnAccept).not.toBeNull();
      btnAccept.click();

      await new Promise(resolve => setTimeout(resolve, 50));
      expect(api.updateItem).toHaveBeenCalledWith(50, { Blackbox: true });
    });

    it('renders target assembly dropdown for items not in hierarchy', async () => {
      const api = await import('../src/api.js');
      mainModule.currentInstructionParentId = 10;
      mainModule.currentInstructionSetIndex = 1;

      api.fetchInstructionSetDetails.mockResolvedValueOnce({
        steps: [],
        sub_assemblies: [
          { id: 50, part_number: '50-00001 Rev.A', description: 'Nova Handle', blackbox: false }
        ],
        comparison: [
          {
            item_id: 99,
            part_number: '99-00099 Rev.A',
            description: 'Extra Screw',
            required_qty: 0,
            instructed_qty: 3,
            discrepancy: 'Not in Hierarchy',
            in_hierarchy: false,
            is_derived: false
          }
        ]
      });

      await mainModule.renderInstructionSetDetailsView();

      const comparisonList = document.getElementById('instructions-comparison-list');
      const selectEl = comparisonList.querySelector('.target-parent-select');
      expect(selectEl).not.toBeNull();
      expect(selectEl.options.length).toBe(2);
      expect(selectEl.options[1].value).toBe('50');

      // Select sub-assembly 50 and click add
      selectEl.value = '50';
      const btnAdd = comparisonList.querySelector('.btn-quick-link');
      expect(btnAdd).not.toBeNull();
      btnAdd.click();

      await new Promise(resolve => setTimeout(resolve, 50));
      expect(api.createAssembly).toHaveBeenCalledWith(50, 99, 3, 0, 'N/A');
    });
  });
});
