import sys

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

insert = '''              <div class="form-group">
                <label class="field-label" style="margin-bottom: 0.5rem;">Measurement</label>
                <div style="display: flex; gap: 0.5rem;">
                  <input type="number" id="assembly-measurement" class="form-input" value="0" min="0" step="0.001" style="flex: 1;">
                  <select id="assembly-measurement-uom" class="form-input" style="flex: 1;">
                    <option value="">Default (From Item)</option>
                  </select>
                </div>
              </div>'''

content = content.replace('''              <div class="form-group">
                <label class="field-label" style="margin-bottom: 0.5rem;">Length (mm)</label>
                <input type="number" id="assembly-length" class="form-input" value="0" min="0">
              </div>''', insert)

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
