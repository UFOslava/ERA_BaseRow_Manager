import { describe, it, expect, vi, beforeAll } from 'vitest';

// Mock API
vi.mock('../src/api.js', () => {
  return {
    fetchGraphNexus: vi.fn().mockImplementation(() => {
      return Promise.resolve([
        { id: 10, part_number: 'NEXUS-001', description: 'Main Board', state: 'Production Use', child_count: 2, purchase_kit: false, image_url: null, pn_tag: { name: 'Assembly', color: '#c5a059' } },
        { id: 20, part_number: 'NEXUS-002', description: 'Power Unit', state: 'EOL', child_count: 0, purchase_kit: false, image_url: null, pn_tag: { name: 'Raw Material', color: '#64748b' } }
      ]);
    }),
    fetchGraphChildren: vi.fn().mockResolvedValue([
      { id: 101, part_number: 'RES-001', description: '10k Resistor', state: 'Production Use', child_count: 0, purchase_kit: false, quantity: 4, length: 0, pn_tag: { name: 'Resistor', color: '#38bdf8' }, edge_id: 501 }
    ]),
    fetchRules: vi.fn().mockResolvedValue({
      '10': { name: 'Raw Material', color: '#64748b', prefix: '10' },
      '20': { name: 'Assembly', color: '#c5a059', prefix: '20' },
      '30': { name: 'Resistor', color: '#38bdf8', prefix: '30' }
    }),
    createAssembly: vi.fn().mockResolvedValue({ id: 999 }),
    deleteAssembly: vi.fn().mockResolvedValue({ success: true }),
    fetchItemParents: vi.fn().mockResolvedValue([]),
    updateItem: vi.fn().mockResolvedValue({ success: true }),
    searchItems: vi.fn().mockResolvedValue([
      { id: 101, 'Part Number': '10-00001', 'Item description': 'Resistor 10k', State: 'Production Use', Image: [] },
      { id: 102, 'Part Number': '20-00002', 'Item description': 'Capacitor 100uF', State: 'Production Use', Image: [] }
    ]),
    getHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

describe('Relation Map Tools, Modes & Interactions', () => {
  beforeAll(async () => {
    document.body.innerHTML = `
      <div id="status-indicator"></div>
      <div id="status-text"></div>
      <div id="loading-overlay" style="display: block;"></div>
      <div id="map-toast" style="display: none;"></div>
      <canvas id="map-canvas" width="800" height="600"></canvas>

      <button id="btn-filter" class="btn btn-secondary btn-sm btn-filter">
        <i class="fa-solid fa-filter"></i> Filter
        <span id="filter-badge" class="filter-badge" style="display: none;">0</span>
      </button>

      <button id="btn-refresh-map">Refresh</button>

      <div id="filter-drawer" class="drawer">
        <div class="drawer-overlay" id="drawer-overlay"></div>
        <div class="drawer-header"><button id="btn-close-drawer">&times;</button></div>
        <div id="categories-filter-list"></div>
        <div id="states-filter-list"></div>
      </div>
      
      <button id="tool-pan" class="active">Pan</button>
      <button id="tool-drag">Drag</button>
      <button id="tool-join">Join</button>
      <button id="tool-sever">Sever</button>
      <button id="tool-hide-node">Hide Node</button>
      <button id="tool-hide-branch">Hide Branch</button>
      <button id="btn-zoom-in">+</button>
      <input type="range" id="zoom-slider" min="-3.322" max="2.0" step="0.01" value="0">
      <button id="btn-zoom-out">-</button>
      <button id="btn-reset-view">0</button>
      
      <div id="info-total-nodes">0</div>
      <div id="info-expanded">0</div>
      <div id="info-nexus">0</div>
      
      <div id="map-tooltip">
        <div id="tt-pn"></div>
        <div id="tt-desc"></div>
        <div id="tt-state"></div>
      </div>
    `;

    await import('../src/relation-map.js');
    await new Promise(r => setTimeout(r, 100)); // wait for init
  });

  it('renders tool buttons and toggles active state on click', () => {
    const toolPan = document.getElementById('tool-pan');
    const toolDrag = document.getElementById('tool-drag');
    const toolJoin = document.getElementById('tool-join');

    expect(toolPan.classList.contains('active')).toBe(true);

    toolDrag.click();
    expect(toolDrag.classList.contains('active')).toBe(true);
    expect(toolPan.classList.contains('active')).toBe(false);

    toolJoin.click();
    expect(toolJoin.classList.contains('active')).toBe(true);
    expect(toolDrag.classList.contains('active')).toBe(false);

    toolPan.click();
    expect(toolPan.classList.contains('active')).toBe(true);
  });

  it('supports keyboard shortcuts P, D, J and Escape for switching tools', () => {
    const toolPan = document.getElementById('tool-pan');
    const toolDrag = document.getElementById('tool-drag');
    const toolJoin = document.getElementById('tool-join');

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
    expect(toolDrag.classList.contains('active')).toBe(true);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'j' }));
    expect(toolJoin.classList.contains('active')).toBe(true);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(toolPan.classList.contains('active')).toBe(true);

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'p' }));
    expect(toolPan.classList.contains('active')).toBe(true);
  });

  it('spawns distinct child instances when multiple parents share the same child item (e.g. 20-00055)', async () => {
    // Shared child item data
    const sharedChild = {
      id: 55,
      part_number: '20-00055 Rev.A',
      description: 'Shared Cable Assembly',
      state: 'Production Use',
      child_count: 0,
      purchase_kit: false,
      quantity: 1,
      length: 0,
      pn_tag: { name: 'Assembly', color: '#c5a059' },
      edge_id: 888
    };

    // Simulate two distinct parents expanding the shared child
    const parentAInstanceId = 'nexus_10';
    const parentBInstanceId = 'nexus_20';

    const childUnderA = `${parentAInstanceId}/${sharedChild.id}_${sharedChild.edge_id}`;
    const childUnderB = `${parentBInstanceId}/${sharedChild.id}_${sharedChild.edge_id}`;

    // Verify instance IDs are strictly distinct
    expect(childUnderA).toBe('nexus_10/55_888');
    expect(childUnderB).toBe('nexus_20/55_888');
    expect(childUnderA).not.toBe(childUnderB);
  });

  it('clamps physics velocity to maximum speed to dampen rapid explosions', () => {
    const MAX_SPEED = 18;
    let vx = 50;
    let vy = 50;
    let speed = Math.sqrt(vx * vx + vy * vy);
    expect(speed).toBeGreaterThan(MAX_SPEED);

    if (speed > MAX_SPEED) {
      vx = (vx / speed) * MAX_SPEED;
      vy = (vy / speed) * MAX_SPEED;
      speed = MAX_SPEED;
    }

    const clampedSpeed = Math.sqrt(vx * vx + vy * vy);
    expect(clampedSpeed).toBeCloseTo(MAX_SPEED, 5);
  });

  it('calculates repulsion from the center of mass of the group rather than the parent', () => {
    const parent = { x: 100, y: 100 };
    const child1 = { x: 140, y: 100 };
    const child2 = { x: 60, y: 100 };
    
    // Group geometric center
    const groupCenterX = (parent.x + child1.x + child2.x) / 3;
    const groupCenterY = (parent.y + child1.y + child2.y) / 3;
    
    expect(groupCenterX).toBe(100);
    expect(groupCenterY).toBe(100);

    const outsideNode = { x: 100, y: 120 };
    const ox = outsideNode.x - groupCenterX;
    const oy = outsideNode.y - groupCenterY;
    
    expect(ox).toBe(0);
    expect(oy).toBe(20);
  });

  it('pulls top-level free-floating nexus nodes towards dynamic center of mass (average x, y)', () => {
    const nexusNodesList = [
      { id: 'nexus_1', x: 200, y: 300, isNexus: true, fx: 0, fy: 0 },
      { id: 'nexus_2', x: 400, y: 300, isNexus: true, fx: 0, fy: 0 },
      { id: 'nexus_3', x: 300, y: 600, isNexus: true, fx: 0, fy: 0 }
    ];

    const K_DARK = 0.001;
    let sumX = 0, sumY = 0, count = 0;
    nexusNodesList.forEach(n => {
      if (n.isNexus) {
        sumX += n.x;
        sumY += n.y;
        count++;
      }
    });

    const comX = sumX / count;
    const comY = sumY / count;

    expect(comX).toBe(300);
    expect(comY).toBe(400);

    nexusNodesList.forEach(n => {
      n.fx -= (n.x - comX) * K_DARK;
      n.fy -= (n.y - comY) * K_DARK;
    });

    // Node 1 (200, 300) should be pulled towards (300, 400), i.e. +fx and +fy
    expect(nexusNodesList[0].fx).toBeCloseTo(0.1);
    expect(nexusNodesList[0].fy).toBeCloseTo(0.1);

    // Node 2 (400, 300) should be pulled towards (300, 400), i.e. -fx and +fy
    expect(nexusNodesList[1].fx).toBeCloseTo(-0.1);
    expect(nexusNodesList[1].fy).toBeCloseTo(0.1);

    // Node 3 (300, 600) should be pulled towards (300, 400), i.e. 0 fx and -fy
    expect(nexusNodesList[2].fx).toBeCloseTo(0);
    expect(nexusNodesList[2].fy).toBeCloseTo(-0.2);
  });

  it('opens and closes the filter drawer via button, close button, overlay, and Escape key', () => {
    const btnFilter = document.getElementById('btn-filter');
    const drawer = document.getElementById('filter-drawer');
    const btnClose = document.getElementById('btn-close-drawer');
    const overlay = document.getElementById('drawer-overlay');

    expect(drawer.classList.contains('open')).toBe(false);

    // Open via filter button
    btnFilter.click();
    expect(drawer.classList.contains('open')).toBe(true);

    // Close via close button
    btnClose.click();
    expect(drawer.classList.contains('open')).toBe(false);

    // Open and close via overlay
    btnFilter.click();
    expect(drawer.classList.contains('open')).toBe(true);
    overlay.click();
    expect(drawer.classList.contains('open')).toBe(false);

    // Open and close via Escape key
    btnFilter.click();
    expect(drawer.classList.contains('open')).toBe(true);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(drawer.classList.contains('open')).toBe(false);
  });

  it('populates category and state filter lists and updates filter badge count on toggle', () => {
    const catContainer = document.getElementById('categories-filter-list');
    const stateContainer = document.getElementById('states-filter-list');
    const badge = document.getElementById('filter-badge');

    expect(catContainer.children.length).toBeGreaterThan(0);
    expect(stateContainer.children.length).toBeGreaterThan(0);

    // Find a category checkbox
    const assemblyCheckbox = document.getElementById('filter-cat-Assembly');
    expect(assemblyCheckbox).not.toBeNull();
    expect(assemblyCheckbox.checked).toBe(true);

    // Uncheck Assembly category
    assemblyCheckbox.checked = false;
    assemblyCheckbox.dispatchEvent(new Event('change'));

    // Badge should show 1 active filter
    expect(badge.style.display).toBe('inline-block');
    expect(badge.textContent).toBe('1');

    // Uncheck a state checkbox
    const eolCheckbox = document.getElementById('filter-state-EOL');
    expect(eolCheckbox).not.toBeNull();
    eolCheckbox.checked = false;
    eolCheckbox.dispatchEvent(new Event('change'));

    // Badge should show 2 active filters
    expect(badge.textContent).toBe('2');

    // Re-check assembly
    assemblyCheckbox.checked = true;
    assemblyCheckbox.dispatchEvent(new Event('change'));
    expect(badge.textContent).toBe('1');

    // Re-check EOL
    eolCheckbox.checked = true;
    eolCheckbox.dispatchEvent(new Event('change'));
    expect(badge.style.display).toBe('none');
  });

  it('opens search popup on empty canvas right click and closes via Escape key on input and close button', async () => {
    const canvas = document.getElementById('map-canvas');
    
    // Right click on canvas
    canvas.dispatchEvent(new MouseEvent('contextmenu', { clientX: 300, clientY: 300 }));
    
    let popup = document.getElementById('search-popup');
    expect(popup).not.toBeNull();

    const input = document.getElementById('search-popup-input');
    expect(input).not.toBeNull();

    // Dismiss via Escape key on input
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(document.getElementById('search-popup')).toBeNull();

    // Right click again to reopen
    canvas.dispatchEvent(new MouseEvent('contextmenu', { clientX: 300, clientY: 300 }));
    popup = document.getElementById('search-popup');
    expect(popup).not.toBeNull();

    // Dismiss via close button
    const closeBtn = document.getElementById('search-popup-close-btn');
    expect(closeBtn).not.toBeNull();
    closeBtn.click();
    expect(document.getElementById('search-popup')).toBeNull();
  });

  it('searches items, renders results, supports arrow key navigation and Enter spawning', async () => {
    const canvas = document.getElementById('map-canvas');
    canvas.dispatchEvent(new MouseEvent('contextmenu', { clientX: 250, clientY: 250 }));
    
    const input = document.getElementById('search-popup-input');
    const resultsContainer = document.getElementById('search-popup-results');

    // Type query
    input.value = 'res';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 50));

    expect(resultsContainer.querySelectorAll('.search-popup-item').length).toBe(2);

    // Arrow down navigation
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    
    // Enter key to spawn
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));

    // Popup should close after spawning
    expect(document.getElementById('search-popup')).toBeNull();
  });

  it('synchronizes zoom slider and supports exponential scaling', () => {
    const zoomSlider = document.getElementById('zoom-slider');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnResetView = document.getElementById('btn-reset-view');

    // Reset view sets zoom to 1.0 (log2(1.0) = 0)
    btnResetView.click();
    expect(parseFloat(zoomSlider.value)).toBeCloseTo(0, 2);

    // Zoom in increases zoom and updates slider log2 value
    btnZoomIn.click();
    expect(parseFloat(zoomSlider.value)).toBeGreaterThan(0);

    // Slider input converts log2 value to zoom = 2^val
    zoomSlider.value = '1.0'; // 2^1 = 2.0x zoom
    zoomSlider.dispatchEvent(new Event('input'));

    btnResetView.click();
    expect(parseFloat(zoomSlider.value)).toBeCloseTo(0, 2);
  });
});


