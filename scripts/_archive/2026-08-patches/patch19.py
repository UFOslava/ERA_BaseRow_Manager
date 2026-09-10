import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

insert = '''  async function handleConfirmAssembly() {
    if (assemblyMode !== 'edit') {
      if (!assemblySelectedParentId || !assemblySelectedChildId) return;
    }

    const qty = parseInt(assemblyQuantity ? assemblyQuantity.value : 1) || 1;
    const len = parseFloat(assemblyMeasurement ? assemblyMeasurement.value : 0) || 0;
    const uomId = assemblyMeasurementUoM && assemblyMeasurementUoM.value ? parseInt(assemblyMeasurementUoM.value, 10) : null;
    const pcb = assemblyPcb ? assemblyPcb.value.trim() : '';

    try {
      if (btnConfirmAssembly) {
        btnConfirmAssembly.disabled = true;
        btnConfirmAssembly.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
      }

      if (assemblyMode === 'edit') {
        await updateAssembly(assemblyEdgeId, qty, len, pcb, assemblySelectedParentId, assemblySelectedChildId, uomId);
        showToast('Assembly properties saved.');
      } else {
        await createAssembly(assemblySelectedParentId, assemblySelectedChildId, qty, len, pcb, uomId);
        showToast('Assembly updated successfully.');
      }'''

content = content.replace('''async function handleConfirmAssembly() {
    if (assemblyMode !== 'edit') {
      if (!assemblySelectedParentId || !assemblySelectedChildId) return;
    }
  
    const qty = parseInt(assemblyQuantity ? assemblyQuantity.value : 1) || 1;
    const len = parseFloat(assemblyLength ? assemblyLength.value : 0) || 0;
    const pcb = assemblyPcb ? assemblyPcb.value.trim() : '';
  
    try {
      if (btnConfirmAssembly) {
        btnConfirmAssembly.disabled = true;
        btnConfirmAssembly.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
      }
  
      if (assemblyMode === 'edit') {
        await updateAssembly(assemblyEdgeId, qty, len, pcb, assemblySelectedParentId, assemblySelectedChildId);
        showToast('Assembly properties saved.');
      } else {
        await createAssembly(assemblySelectedParentId, assemblySelectedChildId, qty, len, pcb);
        showToast('Assembly updated successfully.');
      }''', insert)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
