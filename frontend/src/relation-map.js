import { fetchGraphNexus, fetchGraphChildren, getHealth, checkGlobalAuthStatus, createAssembly, fetchRules, deleteAssembly, fetchItemParents, updateItem, searchItems } from './api.js';

const canvas = document.getElementById('map-canvas');
const ctx = canvas.getContext('2d');
const tooltip = document.getElementById('map-tooltip');
const ttPn = document.getElementById('tt-pn');
const ttDesc = document.getElementById('tt-desc');
const ttState = document.getElementById('tt-state');

let width = window.innerWidth;
let height = window.innerHeight;
canvas.width = width;
canvas.height = height;

// Filter state
let categoryRules = {};
let disabledCategories = new Set();
let disabledStates = new Set();

const STATE_COLORS = {
  "Production Use": "#00FF00",
  "Engineerig Use": "hsl(210, 75%, 50%)",
  "Unknown": "hsl(0, 0%, 60%)",
  "Finish Stock (Use Up)": "hsl(38, 95%, 50%)",
  "EOL": "hsl(25, 75%, 45%)",
  "Do Not Use (Discard)": "hsl(355, 80%, 50%)"
};

// Tools & Interaction state
let currentTool = 'pan'; // 'pan' | 'drag' | 'join' | 'sever' | 'hide-node' | 'hide-branch'
let isNodeDragging = false;
let draggedNode = null;
let joinSourceNode = null;
let joinCandidateTarget = null;
let joinCursorPos = null;
let joinMouseDownPos = null;
let toastTimeout = null;

// Camera state
let camera = { x: 0, y: 0, zoom: 1 };
let isDragging = false;
let lastMouse = { x: 0, y: 0 };
let hoveredNode = null;
let hoveredEdge = null;
let branchNodes = new Set();

// Graph state
let nodes = new Map(); // instanceId -> node object
let edges = []; // { sourceId, targetId, qty, length, color, edgeId }
let nexusNodes = new Set(); // set of nexus instance IDs
let imageCache = new Map(); // url -> Image object

let simulationActive = false;
let simulationAlpha = 1;

// Metrics
let totalNodesCount = 0;
let expandedNexusCount = 0;

// Setup status check
async function checkHealth() {
  try {
    const authState = await checkGlobalAuthStatus();
    if (authState.isComplete) {
      const indicator = document.getElementById('status-indicator');
      const text = document.getElementById('status-text');
      if (indicator) indicator.className = 'status-indicator healthy';
      if (text) text.textContent = 'Connected';
    }
  } catch (err) {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    if (indicator) indicator.className = 'status-indicator error';
    if (text) text.textContent = 'Offline';
  }
}

function showToast(message, isError = false) {
  const toast = document.getElementById('map-toast');
  if (!toast) return;
  if (toastTimeout) clearTimeout(toastTimeout);
  toast.innerHTML = (isError ? '<i class="fa-solid fa-triangle-exclamation" style="color: var(--color-danger);"></i> ' : '<i class="fa-solid fa-circle-check" style="color: var(--color-success);"></i> ') + message;
  toast.style.borderColor = isError ? 'var(--color-danger)' : 'var(--color-gold)';
  toast.style.display = 'flex';
  toast.style.opacity = '1';
  toastTimeout = setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => { toast.style.display = 'none'; }, 300);
  }, 3000);
}

function setTool(tool) {
  currentTool = tool;
  ['tool-pan', 'tool-drag', 'tool-join', 'tool-sever', 'tool-hide-node', 'tool-hide-branch'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.classList.toggle('active', id === `tool-${tool}`);
  });
  joinSourceNode = null;
  joinCandidateTarget = null;
  joinCursorPos = null;
  joinMouseDownPos = null;
  updateCursor(!!hoveredNode);
}

function updateCursor(isHoveringNode = false) {
  if (currentTool === 'pan') {
    canvas.style.cursor = isDragging ? 'grabbing' : (isHoveringNode ? 'pointer' : 'grab');
  } else if (currentTool === 'drag') {
    canvas.style.cursor = isNodeDragging ? 'grabbing' : (isHoveringNode ? 'move' : (isDragging ? 'grabbing' : 'default'));
  } else if (currentTool === 'join') {
    canvas.style.cursor = isHoveringNode ? 'pointer' : 'crosshair';
  }
}

async function handleJoin(sourceChild, targetParent) {
  if (!sourceChild || !targetParent) return;
  if (sourceChild.itemId === targetParent.itemId) {
    showToast("Cannot connect an item to itself.", true);
    return;
  }
  
  const alreadyConnected = edges.some(e => e.sourceId === targetParent.id && e.targetId === sourceChild.id);
  if (alreadyConnected) {
    showToast(`"${sourceChild.pn || 'Item'}" is already a child of "${targetParent.pn || 'Parent'}".`, true);
    return;
  }
  
  try {
    const res = await createAssembly(targetParent.itemId, sourceChild.itemId, 1, 0, '');
    const edgeId = res?.id || res?.data?.id || null;
    edges.push({
      sourceId: targetParent.id,
      targetId: sourceChild.id,
      qty: 1,
      length: 0,
      color: adjustColor(sourceChild.color, -30),
      edgeId: edgeId
    });

    targetParent.child_count = (targetParent.child_count || 0) + 1;
    targetParent.expanded = true;
    targetParent.childrenFetched = true;
    nexusNodes.delete(sourceChild.id);

    updateNodeScales();
    updateHudMetrics();
    startSimulation();
    showToast(`Linked "${sourceChild.pn || 'Item'}" as child of "${targetParent.pn || 'Parent'}"`);
  } catch (err) {
    showToast(`Failed to create assembly relation: ${err.message}`, true);
  } finally {
    joinSourceNode = null;
    joinCandidateTarget = null;
    joinCursorPos = null;
    joinMouseDownPos = null;
  }
}

// Filter functions
function isNodeFiltered(node) {
  if (!node) return false;
  const categoryName = node.category || node.pn_tag?.name || 'Unknown';
  if (disabledCategories.has(categoryName)) return true;
  const stateName = node.state || 'Unknown';
  if (disabledStates.has(stateName)) return true;
  return false;
}

function updateFilterBadge() {
  const badge = document.getElementById('filter-badge');
  if (!badge) return;
  const count = disabledCategories.size + disabledStates.size;
  if (count > 0) {
    badge.textContent = count;
    badge.style.display = 'inline-block';
  } else {
    badge.style.display = 'none';
  }
}

function openFilterDrawer() {
  const drawer = document.getElementById('filter-drawer');
  if (drawer) drawer.classList.add('open');
}

function closeFilterDrawer() {
  const drawer = document.getElementById('filter-drawer');
  if (drawer) drawer.classList.remove('open');
}

