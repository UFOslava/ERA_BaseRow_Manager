import {
  fetchRules, saveRules, fetchProblemDefinitions, saveProblemDefinitions, getHealth,
  fetchProblemDefinitionCount, triggerRescan, fetchScanStatus, fetchLogsConfig,
  saveLogsConfig, fetchActiveLog, fetchQuickActionTemplates, saveQuickActionTemplates,
  fetchWiTemplates, uploadWiTemplate, replaceWiTemplate, deleteWiTemplate,
  fetchWiConfig, saveWiConfig, approveWiTemplate,
  fetchAuthStatus, fetchAuthConfig, testAuthConfig, saveAuthConfig, checkGlobalAuthStatus
} from './api.js';

let originalRules = null;
let currentRules = null;
let originalDefs = null;
let currentDefs = null;
let originalTemplates = null;
let currentTemplates = null;
let currentAuthConfig = null;
let activeSettingsTab = 'auth';
let expandedProblemId = null;
let activeTestTemplateIndex = 0;
let problemOccurrences = {};
let occurrencesPollingInterval = null;
let isPolling = false;

let btnSettingsBack = null;
let btnSettingsRevert = null;
let btnSettingsSave = null;
let rulesEditorContainer = null;
let problemsEditorContainer = null;
let btnAddRule = null;
let btnAddProblem = null;
let btnRescanBom = null;
let statusIndicator = null;
let statusText = null;

async function init() {
  btnSettingsBack = document.getElementById('btn-settings-back');
  btnSettingsRevert = document.getElementById('btn-settings-revert');
  btnSettingsSave = document.getElementById('btn-save-settings') || document.getElementById('btn-settings-save');
  rulesEditorContainer = document.getElementById('rules-editor-container');
  problemsEditorContainer = document.getElementById('problems-editor-container');
  btnAddRule = document.getElementById('btn-add-rule');
  btnAddProblem = document.getElementById('btn-add-problem');
  btnRescanBom = document.getElementById('btn-rescan-bom');
  statusIndicator = document.getElementById('status-indicator');
  statusText = document.getElementById('status-text');

  checkBackendHealth();
  checkGlobalAuthStatus();
  initAuthTab();
  
  const btnHamburger = document.getElementById('btn-hamburger');
  const hamburgerMenu = document.getElementById('hamburger-menu');
  if (btnHamburger && hamburgerMenu) {
    btnHamburger.addEventListener('click', (e) => {
      e.stopPropagation();
      hamburgerMenu.classList.toggle('open');
    });
    
    document.addEventListener('click', (e) => {
      if (!hamburgerMenu.contains(e.target) && e.target !== btnHamburger) {
        hamburgerMenu.classList.remove('open');
      }
    });
    
    const menuItemSettings = document.getElementById('menu-item-settings');
    if (menuItemSettings) {
      menuItemSettings.addEventListener('click', (e) => {
        e.preventDefault();
        hamburgerMenu.classList.remove('open');
      });
    }
  }
  
  if (btnSettingsBack) {
    btnSettingsBack.addEventListener('click', () => {
      if (hasUnsavedSettingsChanges()) {
        if (!confirm("You have unsaved settings. Discard them and return to BOM explorer?")) {
          return;
        }
      }
      stopOccurrencesPolling();
      window.location.href = '/';
    });
  }
  if (btnSettingsRevert) btnSettingsRevert.addEventListener('click', revertSettings);
  if (btnSettingsSave) btnSettingsSave.addEventListener('click', saveSettingsChanges);
  
  if (btnAddRule) btnAddRule.addEventListener('click', addNewRuleRow);
  if (btnAddProblem) btnAddProblem.addEventListener('click', addNewProblemRow);
  if (btnRescanBom) {
    btnRescanBom.addEventListener('click', async () => {
      try {
        btnRescanBom.disabled = true;
        await triggerRescan();
        showToast('BOM rescan triggered successfully', 'success');
        startOccurrencesPolling();
      } catch (err) {
        showToast(`Failed to trigger rescan: ${err.message}`, 'error');
      } finally {
        btnRescanBom.disabled = false;
      }
    });
  }
  
  // Sidebar tabs switcher
  const tabItems = document.querySelectorAll('.settings-tabs .tab-item');
  tabItems.forEach(tab => {
    tab.addEventListener('click', () => {
      tabItems.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      const tabName = tab.getAttribute('data-tab');
      activeSettingsTab = tabName;
      
      document.querySelectorAll('.tab-content').forEach(content => {
        content.style.display = 'none';
      });
      const selectedContent = document.getElementById(`tab-${tabName}`);
      if (selectedContent) selectedContent.style.display = 'block';
      
      if (tabName === 'problems') {
        startOccurrencesPolling();
      } else {
        stopOccurrencesPolling();
      }
      
      if (tabName === 'logs') {
        if (window._loadLogsConfig) window._loadLogsConfig();
      }

      if (tabName === 'templates') {
        renderTemplatesEditor();
        updateTestPreview();
      }

      if (tabName === 'auth') {
        loadAuthConfig();
      }
    });
  });

  // Default tab or hash selection
  let defaultTab = 'auth';
  if (window.location.hash) {
    const hash = window.location.hash.replace('#', '');
    if (document.getElementById(`tab-${hash}`)) {
      defaultTab = hash;
    }
  }
  const defaultTabEl = document.querySelector(`.settings-tabs .tab-item[data-tab="${defaultTab}"]`);
  if (defaultTabEl) {
    defaultTabEl.click();
  }

  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedSettingsChanges()) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    }
  });

  initLogsTab();
  
  ['test-input-action', 'test-input-a1', 'test-input-a2', 'test-input-a3', 'test-input-t1', 'test-input-t2'].forEach(id => {
    const input = document.getElementById(id);
    if (input) {
      input.addEventListener('input', updateTestPreview);
      input.addEventListener('change', updateTestPreview);
    }
  });

  const btnAddTemplate = document.getElementById('btn-add-template');
  if (btnAddTemplate) {
    btnAddTemplate.addEventListener('click', () => {
      currentTemplates.push({ action: 'New Action', template: '{action} {a.1} onto {a.2}' });
      activeTestTemplateIndex = currentTemplates.length - 1;
      renderTemplatesEditor();
      checkSettingsChanges();
      updateTestPreview();
    });
  }

  // WI Templates setup
  const btnUploadWi = document.getElementById('btn-upload-wi-template');
  if (btnUploadWi) btnUploadWi.addEventListener('click', handleUploadWiTemplate);
  const btnSaveWiConfig = document.getElementById('btn-save-wi-config');
  if (btnSaveWiConfig) btnSaveWiConfig.addEventListener('click', handleSaveWiConfig);

  await loadSettingsData();

  setInterval(checkBackendHealth, 15000);
}

async function checkBackendHealth() {
  try {
    await getHealth();
    if (statusIndicator) {
      statusIndicator.className = 'status-indicator healthy';
    }
    if (statusText) statusText.textContent = 'API Connected';
  } catch (err) {
    if (statusIndicator) {
      statusIndicator.className = 'status-indicator error';
    }
    if (statusText) statusText.textContent = 'API Offline';
  }
}

async function loadSettingsData() {
  if (rulesEditorContainer) rulesEditorContainer.innerHTML = '<div class="loading-spinner">Loading settings...</div>';
  if (problemsEditorContainer) problemsEditorContainer.innerHTML = '';
  expandedProblemId = null;
  stopOccurrencesPolling();
  
  try {
    const rules = await fetchRules();
    const defs = await fetchProblemDefinitions();
    const templates = await fetchQuickActionTemplates();
    
    originalRules = rules;
    currentRules = Object.keys(rules).map(k => ({ prefix: k, name: rules[k].name, color: rules[k].color }));
    
    originalDefs = defs;
    currentDefs = JSON.parse(JSON.stringify(defs));

    originalTemplates = templates;
    currentTemplates = JSON.parse(JSON.stringify(templates));
    
    renderRulesEditor();
    renderProblemsEditor();
    renderTemplatesEditor();
    updateTestPreview();
    checkSettingsChanges();
    
    // WI Templates & Config
    await loadWiTemplates();
    await loadWiConfig();

    if (activeSettingsTab === 'problems') {
      startOccurrencesPolling();
    }
  } catch (err) {
    showToast(`Error loading settings: ${err.message}`, 'error');
  }
}

