import os

file_path = "frontend/src/settings.js"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace the first line to include new imports
import_old = "import { fetchRules, saveRules, fetchProblemDefinitions, saveProblemDefinitions, getHealth, fetchProblemDefinitionCount, triggerRescan, fetchScanStatus, fetchLogsConfig, saveLogsConfig, fetchActiveLog, fetchQuickActionTemplates, saveQuickActionTemplates } from './api.js';"
import_new = import_old.replace(" } from './api.js';", ", fetchWiTemplates, uploadWiTemplate, replaceWiTemplate, deleteWiTemplate, fetchWiConfig, saveWiConfig } from './api.js';")
content = content.replace(import_old, import_new)

# Add init logic for WI templates inside init()
init_old = """
  // Load initial data
  await Promise.all([
    loadRules(),
    loadProblemDefinitions(),
    loadQuickActionTemplates(),
    loadLogsConfig(),
    loadActiveLog()
  ]);
"""
init_new = """
  // Load initial data
  await Promise.all([
    loadRules(),
    loadProblemDefinitions(),
    loadQuickActionTemplates(),
    loadLogsConfig(),
    loadActiveLog(),
    loadWiTemplates(),
    loadWiConfig()
  ]);

  // WI Templates setup
  const btnUploadWi = document.getElementById('btn-upload-wi-template');
  if (btnUploadWi) btnUploadWi.addEventListener('click', handleUploadWiTemplate);
  const btnSaveWiConfig = document.getElementById('btn-save-wi-config');
  if (btnSaveWiConfig) btnSaveWiConfig.addEventListener('click', handleSaveWiConfig);
"""
content = content.replace(init_old, init_new)

# Add logic functions
logic = """
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
    
    const isValid = t.Valid;
    const badgeColor = isValid ? 'green' : 'red';
    const badgeText = isValid ? 'Valid' : 'Invalid';
    
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
      <div style="margin-bottom: 10px; font-size: 0.85em; color: #ff4444;">
        <strong>Invalid Tokens:</strong> ${tokensInvalid.map(x => `<span style="background:rgba(255,0,0,0.1); padding: 2px 5px; border-radius:3px; margin: 2px; display:inline-block;">${x}</span>`).join('')}
      </div>` : ''}
      <div style="display: flex; gap: 10px; margin-top: 15px;">
        <label class="btn btn-sm" style="cursor: pointer;">
          Replace File
          <input type="file" style="display:none;" accept=".docx" onchange="window.handleReplaceTemplate(${t.id}, this)">
        </label>
        <button class="btn btn-sm btn-danger" onclick="window.handleDeleteTemplate(${t.id})">Delete</button>
      </div>
    `;
    container.appendChild(card);
  });
}

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
"""

content = content + "\n\n" + logic

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("settings.js patched.")
