import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

edit_block = '''      if (assemblyQuantity) assemblyQuantity.value = options.quantity !== null && options.quantity !== undefined ? options.quantity : 1;
      if (assemblyMeasurement) assemblyMeasurement.value = options.length !== null && options.length !== undefined ? options.length : 0;
      if (assemblyMeasurementUoM) {
        populateUoMDropdown(assemblyMeasurementUoM);
        assemblyMeasurementUoM.value = options.uom || '';
      }
      if (assemblyPcb) assemblyPcb.value = options.pcb_symbol || '';'''

content = content.replace('''      if (assemblyQuantity) assemblyQuantity.value = options.quantity !== null && options.quantity !== undefined ? options.quantity : 1;
      if (assemblyLength) assemblyLength.value = options.length !== null && options.length !== undefined ? options.length : 0;
      if (assemblyPcb) assemblyPcb.value = options.pcb_symbol || '';''', edit_block)

create_block = '''      if (assemblyQuantity) assemblyQuantity.value = 1;
      if (assemblyMeasurement) assemblyMeasurement.value = 0;
      if (assemblyMeasurementUoM) {
        populateUoMDropdown(assemblyMeasurementUoM);
        assemblyMeasurementUoM.value = '';
      }
      if (assemblyPcb) assemblyPcb.value = '';'''

content = content.replace('''      if (assemblyQuantity) assemblyQuantity.value = 1;
      if (assemblyLength) assemblyLength.value = 0;
      if (assemblyPcb) assemblyPcb.value = '';''', create_block)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