function renderDrawerCategories() {
  const container = document.getElementById('categories-filter-list');
  if (!container) return;
  container.innerHTML = '';
  
  const categoriesList = [];
  Object.entries(categoryRules).forEach(([prefix, rule]) => {
    if (rule.name) {
      categoriesList.push({
        prefix: prefix,
        name: rule.name,
        displayName: `${prefix} - ${rule.name}`,
        color: rule.color || '#8e9095'
      });
    }
  });
  
  categoriesList.push({
    prefix: '999',
    name: 'Unknown',
    displayName: 'Unknown',
    color: '#8e9095'
  });
  
  const sortedCategories = categoriesList.sort((a, b) => a.prefix.localeCompare(b.prefix, undefined, { numeric: true }));
  
  // Select All
  const selectAllEl = document.createElement('div');
  selectAllEl.className = 'category-filter-item select-all-item';
  selectAllEl.style.fontWeight = '600';
  selectAllEl.style.borderBottom = '1px solid var(--card-border)';
  selectAllEl.style.paddingBottom = '0.5rem';
  selectAllEl.style.marginBottom = '0.5rem';
  selectAllEl.style.display = 'flex';
  selectAllEl.style.alignItems = 'center';
  selectAllEl.style.gap = '0.5rem';
  selectAllEl.style.cursor = 'pointer';
  
  const selectAllCheckbox = document.createElement('input');
  selectAllCheckbox.type = 'checkbox';
  selectAllCheckbox.className = 'category-filter-checkbox';
  selectAllCheckbox.checked = disabledCategories.size === 0;
  selectAllCheckbox.id = 'filter-cat-select-all';
  
  const selectAllLabel = document.createElement('label');
  selectAllLabel.className = 'category-filter-label';
  selectAllLabel.htmlFor = selectAllCheckbox.id;
  selectAllLabel.textContent = 'Select All';
  selectAllLabel.style.cursor = 'pointer';
  
  selectAllEl.appendChild(selectAllCheckbox);
  selectAllEl.appendChild(selectAllLabel);
  
  selectAllCheckbox.addEventListener('change', () => {
    if (selectAllCheckbox.checked) {
      disabledCategories.clear();
    } else {
      sortedCategories.forEach(cat => {
        disabledCategories.add(cat.name);
      });
    }
    renderDrawerCategories();
    updateFilterBadge();
  });
  
  selectAllEl.addEventListener('click', (e) => {
    if (e.target !== selectAllCheckbox && e.target !== selectAllLabel && !selectAllLabel.contains(e.target)) {
      selectAllCheckbox.checked = !selectAllCheckbox.checked;
      selectAllCheckbox.dispatchEvent(new Event('change'));
    }
  });
  
  container.appendChild(selectAllEl);
  
  sortedCategories.forEach(({ name, displayName, color }) => {
    const isEnabled = !disabledCategories.has(name);
    
    const itemEl = document.createElement('div');
    itemEl.className = 'category-filter-item';
    itemEl.style.display = 'flex';
    itemEl.style.alignItems = 'center';
    itemEl.style.gap = '0.5rem';
    itemEl.style.cursor = 'pointer';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'category-filter-checkbox';
    checkbox.checked = isEnabled;
    checkbox.id = `filter-cat-${name.replace(/\s+/g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'category-filter-label';
    label.htmlFor = checkbox.id;
    label.style.display = 'flex';
    label.style.alignItems = 'center';
    label.style.gap = '0.5rem';
    label.style.cursor = 'pointer';
    
    const colorDot = document.createElement('span');
    colorDot.className = 'category-color-dot';
    colorDot.style.backgroundColor = color;
    colorDot.style.width = '10px';
    colorDot.style.height = '10px';
    colorDot.style.borderRadius = '50%';
    colorDot.style.display = 'inline-block';
    
    const nameText = document.createTextNode(displayName);
    
    label.appendChild(colorDot);
    label.appendChild(nameText);
    
    itemEl.appendChild(checkbox);
    itemEl.appendChild(label);
    
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        disabledCategories.delete(name);
      } else {
        disabledCategories.add(name);
      }
      updateFilterBadge();
    });
    
    itemEl.addEventListener('click', (e) => {
      if (e.target !== checkbox && e.target !== label && !label.contains(e.target)) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    container.appendChild(itemEl);
  });
  
  updateFilterBadge();
}

function renderDrawerStates() {
  const container = document.getElementById('states-filter-list');
  if (!container) return;
  container.innerHTML = '';
  
  const states = Object.keys(STATE_COLORS);
  
  // Select All
  const selectAllEl = document.createElement('div');
  selectAllEl.className = 'category-filter-item select-all-item';
  selectAllEl.style.fontWeight = '600';
  selectAllEl.style.borderBottom = '1px solid var(--card-border)';
  selectAllEl.style.paddingBottom = '0.5rem';
  selectAllEl.style.marginBottom = '0.5rem';
  selectAllEl.style.display = 'flex';
  selectAllEl.style.alignItems = 'center';
  selectAllEl.style.gap = '0.5rem';
  selectAllEl.style.cursor = 'pointer';
  
  const selectAllCheckbox = document.createElement('input');
  selectAllCheckbox.type = 'checkbox';
  selectAllCheckbox.className = 'category-filter-checkbox';
  selectAllCheckbox.checked = disabledStates.size === 0;
  selectAllCheckbox.id = 'filter-state-select-all';
  
  const selectAllLabel = document.createElement('label');
  selectAllLabel.className = 'category-filter-label';
  selectAllLabel.htmlFor = selectAllCheckbox.id;
  selectAllLabel.textContent = 'Select All';
  selectAllLabel.style.cursor = 'pointer';
  
  selectAllEl.appendChild(selectAllCheckbox);
  selectAllEl.appendChild(selectAllLabel);
  
  selectAllCheckbox.addEventListener('change', () => {
    if (selectAllCheckbox.checked) {
      disabledStates.clear();
    } else {
      states.forEach(s => {
        disabledStates.add(s);
      });
    }
    renderDrawerStates();
    updateFilterBadge();
  });
  
  selectAllEl.addEventListener('click', (e) => {
    if (e.target !== selectAllCheckbox && e.target !== selectAllLabel && !selectAllLabel.contains(e.target)) {
      selectAllCheckbox.checked = !selectAllCheckbox.checked;
      selectAllCheckbox.dispatchEvent(new Event('change'));
    }
  });
  
  container.appendChild(selectAllEl);
  
  states.forEach(stateName => {
    const isEnabled = !disabledStates.has(stateName);
    const color = STATE_COLORS[stateName] || '#8e9095';
    
    const itemEl = document.createElement('div');
    itemEl.className = 'category-filter-item';
    itemEl.style.display = 'flex';
    itemEl.style.alignItems = 'center';
    itemEl.style.gap = '0.5rem';
    itemEl.style.cursor = 'pointer';
    
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'category-filter-checkbox';
    checkbox.checked = isEnabled;
    checkbox.id = `filter-state-${stateName.replace(/\s+/g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'category-filter-label';
    label.htmlFor = checkbox.id;
    label.style.display = 'flex';
    label.style.alignItems = 'center';
    label.style.gap = '0.5rem';
    label.style.cursor = 'pointer';
    
    const colorDot = document.createElement('span');
    colorDot.className = 'category-color-dot';
    colorDot.style.backgroundColor = color;
    colorDot.style.width = '10px';
    colorDot.style.height = '10px';
    colorDot.style.borderRadius = '50%';
    colorDot.style.display = 'inline-block';
    
    const nameText = document.createTextNode(stateName === 'Engineerig Use' ? 'Engineering Use' : stateName);
    
    label.appendChild(colorDot);
    label.appendChild(nameText);
    
    itemEl.appendChild(checkbox);
    itemEl.appendChild(label);
    
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) {
        disabledStates.delete(stateName);
      } else {
        disabledStates.add(stateName);
      }
      updateFilterBadge();
    });
    
    itemEl.addEventListener('click', (e) => {
      if (e.target !== checkbox && e.target !== label && !label.contains(e.target)) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
      }
    });
    
    container.appendChild(itemEl);
  });
  
  updateFilterBadge();
}

async function initFilters() {
  try {
    categoryRules = await fetchRules();
  } catch (err) {
    console.error("Failed to load category rules for filter drawer", err);
    categoryRules = {};
  }
  renderDrawerCategories();
  renderDrawerStates();
}

// Background elements
const stars = [];
for (let i = 0; i < 200; i++) {
  stars.push({
    x: (Math.random() - 0.5) * 10000,
    y: (Math.random() - 0.5) * 10000,
    r: 0.5 + Math.random() * 1,
    alpha: 0.6 + Math.random() * 0.2
  });
}

function getNodeHeight(node) {
  if (!node) return 0;
  if (node.child_count === 0) return 0;
  
  if (node.expanded) {
    let maxChildHeight = 0;
    let hasVisibleChildren = false;
    edges.forEach(e => {
      if (e.sourceId === node.id) {
        const child = nodes.get(e.targetId);
        if (child) {
          hasVisibleChildren = true;
          maxChildHeight = Math.max(maxChildHeight, getNodeHeight(child));
        }
      }
    });
    if (hasVisibleChildren) {
      return 1 + maxChildHeight;
    }
  }
  return 1;
}

function getNodeScale(node) {
  const height = getNodeHeight(node);
  return Math.pow(1.2, height);
}

function updateNodeScales() {
  nodes.forEach(node => {
    const scale = getNodeScale(node);
    node.scale = scale;
    node.radius = computeRadius(node, scale);
  });
}

function computeRadius(node, scale) {
  const childCount = node.child_count || 0;
  const baseRadius = 20 + Math.min(childCount * 3, 24); // 20 to 44
  return baseRadius * scale;
}