function startOccurrencesPolling() {
  if (isPolling) return;
  isPolling = true;
  pollOccurrences();
}

function stopOccurrencesPolling() {
  isPolling = false;
}

async function pollOccurrences() {
  if (!isPolling || activeSettingsTab !== 'problems' || !currentDefs) {
    isPolling = false;
    return;
  }
  
  let countChanged = false;
  let allIdle = true;
  
  const promises = currentDefs.map(async (def) => {
    const isUnsaved = !originalDefs || !originalDefs.find(od => od.id === def.id);
    if (isUnsaved) {
      problemOccurrences[def.id] = { count: null, status: 'unsaved' };
      return;
    }
    try {
      const info = await fetchProblemDefinitionCount(def.id);
      
      const newCount = info.count;
      const newStatus = info.status;
      
      if (newStatus === 'running' || newStatus === 'pending') {
        allIdle = false;
      }
      
      const prev = problemOccurrences[def.id];
      const prevCount = prev ? prev.count : undefined;
      const prevStatus = prev ? prev.status : undefined;
      
      if (newCount !== prevCount || newStatus !== prevStatus) {
        countChanged = true;
      }
      
      problemOccurrences[def.id] = { count: newCount, status: newStatus };
    } catch (err) {
      console.error(`Error polling count for ${def.id}:`, err);
    }
  });
  
  await Promise.all(promises);
  
  currentDefs.forEach(def => {
    const badgeWrapper = document.querySelector(`.problem-count-badge-wrapper[data-id="${def.id}"]`);
    if (badgeWrapper) {
      const info = problemOccurrences[def.id];
      badgeWrapper.innerHTML = getOccurrenceBadgeHTML(info);
    }
  });
  
  if (allIdle) {
    try {
      const statusRes = await fetchScanStatus();
      if (statusRes.status === 'completed' || statusRes.status === 'failed') {
        isPolling = false;
        return;
      }
    } catch (err) {
      console.error("Error fetching scanner status:", err);
    }
  }
  
  const delay = countChanged ? 1000 : 5000;
  setTimeout(pollOccurrences, delay);
}

function getOccurrenceBadgeHTML(info) {
  if (!info) {
    return `<span class="prob-badge unknown"><i class="fa-solid fa-spinner fa-spin"></i> Checking</span>`;
  }
  if (info.status === 'unsaved') {
    return `<span class="prob-badge unknown">Unsaved</span>`;
  }
  if (info.status === 'running' || info.status === 'pending') {
    return `<span class="prob-badge unknown"><i class="fa-solid fa-spinner fa-spin"></i> Scanning</span>`;
  }
  if (info.status === 'failed') {
    return `<span class="prob-badge error">Scan Failed</span>`;
  }
  
  const count = info.count;
  if (count === 0) {
    return `<span class="prob-badge ok">✓ 0 occurrences</span>`;
  }
  return `<span class="prob-badge error">⚠️ ${count} ${count === 1 ? 'occurrence' : 'occurrences'}</span>`;
}

function isDefinitionChanged(def) {
  if (!originalDefs) return true;
  const original = originalDefs.find(od => od.id === def.id);
  if (!original) return true;
  return JSON.stringify(original) !== JSON.stringify(def);
}

function renderRulesEditor() {
  if (!rulesEditorContainer) return;
  rulesEditorContainer.innerHTML = '';
  
  currentRules.forEach((rule, idx) => {
    const row = document.createElement('div');
    row.className = 'prefix-rule-row';
    
    const prefixInput = document.createElement('input');
    prefixInput.type = 'text';
    prefixInput.className = 'form-input';
    prefixInput.value = rule.prefix;
    prefixInput.placeholder = 'Prefix...';
    prefixInput.addEventListener('input', (e) => {
      rule.prefix = e.target.value.trim();
      checkSettingsChanges();
    });
    
    // Live Preview Badge
    const previewSpan = document.createElement('span');
    previewSpan.className = 'pn-tag-badge';
    previewSpan.style.textAlign = 'center';
    previewSpan.style.display = 'inline-block';
    
    const updatePreview = () => {
      previewSpan.textContent = rule.name || 'Preview';
      previewSpan.style.borderColor = rule.color || '#ffffff';
      previewSpan.style.color = rule.color || '#ffffff';
      previewSpan.style.backgroundColor = `${rule.color || '#ffffff'}15`;
    };
    updatePreview();
    
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'form-input';
    nameInput.value = rule.name;
    nameInput.placeholder = 'Category Name...';
    nameInput.addEventListener('input', (e) => {
      rule.name = e.target.value;
      updatePreview();
      checkSettingsChanges();
    });
    
    const colorWrapper = document.createElement('div');
    colorWrapper.className = 'color-input-wrapper';
    
    const picker = document.createElement('input');
    picker.type = 'color';
    picker.className = 'color-picker';
    picker.value = rule.color || '#ffffff';
    
    const colorText = document.createElement('input');
    colorText.type = 'text';
    colorText.className = 'form-input color-text';
    colorText.value = rule.color || '#ffffff';
    colorText.placeholder = '#ffffff';
    
    picker.addEventListener('input', (e) => {
      colorText.value = e.target.value;
      rule.color = e.target.value;
      updatePreview();
      checkSettingsChanges();
    });
    colorText.addEventListener('input', (e) => {
      picker.value = e.target.value;
      rule.color = e.target.value;
      updatePreview();
      checkSettingsChanges();
    });
    
    colorWrapper.appendChild(picker);
    colorWrapper.appendChild(colorText);
    
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-secondary btn-delete-cond-btn';
    delBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
    delBtn.addEventListener('click', () => {
      currentRules.splice(idx, 1);
      renderRulesEditor();
      checkSettingsChanges();
    });
    
    row.appendChild(prefixInput);
    row.appendChild(nameInput);
    row.appendChild(colorWrapper);
    row.appendChild(previewSpan);
    row.appendChild(delBtn);
    
    rulesEditorContainer.appendChild(row);
  });
}

const PROBLEM_FIELD_CONFIGS = {
  'Part Number': {
    type: 'text',
    label: 'Part Number',
    placeholder: 'Enter part number...'
  },
  'Item description': {
    type: 'text',
    label: 'Item description',
    placeholder: 'Enter item description...'
  },
  'External PN': {
    type: 'text',
    label: 'External PN',
    placeholder: 'Enter external PN...'
  },
  'State': {
    type: 'select',
    label: 'State',
    options: [
      { value: 'Production Use', label: 'Production Use' },
      { value: 'Engineerig Use', label: 'Engineering Use' },
      { value: 'Unknown', label: 'Unknown' },
      { value: 'Finish Stock (Use Up)', label: 'Finish Stock (Use Up)' },
      { value: 'EOL', label: 'EOL' },
      { value: 'Do Not Use (Discard)', label: 'Do Not Use (Discard)' }
    ]
  },
  'Source URL': {
    type: 'text',
    label: 'Source Link',
    placeholder: 'https://octopart.com/...'
  },
  'Sourced By': {
    type: 'select',
    label: 'Sourced By',
    options: [
      { value: 'Purchased by Contractor', label: 'Purchased by Contractor' },
      { value: 'Produced by Contractor', label: 'Produced by Contractor' },
      { value: 'Purchased by ERA', label: 'Purchased by ERA' },
      { value: 'Produced by ERA', label: 'Produced by ERA' },
      { value: 'TBD', label: 'TBD' }
    ]
  },
  'is_in_assembly': {
    type: 'binary',
    label: 'Is Contained in Assembly'
  },
  'has_children': {
    type: 'binary',
    label: 'Has children'
  },
  'Blackbox': {
    type: 'binary',
    label: 'Blackbox'
  },
  'has_photos': {
    type: 'binary',
    label: 'Has photos'
  },
  'bom_equilibrium': {
    type: 'binary',
    label: 'BOM equilibrium (balance)'
  },
  'has_all_images': {
    type: 'binary',
    label: 'Has all images'
  },
  'Price per unit': {
    type: 'numeric',
    label: 'Price per unit',
    placeholder: '0.00'
  }
};

