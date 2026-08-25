import sys

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

insert = '''            <div class="input-field">
              <label for="input-purchase-uom">Purchase UoM</label>
              <select id="input-purchase-uom" class="form-input">
                <option value="">None</option>
              </select>
            </div>
            <div class="input-field">
              <label for="input-consumption-uom">Consumption UoM</label>
              <select id="input-consumption-uom" class="form-input">
                <option value="">None</option>
              </select>
            </div>
'''
content = content.replace('            <div class="input-field">\n              <label for="input-price">Price per unit</label>', insert + '            <div class="input-field">\n              <label for="input-price">Price per unit</label>')

with open('frontend/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
