import os

file_path = "frontend/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

modal_html = """
  <!-- WI Export Modal -->
  <div id="wi-export-modal" class="modal-overlay" style="display: none;">
    <div class="modal-card" style="max-width: 450px;">
      <div class="modal-header">
        <h2>Export Work Instruction</h2>
        <button id="btn-close-wi-export" class="btn-close">&times;</button>
      </div>
      <div class="modal-body" style="padding: 1.5rem 0;">
        <div class="form-group" style="margin-bottom: 1.25rem;">
          <label class="field-label" style="margin-bottom: 0.5rem;">Select Template</label>
          <select id="wi-template-select" class="form-input">
            <!-- Populated dynamically -->
          </select>
        </div>
      </div>
      <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 1rem; width: 100%;">
        <button id="btn-wi-export-cancel" class="btn btn-secondary">Cancel</button>
        <button id="btn-wi-export-confirm" class="btn btn-primary">Export .docx</button>
      </div>
    </div>
  </div>
"""

# inject before toast container
if "wi-export-modal" not in content:
    content = content.replace('<div id="toast-container"', modal_html + '\n  <div id="toast-container"')
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("index.html patched.")
else:
    print("Modal already exists.")
