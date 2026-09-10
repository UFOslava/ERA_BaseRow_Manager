import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

insert = '''    const btnChange = document.getElementById('btn-change-child');
    if (btnChange) {
      btnChange.style.display = assemblyLockedChild ? 'none' : 'flex';
    }

    if (assemblyMode === 'create' && assemblyMeasurementUoM) {
       const childConUoM = (childItem["Consumption UoM"] && childItem["Consumption UoM"].length > 0) ? childItem["Consumption UoM"][0].id : '';
       if (childConUoM) {
         assemblyMeasurementUoM.value = childConUoM;
       } else {
         assemblyMeasurementUoM.value = '';
       }
    }'''

content = content.replace('''    const btnChange = document.getElementById('btn-change-child');
    if (btnChange) {
      btnChange.style.display = assemblyLockedChild ? 'none' : 'flex';''', insert)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
