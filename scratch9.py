import re

# 1. Fix backend/tests/test_api.py
with open('backend/tests/test_api.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("mock_instance.create_assembly.assert_called_once_with(10, 11, 2, 0, \"\")", "mock_instance.create_assembly.assert_called_once_with(10, 11, 2, 0, \"\", None)")
content = content.replace("mock_instance.update_assembly.assert_called_once_with(10, 5, 200, \"C2\", 1, 2)", "mock_instance.update_assembly.assert_called_once_with(10, 5, 200, \"C2\", 1, 2, None)")

with open('backend/tests/test_api.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Fix backend/tests/test_baserow_client.py
with open('backend/tests/test_baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"Length (mm)":', '"Measurement":')

with open('backend/tests/test_baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 3. Fix backend/tests/test_graph_endpoints.py
with open('backend/tests/test_graph_endpoints.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"Length (mm)":', '"Measurement":')

with open('backend/tests/test_graph_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(content)
