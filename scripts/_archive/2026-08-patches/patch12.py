import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

revert = '''    if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
    if (inputPurchaseUoM) inputPurchaseUoM.value = originalData.purchaseUoM;
    if (inputConsumptionUoM) inputConsumptionUoM.value = originalData.consumptionUoM;
    if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';'''

content = content.replace('''    if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
    if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';''', revert)

save1 = '''      const mfgVal = inputManufacturer && inputManufacturer.value ? [parseInt(inputManufacturer.value, 10)] : [];
      const purUoM = inputPurchaseUoM && inputPurchaseUoM.value ? [parseInt(inputPurchaseUoM.value, 10)] : [];
      const conUoM = inputConsumptionUoM && inputConsumptionUoM.value ? [parseInt(inputConsumptionUoM.value, 10)] : [];
      const priceVal = inputPrice && inputPrice.value.trim() !== '' ? parseFloat(inputPrice.value) : null;'''

content = content.replace('''      const mfgVal = inputManufacturer && inputManufacturer.value ? [parseInt(inputManufacturer.value, 10)] : [];
      const priceVal = inputPrice && inputPrice.value.trim() !== '' ? parseFloat(inputPrice.value) : null;''', save1)

save2 = '''        await updateItem(currentItemId, {
          "Item description": descVal,
          "Source URL": srcVal,
          "External Part Number": extPnVal,
          "State": stateVal,
          "Manufacturer": mfgVal,
          "Purchase UoM": purUoM,
          "Consumption UoM": conUoM,
          "Price per unit": priceVal,'''

content = content.replace('''        await updateItem(currentItemId, {
          "Item description": descVal,
          "Source URL": srcVal,
          "External Part Number": extPnVal,
          "State": stateVal,
          "Manufacturer": mfgVal,
          "Price per unit": priceVal,''', save2)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
