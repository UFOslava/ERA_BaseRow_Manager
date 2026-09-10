import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

vars = '''    const stateVal = inputState ? inputState.value : 'Unknown';
    const mfgVal = inputManufacturer ? inputManufacturer.value : '';
    const purUoMVal = inputPurchaseUoM ? inputPurchaseUoM.value : '';
    const conUoMVal = inputConsumptionUoM ? inputConsumptionUoM.value : '';
    const priceVal = inputPrice ? inputPrice.value.trim() : '';'''

content = content.replace('''    const stateVal = inputState ? inputState.value : 'Unknown';
    const mfgVal = inputManufacturer ? inputManufacturer.value : '';
    const priceVal = inputPrice ? inputPrice.value.trim() : '';''', vars)

cmp = '''           stateVal !== originalData.state ||
           String(mfgVal) !== String(originalData.manufacturerId) ||
           String(purUoMVal) !== String(originalData.purchaseUoM) ||
           String(conUoMVal) !== String(originalData.consumptionUoM) ||
           priceChanged ||'''

content = content.replace('''           stateVal !== originalData.state ||
           String(mfgVal) !== String(originalData.manufacturerId) ||
           priceChanged ||''', cmp)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