function processNodeData(data, isNexus = false, parentInstanceId = null, edgeId = null) {
  const category = data.pn_tag?.name || 'Unknown';
  const instanceId = `${data.id}_${Math.random().toString(36).substr(2, 6)}`;

  if (nodes.has(instanceId)) {
    const node = nodes.get(instanceId);
    node.itemId = data.id;
    node.pn = data.part_number || '';
    node.desc = data.description || '';
    node.state = data.state || 'Unknown';
    node.category = category;
    node.child_count = data.child_count || 0;
    node.purchase_kit = !!data.purchase_kit;
    node.color = data.pn_tag?.color || '#8e9095';
    node.imageUrl = data.image_url;
    return node;
  }

  const radius = computeRadius(data, 1.0);
  const color = data.pn_tag?.color || '#8e9095';
  
  // Random initial position near parent or center
  let startX = (Math.random() - 0.5) * 100;
  let startY = (Math.random() - 0.5) * 100;
  
  if (parentInstanceId && nodes.has(parentInstanceId)) {
    const pNode = nodes.get(parentInstanceId);
    // Distribute initial positions evenly in a circle around the parent to break symmetry immediately
    const angle = Math.random() * Math.PI * 2;
    const spawnDist = 30 + Math.random() * 20;
    startX = pNode.x + Math.cos(angle) * spawnDist;
    startY = pNode.y + Math.sin(angle) * spawnDist;
  } else if (isNexus) {
    // Grid-like spread centered around origin for initial nexus nodes
    const idx = nexusNodes.size;
    const cols = 6;
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    startX = (col - (cols - 1) / 2) * 220 + (Math.random() - 0.5) * 30;
    startY = (row - 1.5) * 220 + (Math.random() - 0.5) * 30;
  }

  const node = {
    id: instanceId,
    itemId: data.id,
    pn: data.part_number || '',
    desc: data.description || '',
    state: data.state || 'Unknown',
    category: category,
    child_count: data.child_count || 0,
    purchase_kit: !!data.purchase_kit,
    color: color,
    radius: radius,
    isNexus: isNexus,
    parentInstanceId: parentInstanceId,
    expanded: false,
    x: startX,
    y: startY,
    vx: 0,
    vy: 0,
    imageUrl: data.image_url,
    childrenFetched: false,
    clusterId: instanceId, // Freeform
    scale: 1.0,
    spawnTime: Date.now(),
    blackbox: !!data.blackbox // Make sure this is stored if it exists
  };
  
  if (data.image_url && !imageCache.has(data.image_url)) {
    const img = new Image();
    img.src = data.image_url;
    imageCache.set(data.image_url, img);
  }

  nodes.set(node.id, node);
  if (isNexus) nexusNodes.add(node.id);
  
  updateNodeScales();
  updateHudMetrics();
  
  return node;
}

async function loadGraph() {
  try {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.style.display = 'none';

    const authState = await checkGlobalAuthStatus();
    if (!authState.isComplete) {
      if (overlay) {
        overlay.style.display = 'block';
        overlay.innerHTML = `
          <div style="text-align: center; max-width: 400px; padding: 2rem;">
            <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #ef4444; margin-bottom: 1rem;"></i>
            <h2 style="font-size: 1.2rem; margin-bottom: 0.5rem;">Auth Incomplete</h2>
            <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.5rem;">Configure Baserow authentication in Settings to view the Relation Map.</p>
            <a href="/settings.html#auth" class="btn btn-primary" style="display: inline-block;">Configure Authentication</a>
          </div>
        `;
      }
      return;
    }

    // Sandbox starts completely empty
    nodes.clear();
    edges = [];
    nexusNodes.clear();
    expandedNexusCount = 0;

    updateNodeScales();
    updateHudMetrics();
    startSimulation();
  } catch (err) {
    console.error("Failed to initialize relation map", err);
  }
}

function startSimulation() {
  simulationActive = true;
  simulationAlpha = 1.0;
}

