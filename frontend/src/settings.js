import { fetchRules, saveRules, fetchProblemDefinitions, saveProblemDefinitions, getHealth, fetchProblemDefinitionCount, triggerRescan, fetchScanStatus, fetchLogsConfig, saveLogsConfig, fetchActiveLog } from './api.js';

let originalRules = null;
let currentRules = null;
let originalDefs = null;
let currentDefs = null;
let activeSettingsTab = 'categories';
let expandedProblemId = null;
let problemOccurrences = {};
let occurrencesPollingInterval = null;
let isPolling = false;

const btnSettingsBack = document.getElementById('btn-settings-back');
const btnSettingsRevert = document.getElementById('btn-settings-revert');
const btnSettingsSave = document.getElementById('btn-settings-save');
const rulesEditorContainer = document.getElementById('rules-editor-container');
const problemsEditorContainer = document.getElementById('problems-editor-container');
const btnAddRule = document.getElementById('btn-add-rule');
const btnAddProblem = document.getElementById('btn-add-problem');
const btnRescanBom = document.getElementById('btn-rescan-bom');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

async function init() {
  checkBackendHealth();
  
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
    });
  });

  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedSettingsChanges()) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    }
  });

  initLogsTab();
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
    
    originalRules = rules;
    currentRules = Object.keys(rules).map(k => ({ prefix: k, name: rules[k].name, color: rules[k].color }));
    
    originalDefs = defs;
    currentDefs = JSON.parse(JSON.stringify(defs));
    
    renderRulesEditor();
    renderProblemsEditor();
    checkSettingsChanges();
    
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

function buildRuleUI(node, parentGroup = null, onUpdate) {
  if (node.type === "AND" || node.type === "OR") {
    const groupEl = document.createElement('div');
    groupEl.className = 'rule-group';
    
    const headerEl = document.createElement('div');
    headerEl.className = 'rule-group-header';
    
    const selectType = document.createElement('select');
    selectType.className = 'form-input rule-group-select';
    selectType.innerHTML = `
      <option value="AND">ALL OF THESE (AND)</option>
      <option value="OR">ANY OF THESE (OR)</option>
    `;
    selectType.value = node.type;
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
        conditionsContainer.appendChild(buildRuleUI(subNode, node, onUpdate));
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
    
    const fieldSelect = document.createElement('select');
    fieldSelect.className = 'form-input cond-field-select';
    fieldSelect.innerHTML = `
      <option value="Part Number">Part Number</option>
      <option value="Item description">Item description</option>
      <option value="State">State</option>
      <option value="Source URL">Source Link</option>
      <option value="Sourced By">Sourced By</option>
      <option value="is_in_assembly">Is Contained in Assembly</option>
    `;
    fieldSelect.value = node.field || 'Part Number';
    fieldSelect.addEventListener('change', (e) => {
      node.field = e.target.value;
      onUpdate();
    });
    
    const opSelect = document.createElement('select');
    opSelect.className = 'form-input cond-operator-select';
    opSelect.innerHTML = `
      <option value="equals">Equals</option>
      <option value="not_equals">Does Not Equal</option>
      <option value="contains">Contains</option>
      <option value="not_contains">Does Not Contain</option>
      <option value="is_empty">Is Empty</option>
      <option value="is_not_empty">Is Not Empty</option>
    `;
    opSelect.value = node.operator || 'equals';
    opSelect.addEventListener('change', (e) => {
      node.operator = e.target.value;
      onUpdate();
    });
    
    const valInput = document.createElement('input');
    valInput.type = 'text';
    valInput.className = 'form-input cond-value-input';
    valInput.value = node.value || '';
    valInput.placeholder = 'Value...';
    valInput.addEventListener('input', (e) => {
      node.value = e.target.value;
      onUpdate();
    });
    
    if (node.operator === 'is_empty' || node.operator === 'is_not_empty') {
      valInput.disabled = true;
      valInput.value = '';
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
    
    condEl.appendChild(fieldSelect);
    condEl.appendChild(opSelect);
    condEl.appendChild(valInput);
    condEl.appendChild(delCondBtn);
    
    return condEl;
  }
}

function renderProblemsEditor() {
  if (!problemsEditorContainer) return;
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
      });
      card.appendChild(ruleUI);
    }
    
    problemsEditorContainer.appendChild(card);
  });
}

function hasUnsavedSettingsChanges() {
  if (!originalRules || !currentRules || !originalDefs || !currentDefs) return false;
  
  const dictRules = {};
  currentRules.forEach(r => {
    if (r.prefix.trim()) {
      dictRules[r.prefix.trim()] = { name: r.name, color: r.color };
    }
  });
  
  const rulesChanged = JSON.stringify(originalRules) !== JSON.stringify(dictRules);
  const defsChanged = JSON.stringify(originalDefs) !== JSON.stringify(currentDefs);
  
  return rulesChanged || defsChanged;
}

function checkSettingsChanges() {
  const changed = hasUnsavedSettingsChanges();
  if (btnSettingsSave) btnSettingsSave.disabled = !changed;
  if (btnSettingsRevert) btnSettingsRevert.disabled = !changed;
}

function revertSettings() {
  if (!originalRules || !originalDefs) return;
  
  currentRules = Object.keys(originalRules).map(k => ({ prefix: k, name: originalRules[k].name, color: originalRules[k].color }));
  currentDefs = JSON.parse(JSON.stringify(originalDefs));
  
  expandedProblemId = null;
  renderRulesEditor();
  renderProblemsEditor();
  checkSettingsChanges();
  showToast('Settings reverted to saved state', 'success');
}

async function saveSettingsChanges() {
  if (!currentRules || !currentDefs) return;
  
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
  
  const dictRules = {};
  currentRules.forEach(r => {
    dictRules[r.prefix.trim()] = { name: r.name, color: r.color };
  });
  
  try {
    if (btnSettingsSave) btnSettingsSave.disabled = true;
    
    await saveRules(dictRules);
    await saveProblemDefinitions(currentDefs);
    
    originalRules = dictRules;
    originalDefs = JSON.parse(JSON.stringify(currentDefs));
    
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

function showToast(message, type = 'success') {
  const toastContainer = document.getElementById('toast-container');
  if (!toastContainer) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : '✗'}</span>
    <span>${message}</span>
  `;
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 4000);
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

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
