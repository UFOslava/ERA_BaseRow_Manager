import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("fetchStates, fetchWiTemplates", "fetchStates, fetchWiTemplates, fetchUoMs")

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