function getFieldConfig(field) {
  if (field === 'External Part Number') return PROBLEM_FIELD_CONFIGS['External PN'];
  if (field === 'Source Link') return PROBLEM_FIELD_CONFIGS['Source URL'];
  if (field === 'Has photos' || field === 'Has Photos') return PROBLEM_FIELD_CONFIGS['has_photos'];
  if (field === 'blackbox') return PROBLEM_FIELD_CONFIGS['Blackbox'];
  if (field === 'bom_equilibrium' || field === 'bom_balance' || field === 'BOM equilibrium (balance)' || field === 'BOM Equilibrium (Balance)') return PROBLEM_FIELD_CONFIGS['bom_equilibrium'];
  if (field === 'has_all_images' || field === 'Has all images' || field === 'has_all_photos' || field === 'Has all photos') return PROBLEM_FIELD_CONFIGS['has_all_images'];
  if (field === 'Price' || field === 'price' || field === 'Price per unit' || field === 'price_per_unit') return PROBLEM_FIELD_CONFIGS['Price per unit'];
  return PROBLEM_FIELD_CONFIGS[field] || { type: 'text', label: field || 'Part Number', placeholder: 'Value...' };
}

let activeDraggedProblemItem = null;

function buildRuleUI(node, parentGroup = null, onUpdate, definitionId = null) {
  if (node.type && (node.type.toUpperCase() === 'AND' || node.type.toUpperCase() === 'OR')) {
    const groupEl = document.createElement('div');
    groupEl.className = 'rule-group';
    
    // Setup group drop zone for dragging conditions
    groupEl.addEventListener('dragover', (e) => {
      if (activeDraggedProblemItem && activeDraggedProblemItem.definitionId === definitionId) {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) {
          e.dataTransfer.dropEffect = 'move';
        }
        groupEl.classList.add('drag-target-hover');
      }
    });
    
    groupEl.addEventListener('dragleave', (e) => {
      if (!groupEl.contains(e.relatedTarget)) {
        groupEl.classList.remove('drag-target-hover');
      }
    });
    
    groupEl.addEventListener('drop', (e) => {
      if (activeDraggedProblemItem && activeDraggedProblemItem.definitionId === definitionId) {
        e.preventDefault();
        e.stopPropagation();
        groupEl.classList.remove('drag-target-hover');
        
        const srcGroup = activeDraggedProblemItem.parentGroup;
        const draggedNode = activeDraggedProblemItem.node;
        
        if (srcGroup && srcGroup.conditions) {
          const idx = srcGroup.conditions.indexOf(draggedNode);
          if (idx !== -1) {
            srcGroup.conditions.splice(idx, 1);
          }
        }
        
        if (!node.conditions) node.conditions = [];
        node.conditions.push(draggedNode);
        
        activeDraggedProblemItem = null;
        onUpdate();
      }
    });
    
    const headerEl = document.createElement('div');
    headerEl.className = 'rule-group-header';
    
    const selectType = document.createElement('select');
    selectType.className = 'form-input rule-group-select';
    selectType.innerHTML = `
      <option value="AND">Match ALL (AND)</option>
      <option value="OR">Match ANY (OR)</option>
    `;
    selectType.value = node.type.toUpperCase();
    selectType.addEventListener('change', (e) => {
      node.type = e.target.value;
      onUpdate();
    });
    
    const actionsEl = document.createElement('div');
    actionsEl.className = 'rule-group-actions';
    
    const addCondBtn = document.createElement('button');
    addCondBtn.className = 'btn btn-secondary';
    addCondBtn.textContent = '+ Condition';
    addCondBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (!node.conditions) node.conditions = [];
      node.conditions.push({ field: 'Part Number', operator: 'equals', value: '' });
      onUpdate();
    });
    
    const addGroupBtn = document.createElement('button');
    addGroupBtn.className = 'btn btn-secondary';
    addGroupBtn.textContent = '+ Group';
    addGroupBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (!node.conditions) node.conditions = [];
      node.conditions.push({ type: 'AND', conditions: [] });
      onUpdate();
    });
    
    actionsEl.appendChild(addCondBtn);
    actionsEl.appendChild(addGroupBtn);
    
    if (parentGroup) {
      const delGroupBtn = document.createElement('button');
      delGroupBtn.className = 'btn btn-secondary btn-delete-group-btn';
      delGroupBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
      delGroupBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const idx = parentGroup.conditions.indexOf(node);
        if (idx !== -1) {
          parentGroup.conditions.splice(idx, 1);
          onUpdate();
        }
      });
      actionsEl.appendChild(delGroupBtn);
    }
    
    headerEl.appendChild(selectType);
    headerEl.appendChild(actionsEl);
    groupEl.appendChild(headerEl);
    
    const conditionsContainer = document.createElement('div');
    conditionsContainer.className = 'rule-group-conditions';
    
    if (node.conditions && node.conditions.length > 0) {
      node.conditions.forEach(subNode => {
        conditionsContainer.appendChild(buildRuleUI(subNode, node, onUpdate, definitionId));
      });
    } else {
      const emptyMsg = document.createElement('div');
      emptyMsg.className = 'tab-description';
      emptyMsg.style.margin = '0';
      emptyMsg.style.fontStyle = 'italic';
      emptyMsg.textContent = 'Empty group. Add conditions...';
      conditionsContainer.appendChild(emptyMsg);
    }
    
    groupEl.appendChild(conditionsContainer);
    return groupEl;
  } else {
    const condEl = document.createElement('div');
    condEl.className = 'rule-condition';
    
    const dragHandle = document.createElement('div');
    dragHandle.className = 'cond-drag-handle';
    dragHandle.title = 'Drag condition into another group';
    dragHandle.innerHTML = '<i class="fa-solid fa-grip-vertical"></i>';
    
    condEl.setAttribute('draggable', 'true');
    condEl.addEventListener('dragstart', (e) => {
      activeDraggedProblemItem = {
        definitionId,
        node,
        parentGroup
      };
      if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', JSON.stringify({ field: node.field }));
      }
      condEl.classList.add('dragging');
    });
    
    condEl.addEventListener('dragend', () => {
      condEl.classList.remove('dragging');
      activeDraggedProblemItem = null;
      document.querySelectorAll('.drag-target-hover').forEach(el => el.classList.remove('drag-target-hover'));
    });
    
    let currentField = node.field || 'Part Number';
    if (currentField === 'External Part Number') currentField = 'External PN';
    if (currentField === 'Source Link') currentField = 'Source URL';
    if (currentField === 'Has photos' || currentField === 'Has Photos') currentField = 'has_photos';
    if (currentField === 'blackbox') currentField = 'Blackbox';
    if (currentField === 'BOM equilibrium (balance)' || currentField === 'bom_balance') currentField = 'bom_equilibrium';
    if (currentField === 'Has all images' || currentField === 'has_all_photos') currentField = 'has_all_images';
    if (currentField === 'Price' || currentField === 'price' || currentField === 'price_per_unit') currentField = 'Price per unit';
    
    const currentConfig = getFieldConfig(currentField);
    
    const fieldSelect = document.createElement('select');
    fieldSelect.className = 'form-input cond-field-select';
    fieldSelect.innerHTML = `
      <option value="Part Number">Part Number</option>
      <option value="Item description">Item description</option>
      <option value="External PN">External PN</option>
      <option value="Price per unit">Price per unit</option>
      <option value="State">State</option>
      <option value="Source URL">Source Link</option>
      <option value="Sourced By">Sourced By</option>
      <option value="is_in_assembly">Is Contained in Assembly</option>
      <option value="has_children">Has children</option>
      <option value="Blackbox">Blackbox</option>
      <option value="has_photos">Has photos</option>
      <option value="bom_equilibrium">BOM equilibrium (balance)</option>
      <option value="has_all_images">Has all images</option>
    `;
    fieldSelect.value = currentField;
    fieldSelect.addEventListener('change', (e) => {
      const newField = e.target.value;
      const newConfig = getFieldConfig(newField);
      const oldConfig = getFieldConfig(node.field);
      node.field = newField;
      
      if (newConfig.type === 'binary') {
        node.value = 'true';
        if (node.operator === 'contains' || node.operator === 'not_contains' || node.operator === 'is_empty' || node.operator === 'is_not_empty' || node.operator === 'greater_than' || node.operator === 'less_than' || node.operator === 'greater_than_or_equal' || node.operator === 'less_than_or_equal') {
          node.operator = 'equals';
        }
      } else if (newConfig.type === 'select') {
        if (node.operator === 'contains' || node.operator === 'not_contains' || node.operator === 'greater_than' || node.operator === 'less_than' || node.operator === 'greater_than_or_equal' || node.operator === 'less_than_or_equal') {
          node.operator = 'equals';
        }
        if (!newConfig.options.some(o => o.value === node.value)) {
          node.value = newConfig.options[0].value;
        }
      } else if (newConfig.type === 'numeric') {
        if (node.operator === 'contains' || node.operator === 'not_contains') {
          node.operator = 'equals';
        }
        if (oldConfig.type === 'binary') {
          node.value = '';
        }
      } else {
        if (node.operator === 'greater_than' || node.operator === 'less_than' || node.operator === 'greater_than_or_equal' || node.operator === 'less_than_or_equal') {
          node.operator = 'equals';
        }
        if (oldConfig.type === 'binary') {
          node.value = '';
        }
      }
      onUpdate();
    });
    
    const opSelect = document.createElement('select');
    opSelect.className = 'form-input cond-operator-select';
    if (currentConfig.type === 'numeric') {
      opSelect.innerHTML = `
        <option value="equals">Equals (=)</option>
        <option value="not_equals">Does Not Equal (&ne;)</option>
        <option value="greater_than">Greater Than (&gt;)</option>
        <option value="less_than">Less Than (&lt;)</option>
        <option value="greater_than_or_equal">Greater Than or Equal (&ge;)</option>
        <option value="less_than_or_equal">Less Than or Equal (&le;)</option>
        <option value="is_empty">Is Empty</option>
        <option value="is_not_empty">Is Not Empty</option>
      `;
    } else if (currentConfig.type === 'binary') {
      opSelect.innerHTML = `
        <option value="equals">Equals</option>
        <option value="not_equals">Does Not Equal</option>
      `;
    } else if (currentConfig.type === 'select') {
      opSelect.innerHTML = `
        <option value="equals">Equals</option>
        <option value="not_equals">Does Not Equal</option>
        <option value="is_empty">Is Empty</option>
        <option value="is_not_empty">Is Not Empty</option>
      `;
    } else {
      opSelect.innerHTML = `
        <option value="equals">Equals</option>
        <option value="not_equals">Does Not Equal</option>
        <option value="contains">Contains</option>
        <option value="not_contains">Does Not Contain</option>
        <option value="is_empty">Is Empty</option>
        <option value="is_not_empty">Is Not Empty</option>
      `;
    }
    opSelect.value = node.operator || 'equals';
    opSelect.addEventListener('change', (e) => {
      node.operator = e.target.value;
      onUpdate();
    });
    
    const isOperatorEmpty = (node.operator === 'is_empty' || node.operator === 'is_not_empty');
    let valEl;
    
    if (currentConfig.type === 'select') {
      const valSelect = document.createElement('select');
      valSelect.className = 'form-input cond-value-select';
      
      currentConfig.options.forEach(opt => {
        const optEl = document.createElement('option');
        optEl.value = opt.value;
        optEl.textContent = opt.label;
        valSelect.appendChild(optEl);
      });
      
      if (node.value !== undefined && node.value !== null && node.value !== '') {
        if (currentConfig.options.some(o => o.value === node.value)) {
          valSelect.value = node.value;
        } else if (node.value === 'Engineering Use' && currentConfig.options.some(o => o.value === 'Engineerig Use')) {
          valSelect.value = 'Engineerig Use';
        } else {
          const customOpt = document.createElement('option');
          customOpt.value = node.value;
          customOpt.textContent = node.value;
          valSelect.appendChild(customOpt);
          valSelect.value = node.value;
        }
      } else {
        if (currentConfig.options.length > 0) {
          node.value = currentConfig.options[0].value;
          valSelect.value = node.value;
        }
      }
      
      if (isOperatorEmpty) {
        valSelect.disabled = true;
      }
      
      valSelect.addEventListener('change', (e) => {
        node.value = e.target.value;
        checkSettingsChanges();
      });
      valEl = valSelect;
    } else if (currentConfig.type === 'binary') {
      const isTrue = (node.value === true || String(node.value).toLowerCase() === 'true');
      node.value = isTrue ? 'true' : 'false';
      
      const toggleWrapper = document.createElement('div');
      toggleWrapper.className = 'cond-toggle-wrapper';
      
      const toggleLabel = document.createElement('label');
      toggleLabel.className = 'theme-toggle-switch';
      
      const toggleInput = document.createElement('input');
      toggleInput.type = 'checkbox';
      toggleInput.className = 'cond-toggle-input';
      toggleInput.checked = isTrue;
      if (isOperatorEmpty) {
        toggleInput.disabled = true;
      }
      
      const toggleSlider = document.createElement('span');
      toggleSlider.className = 'theme-toggle-slider';
      
      const toggleText = document.createElement('span');
      toggleText.className = 'theme-toggle-text';
      toggleText.textContent = isTrue ? 'TRUE' : 'FALSE';
      
      toggleInput.addEventListener('change', (e) => {
        const checked = e.target.checked;
        node.value = checked ? 'true' : 'false';
        toggleText.textContent = checked ? 'TRUE' : 'FALSE';
        checkSettingsChanges();
      });
      
      toggleLabel.appendChild(toggleInput);
      toggleLabel.appendChild(toggleSlider);
      toggleWrapper.appendChild(toggleLabel);
      toggleWrapper.appendChild(toggleText);
      valEl = toggleWrapper;
    } else if (currentConfig.type === 'numeric') {
      const valInput = document.createElement('input');
      valInput.type = 'number';
      valInput.step = 'any';
      valInput.className = 'form-input cond-value-input';
      valInput.value = (node.value !== undefined && node.value !== null) ? node.value : '';
      valInput.placeholder = currentConfig.placeholder || '0.00';
      
      if (isOperatorEmpty) {
        valInput.disabled = true;
        valInput.value = '';
      }
      
      valInput.addEventListener('input', (e) => {
        node.value = e.target.value;
        checkSettingsChanges();
      });
      valEl = valInput;
    } else {
      const valInput = document.createElement('input');
      valInput.type = 'text';
      valInput.className = 'form-input cond-value-input';
      valInput.value = node.value || '';
      valInput.placeholder = currentConfig.placeholder || 'Value...';
      
      if (isOperatorEmpty) {
        valInput.disabled = true;
        valInput.value = '';
      }
      
      valInput.addEventListener('input', (e) => {
        node.value = e.target.value;
        checkSettingsChanges();
      });
      valEl = valInput;
    }
    
    const delCondBtn = document.createElement('button');
    delCondBtn.className = 'btn btn-secondary btn-delete-cond-btn';
    delCondBtn.innerHTML = '<i class="fa-solid fa-xmark"></i>';
    delCondBtn.addEventListener('click', (e) => {
      e.preventDefault();
      if (parentGroup) {
        const idx = parentGroup.conditions.indexOf(node);
        if (idx !== -1) {
          parentGroup.conditions.splice(idx, 1);
          onUpdate();
        }
      }
    });
    
    condEl.appendChild(dragHandle);
    condEl.appendChild(fieldSelect);
    condEl.appendChild(opSelect);
    condEl.appendChild(valEl);
    condEl.appendChild(delCondBtn);
    
    return condEl;
  }
}