// Helper to dim colors
function adjustColor(color, amount) {
  // Simple hex adjust
  if (!color || color[0] !== '#') return '#8e9095';
  let num = parseInt(color.slice(1), 16);
  let r = (num >> 16) + amount;
  let g = ((num >> 8) & 0x00FF) + amount;
  let b = (num & 0x0000FF) + amount;
  r = Math.max(Math.min(255, r), 0);
  g = Math.max(Math.min(255, g), 0);
  b = Math.max(Math.min(255, b), 0);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`;
}

// Ray-segment intersection helper for boundary checks
function getRaySegmentIntersection(P, O_pos, A, B) {
  const ux = O_pos.x - P.x;
  const uy = O_pos.y - P.y;
  const uLen = Math.sqrt(ux * ux + uy * uy);
  if (uLen === 0) return null;
  const u_dir_x = ux / uLen;
  const u_dir_y = uy / uLen;

  const vx = B.x - A.x;
  const vy = B.y - A.y;

  const dx = A.x - P.x;
  const dy = A.y - P.y;

  const D = u_dir_y * vx - u_dir_x * vy;
  if (Math.abs(D) < 1e-6) return null;

  const t = (-dx * vy + dy * vx) / D;
  const s = (u_dir_x * dy - u_dir_y * dx) / D;

  if (t >= 0 && s >= 0 && s <= 1) {
    return {
      x: P.x + t * u_dir_x,
      y: P.y + t * u_dir_y,
      t: t
    };
  }
  return null;
}

// Physics Step
function stepPhysics() {
  if (!simulationActive) return;
  
  const K_REPEL = 20000;
  const K_SPRING = 0.05;
  const K_DARK = 0.001;
  const DAMPING = 0.85;
  const RAMP_TIME = 2.0; // 2 seconds to fully mature
  
  const now = Date.now();
  
  // Helper to compute node growth/ramp-up factor
  function getGrowth(n) {
    if (!n.spawnTime) return 1.0;
    return Math.min(1.0, (now - n.spawnTime) / (RAMP_TIME * 1000));
  }
  
  let maxVel = 0;
  
  const visibleNodes = getVisibleNodes();
  const visibleEdges = getVisibleEdges();
  
  // Reset forces
  visibleNodes.forEach(n => { n.fx = 0; n.fy = 0; });
  
  // Repulsion between neighbors (scaled by nodes growth)
  for (let i = 0; i < visibleNodes.length; i++) {
    for (let j = i + 1; j < visibleNodes.length; j++) {
      let a = visibleNodes[i];
      let b = visibleNodes[j];
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      let distSq = dx * dx + dy * dy;
      if (distSq < 0.1) { distSq = 0.1; dx = Math.random(); dy = Math.random(); }
      let dist = Math.sqrt(distSq);
      
      if (dist < 400) {
        const growthA = getGrowth(a);
        const growthB = getGrowth(b);
        let f = (K_REPEL * growthA * growthB) / distSq;
        let fx = (dx / dist) * f;
        let fy = (dy / dist) * f;
        a.fx += fx; a.fy += fy;
        b.fx -= fx; b.fy -= fy;
      }
    }
  }
  
  // Springs (visible edges) with tether level scaling and growth ramp up
  visibleEdges.forEach(e => {
    let source = nodes.get(e.sourceId);
    let target = nodes.get(e.targetId);
    if (!source || !target) return;
    
    let dx = target.x - source.x;
    let dy = target.y - source.y;
    let dist = Math.sqrt(dx*dx + dy*dy);
    if (dist === 0) dist = 0.1;
    
    // Scale tether length up based on parent (source) scale
    let tetherLength = 80 + (source.child_count * 25);
    if (tetherLength > 300) tetherLength = 300;
    tetherLength *= (source.scale || 1.0);
    
    // Ramp up tether length and spring constant gradually for newly spawned nodes
    const targetGrowth = getGrowth(target);
    const currentTetherLength = tetherLength * targetGrowth;
    const currentKSpring = K_SPRING * targetGrowth;
    
    let f = currentKSpring * (dist - currentTetherLength);
    let fx = (dx / dist) * f;
    let fy = (dy / dist) * f;
    
    source.fx += fx; source.fy += fy;
    target.fx -= fx; target.fy -= fy;
  });
  
  // Group boundary push: calculate center of the group (parent + children) and repulse from the group center
  visibleNodes.forEach(parent => {
    if (!parent.expanded) return;
    
    // Collect direct children of this parent instance
    const children = [];
    visibleEdges.forEach(e => {
      if (e.sourceId === parent.id) {
        const child = nodes.get(e.targetId);
        if (child) children.push(child);
      }
    });
    
    if (children.length === 0) return;
    
    // Group geometric center (parent + visible children)
    let sumX = parent.x;
    let sumY = parent.y;
    children.forEach(c => {
      sumX += c.x;
      sumY += c.y;
    });
    const groupCenterX = sumX / (children.length + 1);
    const groupCenterY = sumY / (children.length + 1);
    const groupCenter = { x: groupCenterX, y: groupCenterY };
    
    // Case 1: Only 1 child: boundary is a circle centered around the group
    if (children.length === 1) {
      const child = children[0];
      const cdx = child.x - groupCenterX;
      const cdy = child.y - groupCenterY;
      const boundaryRadius = Math.max(Math.sqrt(cdx * cdx + cdy * cdy) + 40, 80);
      
      visibleNodes.forEach(O => {
        if (O.id === parent.id || O.id === child.id) return;
        
        const ox = O.x - groupCenterX;
        const oy = O.y - groupCenterY;
        const oDist = Math.sqrt(ox * ox + oy * oy) || 0.1;
        
        if (oDist < boundaryRadius) {
          const pushForce = 0.6 * (boundaryRadius - oDist);
          O.fx += (ox / oDist) * pushForce;
          O.fy += (oy / oDist) * pushForce;
          
          parent.fx -= (ox / oDist) * pushForce * 0.5;
          parent.fy -= (oy / oDist) * pushForce * 0.5;
          child.fx -= (ox / oDist) * pushForce * 0.5;
          child.fy -= (oy / oDist) * pushForce * 0.5;
        }
      });
    } else {
      // Case 2: 2+ children: sort by angle around groupCenter to form polygon chain
      const sortedChildren = [...children].sort((a, b) => {
        return Math.atan2(a.y - groupCenterY, a.x - groupCenterX) - Math.atan2(b.y - groupCenterY, b.x - groupCenterX);
      });
      const n = sortedChildren.length;
      
      visibleNodes.forEach(O => {
        // Skip if O is part of this group
        if (O.id === parent.id || children.some(c => c.id === O.id)) return;
        
        const ox = O.x - groupCenterX;
        const oy = O.y - groupCenterY;
        const oDist = Math.sqrt(ox * ox + oy * oy) || 0.1;
        
        let minT = Infinity;
        
        for (let i = 0; i < n; i++) {
          const A = sortedChildren[i];
          const B = sortedChildren[(i + 1) % n];
          
          // Check ray intersection from groupCenter through O
          const intersection = getRaySegmentIntersection(groupCenter, O, A, B);
          if (intersection && intersection.t < minT) {
            minT = intersection.t;
          }
          
          // Also apply line segment repulsion to avoid crossing the line closely
          const vx = B.x - A.x;
          const vy = B.y - A.y;
          const wx = O.x - A.x;
          const wy = O.y - A.y;
          const vSq = vx * vx + vy * vy;
          if (vSq > 0) {
            let t_proj = (wx * vx + wy * vy) / vSq;
            t_proj = Math.max(0, Math.min(1, t_proj));
            const projX = A.x + t_proj * vx;
            const projY = A.y + t_proj * vy;
            const rx = O.x - projX;
            const ry = O.y - projY;
            const rDist = Math.sqrt(rx * rx + ry * ry) || 0.1;
            if (rDist < 60) {
              const fRepel = 2.0 * (60 - rDist) / (rDist + 0.1);
              O.fx += (rx / rDist) * fRepel;
              O.fy += (ry / rDist) * fRepel;
            }
          }
        }
        
        // If O is inside the polygon (closer to groupCenter than boundary intersection)
        if (minT !== Infinity && oDist < minT) {
          const pushForce = 2.0 * (minT - oDist);
          O.fx += (ox / oDist) * pushForce;
          O.fy += (oy / oDist) * pushForce;
          
          const share = pushForce / (children.length + 1);
          parent.fx -= (ox / oDist) * share;
          parent.fy -= (oy / oDist) * share;
          children.forEach(c => {
            c.fx -= (ox / oDist) * share;
            c.fy -= (oy / oDist) * share;
          });
        }
      });
    }
  });
  
  // Dark Force (pull top-level nexus nodes towards collective center of mass, children are tethered to parents via springs)
  let sumNexusX = 0;
  let sumNexusY = 0;
  let nexusCount = 0;
  visibleNodes.forEach(n => {
    if (n.isNexus) {
      sumNexusX += n.x;
      sumNexusY += n.y;
      nexusCount++;
    }
  });

  const centerOfMassX = nexusCount > 0 ? (sumNexusX / nexusCount) : 0;
  const centerOfMassY = nexusCount > 0 ? (sumNexusY / nexusCount) : 0;

  visibleNodes.forEach(n => {
    if (n.isNexus) {
      n.fx -= (n.x - centerOfMassX) * K_DARK;
      n.fy -= (n.y - centerOfMassY) * K_DARK;
    }
  });
  
  const MAX_SPEED = 18; // Maximum movement speed in px/frame to dampen rapid expansion explosions

  // Apply forces
  visibleNodes.forEach(n => {
    n.vx = (n.vx + n.fx) * DAMPING;
    n.vy = (n.vy + n.fy) * DAMPING;
    
    let speed = Math.sqrt(n.vx * n.vx + n.vy * n.vy);
    if (speed > MAX_SPEED) {
      n.vx = (n.vx / speed) * MAX_SPEED;
      n.vy = (n.vy / speed) * MAX_SPEED;
      speed = MAX_SPEED;
    }

    n.x += n.vx * simulationAlpha;
    n.y += n.vy * simulationAlpha;
    
    if (speed > maxVel) maxVel = speed;
  });
  
  simulationAlpha *= 0.99;
  
  if (maxVel < 0.5 && simulationAlpha < 0.1) {
    simulationActive = false;
  }
}

function getVisibleNodes() {
  const visible = new Set();
  nexusNodes.forEach(id => addVisible(id, visible));
  return Array.from(visible).map(id => nodes.get(id)).filter(Boolean);
}

function addVisible(nodeId, visibleSet) {
  visibleSet.add(nodeId);
  const node = nodes.get(nodeId);
  if (node && node.expanded) {
    edges.forEach(e => {
      if (e.sourceId === nodeId) {
        addVisible(e.targetId, visibleSet);
      }
    });
  }
}

function getVisibleEdges() {
  const vNodes = new Set(getVisibleNodes().map(n => n.id));
  return edges.filter(e => vNodes.has(e.sourceId) && vNodes.has(e.targetId));
}

// Rendering
function drawRhumbLines() {
  ctx.save();
  ctx.lineWidth = 0.5;
  // Draw fixed pattern scaled with camera
  for (let i = 0; i < 12; i++) {
    ctx.strokeStyle = i % 2 === 0 ? 'rgba(197, 160, 89, 0.06)' : 'rgba(160, 168, 176, 0.04)';
    ctx.beginPath();
    let cx = Math.sin(i) * 5000;
    let cy = Math.cos(i) * 5000;
    let r = 5000 + (i * 200);
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();
}

function drawStars() {
  ctx.save();
  stars.forEach(s => {
    ctx.fillStyle = `rgba(255, 255, 255, ${s.alpha})`;
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.restore();
}

function render() {
  if (!ctx) return;
  // Clear
  ctx.fillStyle = '#0a0a1a';
  ctx.fillRect(0, 0, width, height);
  
  ctx.save();
  // Apply camera
  ctx.translate(width/2, height/2);
  ctx.scale(camera.zoom, camera.zoom);
  ctx.translate(-camera.x, -camera.y);
  
  drawStars();
  drawRhumbLines();
  
  const vEdges = getVisibleEdges();
  const vNodes = getVisibleNodes();
  
  // Draw edges
  vEdges.forEach(e => {
    const s = nodes.get(e.sourceId);
    const t = nodes.get(e.targetId);
    if (!s || !t) return;
    
    const isFiltered = isNodeFiltered(s) || isNodeFiltered(t);
    const inBranch = branchNodes.has(s.id) || branchNodes.has(t.id);
    
    ctx.save();
    if (isFiltered || inBranch) {
      ctx.globalAlpha = inBranch ? 0.2 : 0.12;
    }
    
    if (e === hoveredEdge && !isFiltered) {
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 4;
      ctx.shadowColor = '#ef4444';
      ctx.shadowBlur = 10;
    } else {
      ctx.strokeStyle = e.color || '#555';
      ctx.lineWidth = e.qty > 1 ? 3 : 1;
    }
    
    if (e.length > 0) {
      ctx.setLineDash([5, 5]);
    } else {
      ctx.setLineDash([]);
    }
    
    ctx.beginPath();
    if (e.qty > 1) {
      // Draw double parallel lines if qty >= 2
      let dx = t.x - s.x;
      let dy = t.y - s.y;
      let len = Math.sqrt(dx*dx + dy*dy);
      let nx = -dy / len * 4;
      let ny = dx / len * 4;
      
      ctx.moveTo(s.x + nx, s.y + ny);
      ctx.lineTo(t.x + nx, t.y + ny);
      ctx.stroke();
      
      ctx.beginPath();
      ctx.moveTo(s.x - nx, s.y - ny);
      ctx.lineTo(t.x - nx, t.y - ny);
      ctx.stroke();
    } else {
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.restore();
  });
  
  // Draw nodes
  vNodes.forEach(n => {
    const isFiltered = isNodeFiltered(n);
    const inBranch = branchNodes.has(n.id);
    ctx.save();
    ctx.translate(n.x, n.y);
    
    if (isFiltered || inBranch) {
      ctx.globalAlpha = inBranch ? 0.3 : 0.15;
    }
    
    // Draw glow and stroke
    ctx.shadowColor = n.color;
    ctx.shadowBlur = isFiltered ? 0 : 12;
    ctx.strokeStyle = n.color;
    ctx.lineWidth = 3;
    
    if (n === hoveredNode && !isFiltered) {
      ctx.shadowBlur = 20;
      ctx.lineWidth = 4;
      if (currentTool === 'hide-node' || currentTool === 'hide-branch') {
        ctx.strokeStyle = '#ef4444';
        ctx.shadowColor = '#ef4444';
      }
    }
    
    if (isNodeDragging && n === draggedNode) {
      ctx.shadowColor = '#ffffff';
      ctx.shadowBlur = 25;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 4;
    }
    
    ctx.beginPath();
    ctx.arc(0, 0, n.radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.shadowBlur = 0; // reset for fill
    
    // Clip and fill
    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, n.radius, 0, Math.PI * 2);
    ctx.clip();
    
    const cachedImg = n.imageUrl && imageCache.get(n.imageUrl);
    if (cachedImg && cachedImg.complete && cachedImg.naturalWidth > 0) {
      ctx.drawImage(cachedImg, -n.radius, -n.radius, n.radius * 2, n.radius * 2);
    } else {
      ctx.fillStyle = 'rgba(12, 12, 15, 0.9)';
      ctx.fill();
      
      // Text fallback
      ctx.fillStyle = '#fff';
      ctx.font = '12px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      // Truncate pn
      let text = n.pn;
      if (text.length > 10) text = text.substring(0, 8) + '..';
      ctx.fillText(text, 0, 0);
    }
    ctx.restore();
    
    // Plus/Minus indicator for children
    if (n.child_count > 0) {
      ctx.fillStyle = n.color;
      ctx.beginPath();
      ctx.arc(n.radius * 0.7, -n.radius * 0.7, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#000';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(n.expanded ? '-' : '+', n.radius * 0.7, -n.radius * 0.7);
    }
    
    // Blackbox indicator
    if (n.blackbox) {
      ctx.fillStyle = '#000';
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.rect(-n.radius * 0.9, -n.radius * 0.9, 12, 12);
      ctx.fill();
      ctx.stroke();
    }
    
    // Purchase kit indicator
    if (n.purchase_kit) {
      ctx.fillStyle = '#eab308';
      ctx.beginPath();
      ctx.arc(-n.radius * 0.7, n.radius * 0.7, 6, 0, Math.PI * 2);
      ctx.fill();
    }
    
    ctx.restore();
    
    // Draw label below if zoomed in enough
    if (camera.zoom > 0.6) {
      ctx.fillStyle = isFiltered ? 'rgba(255, 255, 255, 0.25)' : 'rgba(255, 255, 255, 0.8)';
      ctx.font = '12px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(n.pn, n.x, n.y + n.radius + 15);
    }
  });

  // Draw Join In-Progress Connection Line and Badges
  if (currentTool === 'join') {
    if (joinSourceNode && joinCursorPos) {
      const startX = joinSourceNode.x;
      const startY = joinSourceNode.y;
      const endX = joinCandidateTarget ? joinCandidateTarget.x : joinCursorPos.x;
      const endY = joinCandidateTarget ? joinCandidateTarget.y : joinCursorPos.y;
      
      ctx.save();
      ctx.shadowColor = '#e5c185';
      ctx.shadowBlur = 14;
      ctx.strokeStyle = '#e5c185';
      ctx.lineWidth = 2.5;
      ctx.setLineDash([8, 6]);
      
      ctx.beginPath();
      ctx.moveTo(startX, startY);
      ctx.lineTo(endX, endY);
      ctx.stroke();
      ctx.setLineDash([]);
      
      // Arrowhead pointing towards target parent
      const angle = Math.atan2(endY - startY, endX - startX);
      const arrowLength = 14;
      const arrowWidth = 7;
      
      ctx.fillStyle = '#e5c185';
      ctx.beginPath();
      ctx.moveTo(endX, endY);
      ctx.lineTo(
        endX - arrowLength * Math.cos(angle) + arrowWidth * Math.sin(angle),
        endY - arrowLength * Math.sin(angle) - arrowWidth * Math.cos(angle)
      );
      ctx.lineTo(
        endX - arrowLength * Math.cos(angle) - arrowWidth * Math.sin(angle),
        endY - arrowLength * Math.sin(angle) + arrowWidth * Math.cos(angle)
      );
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    if (joinSourceNode) {
      ctx.save();
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#38bdf8';
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.arc(joinSourceNode.x, joinSourceNode.y, joinSourceNode.radius + 6, 0, Math.PI * 2);
      ctx.stroke();
      
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 11px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Source (Child)', joinSourceNode.x, joinSourceNode.y - joinSourceNode.radius - 12);
      ctx.restore();
    }
    
    if (joinCandidateTarget) {
      ctx.save();
      ctx.strokeStyle = '#e5c185';
      ctx.lineWidth = 3;
      ctx.shadowColor = '#e5c185';
      ctx.shadowBlur = 20;
      ctx.beginPath();
      ctx.arc(joinCandidateTarget.x, joinCandidateTarget.y, joinCandidateTarget.radius + 8, 0, Math.PI * 2);
      ctx.stroke();
      
      ctx.fillStyle = '#e5c185';
      ctx.font = 'bold 11px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Target (Parent)', joinCandidateTarget.x, joinCandidateTarget.y - joinCandidateTarget.radius - 14);
      ctx.restore();
    }
  }
  
  ctx.restore();
}

function loop() {
  stepPhysics();
  render();
  requestAnimationFrame(loop);
}

// Input Handlers
function getMouseWorldPos(e) {
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;
  
  const wx = (mx - width/2) / camera.zoom + camera.x;
  const wy = (my - height/2) / camera.zoom + camera.y;
  return { x: wx, y: wy };
}

canvas.addEventListener('mousedown', e => {
  if (e.button !== 0) return;
  const worldPos = getMouseWorldPos(e);

  if (currentTool === 'pan') {
    isDragging = true;
    lastMouse = { x: e.clientX, y: e.clientY };
    updateCursor(!!hoveredNode);
  } else if (currentTool === 'drag') {
    if (hoveredNode) {
      draggedNode = hoveredNode;
      isNodeDragging = true;
      draggedNode.vx = 0;
      draggedNode.vy = 0;
      simulationActive = false; // Pause physics completely during drag
      updateCursor(true);
    } else {
      isDragging = true;
      lastMouse = { x: e.clientX, y: e.clientY };
      updateCursor(false);
    }
  } else if (currentTool === 'join') {
    if (hoveredNode) {
      if (!joinSourceNode) {
        joinSourceNode = hoveredNode;
        joinCursorPos = worldPos;
        joinMouseDownPos = { x: e.clientX, y: e.clientY };
      } else if (joinSourceNode.id !== hoveredNode.id) {
        handleJoin(joinSourceNode, hoveredNode);
      }
    } else {
      if (joinSourceNode) {
        joinSourceNode = null;
        joinCandidateTarget = null;
        joinCursorPos = null;
        joinMouseDownPos = null;
      }
      isDragging = true;
      lastMouse = { x: e.clientX, y: e.clientY };
    }
    updateCursor(!!hoveredNode);
  }
});

canvas.addEventListener('mousemove', e => {
  const worldPos = getMouseWorldPos(e);
  
  if (isNodeDragging && draggedNode) {
    draggedNode.x = worldPos.x;
    draggedNode.y = worldPos.y;
    draggedNode.vx = 0;
    draggedNode.vy = 0;
  } else if (isDragging) {
    const dx = (e.clientX - lastMouse.x) / camera.zoom;
    const dy = (e.clientY - lastMouse.y) / camera.zoom;
    camera.x -= dx;
    camera.y -= dy;
    lastMouse = { x: e.clientX, y: e.clientY };
  }
  
  // Hover detection
  const vNodes = getVisibleNodes();
  let found = null;
  for (let i = vNodes.length - 1; i >= 0; i--) {
    let n = vNodes[i];
    let dx = n.x - worldPos.x;
    let dy = n.y - worldPos.y;
    if (dx*dx + dy*dy <= n.radius*n.radius) {
      found = n;
      break;
    }
  }
  
  hoveredNode = found;

  hoveredEdge = null;
  if (!hoveredNode && currentTool === 'sever') {
    // Find closest edge
    const vEdges = getVisibleEdges();
    let minDist = 15 / camera.zoom; // interaction radius
    for (const edge of vEdges) {
      const s = nodes.get(edge.sourceId);
      const t = nodes.get(edge.targetId);
      if (s && t) {
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const l2 = dx*dx + dy*dy;
        if (l2 === 0) continue;
        let t_param = ((worldPos.x - s.x) * dx + (worldPos.y - s.y) * dy) / l2;
        t_param = Math.max(0, Math.min(1, t_param));
        const px = s.x + t_param * dx;
        const py = s.y + t_param * dy;
        const dist = Math.hypot(worldPos.x - px, worldPos.y - py);
        if (dist < minDist) {
          minDist = dist;
          hoveredEdge = edge;
        }
      }
    }
  }

  branchNodes.clear();
  if (hoveredNode && currentTool === 'hide-branch') {
    // Collect all recursive descendants
    function collectDescendants(id) {
      branchNodes.add(id);
      edges.filter(e => e.sourceId === id).forEach(e => {
        collectDescendants(e.targetId);
      });
    }
    collectDescendants(hoveredNode.id);
  } else if (hoveredNode && currentTool === 'hide-node') {
    branchNodes.add(hoveredNode.id);
  }

  if (currentTool === 'join' && joinSourceNode) {
    joinCursorPos = worldPos;
    joinCandidateTarget = (hoveredNode && hoveredNode.id !== joinSourceNode.id) ? hoveredNode : null;
  }
  
  if (hoveredNode) {
    showTooltip(e.clientX, e.clientY, hoveredNode);
  } else {
    hideTooltip();
  }

  updateCursor(!!hoveredNode || !!hoveredEdge);
});

window.addEventListener('mouseup', e => {
  if (isNodeDragging) {
    isNodeDragging = false;
    draggedNode = null;
    startSimulation(); // Unfreeze and settle physics
  }

  if (isDragging) {
    isDragging = false;
  }

  if (currentTool === 'join' && joinSourceNode) {
    if (hoveredNode && hoveredNode.id !== joinSourceNode.id) {
      handleJoin(joinSourceNode, hoveredNode);
    } else if (joinMouseDownPos) {
      const dist = Math.hypot(e.clientX - joinMouseDownPos.x, e.clientY - joinMouseDownPos.y);
      if (dist > 15 && (!hoveredNode || hoveredNode.id === joinSourceNode.id)) {
        joinSourceNode = null;
        joinCandidateTarget = null;
        joinCursorPos = null;
        joinMouseDownPos = null;
      }
    }
  }

  updateCursor(!!hoveredNode);
});

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const zoomFactor = 1.1;
  if (e.deltaY < 0) {
    setCameraZoom(camera.zoom * zoomFactor);
  } else {
    setCameraZoom(camera.zoom / zoomFactor);
  }
}, { passive: false });

canvas.addEventListener('click', async e => {
  if (currentTool === 'sever' && hoveredEdge) {
    if (confirm('Are you sure you want to sever this connection? This will delete the assembly record.')) {
      const targetChildId = hoveredEdge.targetId;
      const sourceParentId = hoveredEdge.sourceId;
      const edgeToRemove = hoveredEdge;
      hoveredEdge = null;

      try {
        if (edgeToRemove.edgeId) {
          await deleteAssembly(edgeToRemove.edgeId);
          showToast('Connection severed.');
        } else {
          showToast('Connection severed locally.');
        }

        edges = edges.filter(ed => ed !== edgeToRemove && !(ed.sourceId === sourceParentId && ed.targetId === targetChildId));

        // Promote severed child to nexusNodes so it remains visible
        if (targetChildId && nodes.has(targetChildId)) {
          nexusNodes.add(targetChildId);
        }

        // Update parent child_count
        const parentNode = nodes.get(sourceParentId);
        if (parentNode) {
          parentNode.child_count = Math.max(0, (parentNode.child_count || 1) - 1);
        }

        updateNodeScales();
        updateHudMetrics();
        startSimulation();
      } catch (err) {
        showToast('Failed to sever connection: ' + err.message, true);
      }
    }
    return;
  }
  
  if (currentTool === 'hide-node' && hoveredNode) {
    const targetNodeId = hoveredNode.id;
    // Promote direct children of this node to nexusNodes so they remain visible
    edges.filter(ed => ed.sourceId === targetNodeId).forEach(ed => {
      nexusNodes.add(ed.targetId);
    });
    nexusNodes.delete(targetNodeId);
    nodes.delete(targetNodeId);
    edges = edges.filter(ed => ed.sourceId !== targetNodeId && ed.targetId !== targetNodeId);
    hoveredNode = null;
    updateNodeScales();
    updateHudMetrics();
    startSimulation();
    return;
  }
  
  if (currentTool === 'hide-branch' && hoveredNode) {
    branchNodes.forEach(id => {
      nexusNodes.delete(id);
      nodes.delete(id);
      edges = edges.filter(ed => ed.sourceId !== id && ed.targetId !== id);
    });
    branchNodes.clear();
    hoveredNode = null;
    updateNodeScales();
    updateHudMetrics();
    startSimulation();
    return;
  }

  if (currentTool !== 'pan') return;
  if (hoveredNode) {
    if (hoveredNode.child_count > 0) {
      if (hoveredNode.expanded) collapseNode(hoveredNode);
      else expandNode(hoveredNode);
    }
  }
});

canvas.addEventListener('dblclick', e => {
  if (hoveredNode) {
    window.location.href = `index.html#/item/${hoveredNode.itemId}`;
  }
});

