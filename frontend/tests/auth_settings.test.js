import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockAuthConfig = {
  is_complete: true,
  is_connected: true,
  connection_message: 'Baserow server reached successfully.',
  token_valid: true,
  token_warning: null,
  jwt_provided: true,
  jwt_valid: true,
  jwt_message: 'JWT Admin credentials authenticated successfully.',
  api_url: 'http://localhost:7070',
  host: 'http://localhost',
  port: '7070',
  database_id: '1',
  tables: {
    'BOM': {
      name: 'BOM',
      env_var: 'BASEROW_TABLE_BOM',
      id: '508',
      found: true,
      all_fields_found: true,
      fields: [
        { name: 'Part Number', type: 'text', primary: true, id: 101, found: true },
        { name: 'Item description', type: 'text', primary: false, id: 102, found: true }
      ]
    },
    'Assembly': {
      name: 'Assembly',
      env_var: 'BASEROW_TABLE_ASSEMBLY',
      id: '701',
      found: true,
      all_fields_found: true,
      fields: [
        { name: 'Item', type: 'link_row', primary: true, id: 201, found: true },
        { name: 'Contains', type: 'link_row', primary: false, id: 202, found: true }
      ]
    }
  },
  all_tables_found: true,
  all_fields_found: true
};

const mockAuthStatus = {
  is_complete: true,
  is_connected: true,
  token_valid: true,
  token_warning: null,
  missing: [],
  api_url: 'http://localhost:7070',
  host: 'http://localhost',
  port: '7070',
  database_id: '1',
  has_admin_credentials: true
};

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
  fetchQuickActionTemplates: vi.fn().mockResolvedValue([]),
  saveQuickActionTemplates: vi.fn().mockResolvedValue({ status: 'success' }),
  fetchWiTemplates: vi.fn().mockResolvedValue([]),
  uploadWiTemplate: vi.fn(),
  replaceWiTemplate: vi.fn(),
  deleteWiTemplate: vi.fn(),
  fetchWiConfig: vi.fn().mockResolvedValue({ filename_pattern: 'test' }),
  saveWiConfig: vi.fn().mockResolvedValue({}),
  approveWiTemplate: vi.fn(),
  fetchAuthStatus: vi.fn().mockResolvedValue(mockAuthStatus),
  fetchAuthConfig: vi.fn().mockResolvedValue(mockAuthConfig),
  testAuthConfig: vi.fn().mockResolvedValue(mockAuthConfig),
  saveAuthConfig: vi.fn().mockResolvedValue({ success: true, schema: mockAuthConfig }),
  checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: mockAuthStatus })
}));

describe('Authentication Settings Tab', () => {
  let settingsModule;
  let apiModule;

  beforeEach(async () => {
    document.body.innerHTML = `
      <header class="app-header">
        <div class="header-container">
          <div class="api-status">
            <span class="status-indicator" id="status-indicator"></span>
            <span id="status-text">Connecting...</span>
          </div>
        </div>
      </header>

      <ul class="settings-tabs">
        <li class="tab-item active" data-tab="auth" id="tab-nav-auth">
          Authentication
          <span id="auth-nav-warning" class="status-warning-badge" style="display: none;">!</span>
        </li>
        <li class="tab-item" data-tab="categories">PN Categories</li>
      </ul>

      <div class="tab-content" id="tab-auth">
        <input type="text" id="auth-input-host" value="">
        <input type="text" id="auth-input-port" value="">
        <input type="password" id="auth-input-token" value="">
        <button id="btn-toggle-token"></button>
        <div id="auth-token-warning" style="display: none;">
          <span id="auth-token-warning-text"></span>
        </div>

        <input type="email" id="auth-input-email" value="">
        <input type="password" id="auth-input-password" value="">
        <button id="btn-toggle-password"></button>

        <input type="text" id="auth-input-db-id" value="">
        <div id="auth-overall-schema-badge"></div>

        <button id="btn-auth-test">Test Connection</button>
        <button id="btn-auth-save">Save & Validate</button>

        <div id="auth-tables-container"></div>
      </div>
      <div id="toast-container"></div>
    `;

    vi.clearAllMocks();
    apiModule = await import('../src/api.js');
    settingsModule = await import('../src/settings.js');
  });

  it('initializes and populates form fields with loaded auth config', async () => {
    settingsModule.initAuthTab();
    await settingsModule.loadAuthConfig();

    expect(document.getElementById('auth-input-host').value).toBe('http://localhost');
    expect(document.getElementById('auth-input-port').value).toBe('7070');
    expect(document.getElementById('auth-input-db-id').value).toBe('1');
  });

  it('toggles password visibility for token and admin password fields', () => {
    settingsModule.initAuthTab();

    const tokenInput = document.getElementById('auth-input-token');
    const tokenToggle = document.getElementById('btn-toggle-token');
    expect(tokenInput.type).toBe('password');

    tokenToggle.click();
    expect(tokenInput.type).toBe('text');

    tokenToggle.click();
    expect(tokenInput.type).toBe('password');

    const pwInput = document.getElementById('auth-input-password');
    const pwToggle = document.getElementById('btn-toggle-password');
    expect(pwInput.type).toBe('password');

    pwToggle.click();
    expect(pwInput.type).toBe('text');
  });

  it('renders required tables and their field badges with status checkmarks', () => {
    settingsModule.renderAuthTables(mockAuthConfig.tables);

    const container = document.getElementById('auth-tables-container');
    const cards = container.querySelectorAll('.auth-table-card');
    expect(cards.length).toBe(2);

    expect(cards[0].textContent).toContain('BOM');
    expect(cards[0].textContent).toContain('Part Number');
    expect(cards[0].textContent).toContain('Item description');
    expect(cards[1].textContent).toContain('Assembly');
  });

  it('handles Test Connection click and sends form payload', async () => {
    settingsModule.initAuthTab();
    document.getElementById('auth-input-host').value = 'http://127.0.0.1';
    document.getElementById('auth-input-port').value = '7070';
    document.getElementById('auth-input-token').value = 'test_tok';

    await settingsModule.handleTestAuth();
    expect(apiModule.testAuthConfig).toHaveBeenCalledWith({
      host: 'http://127.0.0.1',
      port: '7070',
      token: 'test_tok',
      admin_email: '',
      admin_password: '',
      database_id: null
    });
  });

  it('handles Save & Validate click and updates status', async () => {
    settingsModule.initAuthTab();
    document.getElementById('auth-input-host').value = 'http://localhost';
    document.getElementById('auth-input-port').value = '7070';
    document.getElementById('auth-input-token').value = 'test_token_xyz';

    await settingsModule.handleSaveAuth();
    expect(apiModule.saveAuthConfig).toHaveBeenCalledWith({
      host: 'http://localhost',
      port: '7070',
      token: 'test_token_xyz',
      admin_email: '',
      admin_password: '',
      database_id: null
    });
  });

  it('displays warning badge and message when auth is incomplete', () => {
    const incompleteConfig = {
      is_complete: false,
      token_warning: 'API Token is missing or invalid.',
      tables: {}
    };

    settingsModule.updateAuthStatusUI(incompleteConfig);

    const navWarning = document.getElementById('auth-nav-warning');
    const tokenWarningBox = document.getElementById('auth-token-warning');
    const tokenWarningText = document.getElementById('auth-token-warning-text');

    expect(navWarning.style.display).toBe('inline-flex');
    expect(tokenWarningBox.style.display).toBe('block');
    expect(tokenWarningText.textContent).toBe('API Token is missing or invalid.');
  });
});
