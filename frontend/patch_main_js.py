import os

file_path = "frontend/src/main.js"
with open(file_path, "a", encoding="utf-8") as f:
    f.write("""
// --- WI Export Logic ---
let wiExportParentId = null;
let wiExportSetIndex = null;

async function openWiExportModal(parentId, setIndex) {
  wiExportParentId = parentId;
  wiExportSetIndex = setIndex;
  
  const modal = document.getElementById('wi-export-modal');
  const select = document.getElementById('wi-template-select');
  if (!modal || !select) return;
  
  select.innerHTML = '<option value="">Loading...</option>';
  modal.style.display = 'flex';
  
  try {
    const { fetchWiTemplates } = await import('./api.js');
    const templates = await fetchWiTemplates();
    const validTemplates = templates.filter(t => t.Valid);
    
    if (validTemplates.length === 0) {
      select.innerHTML = '<option value="">No valid templates found</option>';
      document.getElementById('btn-wi-export-confirm').disabled = true;
    } else {
      select.innerHTML = validTemplates.map(t => `<option value="${t.id}">${t.Name}</option>`).join('');
      document.getElementById('btn-wi-export-confirm').disabled = false;
    }
  } catch (err) {
    select.innerHTML = '<option value="">Failed to load templates</option>';
    document.getElementById('btn-wi-export-confirm').disabled = true;
  }
}

document.getElementById('btn-close-wi-export')?.addEventListener('click', () => {
  document.getElementById('wi-export-modal').style.display = 'none';
});

document.getElementById('btn-wi-export-cancel')?.addEventListener('click', () => {
  document.getElementById('wi-export-modal').style.display = 'none';
});

document.getElementById('btn-wi-export-confirm')?.addEventListener('click', async () => {
  const templateId = document.getElementById('wi-template-select').value;
  if (!templateId) return;
  
  const btn = document.getElementById('btn-wi-export-confirm');
  const origText = btn.textContent;
  btn.textContent = 'Exporting...';
  btn.disabled = true;
  
  try {
    const res = await fetch(`${API_BASE_URL}/api/bom/items/${wiExportParentId}/instruction-sets/${wiExportSetIndex}/export-wi`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_id: templateId })
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Export failed');
    }
    
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    const contentDisposition = res.headers.get('Content-Disposition');
    let fileName = 'Export.docx';
    if (contentDisposition && contentDisposition.indexOf('filename=') !== -1) {
        const matches = /filename[^;=\\n]*=((['"]).*?\\2|[^;\\n]*)/.exec(contentDisposition);
        if (matches != null && matches[1]) {
            fileName = matches[1].replace(/['"]/g, '');
        }
    }
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();
    
    document.getElementById('wi-export-modal').style.display = 'none';
    showToast('Export successful!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.textContent = origText;
    btn.disabled = false;
  }
});
""")
print("main.js patched with WI Export Logic.")
