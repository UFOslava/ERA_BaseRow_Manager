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
    fetchManufacturers: vi.fn().mockResolvedValue([]),
    uploadDatasheet: vi.fn(),
    fetchFlatItems: vi.fn().mockResolvedValue([]),
    addItemRevision: vi.fn(),
    duplicateItem: vi.fn(),
    fetchStates: vi.fn().mockResolvedValue({}),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

let mainModule;

beforeAll(async () => {
  // Set up DOM elements BEFORE importing main.js
  document.body.innerHTML = `
    <span id="title-pn"></span>
    <span id="title-desc"></span>
    <div id="revision-tags-container"></div>
    <select id="input-manufacturer"></select>
    <button id="btn-edit-manufacturer"></button>
    <div id="datasheets-list"></div>
    <input type="file" id="input-photo-file" />
    <div id="drag-drop-overlay"></div>
    <div id="gallery-container"></div>
    <div id="related-items-container"></div>
    <div id="add-related-modal" class="modal-overlay">
      <input type="text" id="add-related-search" />
      <button id="btn-close-add-related"></button>
      <div id="add-related-list"></div>
    </div>
    <div id="confirm-modal" class="modal-overlay">
      <h2 id="confirm-modal-title"></h2>
      <div id="confirm-modal-preview"></div>
      <p id="confirm-modal-message"></p>
      <button id="btn-close-confirm"></button>
      <button id="btn-confirm-cancel"></button>
      <button id="btn-confirm-accept"></button>
    </div>
    
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
      <option value="Purchased by Contractor">Purchased by Contractor</option>
      <option value="Produced by Contractor">Produced by Contractor</option>
      <option value="Purchased by ERA">Purchased by ERA</option>
      <option value="Produced by ERA">Produced by ERA</option>
      <option value="TBD">TBD</option>
    </select>
    <textarea id="input-notes"></textarea>
    <input type="checkbox" id="input-blackbox" />
    <span id="item-category"></span>
    <div id="recategorize-modal" class="modal-overlay">
      <select id="recategorize-category"></select>
      <div id="recategorize-preview">
        <span id="recategorize-new-pn"></span>
      </div>
      <button id="btn-confirm-recategorize"></button>
      <button id="btn-cancel-recategorize"></button>
      <button id="btn-close-recategorize"></button>
    </div>
    
    <div id="duplicate-item-modal" class="modal-overlay" style="display: none;">
      <select id="duplicate-item-category"></select>
      <input type="text" id="duplicate-item-description" />
      <input type="checkbox" id="duplicate-opt-parents" checked />
      <input type="checkbox" id="duplicate-opt-children" checked />
      <input type="checkbox" id="duplicate-opt-instructions" checked />
      <input type="checkbox" id="duplicate-opt-photos" checked />
      <button id="btn-close-duplicate-item"></button>
      <button id="btn-cancel-duplicate-item"></button>
      <button id="btn-confirm-duplicate-item"></button>
    </div>
    <div id="header-default-brand"></div>
    <div id="header-item-reminder" style="display: none;">
      <span id="header-item-pn"></span>
      <span id="header-item-desc"></span>
    </div>
    <div id="header-item-actions" style="display: none;">
      <button id="btn-duplicate"></button>
      <button id="btn-revert"></button>
      <button id="btn-save"></button>
    </div>
    <main id="bom-explorer-view" style="display: none;"></main>
    <main id="item-details-view" style="display: block;"></main>
    <div id="tree-container"></div>
    <span id="item-part-number"></span>
    <div id="toast-container"></div>
  `;

  // Dynamically import main.js so the module scope queries find the DOM elements
  mainModule = await import('../src/main.js');
  await mainModule.init();
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
    document.getElementById('title-pn').textContent = '';
    document.getElementById('title-desc').textContent = '';
    
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

    it('btn-edit-manufacturer navigates to /manufacturers.html with selected manufacturer id', () => {
      const select = document.getElementById('input-manufacturer');
      select.value = '10';

      const originalLocation = window.location;
      delete window.location;
      window.location = { href: '' };

      const btnEdit = document.getElementById('btn-edit-manufacturer');
      btnEdit.click();

      expect(window.location.href).toBe('/manufacturers.html?id=10');
      window.location = originalLocation;
    });
  });

  describe('renderDatasheetsList', () => {
    it('renders datasheet links with icons without name labels', () => {
      mainModule.currentDatasheets.push({ name: 'mfg_spec.pdf', url: 'http://test/pdf1' });
      
      mainModule.renderDatasheetsList();
      
      const container = document.getElementById('datasheets-list');
      expect(container.children.length).toBe(1);
      
      const link = container.children[0];
      expect(link.tagName).toBe('A');
      expect(link.getAttribute('href')).toBe('http://test/pdf1');
      expect(link.querySelector('.pdf-icon')).toBeTruthy();
      expect(link.textContent).not.toContain('mfg_spec.pdf');
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
      document.getElementById('input-sourced-by').value = 'Purchased by ERA';
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
        sourcedBy: 'Purchased by ERA',
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
      document.getElementById('input-sourced-by').value = 'Purchased by ERA';
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
        sourcedBy: 'Purchased by ERA',
        notes: 'Spec note',
        datasheets: [{ name: 'pdf1.pdf' }],
        images: [{ name: 'photo1.jpg' }]
      });
      
      expect(mainModule.hasUnsavedChanges()).toBe(true);
    });

    it('detects changes when Blackbox is toggled', () => {
      // Set values in DOM
      document.getElementById('input-description').value = 'Desc';
      document.getElementById('input-source').value = 'http://source';
      document.getElementById('input-external-pn').value = '12345';
      document.getElementById('input-state').value = 'Production Use';
      document.getElementById('input-manufacturer').value = '';
      document.getElementById('input-price').value = '12.34';
      document.getElementById('input-sourced-by').value = 'Purchased by ERA';
      document.getElementById('input-notes').value = 'Spec note';
      document.getElementById('input-blackbox').checked = true;

      // Set originalData
      Object.assign(mainModule.originalData, {
        description: 'Desc',
        source: 'http://source',
        externalPn: '12345',
        state: 'Production Use',
        manufacturerId: '',
        price: 12.34,
        sourcedBy: 'Purchased by ERA',
        notes: 'Spec note',
        blackbox: false,
        datasheets: [],
        images: []
      });

      expect(mainModule.hasUnsavedChanges()).toBe(true);

      // Revert in DOM
      document.getElementById('input-blackbox').checked = false;
      expect(mainModule.hasUnsavedChanges()).toBe(false);
    });


    it('detects changes when photo gallery is edited', () => {
      // Set values in DOM
      document.getElementById('input-description').value = 'Desc';
      document.getElementById('input-source').value = 'http://source';
      document.getElementById('input-external-pn').value = '12345';
      document.getElementById('input-state').value = 'Production Use';
      document.getElementById('input-manufacturer').value = '';
      document.getElementById('input-price').value = '12.34';
      document.getElementById('input-sourced-by').value = 'Purchased by ERA';
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
        sourcedBy: 'Purchased by ERA',
        notes: 'Spec note',
        datasheets: [{ name: 'pdf1.pdf' }],
        images: [{ name: 'photo1.jpg' }]
      });
      
      expect(mainModule.hasUnsavedChanges()).toBe(true);
    });
  });

  describe('handleDroppedFiles', () => {
    beforeEach(() => {
      vi.spyOn(console, 'error').mockImplementation(() => {});
      global.showToast = vi.fn();
    });

    it('uploads valid PDFs to datasheets and valid images to gallery, discarding invalid files', async () => {
      const mockPDF = { name: 'datasheet1.pdf', url: 'http://test/pdf1' };
      const mockImg = { name: 'photo1.png', url: 'http://test/img1' };
      
      const api = await import('../src/api.js');
      api.uploadDatasheet
        .mockResolvedValueOnce(mockPDF)
        .mockResolvedValueOnce(mockImg);

      const files = [
        new File(['abc'], 'datasheet1.pdf', { type: 'application/pdf' }),
        new File(['def'], 'photo1.png', { type: 'image/png' }),
        new File(['xyz'], 'doc.txt', { type: 'text/plain' })
      ];

      await mainModule.handleDroppedFiles(files);

      expect(mainModule.currentDatasheets.length).toBe(1);
      expect(mainModule.currentDatasheets[0].name).toBe('datasheet1.pdf');

      expect(mainModule.currentImages.length).toBe(1);
      expect(mainModule.currentImages[0].name).toBe('photo1.png');

      expect(api.uploadDatasheet).toHaveBeenCalledTimes(2);
    });
  });

  describe('showConfirmModal', () => {
    it('sets modal content, preview, and executes callback only on accept', () => {
      let acceptTriggered = false;
      const callback = () => { acceptTriggered = true; };

      mainModule.showConfirmModal('Delete item', 'Are you sure?', '<span id="mock-preview"></span>', callback);

      const modal = document.getElementById('confirm-modal');
      const title = document.getElementById('confirm-modal-title');
      const msg = document.getElementById('confirm-modal-message');
      const preview = document.getElementById('confirm-modal-preview');

      expect(modal.style.display).toBe('flex');
      expect(modal.classList.contains('open')).toBe(true);
      expect(title.textContent).toBe('Delete item');
      expect(msg.textContent).toBe('Are you sure?');
      expect(preview.querySelector('#mock-preview')).toBeTruthy();

      expect(acceptTriggered).toBe(false);

      // Click accept
      const btnAccept = document.getElementById('btn-confirm-accept');
      btnAccept.click();

      expect(acceptTriggered).toBe(true);
      expect(modal.classList.contains('open')).toBe(false);
    });
  });


  describe('Decorated Document Title and Window Title', () => {
    it('sets full PN and description on document title and window title', async () => {
      const mockItem = {
        'Part Number': '40-00000',
        'Full PN': '40-00000 Rev.A',
        'Item description': 'Premium Red LED',
        'State': { id: 1, value: 'Unknown' },
        'Sourced By': { id: 1, value: 'TBD' }
      };

      const api = await import('../src/api.js');
      api.fetchItem.mockResolvedValueOnce(mockItem);

      await mainModule.setCurrentItemId(40);
      await mainModule.showItemPage(40);

      const titlePn = document.getElementById('title-pn');
      const titleDesc = document.getElementById('title-desc');

      expect(titlePn.textContent).toBe('40-00000 Rev.A');
      expect(titleDesc.textContent).toBe('Premium Red LED');
      expect(document.title).toBe('40-00000 Rev.A - Premium Red LED');

      // Test dynamic update on description change
      const inputDesc = document.getElementById('input-description');
      inputDesc.value = 'Premium Blue LED';
      inputDesc.dispatchEvent(new Event('input'));

      expect(titleDesc.textContent).toBe('Premium Blue LED');
      expect(document.title).toBe('40-00000 Rev.A - Premium Blue LED');

      // Test revert resets it
      mainModule.revertChanges();
      expect(titleDesc.textContent).toBe('Premium Red LED');
      expect(document.title).toBe('40-00000 Rev.A - Premium Red LED');
    });
  });

  describe('Revision Tags Functionality', () => {
    beforeEach(() => {
      mainModule.allItems.length = 0;
      mainModule.setCurrentItemId(2);
    });

    it('renders revision tags sorted alphanumerically and sets active class on current', () => {
      mainModule.allItems.push(
        { id: 1, 'Part Number': '40-00000', 'Revision': 'B' },
        { id: 2, 'Part Number': '40-00000', 'Revision': 'A' },
        { id: 3, 'Part Number': '40-00000', 'Revision': 'AA' },
        { id: 4, 'Part Number': '40-00000', 'Revision': 'Z' },
        { id: 5, 'Part Number': '40-00000', 'Revision': 'AZ' },
        { id: 6, 'Part Number': '40-00000', 'Revision': 'BA' },
        { id: 7, 'Part Number': '50-99999', 'Revision': 'C' }
      );

      mainModule.renderRevisionTags({ 'Part Number': '40-00000' });

      const container = document.getElementById('revision-tags-container');
      
      expect(container.children.length).toBe(7);

      expect(container.children[0].textContent).toBe('A');
      expect(container.children[0].classList.contains('active')).toBe(true);

      expect(container.children[1].textContent).toBe('B');
      expect(container.children[1].classList.contains('active')).toBe(false);

      expect(container.children[2].textContent).toBe('Z');
      expect(container.children[3].textContent).toBe('AA');
      expect(container.children[4].textContent).toBe('AZ');
      expect(container.children[5].textContent).toBe('BA');

      expect(container.children[6].textContent).toBe('+ Add');
      expect(container.children[6].classList.contains('disabled')).toBe(false);
    });

    it('calls addItemRevision and navigates to new item when + Add is clicked', async () => {
      const { addItemRevision } = await import('../src/api.js');
      addItemRevision.mockResolvedValueOnce({ id: 99, 'Part Number': '40-00000', 'Revision': 'B' });
      const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

      mainModule.allItems.push({ id: 2, 'Part Number': '40-00000', 'Revision': 'A' });
      mainModule.renderRevisionTags({ id: 2, 'Part Number': '40-00000' });

      const container = document.getElementById('revision-tags-container');
      const addBtn = container.querySelector('.revision-tag:last-child');
      expect(addBtn.textContent).toBe('+ Add');

      addBtn.click();

      // Wait for async handler
      await new Promise(resolve => setTimeout(resolve, 50));

      expect(addItemRevision).toHaveBeenCalledWith(2);
      expect(window.location.hash).toBe('#/item/99');
      confirmSpy.mockRestore();
    });
  });

  describe('Recategorize Modal Category Population', () => {
    it('populates category dropdown by fetching rules when categoryRules is empty', async () => {
      const api = await import('../src/api.js');
      api.fetchRules.mockResolvedValueOnce({
        '10': { name: 'Raw Material', color: 'red' },
        '20': { name: 'Mechanical COTS', color: 'blue' }
      });

      for (const key of Object.keys(mainModule.categoryRules)) {
        delete mainModule.categoryRules[key];
      }

      await mainModule.openRecategorizeModal();

      const select = document.getElementById('recategorize-category');
      expect(select).toBeTruthy();
      const options = select.querySelectorAll('option');
      expect(options.length).toBe(2);
      expect(options[0].value).toBe('10');
      expect(options[0].textContent).toBe('10 - Raw Material');
      expect(options[1].value).toBe('20');
      expect(options[1].textContent).toBe('20 - Mechanical COTS');
    });
  });

  describe('Category Specification Rendering', () => {
    it('populates specifications category field from PN Category linked field', async () => {
      const mockItem = {
        'Part Number': '40-00000',
        'Full PN': '40-00000 Rev.A',
        'Item description': 'Premium Red LED',
        'State': { id: 1, value: 'Unknown' },
        'Sourced By': { id: 1, value: 'TBD' },
        'PN Category': [{ id: 4, value: '40' }]
      };

      const api = await import('../src/api.js');
      api.fetchItem.mockResolvedValueOnce(mockItem);
      api.fetchRules.mockResolvedValueOnce({
        '40': { name: 'Electrical COTS', color: '#06b6d4' }
      });

      for (const key of Object.keys(mainModule.categoryRules)) {
        delete mainModule.categoryRules[key];
      }

      await mainModule.setCurrentItemId(40);
      await mainModule.showItemPage(40);

      const categorySpan = document.getElementById('item-category');
      expect(categorySpan.textContent).toBe('40 - Electrical COTS');
    });
  });

  describe('State field extraction and dropdown display', () => {
    it('correctly sets input-state value when State is an array of link row objects', async () => {
      const mockItem = {
        'Part Number': '40-00000',
        'Full PN': '40-00000 Rev.A',
        'Item description': 'Premium Red LED',
        'State': [{ id: 2, value: 'Production Use' }],
        'Sourced By': { id: 1, value: 'TBD' }
      };

      const api = await import('../src/api.js');
      api.fetchItem.mockResolvedValueOnce(mockItem);

      await mainModule.setCurrentItemId(40);
      await mainModule.showItemPage(40);

      const inputState = document.getElementById('input-state');
      expect(inputState.value).toBe('Production Use');
    });

    it('correctly sets input-state value when State is a single object (for backward compatibility)', async () => {
      const mockItem = {
        'Part Number': '40-00000',
        'Full PN': '40-00000 Rev.A',
        'Item description': 'Premium Red LED',
        'State': { id: 2, value: 'Production Use' },
        'Sourced By': { id: 1, value: 'TBD' }
      };

      const api = await import('../src/api.js');
      api.fetchItem.mockResolvedValueOnce(mockItem);

      await mainModule.setCurrentItemId(40);
      await mainModule.showItemPage(40);

      const inputState = document.getElementById('input-state');
      expect(inputState.value).toBe('Production Use');
    });
  });

  describe('Duplicate Item Features', () => {
    let api;
    beforeEach(async () => {
      api = await import('../src/api.js');
      global.showToast = vi.fn();
      
      // Reset modal and inputs
      const modal = document.getElementById('duplicate-item-modal');
      if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('open');
      }
      
      const pnSpan = document.getElementById('item-part-number');
      if (pnSpan) pnSpan.textContent = '10-00000';
      
      const descInput = document.getElementById('input-description');
      if (descInput) descInput.value = 'Nova Handle';

      // Reset checkboxes
      const optParents = document.getElementById('duplicate-opt-parents');
      if (optParents) optParents.checked = true;
      const optChildren = document.getElementById('duplicate-opt-children');
      if (optChildren) optChildren.checked = true;
      const optInstructions = document.getElementById('duplicate-opt-instructions');
      if (optInstructions) optInstructions.checked = true;
      const optPhotos = document.getElementById('duplicate-opt-photos');
      if (optPhotos) optPhotos.checked = true;

      mainModule.setCurrentItemId(1);
    });

    it('openDuplicateItemModal sets correct defaults and shows modal', async () => {
      // Setup rules
      mainModule.categoryRules['10'] = { name: 'Handles' };
      mainModule.categoryRules['20'] = { name: 'Screws' };

      await mainModule.openDuplicateItemModal();

      const modal = document.getElementById('duplicate-item-modal');
      const descInput = document.getElementById('duplicate-item-description');
      const catSelect = document.getElementById('duplicate-item-category');

      expect(modal.style.display).toBe('flex');
      expect(modal.classList.contains('open')).toBe(true);
      expect(descInput.value).toBe('Nova Handle - copy');
      expect(catSelect.options.length).toBeGreaterThanOrEqual(2);
      expect(catSelect.value).toBe('10');
      
      // Verify options are reset to true
      expect(document.getElementById('duplicate-opt-parents').checked).toBe(true);
      expect(document.getElementById('duplicate-opt-children').checked).toBe(true);
      expect(document.getElementById('duplicate-opt-instructions').checked).toBe(true);
      expect(document.getElementById('duplicate-opt-photos').checked).toBe(true);
    });

    it('handleConfirmDuplicateItem calls api.duplicateItem with default options on success', async () => {
      const mockNewItem = { id: 100, 'Part Number': '10-00001' };
      api.duplicateItem.mockResolvedValueOnce(mockNewItem);

      // Populate selects
      const catSelect = document.getElementById('duplicate-item-category');
      const descInput = document.getElementById('duplicate-item-description');
      
      const opt = document.createElement('option');
      opt.value = '10';
      catSelect.appendChild(opt);
      catSelect.value = '10';
      descInput.value = 'Nova Handle - copy';

      await mainModule.handleConfirmDuplicateItem();

      expect(api.duplicateItem).toHaveBeenCalledWith(1, '10', 'Nova Handle - copy', {
        duplicate_parents: true,
        duplicate_children: true,
        duplicate_instructions: true,
        duplicate_photos: true
      });
      const toastContainer = document.getElementById('toast-container');
      expect(toastContainer.textContent).toContain('Item duplicated successfully!');
      expect(window.location.hash).toBe('#/item/100');
    });

    it('handleConfirmDuplicateItem calls api.duplicateItem with custom option toggles if disabled', async () => {
      const mockNewItem = { id: 100, 'Part Number': '10-00001' };
      api.duplicateItem.mockResolvedValueOnce(mockNewItem);

      // Disable some options
      document.getElementById('duplicate-opt-parents').checked = false;
      document.getElementById('duplicate-opt-instructions').checked = false;

      const catSelect = document.getElementById('duplicate-item-category');
      const descInput = document.getElementById('duplicate-item-description');
      catSelect.value = '10';
      descInput.value = 'Nova Handle - copy';

      await mainModule.handleConfirmDuplicateItem();

      expect(api.duplicateItem).toHaveBeenCalledWith(1, '10', 'Nova Handle - copy', {
        duplicate_parents: false,
        duplicate_children: true,
        duplicate_instructions: false,
        duplicate_photos: true
      });
    });
  });

  describe('Persistent Header Scrolling & Item Reminder', () => {
    it('switches to item reminder when scrolled past threshold and back to brand at top', () => {
      const brand = document.getElementById('header-default-brand');
      const reminder = document.getElementById('header-item-reminder');
      const actions = document.getElementById('header-item-actions');
      const itemPn = document.getElementById('header-item-pn');
      const itemDesc = document.getElementById('header-item-desc');
      const itemView = document.getElementById('item-details-view');

      itemView.style.display = 'block';
      mainModule.updateHeaderItemReminder('55-00017 Rev.A', 'Nova Prepared Right Door');

      expect(itemPn.textContent).toBe('55-00017 Rev.A');
      expect(itemDesc.textContent).toBe('Nova Prepared Right Door');

      // Top position (scrollY = 0)
      window.scrollY = 0;
      mainModule.updateHeaderScrollState();
      expect(brand.style.display).toBe('flex');
      expect(reminder.style.display).toBe('none');
      expect(actions.style.display).toBe('flex');

      // Scrolled down (scrollY = 150)
      window.scrollY = 150;
      mainModule.updateHeaderScrollState();
      expect(brand.style.display).toBe('none');
      expect(reminder.style.display).toBe('flex');
      expect(actions.style.display).toBe('flex');

      // Scrolled back up
      window.scrollY = 0;
      mainModule.updateHeaderScrollState();
      expect(brand.style.display).toBe('flex');
      expect(reminder.style.display).toBe('none');
    });

    it('hides header reminder and action buttons when item details view is closed', () => {
      const brand = document.getElementById('header-default-brand');
      const reminder = document.getElementById('header-item-reminder');
      const actions = document.getElementById('header-item-actions');
      const itemView = document.getElementById('item-details-view');

      itemView.style.display = 'none';
      window.scrollY = 200;
      mainModule.updateHeaderScrollState();

      expect(brand.style.display).toBe('flex');
      expect(reminder.style.display).toBe('none');
      expect(actions.style.display).toBe('none');
    });

    it('updates header reminder description in real time when inputDescription changes', () => {
      const descInput = document.getElementById('input-description');
      const headerDesc = document.getElementById('header-item-desc');

      descInput.value = 'Updated description live';
      descInput.dispatchEvent(new Event('input'));

      expect(headerDesc.textContent).toBe('Updated description live');
    });
  });
});