function renderProblemsEditor() {
  if (!problemsEditorContainer) problemsEditorContainer = document.getElementById('problems-editor-container');
  if (!problemsEditorContainer || !currentDefs) return;
  problemsEditorContainer.innerHTML = '';
  
  currentDefs.forEach((definition, idx) => {
    const isExpanded = (definition.id === expandedProblemId);
    const hasChanges = isDefinitionChanged(definition);
    
    const card = document.createElement('div');
    card.className = `problem-def-card ${isExpanded ? 'expanded' : 'collapsed'}`;
    
    const header = document.createElement('div');
    header.className = 'problem-def-header';
    
    const toggleTrigger = document.createElement('div');
    toggleTrigger.className = 'problem-def-toggle-trigger';
    
    const caret = document.createElement('i');
    caret.className = `fa-solid ${isExpanded ? 'fa-chevron-down' : 'fa-chevron-right'} caret-icon`;
    toggleTrigger.appendChild(caret);
    
    if (isExpanded) {
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.className = 'form-input problem-name-input';
      nameInput.value = definition.name;
      nameInput.placeholder = 'Define problem error message...';
      nameInput.addEventListener('input', (e) => {
        definition.name = e.target.value;
        checkSettingsChanges();
      });
      nameInput.addEventListener('click', (e) => e.stopPropagation());
      toggleTrigger.appendChild(nameInput);
    } else {
      const titleSpan = document.createElement('span');
      titleSpan.className = 'problem-title-text';
      titleSpan.textContent = (hasChanges ? '* ' : '') + (definition.name || 'New Problem Definition');
      toggleTrigger.appendChild(titleSpan);
    }
    
    header.appendChild(toggleTrigger);
    
    if (isExpanded) {
      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-secondary btn-delete-problem';
      delBtn.innerHTML = '<i class="fa-solid fa-trash"></i> Delete';
      delBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        currentDefs.splice(idx, 1);
        if (expandedProblemId === definition.id) {
          expandedProblemId = null;
        }
        renderProblemsEditor();
        checkSettingsChanges();
      });
      header.appendChild(delBtn);
    } else {
      const badgeWrapper = document.createElement('div');
      badgeWrapper.className = 'problem-count-badge-wrapper';
      badgeWrapper.setAttribute('data-id', definition.id);
      
      const cachedInfo = problemOccurrences[definition.id];
      badgeWrapper.innerHTML = getOccurrenceBadgeHTML(cachedInfo);
      header.appendChild(badgeWrapper);
    }
    
    header.addEventListener('click', () => {
      expandedProblemId = isExpanded ? null : definition.id;
      renderProblemsEditor();
    });
    
    card.appendChild(header);
    
    if (isExpanded) {
      const ruleUI = buildRuleUI(definition.rule, null, () => {
        renderProblemsEditor();
        checkSettingsChanges();
      }, definition.id);
      card.appendChild(ruleUI);
    }
    
    problemsEditorContainer.appendChild(card);
  });
}

