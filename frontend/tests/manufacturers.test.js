import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

vi.mock('../src/api.js', () => {
  return {
    fetchManufacturers: vi.fn(),
    fetchManufacturer: vi.fn(),
    createManufacturer: vi.fn(),
    updateManufacturer: vi.fn(),
    deleteManufacturer: vi.fn(),
    fetchSuppliers: vi.fn(),
    fetchSupplier: vi.fn(),
    createSupplier: vi.fn(),
    updateSupplier: vi.fn(),
    deleteSupplier: vi.fn(),
    fetchContacts: vi.fn(),
    fetchContact: vi.fn(),
    createContact: vi.fn(),
    updateContact: vi.fn(),
    deleteContact: vi.fn(),
    uploadLogo: vi.fn(),
    fetchFlatItems: vi.fn(),
    getHealth: vi.fn().mockResolvedValue({ status: 'ok' }),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

import * as api from '../src/api.js';

let mfgModule;

beforeAll(async () => {
  document.body.innerHTML = `
    <div id="toast-container"></div>
    <span id="status-indicator"></span>
    <span id="status-text"></span>
    <button id="btn-hamburger"></button>
    <div id="hamburger-menu"></div>

    <input type="text" id="mfg-search-input" />
    <button id="btn-clear-mfg-search"></button>
    <button id="btn-add-mfg-trigger"></button>
    <span id="mfg-count-badge"></span>
    <div id="mfg-list-container"></div>

    <div id="mfg-detail-panel"></div>
    <div id="mfg-empty-state"></div>
    <div id="mfg-detail-content"></div>
    <button id="btn-mfg-save" disabled></button>
    <button id="btn-mfg-revert" disabled></button>
    <button id="btn-mfg-delete"></button>
    <div id="mfg-logo-dropzone"></div>
    <img id="mfg-logo-img" />
    <div id="mfg-logo-placeholder"></div>
    <input type="file" id="mfg-logo-file-input" />
    <button id="btn-mfg-browse-logo"></button>
    <button id="btn-mfg-remove-logo"></button>
    <h1 id="mfg-centerpiece-name"></h1>
    <div id="mfg-website-badge"><a id="mfg-website-anchor"></a></div>
    <input type="text" id="input-mfg-name" />
    <input type="url" id="input-mfg-website" />
    <button id="btn-open-mfg-website"></button>
    <textarea id="input-mfg-notes"></textarea>
    <button id="btn-mfg-own-supplier"></button>
    <button id="btn-open-supplier-picker"></button>
    <span id="mfg-supplier-count-badge"></span>
    <div id="mfg-linked-suppliers-list"></div>
    <span id="mfg-items-count-badge"></span>
    <div id="mfg-items-container"></div>

    <div id="supplier-detail-panel"></div>
    <div id="supplier-empty-state"></div>
    <div id="supplier-detail-content"></div>
    <button id="btn-supplier-save" disabled></button>
    <button id="btn-supplier-revert" disabled></button>
    <button id="btn-supplier-unlink"></button>
    <button id="btn-supplier-delete"></button>
    <div id="supplier-logo-dropzone"></div>
    <img id="supplier-logo-img" />
    <div id="supplier-logo-placeholder"></div>
    <input type="file" id="supplier-logo-file-input" />
    <button id="btn-supplier-browse-logo"></button>
    <button id="btn-supplier-remove-logo"></button>
    <h2 id="supplier-centerpiece-name"></h2>
    <div id="supplier-url-badge"><a id="supplier-url-anchor"></a></div>
    <input type="text" id="input-supplier-name" />
    <input type="url" id="input-supplier-url" />
    <button id="btn-open-supplier-url"></button>
    <input type="checkbox" id="input-supplier-online-store" />
    <textarea id="input-supplier-notes"></textarea>
    <span id="supplier-mfg-count-badge"></span>
    <div id="supplier-mfg-list"></div>
    <span id="supplier-contacts-count-badge"></span>
    <button id="btn-add-contact-trigger"></button>
    <div id="supplier-contacts-list"></div>

    <!-- Modals -->
    <div id="modal-create-mfg" style="display: none;">
      <input type="text" id="modal-input-mfg-name" />
      <input type="url" id="modal-input-mfg-website" />
      <textarea id="modal-input-mfg-notes"></textarea>
      <button id="btn-close-create-mfg-modal"></button>
      <button id="btn-cancel-create-mfg"></button>
      <button id="btn-confirm-create-mfg"></button>
    </div>

    <div id="modal-supplier-picker" style="display: none;">
      <span id="modal-picker-mfg-name"></span>
      <input type="text" id="picker-supplier-search" />
      <button id="btn-create-supplier-in-picker"></button>
      <div id="picker-suppliers-list"></div>
      <button id="btn-close-supplier-picker-modal"></button>
      <button id="btn-cancel-supplier-picker"></button>
      <button id="btn-apply-supplier-picker"></button>
    </div>

    <div id="modal-contact-edit" style="display: none;">
      <h3 id="modal-contact-title"></h3>
      <input type="text" id="modal-input-contact-name" />
      <input type="email" id="modal-input-contact-email" />
      <input type="tel" id="modal-input-contact-phone" />
      <input type="checkbox" id="modal-input-contact-active" />
      <textarea id="modal-input-contact-notes"></textarea>
      <button id="btn-close-contact-modal"></button>
      <button id="btn-cancel-contact-modal"></button>
      <button id="btn-confirm-save-contact"></button>
    </div>

    <div id="modal-confirm-delete" style="display: none;">
      <h3 id="modal-confirm-title"></h3>
      <p id="modal-confirm-message"></p>
      <button id="btn-close-confirm-modal"></button>
      <button id="btn-cancel-confirm"></button>
      <button id="btn-confirm-delete-action"></button>
    </div>
  `;

  mfgModule = await import('../src/manufacturers.js');
});

describe('Manufacturer & Supplier Directory', () => {
  const sampleManufacturers = [
    {
      id: 1,
      Name: 'Schurter',
      Website: 'https://schurter.com',
      Notes: 'Swiss components manufacturer',
      Logo: [{ url: 'http://localhost/schurter.png' }],
      Suppliers: [{ id: 10, value: 'Mouser' }],
      BOM: [{ id: 100, value: '20-00001' }]
    },
    {
      id: 2,
      Name: 'Onsemi',
      Website: 'https://onsemi.com',
      Notes: 'Semiconductors',
      Logo: [],
      Suppliers: [],
      BOM: []
    }
  ];

  const sampleSuppliers = [
    {
      id: 10,
      'Company Name': 'Mouser',
      URL: 'https://mouser.com',
      'Online Store': true,
      Notes: 'Major distributor',
      Logo: [{ url: 'http://localhost/mouser.png' }],
      'Imports From': [{ id: 1, value: 'Schurter' }]
    },
    {
      id: 11,
      'Company Name': 'DigiKey',
      URL: 'https://digikey.com',
      'Online Store': true,
      Notes: '',
      Logo: [],
      'Imports From': []
    }
  ];

  const sampleContacts = [
    {
      id: 101,
      Name: 'John Doe',
      Email: 'john@mouser.com',
      'Phone number': '+1-800-346-6873',
      Active: true,
      Notes: 'Sales Representative',
      Suppliers: [{ id: 10, value: 'Mouser' }]
    }
  ];

  const sampleItems = [
    {
      id: 100,
      'Part Number': '20-00001',
      'Item description': 'Fuse Holder 5x20mm',
      State: { value: 'Production Use' },
      Manufacturer: [{ id: 1, value: 'Schurter' }]
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchManufacturers.mockResolvedValue([...sampleManufacturers]);
    api.fetchSuppliers.mockResolvedValue([...sampleSuppliers]);
    api.fetchContacts.mockResolvedValue([...sampleContacts]);
    api.fetchFlatItems.mockResolvedValue([...sampleItems]);
  });

  it('loads and renders manufacturers list upon init', async () => {
    await mfgModule.init();

    const badge = document.getElementById('mfg-count-badge');
    expect(badge.textContent).toBe('2');

    const listContainer = document.getElementById('mfg-list-container');
    expect(listContainer.children.length).toBe(2);
    expect(listContainer.textContent).toContain('Schurter');
    expect(listContainer.textContent).toContain('Onsemi');
  });

  it('filters manufacturers by search input', async () => {
    await mfgModule.init();

    const searchInput = document.getElementById('mfg-search-input');
    searchInput.value = 'onsemi';
    searchInput.dispatchEvent(new Event('input'));

    const listContainer = document.getElementById('mfg-list-container');
    expect(listContainer.children.length).toBe(1);
    expect(listContainer.textContent).toContain('Onsemi');
    expect(listContainer.textContent).not.toContain('Schurter');
  });

  it('selecting a manufacturer populates centerpiece header and form fields', async () => {
    await mfgModule.init();
    mfgModule.selectManufacturer(1);

    expect(document.getElementById('mfg-centerpiece-name').textContent).toBe('Schurter');
    expect(document.getElementById('input-mfg-name').value).toBe('Schurter');
    expect(document.getElementById('input-mfg-website').value).toBe('https://schurter.com');
    expect(document.getElementById('input-mfg-notes').value).toBe('Swiss components manufacturer');

    // Logo should be displayed in white frame
    const logoImg = document.getElementById('mfg-logo-img');
    expect(logoImg.src).toBe('http://localhost/schurter.png');
    expect(logoImg.style.display).toBe('block');

    // Manufactured BOM items should be listed
    const itemsContainer = document.getElementById('mfg-items-container');
    expect(itemsContainer.textContent).toContain('20-00001');
    expect(itemsContainer.textContent).toContain('Fuse Holder 5x20mm');
  });

  it('enables save and revert buttons when manufacturer form is edited', async () => {
    await mfgModule.init();
    mfgModule.selectManufacturer(1);

    const btnSave = document.getElementById('btn-mfg-save');
    const btnRevert = document.getElementById('btn-mfg-revert');
    expect(btnSave.disabled).toBe(true);
    expect(btnRevert.disabled).toBe(true);

    const inputName = document.getElementById('input-mfg-name');
    inputName.value = 'Schurter AG Updated';
    inputName.dispatchEvent(new Event('input'));

    expect(btnSave.disabled).toBe(false);
    expect(btnRevert.disabled).toBe(false);
    expect(document.getElementById('mfg-centerpiece-name').textContent).toBe('Schurter AG Updated');
  });

  it('saving manufacturer calls updateManufacturer API and updates state', async () => {
    api.updateManufacturer.mockResolvedValueOnce({
      id: 1,
      Name: 'Schurter Holding',
      Website: 'https://schurter.com',
      Notes: 'Updated notes'
    });

    await mfgModule.init();
    mfgModule.selectManufacturer(1);

    const inputName = document.getElementById('input-mfg-name');
    inputName.value = 'Schurter Holding';
    inputName.dispatchEvent(new Event('input'));

    const btnSave = document.getElementById('btn-mfg-save');
    await btnSave.click();

    expect(api.updateManufacturer).toHaveBeenCalledWith(1, {
      Name: 'Schurter Holding',
      Website: 'https://schurter.com',
      Notes: 'Swiss components manufacturer'
    });
  });

  it('creates own supplier when clicking "Manufacturer is Own Supplier"', async () => {
    api.createSupplier.mockResolvedValueOnce({
      id: 50,
      'Company Name': 'Schurter',
      URL: 'https://schurter.com',
      'Online Store': false,
      'Imports From': [1],
      Logo: [{ url: 'http://localhost/schurter.png' }]
    });
    api.updateManufacturer.mockResolvedValueOnce({
      id: 1,
      Name: 'Schurter',
      Suppliers: [10, 50]
    });

    await mfgModule.init();
    mfgModule.selectManufacturer(1);

    const btnOwn = document.getElementById('btn-mfg-own-supplier');
    await btnOwn.click();

    expect(api.createSupplier).toHaveBeenCalledWith(expect.objectContaining({
      'Company Name': 'Schurter',
      URL: 'https://schurter.com'
    }));
  });

  it('selecting a supplier displays supplier details and contacts', async () => {
    await mfgModule.init();
    mfgModule.selectManufacturer(1);
    mfgModule.selectSupplier(10);

    expect(document.getElementById('supplier-centerpiece-name').textContent).toBe('Mouser');
    expect(document.getElementById('input-supplier-name').value).toBe('Mouser');
    expect(document.getElementById('input-supplier-url').value).toBe('https://mouser.com');
    expect(document.getElementById('input-supplier-online-store').checked).toBe(true);

    // Contacts list should contain John Doe with mailto and tel links
    const contactsList = document.getElementById('supplier-contacts-list');
    expect(contactsList.textContent).toContain('John Doe');

    const mailtoLink = contactsList.querySelector('a[href^="mailto:"]');
    expect(mailtoLink).toBeTruthy();
    expect(mailtoLink.getAttribute('href')).toBe('mailto:john%40mouser.com');

    const telLink = contactsList.querySelector('a[href^="tel:"]');
    expect(telLink).toBeTruthy();
    expect(telLink.getAttribute('href')).toContain('tel:');
  });

  it('saving supplier changes calls updateSupplier API', async () => {
    api.updateSupplier.mockResolvedValueOnce({
      id: 10,
      'Company Name': 'Mouser Electronics Inc',
      URL: 'https://mouser.com',
      'Online Store': true,
      Notes: 'Updated supplier notes'
    });

    await mfgModule.init();
    mfgModule.selectManufacturer(1);
    mfgModule.selectSupplier(10);

    const inputName = document.getElementById('input-supplier-name');
    inputName.value = 'Mouser Electronics Inc';
    inputName.dispatchEvent(new Event('input'));

    const btnSave = document.getElementById('btn-supplier-save');
    expect(btnSave.disabled).toBe(false);

    await btnSave.click();

    expect(api.updateSupplier).toHaveBeenCalledWith(10, {
      'Company Name': 'Mouser Electronics Inc',
      URL: 'https://mouser.com',
      'Online Store': true,
      Notes: 'Major distributor'
    });
  });

  it('creates contact for the selected supplier', async () => {
    api.createContact.mockResolvedValueOnce({
      id: 200,
      Name: 'Jane Smith',
      Email: 'jane@mouser.com',
      'Phone number': '054-1234567',
      Active: true,
      Notes: 'Account Manager',
      Suppliers: [10]
    });

    await mfgModule.init();
    mfgModule.selectManufacturer(1);
    mfgModule.selectSupplier(10);

    const btnAddContact = document.getElementById('btn-add-contact-trigger');
    btnAddContact.click();

    const modal = document.getElementById('modal-contact-edit');
    expect(modal.style.display).toBe('flex');

    document.getElementById('modal-input-contact-name').value = 'Jane Smith';
    document.getElementById('modal-input-contact-email').value = 'jane@mouser.com';
    document.getElementById('modal-input-contact-phone').value = '054-1234567';

    const btnConfirm = document.getElementById('btn-confirm-save-contact');
    await btnConfirm.click();

    expect(api.createContact).toHaveBeenCalledWith({
      Name: 'Jane Smith',
      Email: 'jane@mouser.com',
      'Phone number': '054-1234567',
      Active: true,
      Notes: '',
      Suppliers: [10]
    });
  });

  it('creates a new manufacturer via modal dialog', async () => {
    api.createManufacturer.mockResolvedValueOnce({
      id: 99,
      Name: 'Texas Instruments',
      Website: 'https://ti.com',
      Notes: 'Leading analog and digital ICs'
    });

    await mfgModule.init();

    const btnAdd = document.getElementById('btn-add-mfg-trigger');
    btnAdd.click();

    const modal = document.getElementById('modal-create-mfg');
    expect(modal.style.display).toBe('flex');

    document.getElementById('modal-input-mfg-name').value = 'Texas Instruments';
    document.getElementById('modal-input-mfg-website').value = 'https://ti.com';
    document.getElementById('modal-input-mfg-notes').value = 'Leading analog and digital ICs';

    const btnConfirm = document.getElementById('btn-confirm-create-mfg');
    await btnConfirm.click();

    expect(api.createManufacturer).toHaveBeenCalledWith({
      Name: 'Texas Instruments',
      Website: 'https://ti.com',
      Notes: 'Leading analog and digital ICs'
    });
  });
});
