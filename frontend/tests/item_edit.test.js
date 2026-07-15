import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

// Mock the API calls
vi.mock('../src/api.js', () => {
  return {
    fetchBomTree: vi.fn(),
    fetchItem: vi.fn(),
    updateItem: vi.fn(),
    fetchScanStatus: vi.fn(),
    getHealth: vi.fn(),
    fetchRules: vi.fn(),
    fetchManufacturers: vi.fn(),
    uploadDatasheet: vi.fn(),
  };
});

let mainModule;

beforeAll(async () => {
  // Set up DOM elements BEFORE importing main.js
  document.body.innerHTML = `
    <select id="input-manufacturer"></select>
    <div id="datasheets-list"></div>
    <input type="file" id="input-photo-file" />
    <div id="gallery-container"></div>
    
    <input type="text" id="input-description" />
    <input type="text" id="input-source" />
    <input type="text" id="input-external-pn" />
    <select id="input-state">
      <option value="Engineerig Use">Engineering Use</option>
      <option value="Production Use">Production Use</option>
      <option value="Unknown">Unknown</option>
    </select>
    <input type="number" id="input-price" />
    <select id="input-sourced-by">
      <option value="Contractor">Contractor</option>
      <option value="ERA">ERA</option>
      <option value="TBD">TBD</option>
    </select>
    <textarea id="input-notes"></textarea>
  `;

  // Dynamically import main.js so the module scope queries find the DOM elements
  mainModule = await import('../src/main.js');
});

