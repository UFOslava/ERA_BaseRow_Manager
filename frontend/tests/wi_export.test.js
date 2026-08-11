import { describe, test, expect, beforeEach } from 'vitest';

describe('WI Export Modal', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="wi-export-modal" style="display: none;"></div>
      <select id="wi-template-select"></select>
      <button id="btn-wi-export-confirm">Export</button>
      <button id="btn-wi-export-cancel">Cancel</button>
      <button id="btn-close-wi-export">Close</button>
    `;
    
    window.API_BASE_URL = 'http://localhost:5000';
  });

  test('modal UI elements exist', async () => {
    const modal = document.getElementById('wi-export-modal');
    expect(modal.style.display).toBe('none');
    
    expect(document.getElementById('btn-wi-export-confirm')).not.toBeNull();
    expect(document.getElementById('wi-template-select')).not.toBeNull();
  });
});
