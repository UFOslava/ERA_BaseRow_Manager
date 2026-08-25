import sys

with open('frontend/src/main.js', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'const [treeData, rulesData, flatData, statesData] = await Promise.all([\n      fetchBomTree(),\n      fetchRules().catch(err => {\n        console.error("Failed to fetch rules", err);\n        return {};\n      }),\n      fetchFlatItems().catch(err => {\n        console.error("Failed to fetch flat items", err);\n        return [];\n      }),\n      fetchStates().catch(err => {\n        console.error("Failed to fetch states", err);\n        return null;\n      })\n    ]);',
    'const [treeData, rulesData, flatData, statesData, uomsData] = await Promise.all([\n      fetchBomTree(),\n      fetchRules().catch(err => {\n        console.error("Failed to fetch rules", err);\n        return {};\n      }),\n      fetchFlatItems().catch(err => {\n        console.error("Failed to fetch flat items", err);\n        return [];\n      }),\n      fetchStates().catch(err => {\n        console.error("Failed to fetch states", err);\n        return null;\n      }),\n      fetchUoMs().catch(err => {\n        console.error("Failed to fetch UoMs", err);\n        return [];\n      })\n    ]);\n    uoms = uomsData || [];'
)

with open('frontend/src/main.js', 'w', encoding='utf-8') as f:
    f.write(content)
