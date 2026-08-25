import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("let inputPrice;", "let inputPrice;\nlet inputPurchaseUoM;\nlet inputConsumptionUoM;")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