describe('Item Edit Page Functionality', () => {
  beforeEach(() => {
    // Reset inputs and state
    document.getElementById('input-description').value = '';
    document.getElementById('input-source').value = '';
    document.getElementById('input-external-pn').value = '';
    document.getElementById('input-state').value = 'Unknown';
    document.getElementById('input-manufacturer').value = '';
    document.getElementById('input-price').value = '';
    document.getElementById('input-sourced-by').value = 'TBD';
    document.getElementById('input-notes').value = '';
    
    mainModule.currentDatasheets.length = 0;
    mainModule.currentImages.length = 0;
    mainModule.manufacturers.length = 0;
    mainModule.setCurrentItemId(1); // Set item ID so hasUnsavedChanges works
  });

  describe('populateManufacturersDropdown', () => {
    it('populates select options correctly', () => {
      mainModule.manufacturers.push({ id: 10, name: 'Onsemi' });
      mainModule.manufacturers.push({ id: 12, name: 'Schurter' });
      
      mainModule.populateManufacturersDropdown();
      
      const select = document.getElementById('input-manufacturer');
      expect(select.children.length).toBe(3); // None + 2 manufacturers
      expect(select.children[0].value).toBe('');
      expect(select.children[1].value).toBe('10');
      expect(select.children[1].textContent).toBe('Onsemi');
    });
  });

  describe('renderDatasheetsList', () => {
    it('renders datasheet links and visible names', () => {
      mainModule.currentDatasheets.push({ name: 'mfg_spec.pdf', url: 'http://test/pdf1' });
      
      mainModule.renderDatasheetsList();
      
      const container = document.getElementById('datasheets-list');
      expect(container.children.length).toBe(1);
      
      const link = container.children[0];
      expect(link.tagName).toBe('A');
      expect(link.getAttribute('href')).toBe('http://test/pdf1');
      expect(link.textContent).toContain('mfg_spec.pdf');
    });
  });

  describe('renderGallery', () => {
    it('renders photo thumbnails and delete button plus an add button', () => {
      mainModule.currentImages.push({ name: 'photo1.jpg', url: 'http://test/photo1' });
      
      mainModule.renderGallery();
      
      const container = document.getElementById('gallery-container');
      // Should have 2 cards: 1 photo + 1 "Add Photo" card
      expect(container.children.length).toBe(2);
      
      const imgCard = container.children[0];
      expect(imgCard.querySelector('img').getAttribute('src')).toBe('http://test/photo1');
      expect(imgCard.querySelector('.btn-delete-image')).toBeTruthy();
      
      const addCard = container.children[1];
      expect(addCard.classList.contains('add-image-card')).toBe(true);
      expect(addCard.textContent).toContain('Add Photo');
    });
  });

  describe('hasUnsavedChanges', () => {
    it('detects no changes when fields match originalData', () => {
      // Set values in DOM
      document.getElementById('input-description').value = 'Desc';
      document.getElementById('input-source').value = 'http://source';
      document.getElementById('input-external-pn').value = '12345';
      document.getElementById('input-state').value = 'Production Use';
      document.getElementById('input-manufacturer').value = '';
      document.getElementById('input-price').value = '12.34';
      document.getElementById('input-sourced-by').value = 'ERA';
      document.getElementById('input-notes').value = 'Spec note';
      
      mainModule.currentDatasheets.push({ name: 'pdf1.pdf' });
      mainModule.currentImages.push({ name: 'photo1.jpg' });
      
      // Set originalData
      Object.assign(mainModule.originalData, {
        description: 'Desc',
        source: 'http://source',
        externalPn: '12345',
        state: 'Production Use',
        manufacturerId: '',
        price: 12.34,
        sourcedBy: 'ERA',
        notes: 'Spec note',
        datasheets: [{ name: 'pdf1.pdf' }],
        images: [{ name: 'photo1.jpg' }]
      });
      
      expect(mainModule.hasUnsavedChanges()).toBe(false);
    });

    it('detects changes when fields differ from originalData', () => {
      // Set values in DOM
      document.getElementById('input-description').value = 'Desc';
      document.getElementById('input-source').value = 'http://source';
      document.getElementById('input-external-pn').value = 'DIFFERENT';
      document.getElementById('input-state').value = 'Production Use';
      document.getElementById('input-manufacturer').value = '';
      document.getElementById('input-price').value = '12.34';
      document.getElementById('input-sourced-by').value = 'ERA';
      document.getElementById('input-notes').value = 'Spec note';
      
      mainModule.currentDatasheets.push({ name: 'pdf1.pdf' });
      mainModule.currentImages.push({ name: 'photo1.jpg' });
      
      // Set originalData
      Object.assign(mainModule.originalData, {
        description: 'Desc',
        source: 'http://source',
        externalPn: '12345',
        state: 'Production Use',
        manufacturerId: '',
        price: 12.34,
        sourcedBy: 'ERA',
        notes: 'Spec note',
        datasheets: [{ name: 'pdf1.pdf' }],
        images: [{ name: 'photo1.jpg' }]
      });
      
      expect(mainModule.hasUnsavedChanges()).toBe(true);
    });

    it('detects changes when photo gallery is edited', () => {
      // Set values in DOM
      document.getElementById('input-description').value = 'Desc';
      document.getElementById('input-source').value = 'http://source';
      document.getElementById('input-external-pn').value = '12345';
      document.getElementById('input-state').value = 'Production Use';
      document.getElementById('input-manufacturer').value = '';
      document.getElementById('input-price').value = '12.34';
      document.getElementById('input-sourced-by').value = 'ERA';
      document.getElementById('input-notes').value = 'Spec note';
      
      mainModule.currentDatasheets.push({ name: 'pdf1.pdf' });
      // DOM matches, but we add a new image to currentImages
      mainModule.currentImages.push({ name: 'photo1.jpg' });
      mainModule.currentImages.push({ name: 'photo2.jpg' });
      
      // Set originalData
      Object.assign(mainModule.originalData, {
        description: 'Desc',
        source: 'http://source',
        externalPn: '12345',
        state: 'Production Use',
        manufacturerId: '',
        price: 12.34,
        sourcedBy: 'ERA',
        notes: 'Spec note',
        datasheets: [{ name: 'pdf1.pdf' }],
        images: [{ name: 'photo1.jpg' }]
      });
      
      expect(mainModule.hasUnsavedChanges()).toBe(true);
    });
  });
});
