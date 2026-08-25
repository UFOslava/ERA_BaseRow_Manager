import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

orig_data_replace = '''      originalData = {
        fullPn: item["Full PN"] || item["Part Number"] || 'N/A',
        description: item["Item description"] || '',
        source: item["Source URL"] || '',
        externalPn: item["External Part Number"] || '',
        state: originalState,
        manufacturerId: (item["Manufacturer"] && item["Manufacturer"].length > 0) ? item["Manufacturer"][0].id : '',
        price: item["Price per unit"] !== null ? parseFloat(item["Price per unit"]) : null,
        purchaseUoM: (item["Purchase UoM"] && item["Purchase UoM"].length > 0) ? item["Purchase UoM"][0].id : '',
        consumptionUoM: (item["Consumption UoM"] && item["Consumption UoM"].length > 0) ? item["Consumption UoM"][0].id : '',
        sourcedBy: item["Sourced By"] ? item["Sourced By"].value : 'TBD','''

content = content.replace('''      originalData = {
        fullPn: item["Full PN"] || item["Part Number"] || 'N/A',
        description: item["Item description"] || '',
        source: item["Source URL"] || '',
        externalPn: item["External Part Number"] || '',
        state: originalState,
        manufacturerId: (item["Manufacturer"] && item["Manufacturer"].length > 0) ? item["Manufacturer"][0].id : '',
        price: item["Price per unit"] !== null ? parseFloat(item["Price per unit"]) : null,
        sourcedBy: item["Sourced By"] ? item["Sourced By"].value : 'TBD',''', orig_data_replace)

set_vals = '''      if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
      if (inputPurchaseUoM) { populateUoMDropdown(inputPurchaseUoM); inputPurchaseUoM.value = originalData.purchaseUoM; }
      if (inputConsumptionUoM) { populateUoMDropdown(inputConsumptionUoM); inputConsumptionUoM.value = originalData.consumptionUoM; }
      if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';'''

content = content.replace('''      if (inputManufacturer) inputManufacturer.value = originalData.manufacturerId;
      if (inputPrice) inputPrice.value = originalData.price !== null ? parseFloat(originalData.price).toFixed(2) : '';''', set_vals)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
