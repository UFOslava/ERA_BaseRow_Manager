import re

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

insert_str = '''const inputState = document.getElementById('input-state');
const inputManufacturer = document.getElementById('input-manufacturer');
const inputPurchaseUoM = document.getElementById('input-purchase-uom');
const inputConsumptionUoM = document.getElementById('input-consumption-uom');'''

content = content.replace("const inputState = document.getElementById('input-state');\nconst inputManufacturer = document.getElementById('input-manufacturer');", insert_str)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