canvas.addEventListener('contextmenu', e => {
  e.preventDefault();
  closeContextMenu();
  closeSearchPopup();

  if (hoveredNode) {
    showRadialMenu(e.clientX, e.clientY, hoveredNode);
  } else {
    showSearchPopup(e.clientX, e.clientY, getMouseWorldPos(e));
  }
});

window.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (document.getElementById('search-popup')) {
      closeSearchPopup();
      return;
    }
    if (document.getElementById('radial-menu')) {
      closeContextMenu();
      return;
    }
    const drawer = document.getElementById('filter-drawer');
    if (drawer && drawer.classList.contains('open')) {
      closeFilterDrawer();
      return;
    }
    if (joinSourceNode) {
      joinSourceNode = null;
      joinCandidateTarget = null;
      joinCursorPos = null;
      joinMouseDownPos = null;
    } else {
      setTool('pan');
    }
    return;
  }

  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'p' || e.key === 'P') {
    setTool('pan');
  } else if (e.key === 'd' || e.key === 'D') {
    setTool('drag');
  } else if (e.key === 'j' || e.key === 'J') {
    setTool('join');
  }
});

window.addEventListener('resize', () => {
  width = window.innerWidth;
  height = window.innerHeight;
  canvas.width = width;
  canvas.height = height;
});

