import { fetchRules, saveRules, fetchProblemDefinitions, saveProblemDefinitions, getHealth } from './api.js';

let originalRules = null;
let currentRules = null;
let originalDefs = null;
let currentDefs = null;
let activeSettingsTab = 'categories';

const btnSettingsBack = document.getElementById('btn-settings-back');
const btnSettingsRevert = document.getElementById('btn-settings-revert');
const btnSettingsSave = document.getElementById('btn-settings-save');
const rulesEditorContainer = document.getElementById('rules-editor-container');
const problemsEditorContainer = document.getElementById('problems-editor-container');
const btnAddRule = document.getElementById('btn-add-rule');
const btnAddProblem = document.getElementById('btn-add-problem');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

async function init() {
  checkBackendHealth();
  
  if (btnSettingsBack) {
    btnSettingsBack.addEventListener('click', () => {
      if (hasUnsavedSettingsChanges()) {
        if (!confirm("You have unsaved settings. Discard them and return to BOM explorer?")) {
          return;
        }
      }
      window.location.href = '/';
    });
  }
  if (btnSettingsRevert) btnSettingsRevert.addEventListener('click', revertSettings);
  if (btnSettingsSave) btnSettingsSave.addEventListener('click', saveSettingsChanges);
  
  if (btnAddRule) btnAddRule.addEventListener('click', addNewRuleRow);
  if (btnAddProblem) btnAddProblem.addEventListener('click', addNewProblemRow);
  
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
    });
  });

  window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedSettingsChanges()) {
      e.preventDefault();
      e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      return e.returnValue;
    }
  });

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
  } catch (err) {
    showToast(`Error loading settings: ${err.message}`, 'error');
  }
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
    
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'form-input';
    nameInput.value = rule.name;
    nameInput.placeholder = 'Category Name...';
    nameInput.addEventListener('input', (e) => {
      rule.name = e.target.value;
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
      checkSettingsChanges();
    });
    colorText.addEventListener('input', (e) => {
      picker.value = e.target.value;
      rule.color = e.target.value;
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
      <option value="Source">Source Link</option>
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
    const card = document.createElement('div');
    card.className = 'problem-def-card';
    
    const header = document.createElement('div');
    header.className = 'problem-def-header';
    
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'form-input problem-name-input';
    nameInput.value = definition.name;
    nameInput.placeholder = 'Define problem error message...';
    nameInput.addEventListener('input', (e) => {
      definition.name = e.target.value;
      checkSettingsChanges();
    });
    
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-secondary btn-delete-problem';
    delBtn.innerHTML = '<i class="fa-solid fa-trash"></i> Delete Definition';
    delBtn.addEventListener('click', () => {
      currentDefs.splice(idx, 1);
      renderProblemsEditor();
      checkSettingsChanges();
    });
    
    header.appendChild(nameInput);
    header.appendChild(delBtn);
    card.appendChild(header);
    
    const ruleUI = buildRuleUI(definition.rule, null, () => {
      renderProblemsEditor();
      checkSettingsChanges();
    });
    card.appendChild(ruleUI);
    
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

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', init);
}
