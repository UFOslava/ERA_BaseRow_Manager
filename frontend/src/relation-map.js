import { fetchGraphNexus, fetchGraphChildren, getHealth } from './api.js';

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

// Camera state
let camera = { x: 0, y: 0, zoom: 1 };
let isDragging = false;
let lastMouse = { x: 0, y: 0 };
let hoveredNode = null;

// Graph state
let nodes = new Map(); // id -> node object
let edges = []; // { sourceId, targetId, qty, length }
let nexusNodes = new Set(); // set of nexus node IDs
let imageCache = new Map(); // url -> Image object

let simulationActive = false;
let simulationAlpha = 1;

// Metrics
let totalNodesCount = 0;
let expandedNexusCount = 0;

// Setup status check
async function checkHealth() {
  const indicator = document.getElementById('status-indicator');
  const text = document.getElementById('status-text');
  try {
    await getHealth();
    indicator.className = 'status-indicator healthy';
    text.textContent = 'Connected';
  } catch (err) {
    indicator.className = 'status-indicator error';
    text.textContent = 'Offline';
  }
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

function computeRadius(node, isNexus) {
  const childCount = node.child_count || 0;
  if (isNexus) {
    return 28 + Math.min(childCount * 4, 40); // 28 to 68
  }
  return 20 + Math.min(childCount * 3, 24); // 20 to 44
}

function processNodeData(data, isNexus = false, parentId = null) {
  if (nodes.has(data.id)) return nodes.get(data.id);

  const radius = computeRadius(data, isNexus);
  const color = data.pn_tag?.color || '#8e9095';
  
  // Random initial position near parent or center
  let startX = (Math.random() - 0.5) * 100;
  let startY = (Math.random() - 0.5) * 100;
  
  if (parentId && nodes.has(parentId)) {
    const pNode = nodes.get(parentId);
    startX = pNode.x + (Math.random() - 0.5) * 100;
    startY = pNode.y + (Math.random() - 0.5) * 100;
  } else if (isNexus) {
    // Grid-like spread for initial nexus nodes
    const idx = nodes.size;
    const cols = 5;
    startX = (idx % cols) * 200 - (cols * 100) + (Math.random() - 0.5) * 50;
    startY = Math.floor(idx / cols) * 200 - 200 + (Math.random() - 0.5) * 50;
  }

  const node = {
    id: data.id,
    pn: data.part_number,
    desc: data.description,
    state: data.state || 'Unknown',
    child_count: data.child_count || 0,
    color: color,
    radius: radius,
    isNexus: isNexus,
    expanded: false,
    x: startX,
    y: startY,
    vx: 0,
    vy: 0,
    imageUrl: data.image_url,
    childrenFetched: false,
    clusterId: isNexus ? data.id : (parentId ? nodes.get(parentId).clusterId : data.id)
  };
  
  if (data.image_url && !imageCache.has(data.image_url)) {
    const img = new Image();
    img.src = data.image_url;
    imageCache.set(data.image_url, img);
  }

  nodes.set(node.id, node);
  if (isNexus) nexusNodes.add(node.id);
  
  totalNodesCount++;
  updateHudMetrics();
  
  return node;
}

async function loadNexus() {
  try {
    const data = await fetchGraphNexus();
    document.getElementById('loading-overlay').style.display = 'none';
    data.forEach(n => processNodeData(n, true));
    startSimulation();
  } catch (err) {
    document.getElementById('loading-overlay').textContent = 'Failed to load graph data.';
    console.error(err);
  }
}

async function expandNode(node) {
  if (node.expanded) return;
  
  if (!node.childrenFetched) {
    try {
      const data = await fetchGraphChildren(node.id);
      node.childrenFetched = true;
      data.forEach(childData => {
        // childData should have item info + edge info (quantity, length)
        const childNode = processNodeData(childData.item, false, node.id);
        edges.push({
          sourceId: node.id,
          targetId: childNode.id,
          qty: childData.quantity || 1,
          length: childData.length || 0,
          color: adjustColor(childNode.color, -30) // dimmer
        });
      });
    } catch (err) {
      console.error(err);
      return; // Failed to fetch
    }
  }
  
  node.expanded = true;
  if (node.isNexus) expandedNexusCount++;
  updateHudMetrics();
  startSimulation();
}

function collapseNode(node) {
  if (!node.expanded) return;
  node.expanded = false;
  if (node.isNexus) expandedNexusCount--;
  
  // Recursively remove children if they are not connected to anything else?
  // For this simple demo, we can just mark them as not drawn.
  // Actually, let's keep it simple: rebuild visible edges on the fly.
  updateHudMetrics();
  startSimulation();
}

function updateHudMetrics() {
  document.getElementById('info-total-nodes').textContent = totalNodesCount;
  document.getElementById('info-expanded').textContent = expandedNexusCount;
  document.getElementById('info-nexus').textContent = nexusNodes.size;
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
  return `#${(g | (b << 8) | (r << 16)).toString(16).padStart(6, '0')}`;
}

// Physics Step
function stepPhysics() {
  if (!simulationActive) return;
  
  const K_REPEL = 20000;
  const K_SPRING = 0.05;
  const K_DARK = 0.001;
  const DAMPING = 0.85;
  
  let maxVel = 0;
  
  const nodesArray = Array.from(nodes.values());
  const visibleNodes = getVisibleNodes();
  
  // Reset forces
  visibleNodes.forEach(n => { n.fx = 0; n.fy = 0; });
  
  // Repulsion
  for (let i = 0; i < visibleNodes.length; i++) {
    for (let j = i + 1; j < visibleNodes.length; j++) {
      let a = visibleNodes[i];
      let b = visibleNodes[j];
      let dx = a.x - b.x;
      let dy = a.y - b.y;
      let distSq = dx * dx + dy * dy;
      if (distSq < 0.1) { distSq = 0.1; dx = Math.random(); dy = Math.random(); }
      let dist = Math.sqrt(distSq);
      
      // Limit extreme repulsion
      if (dist < 400) {
        let f = K_REPEL / distSq;
        let fx = (dx / dist) * f;
        let fy = (dy / dist) * f;
        a.fx += fx; a.fy += fy;
        b.fx -= fx; b.fy -= fy;
      }
    }
  }
  
  // Springs (visible edges)
  const visibleEdges = getVisibleEdges();
  visibleEdges.forEach(e => {
    let source = nodes.get(e.sourceId);
    let target = nodes.get(e.targetId);
    if (!source || !target) return;
    
    let dx = target.x - source.x;
    let dy = target.y - source.y;
    let dist = Math.sqrt(dx*dx + dy*dy);
    if (dist === 0) dist = 0.1;
    
    // tether length based on children count of parent
    let tetherLength = 80 + (source.child_count * 25);
    if (tetherLength > 300) tetherLength = 300;
    
    let f = K_SPRING * (dist - tetherLength);
    let fx = (dx / dist) * f;
    let fy = (dy / dist) * f;
    
    source.fx += fx; source.fy += fy;
    target.fx -= fx; target.fy -= fy;
  });
  
  // Dark Force (pull towards cluster center)
  // Approximate cluster center as (0,0) for now or center of all nexus
  visibleNodes.forEach(n => {
    n.fx -= n.x * K_DARK;
    n.fy -= n.y * K_DARK;
  });
  
  // Apply forces
  visibleNodes.forEach(n => {
    n.vx = (n.vx + n.fx) * DAMPING;
    n.vy = (n.vy + n.fy) * DAMPING;
    n.x += n.vx * simulationAlpha;
    n.y += n.vy * simulationAlpha;
    
    let speed = Math.sqrt(n.vx*n.vx + n.vy*n.vy);
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
  return Array.from(visible).map(id => nodes.get(id));
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
    
    ctx.strokeStyle = e.color || '#555';
    ctx.lineWidth = e.qty > 1 ? 3 : 1;
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
  });
  
  // Draw nodes
  vNodes.forEach(n => {
    ctx.save();
    ctx.translate(n.x, n.y);
    
    // Draw glow and stroke
    ctx.shadowColor = n.color;
    ctx.shadowBlur = 12;
    ctx.strokeStyle = n.color;
    ctx.lineWidth = 3;
    
    if (n === hoveredNode) {
      ctx.shadowBlur = 20;
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
    
    if (n.imageUrl && imageCache.has(n.imageUrl) && imageCache.get(n.imageUrl).complete) {
      const img = imageCache.get(n.imageUrl);
      ctx.drawImage(img, -n.radius, -n.radius, n.radius * 2, n.radius * 2);
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
    
    ctx.restore();
    
    // Draw label below if zoomed in enough
    if (camera.zoom > 0.6) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.font = '12px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(n.pn, n.x, n.y + n.radius + 15);
    }
  });
  
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
  isDragging = true;
  lastMouse = { x: e.clientX, y: e.clientY };
});

canvas.addEventListener('mousemove', e => {
  const worldPos = getMouseWorldPos(e);
  
  if (isDragging) {
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
  
  if (found !== hoveredNode) {
    hoveredNode = found;
    if (found) {
      canvas.style.cursor = 'pointer';
      showTooltip(e.clientX, e.clientY, found);
    } else {
      canvas.style.cursor = isDragging ? 'grabbing' : 'grab';
      hideTooltip();
    }
  } else if (found) {
    moveTooltip(e.clientX, e.clientY);
  }
});

window.addEventListener('mouseup', () => {
  isDragging = false;
  if (!hoveredNode) canvas.style.cursor = 'grab';
});

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const zoomFactor = 1.1;
  if (e.deltaY < 0) {
    camera.zoom *= zoomFactor;
  } else {
    camera.zoom /= zoomFactor;
  }
  camera.zoom = Math.max(0.1, Math.min(camera.zoom, 5));
});

canvas.addEventListener('click', e => {
  if (hoveredNode) {
    if (hoveredNode.child_count > 0) {
      if (hoveredNode.expanded) collapseNode(hoveredNode);
      else expandNode(hoveredNode);
    }
  }
});

canvas.addEventListener('dblclick', e => {
  if (hoveredNode) {
    window.location.href = `/index.html?item=${hoveredNode.id}`;
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

// HUD Buttons
document.getElementById('btn-zoom-in').addEventListener('click', () => { camera.zoom *= 1.2; });
document.getElementById('btn-zoom-out').addEventListener('click', () => { camera.zoom /= 1.2; });
document.getElementById('btn-reset-view').addEventListener('click', () => {
  camera.x = 0; camera.y = 0; camera.zoom = 1;
});

// Init
checkHealth();
loadNexus();
requestAnimationFrame(loop);
