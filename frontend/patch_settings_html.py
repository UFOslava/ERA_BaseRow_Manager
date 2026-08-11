import os

file_path = "frontend/settings.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

tab_menu_patch = """
          <li class="tab-item" data-tab="quick-actions">
            <i class="fa-solid fa-bolt"></i> Quick Actions
          </li>
          <li class="tab-item" data-tab="wi-templates">
            <i class="fa-solid fa-file-word"></i> WI Templates
          </li>"""

tab_content_patch = """
        <div id="tab-wi-templates" class="tab-content" style="display: none;">
          <h2>WI Templates</h2>
          
          <div class="settings-section">
            <h3>Global Export Settings</h3>
            <div class="input-field">
              <label>Filename Pattern</label>
              <div style="display: flex; gap: 10px;">
                <input type="text" id="wi-filename-pattern" value="ERA_{{pn}}_Rev{{revision}}_WI" style="flex: 1;">
                <button id="btn-save-wi-config" class="btn btn-primary">Save Pattern</button>
              </div>
              <small>Available tokens: {{pn}}, {{revision}}, {{date}}</small>
            </div>
          </div>

          <div class="settings-section">
            <h3>Upload New Template</h3>
            <div style="display: flex; gap: 10px; align-items: flex-end;">
              <div class="input-field">
                <label>Template Name</label>
                <input type="text" id="new-wi-template-name" placeholder="E.g., Standard Assembly WI">
              </div>
              <div class="input-field">
                <label>File (.docx)</label>
                <input type="file" id="new-wi-template-file" accept=".docx">
              </div>
              <button id="btn-upload-wi-template" class="btn btn-primary">Upload</button>
            </div>
          </div>

          <div class="settings-section">
            <h3>Existing Templates</h3>
            <div id="wi-templates-list" class="templates-grid">
              <!-- Templates will be injected here -->
            </div>
          </div>

          <div class="settings-section" style="margin-top: 30px;">
            <details>
              <summary style="cursor: pointer; font-weight: bold; color: var(--accent-color);">View Known Tokens Reference</summary>
              <div style="margin-top: 10px; font-family: monospace; font-size: 0.9em; background: var(--bg-tertiary); padding: 15px; border-radius: 4px;">
                <p><strong>Item Info:</strong> {{item_pn}}, {{pn}}, {{revision}}, {{description}}, {{ext_pn}}, {{date}}, {{item_image}}</p>
                <p><strong>Steps Loop:</strong> {% for step in steps %} ... {% endfor %}</p>
                <p><strong>Step Info:</strong> {{step.step_number}}, {{step.main_action}}, {{step.instruction_text}}, {{step.step_image}}</p>
                <p><strong>Parts Loop (inside step):</strong> {% for part in step.parts %} {{part.part_name}} {{part.part_qty}} {% endfor %}</p>
                <p><strong>Tools Loop (inside step):</strong> {% for tool in step.tools %} {{tool.tool_name}} {{tool.tool_qty}} {% endfor %}</p>
                <p><strong>Unique Tools Loop:</strong> {% for tool in unique_tools %} {{tool.tool_name}} {{tool.tool_qty}} {% endfor %}</p>
              </div>
            </details>
          </div>
        </div>
      </div> <!-- End settings-content -->"""

content = content.replace("""
          <li class="tab-item" data-tab="quick-actions">
            <i class="fa-solid fa-bolt"></i> Quick Actions
          </li>""", tab_menu_patch)

content = content.replace("      </div>\n    </div>\n  </div>", tab_content_patch + "\n    </div>\n  </div>")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("settings.html patched.")
