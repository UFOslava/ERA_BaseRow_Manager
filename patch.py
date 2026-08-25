import sys

with open('backend/app/baserow_client.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '        self.table_contacts = os.getenv("BASEROW_TABLE_CONTACTS", "684")',
    '        self.table_contacts = os.getenv("BASEROW_TABLE_CONTACTS", "684")\n        self.table_uom = os.getenv("BASEROW_TABLE_UOM", "48540")'
)

content = content.replace(
    '    def _get_all_rows(self, table_id, filters=None):',
    '    def get_uoms(self):\n        return self._get_all_rows(self.table_uom)\n\n    def _get_all_rows(self, table_id, filters=None):'
)

with open('backend/app/baserow_client.py', 'w', encoding='utf-8') as f:
    f.write(content)
