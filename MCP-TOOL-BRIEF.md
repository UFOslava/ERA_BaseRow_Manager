# MCP tool-layer brief — fix tool ergonomics for LLM clients (Gemini Spark)

Work ONLY in this worktree (`/home/ufoslava/era-mcp-work`), branch `mcp-tool-ergonomics`.
Target file: `backend/app/mcp_server.py` (low-level `mcp.server.Server` + `@server.tool()`, NOT FastMCP).
Do not touch other files except `backend/app/client.py` if a needed helper is genuinely absent.

## Observed failure (real, reproduced)

Gemini Spark was asked: *"Traverse the tree of item children down to the furthest assemblies, and list
assemblies that 1) are not a Blackbox and 2) don't have instructions."*

Spark answered with a **wrong** result: it claimed PN `80-00000` has 18 flat children (`20-00001`…
`20-00019`, RowIDs 215–233), all leaves, and that `80-00000` is the only assembly in the tree.

Ground truth from `get_bom_tree("80-00000", max_depth=10)`: the depth-1 children are **assemblies**, e.g.
`55-00003` Nova Logo Light Fixture Assembly, `55-00015` Umbilical Cord Assembly, `55-00008` Nova
Footswitch Sub-Assembly, `55-00013` Nova Populated Chassis with Screen — and those have their own
children (e.g. `55-00013` → `55-00014`, `55-00007` → `50-00015` → `10-00017`). The tree is deep.
Spark's "all leaf, single assembly" conclusion is false.

## Root causes (verified in source — fix these)

1. **Payload too large / no projection.** `get_bom_tree` returns the full nested `json.dumps(subtree,
   indent=2)`. For `80-00000` this exceeds ~20 KB and is truncated by the client, which then hallucinates
   a summary. There is no way to request a compact view.
2. **No per-node instruction/blackbox signal.** Tree nodes carry `part_number`, `description`, `state`,
   `quantity`, `children` — but **not** whether the item has work instructions, and not `blackbox`.
   `wi_export.py` already computes exactly this (`is_blackbox`, `child_has_children`,
   `has_instructions` via `get_instruction_sets_for_item`). Reuse that logic; do not reinvent it.
3. **`child_components_count` is ambiguous and misleading.** `get_item_details` reports
   `child_components_count` = 18 for `80-00000`, a raw child count that does **not** correspond to the
   BOM tree's depth-1 nodes. A model reads "18 children" and then invents 18 part numbers. Either
   rename it or document precisely what it counts.
4. **The owner's actual workflow has no tool.** "Which assemblies are non-blackbox and lack
   instructions" requires the model to fetch a 20 KB tree and iterate. There is no
   operation-oriented query for it.

## What to implement

**A. Add a projection/compact mode to `get_bom_tree`.**
New optional params, backwards compatible (defaults preserve today's behavior):
- `compact: bool = False` — when true, each node returns only
  `part_number`, `name`/`description`, `state`, `quantity`, plus `blackbox`, `has_children`,
  `has_instructions`; children nested as today but without the large per-node metadata
  (`edge_id`, `uom_id`, `search_helper`, `pcb_symbol`, `parent_id`, image/datasheet fields).
- `max_nodes: int = 0` — when > 0, cap total emitted nodes and add
  `"truncated": true, "node_count": <n>` to the result so the model KNOWS it was cut. Never silently
  truncate.

**B. Enrich tree nodes** (in both modes) with:
`blackbox: bool`, `has_children: bool`, `has_instructions: bool`.
Compute `has_instructions` from instruction sets, and reuse the existing logic in `wi_export.py`
(`has_instructions` + `is_blackbox` + `child_has_children`) so semantics stay identical across the app.

**C. Add one operation-oriented tool** for the exact owner workflow:
```
find_assemblies_missing_instructions(part_number_or_id: str = "", max_depth: int = 10) -> str
```
Returns, for the tree under the root, the list of assemblies that are
**non-blackbox** and **have children** but **no work instructions** — each with
`part_number`, `name`, `revision`, `id`, `depth`. Blackbox items are excluded and their subtrees
are NOT traversed (a blackbox hides its internals). Mirrors the owner's stated rule exactly.

**D. Clarify descriptions.** Tighten docstrings so a model cannot confuse:
- state explicitly that `get_bom_tree` returns the assembly hierarchy, and that only nodes with
  `has_children: true` are assemblies;
- state what `child_components_count` counts, and warn it is not the BOM depth-1 count;
- in `find_assemblies_missing_instructions`, restate the blackbox rule.

## Constraints

- Python 3, stdlib + existing deps only. No new dependencies.
- Keep the low-level `Server` + `@server.tool()` style and the existing `str`/`json.dumps` return
  convention. Do not migrate to FastMCP; do not change the transport.
- Backwards compatible: existing callers (`get_bom_tree(pn)`) must behave as before.
- Wrap all tool bodies in the existing try/except pattern; return
  `json.dumps({"error": ...})` on failure, never raise.
- Reuse existing helpers in `mcp_server.py` (`_find_item_by_pn_or_id`, `_extract_name_desc`) and the
  Baserow client. Do not invent API methods — verify each exists before calling it.

## Deliverable

Modified `backend/app/mcp_server.py` implementing A–D. Then report:
`SUCCESS`/`FAILED`, files changed, and any place the existing code could not support your change.
