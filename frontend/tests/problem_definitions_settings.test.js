import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/api.js', () => ({
  fetchRules: vi.fn().mockResolvedValue({}),
  saveRules: vi.fn().mockResolvedValue({}),
  fetchProblemDefinitions: vi.fn().mockResolvedValue([
    {
      id: 'rule_test_1',
      name: 'Production item without assembly',
      rule: {
        type: 'AND',
        conditions: [
          { field: 'State', operator: 'equals', value: 'Production Use' },
          { field: 'is_in_assembly', operator: 'equals', value: 'false' }
        ]
      }
    }
  ]),
  saveProblemDefinitions: vi.fn().mockResolvedValue({ status: 'success' }),
  getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  fetchProblemDefinitionCount: vi.fn().mockResolvedValue({ count: 0, status: 'idle' }),
  triggerRescan: vi.fn(),
  fetchScanStatus: vi.fn().mockResolvedValue({ status: 'idle' }),
  fetchLogsConfig: vi.fn().mockResolvedValue({}),
  saveLogsConfig: vi.fn().mockResolvedValue({}),
  fetchActiveLog: vi.fn().mockResolvedValue({ lines: [] }),
  fetchQuickActionTemplates: vi.fn().mockResolvedValue([]),
  saveQuickActionTemplates: vi.fn().mockResolvedValue({ status: 'success' }),
  fetchWiTemplates: vi.fn().mockResolvedValue([]),
  uploadWiTemplate: vi.fn(),
  replaceWiTemplate: vi.fn(),
  deleteWiTemplate: vi.fn(),
  fetchWiConfig: vi.fn().mockResolvedValue({ filename_pattern: 'test' }),
  saveWiConfig: vi.fn().mockResolvedValue({}),
  approveWiTemplate: vi.fn()
}));

