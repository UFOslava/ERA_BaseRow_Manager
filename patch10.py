import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

insert = '''function populateUoMDropdown(selectElement) {
  if (!selectElement) return;
  const currentVal = selectElement.value;
  selectElement.innerHTML = '<option value="">None</option>';
  uoms.forEach(uom => {
    const opt = document.createElement('option');
    opt.value = uom.id;
    opt.textContent = ${uom.Name} ();
    selectElement.appendChild(opt);
  });
  if (currentVal) selectElement.value = currentVal;
}

'''
content = content.replace("function populateManufacturersDropdown() {", insert + "function populateManufacturersDropdown() {")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