function hasUnsavedSettingsChanges() {
  if (!originalRules || !currentRules || !originalDefs || !currentDefs || !originalTemplates || !currentTemplates) return false;
  
  const dictRules = {};
  currentRules.forEach(r => {
    if (r.prefix.trim()) {
      dictRules[r.prefix.trim()] = { name: r.name, color: r.color };
    }
  });
  
  const rulesChanged = JSON.stringify(originalRules) !== JSON.stringify(dictRules);
  const defsChanged = JSON.stringify(originalDefs) !== JSON.stringify(currentDefs);
  const templatesChanged = JSON.stringify(originalTemplates) !== JSON.stringify(currentTemplates);
  
  return rulesChanged || defsChanged || templatesChanged;
}

function checkSettingsChanges() {
  const changed = hasUnsavedSettingsChanges();
  if (btnSettingsSave) btnSettingsSave.disabled = !changed;
  if (btnSettingsRevert) btnSettingsRevert.disabled = !changed;
}

function revertSettings() {
  if (!originalRules || !originalDefs || !originalTemplates) return;
  
  currentRules = Object.keys(originalRules).map(k => ({ prefix: k, name: originalRules[k].name, color: originalRules[k].color }));
  currentDefs = JSON.parse(JSON.stringify(originalDefs));
  currentTemplates = JSON.parse(JSON.stringify(originalTemplates));
  
  expandedProblemId = null;
  activeTestTemplateIndex = 0;
  
  renderRulesEditor();
  renderProblemsEditor();
  renderTemplatesEditor();
  updateTestPreview();
  checkSettingsChanges();
  showToast('Settings reverted to saved state', 'success');
}

async function saveSettingsChanges() {
  if (!currentRules || !currentDefs || !currentTemplates) return;
  
  const invalidRule = currentRules.find(r => !r.prefix.trim() || !r.name.trim());
  if (invalidRule) {
    showToast('Category rules must have a valid prefix and name.', 'error');
    return;
  }
  
  const invalidDef = currentDefs.find(d => !d.name.trim());
  if (invalidDef) {
    showToast('Problem definitions must have a valid name description.', 'error');
    return;
  }

  const invalidTemplate = currentTemplates.find(t => !t.action.trim() || !t.template.trim());
  if (invalidTemplate) {
    showToast('Templates must have a valid action name and template pattern.', 'error');
    return;
  }
  
  const dictRules = {};
  currentRules.forEach(r => {
    dictRules[r.prefix.trim()] = { name: r.name, color: r.color };
  });
  
  try {
    if (btnSettingsSave) btnSettingsSave.disabled = true;
    
    await saveRules(dictRules);
    await saveProblemDefinitions(currentDefs);
    await saveQuickActionTemplates(currentTemplates);
    
    originalRules = dictRules;
    originalDefs = JSON.parse(JSON.stringify(currentDefs));
    originalTemplates = JSON.parse(JSON.stringify(currentTemplates));
    
    checkSettingsChanges();
    showToast('Settings saved successfully. Scanner restarted.', 'success');
    startOccurrencesPolling();
  } catch (err) {
    showToast(`Error saving settings: ${err.message}`, 'error');
    if (btnSettingsSave) btnSettingsSave.disabled = false;
  }
}

function addNewRuleRow() {
  currentRules.push({ prefix: '', name: '', color: '#ffffff' });
  renderRulesEditor();
  checkSettingsChanges();
}

function addNewProblemRow() {
  const newId = `rule_${Date.now()}`;
  currentDefs.push({
    id: newId,
    name: 'New Problem Definition',
    rule: {
      type: 'AND',
      conditions: [
        { field: 'Part Number', operator: 'equals', value: '' }
      ]
    }
  });
  expandedProblemId = newId;
  renderProblemsEditor();
  checkSettingsChanges();
}

function showToast(message, type = 'success', progress = null) {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return null;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconHtml = '✓';
  if (type === 'error') iconHtml = '✗';
  else if (type === 'loading') iconHtml = '<span class="toast-hourglass">⏳</span>';

  let progressBarHtml = '';
  if (type === 'loading') {
    const isIndeterminate = progress === null || progress === undefined;
    const progressWidth = isIndeterminate ? 30 : Math.min(100, Math.max(0, progress));
    const barClass = isIndeterminate ? 'toast-progress-bar indeterminate' : 'toast-progress-bar';
    progressBarHtml = `
      <div class="toast-progress-track">
        <div class="${barClass}" style="width: ${progressWidth}%;"></div>
      </div>
    `;
  }
  
  toast.innerHTML = `
    <span class="toast-icon">${iconHtml}</span>
    <span class="toast-text">${message}</span>
    ${progressBarHtml}
  `;
  toastContainer.appendChild(toast);
  
  const textSpan = toast.querySelector('.toast-text');
  const progressBar = toast.querySelector('.toast-progress-bar');
  
  let timeoutId = null;
  if (type !== 'loading') {
    timeoutId = setTimeout(() => {
      toast.remove();
    }, 4000);
  }
  
  const toastHandle = {
    element: toast,
    updateProgress(percent, newText) {
      if (newText && textSpan) {
        textSpan.textContent = newText;
      }
      if (progressBar) {
        if (percent === null || percent === undefined) {
          progressBar.classList.add('indeterminate');
          progressBar.style.width = '30%';
        } else {
          progressBar.classList.remove('indeterminate');
          const clamped = Math.min(100, Math.max(0, percent));
          progressBar.style.width = `${clamped}%`;
        }
      }
    },
    dismiss() {
      if (timeoutId) clearTimeout(timeoutId);
      toast.remove();
    },
    complete(finalMessage) {
      this.updateProgress(100, finalMessage || 'Done');
      setTimeout(() => {
        this.dismiss();
      }, 600);
    }
  };

  return toastHandle;
}

function showLoadingToast(message, initialProgress = null) {
  return showToast(message, 'loading', initialProgress);
}