describe('Problem Definitions Tab Settings & Rule Builder', () => {
  let settingsModule;

  beforeEach(async () => {
    document.body.innerHTML = `
      <div id="tab-problems" class="tab-content">
        <div id="problems-editor-container" class="problems-editor-container"></div>
        <button id="btn-add-problem">+ Add New Problem Definition</button>
        <button id="btn-save-settings">Save Changes</button>
        <button id="btn-revert-settings">Revert Changes</button>
      </div>
      <div id="toast-container"></div>
    `;

    vi.clearAllMocks();
    settingsModule = await import('../src/settings.js');
    settingsModule.init();
    await settingsModule.loadSettingsData();
  });

  it('renders problem definitions cards and expands card on click', () => {
    const container = document.getElementById('problems-editor-container');
    const cards = container.querySelectorAll('.problem-def-card');
    expect(cards.length).toBe(1);
    expect(cards[0].classList.contains('collapsed')).toBe(true);

    // Expand the card
    const header = cards[0].querySelector('.problem-def-header');
    header.click();

    const expandedCards = container.querySelectorAll('.problem-def-card.expanded');
    expect(expandedCards.length).toBe(1);
  });

  it('replaces value text field with drop-down selector when variable is a list (State, Sourced By)', () => {
    const container = document.getElementById('problems-editor-container');
    // Expand card
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    expect(condElements.length).toBe(2);

    // First condition is 'State' (a select/list variable)
    const firstCond = condElements[0];
    const fieldSelect1 = firstCond.querySelector('.cond-field-select');
    expect(fieldSelect1.value).toBe('State');

    const valueSelect = firstCond.querySelector('select.cond-value-select');
    expect(valueSelect).not.toBeNull();
    expect(valueSelect.value).toBe('Production Use');
    
    // Check State options
    const options = Array.from(valueSelect.options).map(o => o.value);
    expect(options).toContain('Production Use');
    expect(options).toContain('Engineerig Use');
    expect(options).toContain('Unknown');
    expect(options).toContain('Finish Stock (Use Up)');
    expect(options).toContain('EOL');
    expect(options).toContain('Do Not Use (Discard)');

    // Change field to Sourced By
    fieldSelect1.value = 'Sourced By';
    fieldSelect1.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const sourcedBySelect = updatedCond.querySelector('select.cond-value-select');
    expect(sourcedBySelect).not.toBeNull();
    const sourcedOptions = Array.from(sourcedBySelect.options).map(o => o.value);
    expect(sourcedOptions).toContain('Purchased by Contractor');
    expect(sourcedOptions).toContain('Produced by ERA');
    expect(sourcedOptions).toContain('TBD');
  });

  it('renders a themed toggle switch for true/false binary flags (is_in_assembly, has_children)', () => {
    const container = document.getElementById('problems-editor-container');
    // Expand card
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    // Second condition is 'is_in_assembly' (binary hook with value 'false')
    const secondCond = condElements[1];
    const fieldSelect2 = secondCond.querySelector('.cond-field-select');
    expect(fieldSelect2.value).toBe('is_in_assembly');

    const toggleWrapper = secondCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput).not.toBeNull();
    expect(toggleInput.type).toBe('checkbox');
    expect(toggleInput.checked).toBe(false);

    const toggleText = toggleWrapper.querySelector('.theme-toggle-text');
    expect(toggleText.textContent).toBe('FALSE');

    // Toggle switch to true
    toggleInput.checked = true;
    toggleInput.dispatchEvent(new Event('change'));
    expect(toggleText.textContent).toBe('TRUE');
  });

  it('supports "External PN" hook with a testable text input field', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to External PN
    fieldSelect.value = 'External PN';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const valInput = updatedCond.querySelector('input.cond-value-input');
    expect(valInput).not.toBeNull();
    expect(valInput.type).toBe('text');

    valInput.value = 'EXT-5544';
    valInput.dispatchEvent(new Event('input'));
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('EXT-5544');
    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('External PN');
  });

  it('supports "Has children" binary hook with a themed toggle switch', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to has_children
    fieldSelect.value = 'has_children';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const toggleWrapper = updatedCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput.checked).toBe(true); // default for new binary switch is true

    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('has_children');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('true');
  });

  it('supports "Blackbox" binary hook with a themed toggle switch', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to Blackbox
    fieldSelect.value = 'Blackbox';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const toggleWrapper = updatedCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput.checked).toBe(true);

    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('Blackbox');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('true');
  });

  it('supports "Has photos" binary hook with a themed toggle switch', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to has_photos
    fieldSelect.value = 'has_photos';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const toggleWrapper = updatedCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput.checked).toBe(true);

    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('has_photos');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('true');
  });

  it('supports "BOM equilibrium (balance)" binary hook with a themed toggle switch', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to bom_equilibrium
    fieldSelect.value = 'bom_equilibrium';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const toggleWrapper = updatedCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput.checked).toBe(true);

    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('bom_equilibrium');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('true');
  });

  it('supports "Has all images" binary hook with a themed toggle switch', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to has_all_images
    fieldSelect.value = 'has_all_images';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const toggleWrapper = updatedCond.querySelector('.cond-toggle-wrapper');
    expect(toggleWrapper).not.toBeNull();

    const toggleInput = toggleWrapper.querySelector('input.cond-toggle-input');
    expect(toggleInput.checked).toBe(true);

    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('has_all_images');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('true');
  });

  it('supports "Price per unit" numeric hook with number input and numeric comparison operators', () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const condElements = container.querySelectorAll('.rule-condition');
    const firstCond = condElements[0];
    const fieldSelect = firstCond.querySelector('.cond-field-select');

    // Switch to Price per unit
    fieldSelect.value = 'Price per unit';
    fieldSelect.dispatchEvent(new Event('change'));

    const updatedCond = container.querySelectorAll('.rule-condition')[0];
    const opSelect = updatedCond.querySelector('.cond-operator-select');
    expect(opSelect).not.toBeNull();

    // Verify numeric operators are populated
    const opValues = Array.from(opSelect.options).map(o => o.value);
    expect(opValues).toContain('greater_than');
    expect(opValues).toContain('less_than');
    expect(opValues).toContain('greater_than_or_equal');
    expect(opValues).toContain('less_than_or_equal');

    // Set operator to greater_than
    opSelect.value = 'greater_than';
    opSelect.dispatchEvent(new Event('change'));
    expect(settingsModule.currentDefs[0].rule.conditions[0].operator).toBe('greater_than');

    // Verify input type is number
    const numInput = updatedCond.querySelector('input.cond-value-input');
    expect(numInput).not.toBeNull();
    expect(numInput.type).toBe('number');

    numInput.value = '15.75';
    numInput.dispatchEvent(new Event('input'));
    expect(settingsModule.currentDefs[0].rule.conditions[0].field).toBe('Price per unit');
    expect(settingsModule.currentDefs[0].rule.conditions[0].value).toBe('15.75');
  });

  it('allows adding a condition and saving problem definitions', async () => {
    const container = document.getElementById('problems-editor-container');
    container.querySelector('.problem-def-header').click();

    const addCondBtn = container.querySelector('.rule-group-actions button');
    addCondBtn.click();

    const condElements = container.querySelectorAll('.rule-condition');
    expect(condElements.length).toBe(3);

    // Save changes
    const { saveProblemDefinitions } = await import('../src/api.js');
    await settingsModule.saveSettingsChanges();
    expect(saveProblemDefinitions).toHaveBeenCalled();
  });
});
