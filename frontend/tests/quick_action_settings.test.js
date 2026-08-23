import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/api.js', () => ({
  fetchRules: vi.fn().mockResolvedValue({}),
  saveRules: vi.fn().mockResolvedValue({}),
  fetchProblemDefinitions: vi.fn().mockResolvedValue([]),
  saveProblemDefinitions: vi.fn().mockResolvedValue({}),
  getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
  fetchProblemDefinitionCount: vi.fn().mockResolvedValue({ count: 0, status: 'idle' }),
  triggerRescan: vi.fn(),
  fetchScanStatus: vi.fn().mockResolvedValue({ status: 'idle' }),
  fetchLogsConfig: vi.fn().mockResolvedValue({}),
  saveLogsConfig: vi.fn().mockResolvedValue({}),
  fetchActiveLog: vi.fn().mockResolvedValue({ lines: [] }),
  fetchQuickActionTemplates: vi.fn().mockResolvedValue([
    { action: 'Solder', template: '{action} {a.1} onto {a.2} using {t.1}' },
    { action: 'Fasten', template: '{action} {a.1} to {a.2} using {t.1}' }
  ]),
  saveQuickActionTemplates: vi.fn().mockResolvedValue({ status: 'success' }),
  fetchWiTemplates: vi.fn().mockResolvedValue([]),
  uploadWiTemplate: vi.fn(),
  replaceWiTemplate: vi.fn(),
  deleteWiTemplate: vi.fn(),
  fetchWiConfig: vi.fn().mockResolvedValue({ filename_pattern: 'test' }),
  saveWiConfig: vi.fn().mockResolvedValue({}),
  approveWiTemplate: vi.fn(),
  fetchAuthStatus: vi.fn().mockResolvedValue({ is_complete: true }),
  fetchAuthConfig: vi.fn().mockResolvedValue({ tables: {} }),
  testAuthConfig: vi.fn().mockResolvedValue({ is_complete: true }),
  saveAuthConfig: vi.fn().mockResolvedValue({ success: true, schema: { tables: {} } }),
  checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
}));

describe('Quick Action Templates Settings Tab', () => {
  let settingsModule;

  beforeEach(async () => {
    document.body.innerHTML = `
      <div id="tab-templates" class="tab-content">
        <p class="tab-description">Define preset action strings and description templates. Supported variables: {action}, {a.1}, {a.2}..., {t.1}, {t.2}...</p>
        <div id="templates-editor-container"></div>
        <button id="btn-add-template">+ Add New Template</button>
        <button id="btn-save-settings">Save Changes</button>
        
        <input type="text" id="test-input-action" value="Solder">
        <input type="text" id="test-input-t1" value='"Soldering Station" (90-00001 Rev.A)'>
        <input type="text" id="test-input-a1" value='"Nova Amplifier Outer Shell" (30-00062 Rev.A)'>
        <input type="text" id="test-input-a2" value='"Main Logic Board" (20-00014 Rev.A)'>
        <div id="test-template-preview-box"></div>
      </div>
      <div id="toast-container"></div>
    `;

    vi.clearAllMocks();
    settingsModule = await import('../src/settings.js');
    settingsModule.init();
    await settingsModule.loadSettingsData();
  });

  it('renders quick action templates as cards with multiline textareas', () => {
    const container = document.getElementById('templates-editor-container');
    const rows = container.querySelectorAll('.template-rule-row');
    expect(rows.length).toBe(2);

    const firstTextarea = rows[0].querySelector('textarea');
    expect(firstTextarea).not.toBeNull();
    expect(firstTextarea.value).toBe('{action} {a.1} onto {a.2} using {t.1}');
    expect(firstTextarea.placeholder).toContain('{action} {a.1}');
  });

  it('evaluates live preview with actual BOM format examples and respects newlines', () => {
    const previewBox = document.getElementById('test-template-preview-box');
    expect(previewBox.textContent).toBe(
      'Solder "Nova Amplifier Outer Shell" (30-00062 Rev.A) onto "Main Logic Board" (20-00014 Rev.A) using "Soldering Station" (90-00001 Rev.A)'
    );

    // Update the template with multiple lines and test tokens
    const container = document.getElementById('templates-editor-container');
    const firstTextarea = container.querySelector('textarea');
    firstTextarea.value = 'Step 1: {action}\nItem: {a.1}\nTarget: {a.2}\nTool: {t.1}\nRetired: {qty} {a} {b} {tool}';
    firstTextarea.dispatchEvent(new Event('input'));

    expect(previewBox.textContent).toBe(
      'Step 1: Solder\nItem: "Nova Amplifier Outer Shell" (30-00062 Rev.A)\nTarget: "Main Logic Board" (20-00014 Rev.A)\nTool: "Soldering Station" (90-00001 Rev.A)\nRetired: {qty} {a} {b} {tool}'
    );
  });

  it('updates live preview when test input fields change', () => {
    const a1Input = document.getElementById('test-input-a1');
    a1Input.value = '"Power Distribution Board" (10-00099 Rev.C)';
    a1Input.dispatchEvent(new Event('input'));

    const previewBox = document.getElementById('test-template-preview-box');
    expect(previewBox.textContent).toContain('"Power Distribution Board" (10-00099 Rev.C)');
  });

  it('allows adding a new template and saving templates', async () => {
    const addBtn = document.getElementById('btn-add-template');
    addBtn.click();

    const container = document.getElementById('templates-editor-container');
    const rows = container.querySelectorAll('.template-rule-row');
    expect(rows.length).toBe(3);

    const newRowTextarea = rows[2].querySelector('textarea');
    expect(newRowTextarea.value).toBe('{action} {a.1} onto {a.2}');

    const saveBtn = document.getElementById('btn-save-settings');
    await settingsModule.saveSettingsChanges();

    const { saveQuickActionTemplates } = await import('../src/api.js');
    expect(saveQuickActionTemplates).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ action: 'New Action', template: '{action} {a.1} onto {a.2}' })
      ])
    );
  });

  it('allows deleting a template', () => {
    const container = document.getElementById('templates-editor-container');
    const firstDelBtn = container.querySelector('.btn-delete-cond-btn');
    firstDelBtn.click();

    const rows = container.querySelectorAll('.template-rule-row');
    expect(rows.length).toBe(1);
  });
});
