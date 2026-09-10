import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("  inputPrice = document.getElementById('input-price') || inputPrice;", "  inputPrice = document.getElementById('input-price') || inputPrice;\n  inputPurchaseUoM = document.getElementById('input-purchase-uom') || inputPurchaseUoM;\n  inputConsumptionUoM = document.getElementById('input-consumption-uom') || inputConsumptionUoM;")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
