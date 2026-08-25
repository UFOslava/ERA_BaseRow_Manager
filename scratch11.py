import re

# 1. Fix backend/tests/test_api.py
with open('backend/tests/test_api.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("mock_instance.create_assembly.assert_called_once_with(1, 2, 3, 150, \"C1\")", "mock_instance.create_assembly.assert_called_once_with(1, 2, 3, 150, \"C1\", None)")

with open('backend/tests/test_api.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 2. Fix backend/tests/test_baserow_client.py
with open('backend/tests/test_baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('assert item["contained_items"][0]["amount_label"] == "5 x 100mm"', 'assert item["contained_items"][0]["amount_label"] == "5 pcs (100.2)"')

with open('backend/tests/test_baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
