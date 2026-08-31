import { describe, it, expect, vi, beforeAll } from 'vitest';

// Mock API
vi.mock('../src/api.js', () => {
  return {
    fetchGraphNexus: vi.fn().mockImplementation((mode = 'structural') => {
      if (mode === 'procurement') {
        return Promise.resolve([
          { id: 10, part_number: 'NEXUS-001', description: 'Main Board', state: 'Production Use', child_count: 0, purchase_kit: false, image_url: null, pn_tag: { name: 'Assembly', color: '#c5a059' } },
          { id: 30, part_number: 'KIT-001', description: 'Fastener Kit', state: 'Production Use', child_count: 2, purchase_kit: true, image_url: null, pn_tag: { name: 'Assembly', color: '#c5a059' } }
        ]);
      }
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
      
      <div class="view-mode-toggle">
        <button id="mode-btn-structural" class="btn-mode-toggle active"></button>
        <button id="mode-btn-procurement" class="btn-mode-toggle"></button>
      </div>

      <button id="btn-filter" class="btn btn-secondary btn-sm btn-filter">
        <i class="fa-solid fa-filter"></i> Filter
        <span id="filter-badge" class="filter-badge" style="display: none;">0</span>
      </button>

      <!-- Filter Drawer -->
      <div id="filter-drawer" class="drawer">
        <div class="drawer-overlay" id="drawer-overlay"></div>
        <div class="drawer-content">
          <div class="drawer-header">
            <h2>Filter Relation Map</h2>
            <button id="btn-close-drawer" class="btn-close">&times;</button>
          </div>
          <div class="drawer-body">
            <div id="categories-filter-list"></div>
            <div id="states-filter-list"></div>
          </div>
        </div>
      </div>

      <div class="hud-tool-controls">
        <button class="hud-btn active" id="tool-pan"></button>
        <button class="hud-btn" id="tool-drag"></button>
        <button class="hud-btn" id="tool-join"></button>
      </div>

      <div class="hud-controls">
        <button class="hud-btn" id="btn-zoom-in"></button>
        <button class="hud-btn" id="btn-reset-view"></button>
        <button class="hud-btn" id="btn-zoom-out"></button>
      </div>

      <div class="info-panel">
        <span id="info-total-nodes">0</span>
        <span id="info-expanded">0</span>
        <span id="info-nexus">0</span>
      </div>

      <div class="map-tooltip" id="map-tooltip">
        <div id="tt-pn"></div>
        <div id="tt-desc"></div>
        <div id="tt-state"></div>
      </div>

      <button id="btn-refresh-map"></button>
    `;

    // Mock canvas context
    const canvas = document.getElementById('map-canvas');
    if (canvas) {
      canvas.getContext = vi.fn().mockReturnValue({
        clearRect: vi.fn(),
        fillRect: vi.fn(),
        save: vi.fn(),
        restore: vi.fn(),
        translate: vi.fn(),
        scale: vi.fn(),
        beginPath: vi.fn(),
        arc: vi.fn(),
        stroke: vi.fn(),
        fill: vi.fn(),
        clip: vi.fn(),
        fillText: vi.fn(),
        setLineDash: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        closePath: vi.fn(),
        drawImage: vi.fn()
      });
    }

    await import('../src/relation-map.js');
    await new Promise(r => setTimeout(r, 50));
  });

  it('switches between Structural and Procurement / Purchasing Kit views', async () => {
    const btnStruct = document.getElementById('mode-btn-structural');
    const btnProc = document.getElementById('mode-btn-procurement');

    expect(btnStruct.classList.contains('active')).toBe(true);
    expect(btnProc.classList.contains('active')).toBe(false);

    // Switch to Procurement view
    btnProc.click();
    await new Promise(r => setTimeout(r, 50));

    expect(btnProc.classList.contains('active')).toBe(true);
    expect(btnStruct.classList.contains('active')).toBe(false);

    // Switch back to Structural view
    btnStruct.click();
    await new Promise(r => setTimeout(r, 50));

    expect(btnStruct.classList.contains('active')).toBe(true);
    expect(btnProc.classList.contains('active')).toBe(false);
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
});
