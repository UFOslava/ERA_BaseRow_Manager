import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest';

// Mock API
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
    createAssembly: vi.fn(),
    updateAssembly: vi.fn(),
    deleteAssembly: vi.fn(),
    createItem: vi.fn(),
  };
});

let mainModule;

beforeAll(async () => {
  document.body.innerHTML = `
    <!-- Mock required elements for main.js loading -->
    <button id="btn-refresh"></button>
    <div id="tree-container"></div>
    <div id="filter-drawer"></div>
    <span id="filter-badge"></span>
    <button id="btn-filter"></button>
    <div id="categories-filter-list"></div>
    <div id="states-filter-list"></div>

    <span id="title-pn"></span>
    <span id="title-desc"></span>
    <div id="revision-tags-container"></div>
    <select id="input-manufacturer"></select>
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
      <h3 id="confirm-title"></h3>
      <div id="confirm-body"></div>
      <button id="btn-confirm-yes"></button>
      <button id="btn-confirm-no"></button>
    </div>
    
    <!-- Gallery Overlay Elements -->
    <div id="gallery-overlay" class="modal-overlay" style="display: none;">
      <button id="btn-close-gallery-overlay"></button>
      <button id="btn-gallery-prev"></button>
      <img id="gallery-overlay-img" src="" />
      <button id="btn-gallery-next"></button>
    </div>
  `;

  mainModule = await import('../src/main.js');
});

describe('Image Gallery Overlay Viewer', () => {
  beforeEach(() => {
    // Reset state
    mainModule.currentImages.length = 0;
    const overlay = document.getElementById('gallery-overlay');
    if (overlay) {
      overlay.style.display = 'none';
      overlay.classList.remove('open');
    }
    const img = document.getElementById('gallery-overlay-img');
    if (img) img.src = '';
  });

  it('renders gallery placeholder when empty', () => {
    mainModule.renderGallery();
    const container = document.getElementById('gallery-container');
    expect(container.querySelector('.gallery-placeholder')).not.toBeNull();
  });

  it('renders images list with pointers and binds overlay trigger', () => {
    mainModule.currentImages.push(
      { url: 'http://example.com/img1.png', name: 'img1.png' },
      { url: 'http://example.com/img2.png', name: 'img2.png' }
    );
    mainModule.renderGallery();

    const container = document.getElementById('gallery-container');
    const cards = container.querySelectorAll('.gallery-image-card:not(.add-image-card)');
    expect(cards.length).toBe(2);
    expect(cards[0].querySelector('img').src).toBe('http://example.com/img1.png');

    // Click triggers overlay opening
    cards[1].click();
    const overlay = document.getElementById('gallery-overlay');
    expect(overlay.style.display).toBe('flex');
    expect(document.getElementById('gallery-overlay-img').src).toBe('http://example.com/img2.png');
  });

  it('closeGalleryOverlay hides the overlay modal', () => {
    mainModule.currentImages.push({ url: 'http://example.com/img1.png', name: 'img1.png' });
    mainModule.openGalleryOverlay(0);
    
    const overlay = document.getElementById('gallery-overlay');
    expect(overlay.style.display).toBe('flex');

    mainModule.closeGalleryOverlay();
    expect(overlay.classList.contains('open')).toBe(false);
  });

  it('navigateGallery cycles correctly across images forwards and backwards', () => {
    mainModule.currentImages.push(
      { url: 'http://example.com/img1.png', name: 'img1.png' },
      { url: 'http://example.com/img2.png', name: 'img2.png' },
      { url: 'http://example.com/img3.png', name: 'img3.png' }
    );

    mainModule.openGalleryOverlay(1); // Start at index 1 (img2)
    const imgEl = document.getElementById('gallery-overlay-img');
    expect(imgEl.src).toBe('http://example.com/img2.png');

    // Next
    mainModule.navigateGallery(1);
    expect(imgEl.src).toBe('http://example.com/img3.png');

    // Next (cycles to start)
    mainModule.navigateGallery(1);
    expect(imgEl.src).toBe('http://example.com/img1.png');

    // Prev (cycles to end)
    mainModule.navigateGallery(-1);
    expect(imgEl.src).toBe('http://example.com/img3.png');
  });
});