// Tooltip helpers
function showTooltip(x, y, node) {
  ttPn.textContent = node.pn;
  ttDesc.textContent = node.desc || 'No description';
  ttState.textContent = node.state;
  tooltip.style.display = 'flex';
  moveTooltip(x, y);
}

function moveTooltip(x, y) {
  tooltip.style.left = (x + 15) + 'px';
  tooltip.style.top = (y + 15) + 'px';
}

function hideTooltip() {
  tooltip.style.display = 'none';
}

async function expandNode(node) {
  if (node.expanded) return;
  
  if (!node.childrenFetched || !node.childrenExpandedOnce) {
    try {
      const data = node.cachedChildren || await fetchGraphChildren(node.itemId);
      node.childrenFetched = true;
      node.childrenExpandedOnce = true;
      node.child_count = data.length;
      data.forEach(childData => {
        const childNode = processNodeData(childData, false, node.id, childData.edge_id);
        const exists = edges.some(e => e.sourceId === node.id && e.targetId === childNode.id);
        if (!exists) {
          edges.push({
            sourceId: node.id,
            targetId: childNode.id,
            qty: childData.quantity || 1,
            length: childData.length || 0,
            color: adjustColor(childNode.color, -30),
            edgeId: childData.edge_id
          });
        }
      });
    } catch (err) {
      console.error("Failed to fetch children for node", err);
      return;
    }
  }
  
  node.expanded = true;
  if (node.isNexus) expandedNexusCount++;
  updateNodeScales();
  updateHudMetrics();
  startSimulation();
}

