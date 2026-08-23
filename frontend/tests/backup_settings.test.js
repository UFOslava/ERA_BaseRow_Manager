import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockBackups = [
  {
    backup_id: 'backup_2026-08-20_00-00-00_daily',
    filename: 'backup_2026-08-20_00-00-00_daily.zip',
    timestamp: '2026-08-20T00:00:00Z',
    created_at_display: '2026-08-20 00:00:00 UTC',
    day_of_week: 'Thursday',
    is_thursday: true,
    backup_type: 'daily',
    retention_policy: '52_weeks_thursday',
    metrics: {
      bom_items_count: 42,
      instruction_steps_count: 15,
      images_count: 8,
      total_tables_count: 9,
      total_rows_count: 120,
      archive_size_bytes: 1048576 // 1 MB
    }
  },
  {
    backup_id: 'backup_2026-08-22_12-00-00_daily',
    filename: 'backup_2026-08-22_12-00-00_daily.zip',
    timestamp: '2026-08-22T12:00:00Z',
    created_at_display: '2026-08-22 12:00:00 UTC',
    day_of_week: 'Saturday',
    is_thursday: false,
    backup_type: 'daily',
    retention_policy: '14_days',
    metrics: {
      bom_items_count: 45,
      instruction_steps_count: 18,
      images_count: 10,
      total_tables_count: 9,
      total_rows_count: 130,
      archive_size_bytes: 524288 // 512 KB
    }
  }
];

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
  fetchAuthStatus: vi.fn().mockResolvedValue({ is_complete: true }),
  fetchAuthConfig: vi.fn().mockResolvedValue({ is_complete: true, tables: {} }),
  testAuthConfig: vi.fn().mockResolvedValue({ is_complete: true }),
  saveAuthConfig: vi.fn().mockResolvedValue({ success: true, schema: {} }),
  checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true }),
  fetchBackupsList: vi.fn().mockResolvedValue(mockBackups),
  createBackup: vi.fn().mockResolvedValue({ backup_id: 'new_backup', metrics: { archive_size_bytes: 50000 } }),
  restoreBackup: vi.fn().mockResolvedValue({ success: true }),
  deleteBackup: vi.fn().mockResolvedValue({ status: 'success' }),
  fetchBackupConfig: vi.fn().mockResolvedValue({ auto_backup_enabled: true }),
  saveBackupConfig: vi.fn().mockResolvedValue({ auto_backup_enabled: true })
}));

describe('Backup and Restore Settings', () => {
  let settingsModule;
  let apiModule;

  beforeEach(async () => {
    document.body.innerHTML = `
      <div id="tab-auth">
        <button id="btn-backup-now">Create Backup Now</button>
        <button id="btn-backup-refresh">Refresh</button>
        <div id="backup-list-container"></div>
        <div id="auth-tables-container"></div>
      </div>
      <div id="toast-container"></div>
    `;

    vi.clearAllMocks();
    apiModule = await import('../src/api.js');
    settingsModule = await import('../src/settings.js');
  });

  it('renders backup archives list with metrics and retention badges', () => {
    settingsModule.renderBackupsList(mockBackups);

    const container = document.getElementById('backup-list-container');
    const cards = container.querySelectorAll('.backup-item-card');
    expect(cards.length).toBe(2);

    // Thursday card
    expect(cards[0].className).toContain('thursday-retained');
    expect(cards[0].textContent).toContain('52-Week Retention');
    expect(cards[0].textContent).toContain('42 BOM');
    expect(cards[0].textContent).toContain('15 Steps');
    expect(cards[0].textContent).toContain('8 Images');
    expect(cards[0].textContent).toContain('1 MB');

    // Saturday card
    expect(cards[1].textContent).toContain('14-Day Retention');
    expect(cards[1].textContent).toContain('45 BOM');
    expect(cards[1].textContent).toContain('512 KB');
  });

  it('renders empty state message when no backups exist', () => {
    settingsModule.renderBackupsList([]);

    const container = document.getElementById('backup-list-container');
    expect(container.textContent).toContain('No database backups created yet');
  });

  it('handles Create Backup Now button click', async () => {
    await settingsModule.handleCreateBackupNow();

    expect(apiModule.createBackup).toHaveBeenCalledWith({
      type: 'manual',
      note: 'Created via web interface'
    });
    expect(apiModule.fetchBackupsList).toHaveBeenCalled();
  });

  it('handles Restore Backup with confirmation dialog', async () => {
    window.confirm = vi.fn().mockReturnValue(true);

    await settingsModule.handleRestoreBackup('backup_2026-08-20_00-00-00_daily');

    expect(window.confirm).toHaveBeenCalled();
    expect(apiModule.restoreBackup).toHaveBeenCalledWith('backup_2026-08-20_00-00-00_daily');
  });

  it('handles Delete Backup with confirmation dialog', async () => {
    window.confirm = vi.fn().mockReturnValue(true);

    await settingsModule.handleDeleteBackup('backup_2026-08-22_12-00-00_manual');

    expect(window.confirm).toHaveBeenCalled();
    expect(apiModule.deleteBackup).toHaveBeenCalledWith('backup_2026-08-22_12-00-00_manual');
    expect(apiModule.fetchBackupsList).toHaveBeenCalled();
  });
});