function initLogsTab() {
  const LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"];
  const slider = document.getElementById('log-verbosity-slider');
  const label = document.getElementById('log-verbosity-label');
  const btnSave = document.getElementById('btn-save-log-config');
  const btnRefresh = document.getElementById('btn-refresh-logs');
  const btnCopy = document.getElementById('btn-copy-logs');
  const logArea = document.getElementById('log-content-area');
  const activeFilename = document.getElementById('active-log-filename');

  if (!slider || !label || !btnSave || !btnRefresh || !btnCopy || !logArea || !activeFilename) return;

  // Handle slider input (visual change only)
  slider.addEventListener('input', () => {
    const val = parseInt(slider.value);
    label.textContent = LOG_LEVELS[val];
  });

  // Handle save button click
  btnSave.addEventListener('click', async () => {
    const val = parseInt(slider.value);
    const selectedLevel = LOG_LEVELS[val];
    try {
      btnSave.disabled = true;
      btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
      await saveLogsConfig(selectedLevel);
      showToast(`Log verbosity level saved: ${selectedLevel}`, 'success');
      await refreshActiveLogContent();
    } catch (err) {
      showToast(`Failed to save log level: ${err.message}`, 'error');
    } finally {
      btnSave.disabled = false;
      btnSave.innerHTML = '<i class="fa-solid fa-save"></i> Save Log Settings';
    }
  });

  // Handle refresh click
  btnRefresh.addEventListener('click', refreshActiveLogContent);

  // Handle copy click
  btnCopy.addEventListener('click', () => {
    const textToCopy = logArea.innerText;
    navigator.clipboard.writeText(textToCopy).then(() => {
      showToast('Logs copied to clipboard', 'success');
    }).catch(err => {
      showToast(`Failed to copy logs: ${err.message}`, 'error');
    });
  });

  async function refreshActiveLogContent() {
    try {
      logArea.innerHTML = '<div class="log-line" style="color: #64748b; font-style: italic;"><i class="fa-solid fa-spinner fa-spin"></i> Fetching active logs...</div>';
      const info = await fetchActiveLog();
      activeFilename.textContent = info.filename || 'None';
      
      if (!info.content) {
        logArea.innerHTML = '<div class="log-line" style="color: #64748b; font-style: italic;">Log file is empty.</div>';
      } else {
        logArea.innerHTML = formatLogLines(info.content);
        logArea.scrollTop = logArea.scrollHeight;
      }
    } catch (err) {
      logArea.innerHTML = `<div class="log-line" style="color: #f87171;">Failed to load active log: ${escapeHtml(err.message)}</div>`;
    }
  }

  // Load initial settings
  async function loadLogsConfig() {
    try {
      const config = await fetchLogsConfig();
      const level = config.level || "INFO";
      const idx = LOG_LEVELS.indexOf(level);
      if (idx !== -1) {
        slider.value = idx;
        label.textContent = level;
      }
      await refreshActiveLogContent();
    } catch (err) {
      showToast(`Failed to load logs configuration: ${err.message}`, 'error');
    }
  }

  window._loadLogsConfig = loadLogsConfig;
}

