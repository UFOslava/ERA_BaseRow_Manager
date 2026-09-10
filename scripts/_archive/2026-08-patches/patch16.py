import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("  assemblyLength = document.getElementById('assembly-length') || assemblyLength;", "  assemblyMeasurement = document.getElementById('assembly-measurement') || assemblyMeasurement;\n  assemblyMeasurementUoM = document.getElementById('assembly-measurement-uom') || assemblyMeasurementUoM;")
content = content.replace("let assemblyLength;", "let assemblyMeasurement;\nlet assemblyMeasurementUoM;")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
