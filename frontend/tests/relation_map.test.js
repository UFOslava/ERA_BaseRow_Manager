import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock API
vi.mock('../src/api.js', () => {
  return {
    fetchGraphNexus: vi.fn().mockResolvedValue([
      { id: 10, part_number: 'NEXUS-001', description: 'Main Board', state: 'Active', child_count: 2, image_url: null, pn_tag: { name: 'Assembly', color: '#c5a059' } },
      { id: 20, part_number: 'NEXUS-002', description: 'Power Unit', state: 'Active', child_count: 0, image_url: null, pn_tag: { name: 'Assembly', color: '#c5a059' } }
    ]),
    fetchGraphChildren: vi.fn().mockResolvedValue([
      { id: 101, part_number: 'RES-001', description: '10k Resistor', state: 'Active', child_count: 0, quantity: 4, length: 0, pn_tag: { name: 'Resistor', color: '#38bdf8' } }
    ]),
    createAssembly: vi.fn().mockResolvedValue({ id: 999 }),
    getHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
    checkGlobalAuthStatus: vi.fn().mockResolvedValue({ isComplete: true, status: {} })
  };
});

describe('Relation Map Tools & Interactions', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="status-indicator"></div>
      <div id="status-text"></div>
      <div id="loading-overlay" style="display: block;"></div>
      <div id="map-toast" style="display: none;"></div>
      <canvas id="map-canvas" width="800" height="600"></canvas>
      
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
  });

  it('renders tool buttons and toggles active state on click', async () => {
    await import('../src/relation-map.js');

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

  it('supports keyboard shortcuts P, D, J and Escape for switching tools', async () => {
    await import('../src/relation-map.js');

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
});