function collapseNode(node) {
  if (!node.expanded) return;
  node.expanded = false;
  if (node.isNexus) expandedNexusCount--;
  
  // Recursively collapse expanded children
  function collapseDescendants(parentInstId) {
    const childEdges = edges.filter(e => e.sourceId === parentInstId);
    childEdges.forEach(e => {
      const child = nodes.get(e.targetId);
      if (child) {
        if (child.expanded) {
          child.expanded = false;
        }
        collapseDescendants(child.id);
      }
    });
  }
  collapseDescendants(node.id);

  updateNodeScales();
  updateHudMetrics();
  startSimulation();
}

function updateHudMetrics() {
  const vNodes = getVisibleNodes();
  const totalEl = document.getElementById('info-total-nodes');
  const expEl = document.getElementById('info-expanded');
  const nexEl = document.getElementById('info-nexus');
  if (totalEl) totalEl.textContent = vNodes.length;
  if (expEl) expEl.textContent = Array.from(nodes.values()).filter(n => n.expanded && n.isNexus).length;
  if (nexEl) nexEl.textContent = nexusNodes.size;
}

function resetMap() {
  nodes.clear();
  edges = [];
  nexusNodes.clear();
  expandedNexusCount = 0;
  hoveredNode = null;
  hoveredEdge = null;
  draggedNode = null;
  branchNodes.clear();
  joinSourceNode = null;
  joinCandidateTarget = null;
  joinCursorPos = null;
  joinMouseDownPos = null;
  camera.x = 0;
  camera.y = 0;
  setCameraZoom(1.0);
  updateNodeScales();
  updateHudMetrics();
  startSimulation();
  showToast('Sandbox reset.');
}

// Tool Switcher Buttons
document.getElementById('tool-pan')?.addEventListener('click', () => setTool('pan'));
document.getElementById('tool-drag')?.addEventListener('click', () => setTool('drag'));
document.getElementById('tool-join')?.addEventListener('click', () => setTool('join'));
document.getElementById('tool-sever')?.addEventListener('click', () => setTool('sever'));
document.getElementById('tool-hide-node')?.addEventListener('click', () => setTool('hide-node'));
document.getElementById('tool-hide-branch')?.addEventListener('click', () => setTool('hide-branch'));

// Camera Zoom Controls
function setCameraZoom(newZoom) {
  camera.zoom = Math.max(0.1, Math.min(newZoom, 4.0));
  syncZoomSlider();
}

function syncZoomSlider() {
  const zoomSlider = document.getElementById('zoom-slider');
  if (zoomSlider) {
    zoomSlider.value = Math.log2(camera.zoom).toFixed(3);
  }
}

// HUD Buttons
document.getElementById('btn-zoom-in')?.addEventListener('click', () => { setCameraZoom(camera.zoom * 1.2); });
document.getElementById('btn-zoom-out')?.addEventListener('click', () => { setCameraZoom(camera.zoom / 1.2); });
document.getElementById('btn-reset-view')?.addEventListener('click', () => {
  camera.x = 0; camera.y = 0;
  setCameraZoom(1.0);
});
document.getElementById('btn-reset-map')?.addEventListener('click', resetMap);
document.getElementById('btn-refresh-map')?.addEventListener('click', resetMap);
const zoomSlider = document.getElementById('zoom-slider');
if (zoomSlider) {
  zoomSlider.addEventListener('input', (e) => {
    camera.zoom = Math.max(0.1, Math.min(Math.pow(2, parseFloat(e.target.value)), 4.0));
  });
}

// Filter Drawer Buttons
document.getElementById('btn-filter')?.addEventListener('click', openFilterDrawer);
document.getElementById('btn-close-drawer')?.addEventListener('click', closeFilterDrawer);
document.getElementById('drawer-overlay')?.addEventListener('click', closeFilterDrawer);

// Init
checkHealth();
initFilters();
loadGraph();
requestAnimationFrame(loop);

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatItemForNode(rawItem) {
  const pn = rawItem['Part Number'] || rawItem.part_number || '';
  let pnTag = { name: 'Unknown', color: '#8e9095' };
  const prefix = pn.split('-')[0];
  if (categoryRules && categoryRules[prefix]) {
    pnTag = { name: categoryRules[prefix].name, color: categoryRules[prefix].color };
  } else if (rawItem.pn_tag) {
    pnTag = rawItem.pn_tag;
  }
  const stateVal = typeof rawItem.State === 'object' ? rawItem.State?.value : (rawItem.State || rawItem.state || 'Unknown');
  const imgUrl = (rawItem.Image && rawItem.Image[0]?.url) || rawItem.image_url || null;

  return {
    id: rawItem.id,
    part_number: pn,
    description: rawItem['Item description'] || rawItem.description || '',
    state: stateVal,
    pn_tag: pnTag,
    image_url: imgUrl,
    child_count: rawItem.child_count || 0,
    purchase_kit: !!(rawItem['Purchase Kit'] || rawItem.purchase_kit),
    blackbox: !!(rawItem['Blackbox'] || rawItem.blackbox)
  };
}

function closeContextMenu() {
  const existing = document.getElementById('radial-menu');
  if (existing) existing.remove();
  if (!document.getElementById('search-popup')) {
    startSimulation(); // Unfreeze physics if neither menu is open
  }
}

async function handleSpawnParents(node) {
  try {
    const parents = await fetchItemParents(node.itemId);
    parents.forEach(pData => {
      // Find existing instances of this parent
      const existingInstances = Array.from(nodes.values()).filter(n => n.itemId === pData.id);
      if (existingInstances.length > 0) {
        existingInstances.forEach(parentInst => {
          // Check if edge already exists
          const exists = edges.some(e => e.sourceId === parentInst.id && e.targetId === node.id);
          if (!exists) {
            edges.push({
              sourceId: parentInst.id,
              targetId: node.id,
              qty: 1,
              length: 0,
              color: adjustColor(node.color, -30)
            });
          }
        });
      } else {
        const newParent = processNodeData(pData, false, null);
        newParent.x = node.x + (Math.random() - 0.5) * 100;
        newParent.y = node.y - 100;
        edges.push({
          sourceId: newParent.id,
          targetId: node.id,
          qty: 1,
          length: 0,
          color: adjustColor(node.color, -30)
        });
      }
    });
    updateNodeScales();
    updateHudMetrics();
    startSimulation();
  } catch (err) {
    showToast('Failed to spawn parents', true);
  }
}

