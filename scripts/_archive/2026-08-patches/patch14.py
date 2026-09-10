import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("  if (inputManufacturer) inputManufacturer.addEventListener('change', checkChanges);", "  if (inputManufacturer) inputManufacturer.addEventListener('change', checkChanges);\n  if (inputPurchaseUoM) inputPurchaseUoM.addEventListener('change', checkChanges);\n  if (inputConsumptionUoM) inputConsumptionUoM.addEventListener('change', checkChanges);")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