function formatLogLines(text) {
  if (!text) return '<div class="log-line" style="color: #64748b; font-style: italic;">No logs found.</div>';
  const lines = text.split('\n');
  return lines.map(line => {
    if (!line.trim()) return '';
    
    let cssClass = 'log-line-info';
    if (line.includes(' - TRACE - ')) {
      cssClass = 'log-line-trace';
    } else if (line.includes(' - DEBUG - ')) {
      cssClass = 'log-line-debug';
    } else if (line.includes(' - INFO - ')) {
      cssClass = 'log-line-info';
    } else if (line.includes(' - WARNING - ')) {
      cssClass = 'log-line-warning';
    } else if (line.includes(' - ERROR - ')) {
      cssClass = 'log-line-error';
    }
    
    return `<div class="log-line ${cssClass}">${escapeHtml(line)}</div>`;
  }).join('');
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderTemplatesEditor() {
  const container = document.getElementById('templates-editor-container');
  if (!container) return;
  container.innerHTML = '';
  
  if (!currentTemplates || currentTemplates.length === 0) {
    container.innerHTML = '<div style="color: var(--text-secondary); text-align: center; padding: 1rem;">No templates defined. Click "+ Add New Template" to add one.</div>';
    return;
  }
  
  currentTemplates.forEach((tpl, idx) => {
    const card = document.createElement('div');
    card.className = 'template-rule-row';
    card.style.cssText = 'display: flex; gap: 1rem; align-items: flex-start; padding: 1rem; background: rgba(255, 255, 255, 0.02); border: 1px solid var(--card-border); border-radius: 6px;';
    
    if (activeTestTemplateIndex === idx) {
      card.style.borderColor = 'var(--color-gold-bright)';
      card.style.background = 'rgba(197, 160, 89, 0.04)';
    }

    const setCardActive = () => {
      activeTestTemplateIndex = idx;
      const cards = container.querySelectorAll('.template-rule-row');
      cards.forEach((c, i) => {
        if (i === idx) {
          c.style.borderColor = 'var(--color-gold-bright)';
          c.style.background = 'rgba(197, 160, 89, 0.04)';
        } else {
          c.style.borderColor = 'var(--card-border)';
          c.style.background = 'rgba(255, 255, 255, 0.02)';
        }
      });
      updateTestPreview();
    };

    const actionDiv = document.createElement('div');
    actionDiv.style.cssText = 'flex: 1; display: flex; flex-direction: column; gap: 0.3rem;';
    actionDiv.innerHTML = '<label style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase;">Button Action Name</label>';
    const actionInput = document.createElement('input');
    actionInput.type = 'text';
    actionInput.className = 'form-input';
    actionInput.value = tpl.action || '';
    actionInput.placeholder = 'e.g. Solder';
    actionInput.style.padding = '0.5rem 0.75rem';
    actionInput.addEventListener('input', (e) => {
      tpl.action = e.target.value;
      checkSettingsChanges();
      updateTestPreview();
    });
    actionInput.addEventListener('focus', setCardActive);
    actionDiv.appendChild(actionInput);
    
    const templateDiv = document.createElement('div');
    templateDiv.style.cssText = 'flex: 3; display: flex; flex-direction: column; gap: 0.3rem;';
    templateDiv.innerHTML = '<label style="font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase;">Description Template Pattern</label>';
    const templateInput = document.createElement('textarea');
    templateInput.className = 'form-input';
    templateInput.rows = 2;
    templateInput.value = tpl.template || '';
    templateInput.placeholder = 'e.g. {action} {a.1} onto {a.2} using {t.1}';
    templateInput.style.cssText = 'padding: 0.5rem 0.75rem; resize: vertical; min-height: 2.5rem; font-family: inherit; line-height: 1.4;';
    templateInput.addEventListener('input', (e) => {
      tpl.template = e.target.value;
      checkSettingsChanges();
      updateTestPreview();
    });
    templateInput.addEventListener('focus', setCardActive);
    templateDiv.appendChild(templateInput);
    
    const actionsDiv = document.createElement('div');
    actionsDiv.style.cssText = 'display: flex; gap: 0.5rem; margin-top: 1.3rem;';
    
    const testBtn = document.createElement('button');
    testBtn.type = 'button';
    testBtn.className = 'btn btn-secondary';
    testBtn.style.padding = '0.5rem';
    testBtn.title = 'Test this template';
    testBtn.innerHTML = '<i class="fa-solid fa-flask"></i>';
    testBtn.addEventListener('click', setCardActive);
    
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'btn btn-secondary btn-delete-cond-btn';
    delBtn.style.padding = '0.5rem';
    delBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
    delBtn.addEventListener('click', () => {
      currentTemplates.splice(idx, 1);
      if (activeTestTemplateIndex >= currentTemplates.length) {
        activeTestTemplateIndex = Math.max(0, currentTemplates.length - 1);
      }
      renderTemplatesEditor();
      checkSettingsChanges();
      updateTestPreview();
    });
    
    actionsDiv.appendChild(testBtn);
    actionsDiv.appendChild(delBtn);
    
    card.appendChild(actionDiv);
    card.appendChild(templateDiv);
    card.appendChild(actionsDiv);
    container.appendChild(card);
  });
}

function updateTestPreview() {
  const previewBox = document.getElementById('test-template-preview-box');
  if (!previewBox || !currentTemplates || currentTemplates.length === 0) {
    if (previewBox) previewBox.textContent = '';
    return;
  }
  
  const idx = Math.min(activeTestTemplateIndex, currentTemplates.length - 1);
  const activeTemplateObj = currentTemplates[idx >= 0 ? idx : 0];
  if (!activeTemplateObj) {
    previewBox.textContent = '';
    return;
  }
  
  const actionInput = document.getElementById('test-input-action');
  const a1Input = document.getElementById('test-input-a1');
  const a2Input = document.getElementById('test-input-a2');
  const a3Input = document.getElementById('test-input-a3');
  const t1Input = document.getElementById('test-input-t1');
  const t2Input = document.getElementById('test-input-t2');
  
  const action = actionInput ? actionInput.value : '';
  const a1 = a1Input ? a1Input.value : '"Nova Amplifier Outer Shell" (30-00062 Rev.A)';
  const a2 = a2Input ? a2Input.value : '"Main Logic Board" (20-00014 Rev.A)';
  const a3 = a3Input ? a3Input.value : '"Front Bezel" (30-00063 Rev.A)';
  const t1 = t1Input ? t1Input.value : '"Soldering Station" (90-00001 Rev.A)';
  const t2 = t2Input ? t2Input.value : '"Torque Driver" (90-00005 Rev.A)';
  
  const templateStr = activeTemplateObj.template || '';
  
  let preview = templateStr
    .replaceAll('{action}', action || (activeTemplateObj.action || 'Action'))
    .replaceAll('{a.1}', a1)
    .replaceAll('{a.2}', a2)
    .replaceAll('{a.3}', a3)
    .replaceAll('{t.1}', t1)
    .replaceAll('{t.2}', t2);
  
  for (let i = 1; i <= 20; i++) {
    const aToken = `{a.${i}}`;
    if (preview.includes(aToken)) {
      preview = preview.replaceAll(aToken, `[Slot ${aToken} not found]`);
    }
    const tToken = `{t.${i}}`;
    if (preview.includes(tToken)) {
      preview = preview.replaceAll(tToken, `[Slot ${tToken} not found]`);
    }
  }
    
  previewBox.textContent = preview;
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}



// --- WI Templates Logic ---
let wiTemplates = [];

async function loadWiTemplates() {
  try {
    wiTemplates = await fetchWiTemplates();
    renderWiTemplates();
  } catch (e) {
    console.error(e);
  }
}

async function loadWiConfig() {
  try {
    const config = await fetchWiConfig();
    const input = document.getElementById('wi-filename-pattern');
    if (input && config.filename_pattern) {
      input.value = config.filename_pattern;
    }
  } catch (e) {
    console.error(e);
  }
}

async function handleSaveWiConfig() {
  const input = document.getElementById('wi-filename-pattern');
  if (!input) return;
  try {
    await saveWiConfig({ filename_pattern: input.value });
    alert('Config saved successfully');
  } catch (e) {
    alert('Error saving config: ' + e.message);
  }
}

async function handleUploadWiTemplate() {
  const nameInput = document.getElementById('new-wi-template-name');
  const fileInput = document.getElementById('new-wi-template-file');
  if (!nameInput.value || !fileInput.files.length) {
    alert("Please provide a name and select a .docx file");
    return;
  }
  
  try {
    const file = fileInput.files[0];
    await uploadWiTemplate(file, nameInput.value);
    nameInput.value = '';
    fileInput.value = '';
    await loadWiTemplates();
  } catch (e) {
    alert('Error uploading template: ' + e.message);
  }
}

function renderWiTemplates() {
  const container = document.getElementById('wi-templates-list');
  if (!container) return;
  
  container.innerHTML = '';
  if (wiTemplates.length === 0) {
    container.innerHTML = '<p>No templates found.</p>';
    return;
  }
  
  wiTemplates.forEach(t => {
    const card = document.createElement('div');
    card.className = 'template-card';
    card.style = 'border: 1px solid var(--border-color); padding: 15px; border-radius: 6px; margin-bottom: 10px; background: var(--bg-secondary);';
    
    const isValid = !!t.Valid;
    const isApproved = !!t.Approved;
    
    let badgeColor = 'orange';
    let badgeText = 'Unapproved (Warning: Unrecognized Tokens)';
    if (isValid) {
      badgeColor = 'green';
      badgeText = 'Valid';
    } else if (isApproved) {
      badgeColor = 'green';
      badgeText = 'Approved';
    }
    
    let tokensFound = [];
    try { tokensFound = JSON.parse(t['Tokens Found'] || '[]'); } catch(e){}
    let tokensInvalid = [];
    try { tokensInvalid = JSON.parse(t['Invalid Tokens'] || '[]'); } catch(e){}
    
    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h4 style="margin:0;">${t.Name}</h4>
        <span style="background: ${badgeColor}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 0.8em;">${badgeText}</span>
      </div>
      <p style="font-size: 0.9em; color: var(--text-secondary); margin-bottom: 5px;">File: ${t.Filename}</p>
      <div style="margin-bottom: 10px; font-size: 0.85em;">
        <strong>Found Tokens:</strong> ${tokensFound.map(x => `<span style="background:var(--bg-tertiary); padding: 2px 5px; border-radius:3px; margin: 2px; display:inline-block;">${x}</span>`).join('')}
      </div>
      ${tokensInvalid.length > 0 ? `
      <div style="margin-bottom: 10px; font-size: 0.85em; color: #ff9900;">
        <strong>Unrecognized Tokens (Ignored on Export):</strong> ${tokensInvalid.map(x => `<span style="background:rgba(255,150,0,0.1); padding: 2px 5px; border-radius:3px; margin: 2px; display:inline-block;">${x}</span>`).join('')}
      </div>` : ''}
      <div style="display: flex; gap: 10px; margin-top: 15px;">
        <label class="btn btn-sm" style="cursor: pointer;">
          Replace File
          <input type="file" style="display:none;" accept=".docx" onchange="window.handleReplaceTemplate(${t.id}, this)">
        </label>
        ${!isValid ? `
          <button class="btn btn-sm ${isApproved ? 'btn-secondary' : 'btn-success'}" onclick="window.handleApproveTemplate(${t.id}, ${!isApproved})">
            ${isApproved ? 'Revoke Approval' : 'Approve'}
          </button>
        ` : ''}
        <button class="btn btn-sm btn-danger" onclick="window.handleDeleteTemplate(${t.id})">Delete</button>
      </div>
    `;
    container.appendChild(card);
  });
}

window.handleApproveTemplate = async function(id, approved) {
  try {
    await approveWiTemplate(id, approved);
    await loadWiTemplates();
  } catch (e) {
    alert("Error updating template approval: " + e.message);
  }
};

window.handleReplaceTemplate = async function(id, input) {
  if (!input.files.length) return;
  try {
    await replaceWiTemplate(id, input.files[0]);
    await loadWiTemplates();
  } catch(e) {
    alert("Error replacing template: " + e.message);
  }
};

window.handleDeleteTemplate = async function(id) {
  if (!confirm("Delete this template?")) return;
  try {
    await deleteWiTemplate(id);
    await loadWiTemplates();
  } catch (e) {
    alert("Error deleting template: " + e.message);
  }
};

/* ==========================================================================
   Baserow Authentication Tab Handlers
   ========================================================================== */

function initAuthTab() {
  const btnToggleToken = document.getElementById('btn-toggle-token');
  const inputToken = document.getElementById('auth-input-token');
  if (btnToggleToken && inputToken) {
    btnToggleToken.addEventListener('click', () => {
      if (inputToken.type === 'password') {
        inputToken.type = 'text';
        btnToggleToken.innerHTML = '<i class="fa-regular fa-eye-slash"></i>';
      } else {
        inputToken.type = 'password';
        btnToggleToken.innerHTML = '<i class="fa-regular fa-eye"></i>';
      }
    });
  }

  const btnTogglePw = document.getElementById('btn-toggle-password');
  const inputPw = document.getElementById('auth-input-password');
  if (btnTogglePw && inputPw) {
    btnTogglePw.addEventListener('click', () => {
      if (inputPw.type === 'password') {
        inputPw.type = 'text';
        btnTogglePw.innerHTML = '<i class="fa-regular fa-eye-slash"></i>';
      } else {
        inputPw.type = 'password';
        btnTogglePw.innerHTML = '<i class="fa-regular fa-eye"></i>';
      }
    });
  }

  const btnTest = document.getElementById('btn-auth-test');
  if (btnTest) {
    btnTest.addEventListener('click', handleTestAuth);
  }

  const btnSave = document.getElementById('btn-auth-save');
  if (btnSave) {
    btnSave.addEventListener('click', handleSaveAuth);
  }

  loadAuthConfig();
}

function getAuthFormData() {
  const host = (document.getElementById('auth-input-host')?.value || '').trim();
  const port = (document.getElementById('auth-input-port')?.value || '').trim();
  const token = (document.getElementById('auth-input-token')?.value || '').trim();
  const email = (document.getElementById('auth-input-email')?.value || '').trim();
  const password = (document.getElementById('auth-input-password')?.value || '').trim();
  const dbId = (document.getElementById('auth-input-db-id')?.value || '').trim();

  return {
    host,
    port,
    token,
    admin_email: email,
    admin_password: password,
    database_id: dbId || null
  };
}

async function loadAuthConfig() {
  const container = document.getElementById('auth-tables-container');
  try {
    const config = await fetchAuthConfig();
    currentAuthConfig = config;

    const hostInput = document.getElementById('auth-input-host');
    const portInput = document.getElementById('auth-input-port');
    const tokenInput = document.getElementById('auth-input-token');
    const emailInput = document.getElementById('auth-input-email');
    const dbIdInput = document.getElementById('auth-input-db-id');

    if (hostInput && config.host) hostInput.value = config.host;
    if (portInput) portInput.value = config.port || '';
    if (tokenInput && config.token !== undefined) tokenInput.value = config.token;
    if (emailInput && config.admin_email) emailInput.value = config.admin_email;
    if (dbIdInput) dbIdInput.value = config.database_id || '';

    updateAuthStatusUI(config);
    renderAuthTables(config.tables);
  } catch (err) {
    if (container) {
      container.innerHTML = `<div class="auth-pill pill-danger" style="padding: 1rem; text-align: center;">Failed to load Baserow schema configuration: ${err.message}</div>`;
    }
  }
}

function updateAuthStatusUI(config) {
  const warningNavBadge = document.getElementById('auth-nav-warning');
  const tokenWarningBox = document.getElementById('auth-token-warning');
  const tokenWarningText = document.getElementById('auth-token-warning-text');
  const schemaBadge = document.getElementById('auth-overall-schema-badge');

  if (warningNavBadge) {
    warningNavBadge.style.display = config.is_complete ? 'none' : 'inline-flex';
  }

  if (tokenWarningBox) {
    if (config.token_warning) {
      tokenWarningBox.style.display = 'block';
      if (tokenWarningText) tokenWarningText.textContent = config.token_warning;
    } else {
      tokenWarningBox.style.display = 'none';
    }
  }

  if (schemaBadge) {
    if (config.is_complete) {
      schemaBadge.innerHTML = '<span class="auth-pill pill-success"><i class="fa-solid fa-circle-check"></i> Schema Ready & Complete</span>';
    } else {
      schemaBadge.innerHTML = '<span class="auth-pill pill-danger"><i class="fa-solid fa-triangle-exclamation"></i> Schema Incomplete</span>';
    }
  }
}

function renderAuthTables(tables) {
  const container = document.getElementById('auth-tables-container');
  if (!container) return;
  if (!tables || Object.keys(tables).length === 0) {
    container.innerHTML = '<div style="color: var(--text-secondary); padding: 1rem;">No table schema information available.</div>';
    return;
  }

  container.innerHTML = '';
  Object.entries(tables).forEach(([tableName, tableData]) => {
    const card = document.createElement('div');
    card.className = `auth-table-card ${tableData.found ? 'valid' : 'invalid'}`;

    const tableIdText = tableData.id ? `ID: ${tableData.id}` : 'Unassigned';
    const statusPillClass = tableData.found ? 'pill-success' : 'pill-danger';
    const statusPillIcon = tableData.found ? 'fa-check' : 'fa-triangle-exclamation';
    const statusPillLabel = tableData.found ? (tableData.all_fields_found ? 'Valid & Linked' : 'Table Linked (Partial Fields)') : 'Table Missing';

    let fieldsHtml = '';
    if (tableData.fields && tableData.fields.length > 0) {
      fieldsHtml = `
        <div style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-secondary); font-weight: 600; margin-top: 0.5rem; margin-bottom: 0.25rem;">Required Fields:</div>
        <div class="auth-fields-grid">
          ${tableData.fields.map(f => `
            <div class="auth-field-badge ${f.found ? 'found' : 'missing'}" title="${f.found ? `Field verified in Baserow (ID: ${f.id || 'N/A'}, Type: ${f.type})` : 'Field not found in table'}">
              <div style="display: flex; align-items: center; gap: 0.35rem; min-width: 0;">
                <i class="fa-solid ${f.found ? 'fa-check' : 'fa-xmark'}" style="color: ${f.found ? '#4ade80' : '#f87171'}; font-size: 0.75rem;"></i>
                <span class="auth-field-name">${f.actual_name || f.name}</span>
                ${f.primary ? '<span style="font-size: 0.65rem; background: var(--bg-tertiary, #374151); color: var(--text-secondary); padding: 1px 4px; border-radius: 3px; margin-left: 2px;">Primary</span>' : ''}
              </div>
              <span class="auth-field-type">${f.id ? `ID ${f.id}` : f.type}</span>
            </div>
          `).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="auth-table-header">
        <div class="auth-table-title">
          <i class="fa-solid ${tableData.found ? 'fa-table' : 'fa-table-cells'}"></i>
          <span>${tableName}</span>
          <span style="font-family: monospace; font-size: 0.75rem; color: var(--text-secondary); font-weight: normal; margin-left: 0.5rem;">(${tableData.env_var})</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <span class="auth-pill pill-neutral">${tableIdText}</span>
          <span class="auth-pill ${statusPillClass}"><i class="fa-solid ${statusPillIcon}"></i> ${statusPillLabel}</span>
        </div>
      </div>
      ${fieldsHtml}
    `;
    container.appendChild(card);
  });
}

async function handleTestAuth() {
  const btnTest = document.getElementById('btn-auth-test');
  if (btnTest) {
    btnTest.disabled = true;
    btnTest.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Testing...';
  }
  try {
    const formData = getAuthFormData();
    const result = await testAuthConfig(formData);
    updateAuthStatusUI(result);
    renderAuthTables(result.tables);

    if (result.is_complete) {
      showToast('Connection and Baserow schema verified successfully!', 'success');
    } else if (result.is_connected && !result.token_valid) {
      showToast(`Connected to server, but API token warning: ${result.token_warning || 'Token invalid'}`, 'warning');
    } else if (!result.is_connected) {
      showToast(`Cannot reach Baserow: ${result.connection_message || 'Connection failed'}`, 'error');
    } else {
      showToast('Connection test finished. Some tables or fields are still missing.', 'warning');
    }
  } catch (err) {
    showToast(`Test failed: ${err.message}`, 'error');
  } finally {
    if (btnTest) {
      btnTest.disabled = false;
      btnTest.innerHTML = '<i class="fa-solid fa-plug"></i> Test Connection';
    }
  }
}

async function handleSaveAuth() {
  const btnSave = document.getElementById('btn-auth-save');
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
  }
  try {
    const formData = getAuthFormData();
    const result = await saveAuthConfig(formData);
    const schema = result.schema || result;
    updateAuthStatusUI(schema);
    renderAuthTables(schema.tables);
    await checkGlobalAuthStatus();

    showToast('Baserow configuration saved to .env & validated successfully!', 'success');
  } catch (err) {
    showToast(`Failed to save authentication settings: ${err.message}`, 'error');
  } finally {
    if (btnSave) {
      btnSave.disabled = false;
      btnSave.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save & Validate';
    }
  }
}

export {
  init,
  loadSettingsData,
  renderProblemsEditor,
  buildRuleUI,
  PROBLEM_FIELD_CONFIGS,
  getFieldConfig,
  renderTemplatesEditor,
  updateTestPreview,
  saveSettingsChanges,
  revertSettings,
  hasUnsavedSettingsChanges,
  currentDefs,
  originalDefs,
  currentTemplates,
  originalTemplates,
  initAuthTab,
  loadAuthConfig,
  renderAuthTables,
  handleTestAuth,
  handleSaveAuth,
  getAuthFormData,
  updateAuthStatusUI
};