function showRadialMenu(x, y, node) {
  simulationActive = false; // Freeze physics
  const menu = document.createElement('div');
  menu.id = 'radial-menu';
  menu.style.position = 'absolute';
  menu.style.left = x + 'px';
  menu.style.top = y + 'px';
  menu.style.zIndex = 1000;
  menu.style.background = 'rgba(12, 12, 15, 0.9)';
  menu.style.border = '1px solid var(--color-gold)';
  menu.style.padding = '0.5rem';
  menu.style.display = 'flex';
  menu.style.flexDirection = 'column';
  menu.style.gap = '0.25rem';
  
  const createBtn = (text, onClick) => {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.className = 'btn btn-secondary btn-sm';
    btn.onclick = onClick;
    return btn;
  };
  
  menu.appendChild(createBtn(node.blackbox ? 'Unset Blackbox' : 'Set Blackbox', async () => {
    try {
      await updateItem(node.itemId, { Blackbox: !node.blackbox });
      node.blackbox = !node.blackbox;
      closeContextMenu();
      startSimulation();
    } catch (e) { showToast('Error', true); }
  }));
  
  menu.appendChild(createBtn(node.purchase_kit ? 'Unset Purchase Kit' : 'Set Purchase Kit', async () => {
    try {
      await updateItem(node.itemId, { "Purchase Kit": !node.purchase_kit });
      node.purchase_kit = !node.purchase_kit;
      closeContextMenu();
      startSimulation();
    } catch (e) { showToast('Error', true); }
  }));
  
  menu.appendChild(createBtn('Spawn Parents', () => {
    handleSpawnParents(node);
    closeContextMenu();
  }));
  
  document.body.appendChild(menu);
}

function filterDuplicateRevisions(items) {
  if (!items || items.length === 0) return [];

  const groups = new Map();
  items.forEach(item => {
    const pn = item['Part Number'] || item.part_number || '';
    if (!pn) {
      groups.set(`item_${item.id}`, [item]);
      return;
    }
    if (!groups.has(pn)) {
      groups.set(pn, []);
    }
    groups.get(pn).push(item);
  });

  const result = [];
  groups.forEach((groupItems) => {
    if (groupItems.length === 1) {
      result.push(groupItems[0]);
    } else {
      groupItems.sort((a, b) => {
        const revA = a.Revision || a.revision || '';
        const revB = b.Revision || b.revision || '';
        if (revA.length !== revB.length) {
          return revA.length - revB.length;
        }
        return revA.localeCompare(revB);
      });
      result.push(groupItems[groupItems.length - 1]);
    }
  });
  return result;
}

function closeSearchPopup() {
  const existing = document.getElementById('search-popup');
  if (existing) existing.remove();
  if (!document.getElementById('radial-menu')) {
    startSimulation();
  }
}

function showSearchPopup(clientX, clientY, worldPos) {
  simulationActive = false;
  closeSearchPopup();
  closeContextMenu();

  const popup = document.createElement('div');
  popup.id = 'search-popup';
  popup.style.position = 'absolute';
  const posX = Math.min(clientX, window.innerWidth - 320);
  const posY = Math.min(clientY, window.innerHeight - 350);
  popup.style.left = Math.max(10, posX) + 'px';
  popup.style.top = Math.max(10, posY) + 'px';
  popup.style.zIndex = '1000';
  popup.style.background = 'rgba(12, 12, 15, 0.95)';
  popup.style.border = '1px solid var(--color-gold)';
  popup.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.6)';
  popup.style.borderRadius = '4px';
  popup.style.padding = '0.75rem';
  popup.style.width = '300px';
  popup.style.backdropFilter = 'blur(10px)';

  popup.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; border-bottom: 1px solid var(--card-border); padding-bottom: 0.35rem;">
      <span style="font-weight: 600; font-size: 0.85rem; color: var(--color-gold-bright);"><i class="fa-solid fa-plus-circle" style="margin-right: 0.35rem;"></i> Spawn Item Node</span>
      <button id="search-popup-close-btn" style="background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 1.2rem; line-height: 1; padding: 0 0.25rem;">&times;</button>
    </div>
    <input type="text" id="search-popup-input" placeholder="Search part # or description..." class="form-control" style="width: 100%; margin-bottom: 0.5rem; font-size: 0.85rem; padding: 0.4rem 0.6rem;" />
    <div id="search-popup-results" style="max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px;"></div>
  `;

  document.body.appendChild(popup);

  const closeBtn = document.getElementById('search-popup-close-btn');
  if (closeBtn) {
    closeBtn.onclick = () => closeSearchPopup();
  }

  const input = document.getElementById('search-popup-input');
  const resultsContainer = document.getElementById('search-popup-results');

  let currentResults = [];
  let selectedIndex = 0;
  let searchSeq = 0;
  let searchDebounceTimer = null;

  function renderSelection() {
    const items = resultsContainer.querySelectorAll('.search-popup-item');
    items.forEach((div, idx) => {
      if (idx === selectedIndex) {
        div.style.background = 'rgba(197, 160, 89, 0.25)';
        div.style.outline = '1px solid var(--color-gold)';
      } else {
        div.style.background = 'transparent';
        div.style.outline = 'none';
      }
    });
  }

  function scrollSelectedIntoView() {
    const items = resultsContainer.querySelectorAll('.search-popup-item');
    if (items[selectedIndex] && typeof items[selectedIndex].scrollIntoView === 'function') {
      items[selectedIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  async function spawnItem(item) {
    const node = processNodeData(item, true, null);
    node.x = worldPos.x;
    node.y = worldPos.y;
    closeSearchPopup();
    
    try {
      const children = await fetchGraphChildren(item.id);
      if (Array.isArray(children)) {
        node.child_count = children.length;
        node.childrenFetched = true;
        node.cachedChildren = children;
      }
    } catch (e) {
      // Keep default child count if fetch fails
    }
    
    updateNodeScales();
    updateHudMetrics();
    startSimulation();
  }

  function renderResultsList() {
    resultsContainer.innerHTML = '';
    if (currentResults.length === 0) {
      const emptyDiv = document.createElement('div');
      emptyDiv.style.padding = '0.5rem';
      emptyDiv.style.color = 'var(--text-secondary)';
      emptyDiv.style.fontSize = '0.8rem';
      emptyDiv.style.textAlign = 'center';
      emptyDiv.textContent = 'No matching items found.';
      resultsContainer.appendChild(emptyDiv);
      return;
    }

    currentResults.forEach((rawItem, idx) => {
      const item = formatItemForNode(rawItem);
      const div = document.createElement('div');
      div.className = 'search-popup-item';
      div.style.padding = '6px 8px';
      div.style.cursor = 'pointer';
      div.style.borderRadius = '3px';
      div.style.display = 'flex';
      div.style.flexDirection = 'column';
      div.style.gap = '2px';
      div.style.transition = 'background 0.15s';

      if (idx === selectedIndex) {
        div.style.background = 'rgba(197, 160, 89, 0.25)';
        div.style.outline = '1px solid var(--color-gold)';
      } else {
        div.style.background = 'transparent';
        div.style.outline = 'none';
      }

      div.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-weight: 600; font-size: 0.85rem; color: ${item.pn_tag?.color || 'var(--color-gold-bright)'}">${escapeHtml(item.part_number)}</span>
          <span style="font-size: 0.7rem; padding: 1px 5px; border-radius: 2px; background: rgba(255,255,255,0.05); color: var(--text-secondary);">${escapeHtml(item.state)}</span>
        </div>
        <div style="font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(item.description || 'No description')}</div>
      `;

      div.onmouseenter = () => {
        selectedIndex = idx;
        renderSelection();
      };

      div.onclick = () => {
        spawnItem(item);
      };

      resultsContainer.appendChild(div);
    });

    scrollSelectedIntoView();
  }

  input.addEventListener('input', (e) => {
    const query = e.target.value.trim();
    clearTimeout(searchDebounceTimer);
    if (!query) {
      searchSeq++;
      currentResults = [];
      resultsContainer.innerHTML = '';
      return;
    }

    searchDebounceTimer = setTimeout(async () => {
      const thisSeq = ++searchSeq;
      try {
        const rawData = await searchItems(query);
        if (thisSeq !== searchSeq) return; // Discard outdated response
        const items = Array.isArray(rawData) ? rawData : (rawData.items || []);
        currentResults = filterDuplicateRevisions(items);
        selectedIndex = 0;
        renderResultsList();
      } catch (err) {
        if (thisSeq === searchSeq) {
          console.error('Failed to search items:', err);
        }
      }
    }, 150);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      closeSearchPopup();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (currentResults.length > 0) {
        selectedIndex = (selectedIndex + 1) % currentResults.length;
        renderSelection();
        scrollSelectedIntoView();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentResults.length > 0) {
        selectedIndex = (selectedIndex - 1 + currentResults.length) % currentResults.length;
        renderSelection();
        scrollSelectedIntoView();
      }
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (currentResults.length > 0 && currentResults[selectedIndex]) {
        spawnItem(formatItemForNode(currentResults[selectedIndex]));
      }
    }
  });

  input.focus();
}
