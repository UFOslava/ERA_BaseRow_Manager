"""
mcp_server.py
Model Context Protocol (MCP) Server for ERA BaseRow ERP.

Provides tools, resources, and prompt templates for interacting with:
- Item & Catalog Management (Search, inspect, create, update, lifecycle states, categories)
- Multi-tier BOM Hierarchies & Where-Used (Traverse BOM trees, assembly parents)
- Automated BOM Equilibrium & Balance Audit (Math check between BOM quantities & WI step tolling)
- Dynamic Work Instructions & Step Management (Author and inspect steps, photos, tolling)
- Quality & Problem Rule Diagnostics (Missing datasheets, missing images, broken refs)
- Inventory Stock & Requirements Analysis (Flat/nested parts requirement calculations)
"""

import os
import json
import logging
import asyncio
import threading
from typing import Optional, Dict, Any, List, Union, Set
from collections import defaultdict
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.baserow_client import (
    BaserowClient,
    evaluate_condition,
    parse_toll_map,
    _extract_lifecycle_state,
    _lifecycle_state_rank
)

logger = logging.getLogger(__name__)


import jwt
from mcp.server.auth.provider import TokenVerifier, AccessToken
from mcp.server.auth.settings import AuthSettings

class MCPAuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for ERA MCP Server.
    Enforces Bearer token, X-API-Key, or URL query token authentication when MCP_AUTH_TOKEN is configured.
    """
    def __init__(self, app, token: Optional[str] = None, resource_metadata_url: Optional[str] = None):
        super().__init__(app)
        self.token = token.strip() if token else ""
        self.resource_metadata_url = resource_metadata_url

    async def dispatch(self, request, call_next):
        # 1. Exempt public paths
        if request.url.path.startswith("/.well-known/") or request.url.path in ("/health", "/"):
            return await call_next(request)

        # We will extract any credential (X-API-Key, ?token, or Bearer)
        provided_token = None

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header.split(" ", 1)[1].strip()
        
        if not provided_token:
            api_key = request.headers.get("X-API-Key")
            if api_key:
                provided_token = api_key.strip()
                
        if not provided_token:
            query_token = request.query_params.get("token") or request.query_params.get("api_key")
            if query_token:
                provided_token = query_token.strip()

        # If a static token is configured but no token was provided, reject immediately.
        # This restores the 401 behavior for missing tokens when OAuth is not fully configured.
        if self.token and not provided_token:
            challenge = f'Bearer resource_metadata="{self.resource_metadata_url}"' if self.resource_metadata_url else 'Bearer'
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"error": "Unauthorized: Invalid or missing MCP authentication token"},
                status_code=401,
                headers={"WWW-Authenticate": challenge}
            )

        # If a static token is configured and no OAuth resource metadata URL is present,
        # reject invalid static tokens immediately.
        if self.token and not self.resource_metadata_url and provided_token != self.token:
            from starlette.responses import JSONResponse
            return JSONResponse(
                {"error": "Unauthorized: Invalid or missing MCP authentication token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )
                
        if provided_token and not auth_header:
            headers = dict(request.scope["headers"])
            headers[b"authorization"] = f"Bearer {provided_token}".encode()
            request.scope["headers"] = [(k, v) for k, v in headers.items()]
            
        response = await call_next(request)
        
        # If response is 401, ensure we have the correct WWW-Authenticate header
        if response.status_code == 401:
            if self.resource_metadata_url:
                challenge = f'Bearer resource_metadata="{self.resource_metadata_url}"'
                # If there's already a WWW-Authenticate header, we don't strictly need to overwrite it unless it's missing the resource_metadata
                if "WWW-Authenticate" not in response.headers or "resource_metadata" not in response.headers["WWW-Authenticate"]:
                    response.headers["WWW-Authenticate"] = challenge
            elif "WWW-Authenticate" not in response.headers:
                response.headers["WWW-Authenticate"] = 'Bearer'
                
        return response

class ERATokenVerifier(TokenVerifier):
    def __init__(self, static_token: str, jwks_url: str, resource_url: str):
        self.static_token = static_token
        self.jwks_url = jwks_url
        self.resource_url = resource_url
        self.jwks_client = jwt.PyJWKClient(jwks_url) if jwks_url else None

    async def verify_token(self, token: str) -> Optional[AccessToken]:
        if self.static_token and token == self.static_token:
            return AccessToken(
                token=token,
                client_id="legacy_client",
                scopes=[],
                resource=self.resource_url
            )
            
        if self.jwks_client:
            try:
                signing_key = self.jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    audience=self.resource_url,
                    options={"verify_exp": True, "verify_iss": False, "verify_aud": True}
                )
                return AccessToken(
                    token=token,
                    client_id=payload.get("sub", ""),
                    scopes=payload.get("scope", "").split(" "),
                    resource=self.resource_url,
                    expires_at=int(payload["exp"]) if payload.get("exp") is not None else None,
                    subject=payload.get("sub")
                )
            except Exception as e:
                logger.debug(f"JWT verification failed: {e}")
                
        return None





def _find_item_by_pn_or_id(client: BaserowClient, identifier: str) -> Optional[Dict[str, Any]]:
    """
    Helper to locate an item row by numeric ID, exact Full PN, or Part Number.
    Exact Full PN or numeric ID is unambiguous. When a bare Part Number matches multiple
    revisions, the most current revision by lifecycle state is selected, and an
    '_ambiguous_matches' annotation containing matching Full PNs is added to the result.
    """
    if not identifier:
        return None
    
    clean_id = str(identifier).strip()
    
    # Try by numeric ID first if numeric
    if clean_id.isdigit():
        try:
            item = client.get_item(int(clean_id))
            if item and not item.get("error"):
                return item
        except Exception:
            pass
            
    # Search all items by Full PN (exact match wins), Part Number, or Name
    try:
        items = None
        if hasattr(client, "get_items"):
            res = client.get_items()
            if isinstance(res, list):
                items = res
        if items is None and hasattr(client, "_get_all_rows") and hasattr(client, "table_bom"):
            res = client._get_all_rows(client.table_bom)
            if isinstance(res, list):
                items = res
        if not items:
            items = []
        clean_lower = clean_id.lower()

        # 1. Exact Full PN match must win over any bare-Part-Number match
        full_pn_matches = []
        for it in items:
            full_pn = str(it.get("Full PN", "")).strip().lower()
            if clean_lower == full_pn:
                full_pn_matches.append(it)
        if full_pn_matches:
            if len(full_pn_matches) == 1:
                return full_pn_matches[0]
            return min(full_pn_matches, key=lambda it: _lifecycle_state_rank(_extract_lifecycle_state(it)))

        # 2. Exact bare Part Number match
        pn_matches = []
        for it in items:
            pn = str(it.get("Part Number", "")).strip().lower()
            if clean_lower == pn:
                pn_matches.append(it)
        if pn_matches:
            if len(pn_matches) == 1:
                return pn_matches[0]
            best_item = min(pn_matches, key=lambda it: _lifecycle_state_rank(_extract_lifecycle_state(it)))
            ambiguous_pns = [m.get("Full PN") or f"{m.get('Part Number')} (id {m.get('id')})" for m in pn_matches]
            best_item["_ambiguous_matches"] = ambiguous_pns
            logger.info(
                f"Part Number '{clean_id}' matched multiple revisions: {ambiguous_pns}. "
                f"Selected '{best_item.get('Full PN') or best_item.get('Part Number')}' (state: '{_extract_lifecycle_state(best_item)}')."
            )
            return best_item

        # 3. No fuzzy fallback. An identifier must match a numeric ID, an exact Full PN,
        #    or an exact bare Part Number. A substring/name fallback would silently
        #    resolve a truncated or misspelled identifier to an unrelated item -- e.g.
        #    '55-0002' matching '55-00020' -- which is dangerous because this resolver
        #    also backs the write path (create_or_update_wi_step, update_item,
        #    deactivate/state changes). Callers that want name/category search must use
        #    search_items instead.
        logger.info(
            f"Item identifier '{clean_id}' matched no exact Part Number, Full PN, or row ID."
        )
    except Exception as e:
        logger.error(f"Error finding item '{identifier}': {e}")

    return None


def _extract_name_desc(item: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract name and description respecting Baserow field conventions."""
    name = item.get("Name") or item.get("Item description")
    desc = item.get("Description") or item.get("Item description")
    return name, desc


def _get_tree_enrichment_context(client: Any) -> tuple[Dict[int, Dict[str, Any]], Set[int]]:
    """
    Load BOM items map and the set of item IDs that have instruction sets.
    Reuses the exact logic from wi_export.py (table_bom + table_instructions).
    """
    bom_map: Dict[int, Dict[str, Any]] = {}
    items_with_instructions: Set[int] = set()

    # 1. Load BOM rows
    if hasattr(client, "table_bom") and hasattr(client, "_get_all_rows"):
        try:
            bom_rows = client._get_all_rows(client.table_bom)
            if isinstance(bom_rows, list):
                for r in bom_rows:
                    if isinstance(r, dict) and "id" in r:
                        bom_map[r["id"]] = r
        except Exception as e:
            logger.debug(f"Could not load table_bom rows: {e}")

    if not bom_map and hasattr(client, "get_items"):
        try:
            items = client.get_items()
            if isinstance(items, list):
                for r in items:
                    if isinstance(r, dict) and "id" in r:
                        bom_map[r["id"]] = r
        except Exception as e:
            logger.debug(f"Could not load items via get_items: {e}")

    # 2. Load Instruction rows
    if hasattr(client, "table_instructions") and hasattr(client, "_get_all_rows"):
        try:
            instruction_rows = client._get_all_rows(client.table_instructions)
            if isinstance(instruction_rows, list):
                for row in instruction_rows:
                    p_link = row.get("Parent Item")
                    if p_link:
                        if isinstance(p_link, list) and len(p_link) > 0:
                            first = p_link[0]
                            pid = first.get("id") if isinstance(first, dict) else first
                        elif isinstance(p_link, dict):
                            pid = p_link.get("id")
                        else:
                            pid = p_link
                        if pid is not None:
                            try:
                                items_with_instructions.add(int(pid))
                            except (ValueError, TypeError):
                                pass
        except Exception as e:
            logger.debug(f"Could not load instruction rows: {e}")

    return bom_map, items_with_instructions


def _check_is_blackbox(node: Dict[str, Any], bom_map: Dict[int, Dict[str, Any]]) -> bool:
    """Determine whether a node represents a blackbox item."""
    for key in ("blackbox", "Blackbox"):
        if key in node:
            val = node[key]
            return bool(val) if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes")

    node_id = node.get("id")
    if node_id is not None and node_id in bom_map:
        val = bom_map[node_id].get("Blackbox", False)
        return bool(val) if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes")

    return False


def _check_is_purchase_kit(node: Dict[str, Any], bom_map: Dict[int, Dict[str, Any]]) -> bool:
    """Determine whether a node represents a purchase kit item."""
    for key in ("purchase_kit", "Purchase Kit"):
        if key in node:
            val = node[key]
            return bool(val) if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes")

    node_id = node.get("id")
    if node_id is not None and node_id in bom_map:
        val = bom_map[node_id].get("Purchase Kit", bom_map[node_id].get("purchase_kit", False))
        return bool(val) if isinstance(val, bool) else str(val).strip().lower() in ("true", "1", "yes")

    return False


def _check_has_instructions(
    client: Any,
    item_id: Optional[int],
    items_with_instructions: Set[int],
    cache: Dict[int, bool]
) -> bool:
    """Determine whether an item has work instructions."""
    if item_id is None:
        return False
    if item_id in items_with_instructions:
        return True
    if item_id in cache:
        return cache[item_id]

    if not items_with_instructions and hasattr(client, "get_instruction_sets_for_item"):
        try:
            sets = client.get_instruction_sets_for_item(item_id)
            has_inst = bool(sets) and len(sets) > 0
            cache[item_id] = has_inst
            return has_inst
        except Exception:
            pass

    return False


def _extract_relation_id(link_val: Any) -> Optional[int]:
    """Safely extracts a row ID from a Baserow link-to-table field value."""
    if isinstance(link_val, list) and link_val:
        first = link_val[0]
        if isinstance(first, dict):
            return first.get("id")
        try:
            return int(first)
        except (ValueError, TypeError):
            return None
    elif isinstance(link_val, dict):
        return link_val.get("id")
    elif link_val is not None:
        try:
            return int(link_val)
        except (ValueError, TypeError):
            return None
    return None


def _resolve_manufacturer(client: Any, mfg_input: Union[str, int]) -> Optional[List[int]]:
    """
    Resolve manufacturer name or ID to a link_row ID list.
    Returns [id] if found, None if unresolved.
    """
    if not mfg_input:
        return None
    mfgs = client.get_manufacturers() if hasattr(client, "get_manufacturers") else []
    str_val = str(mfg_input).strip()
    try:
        int_id = int(str_val)
        for m in mfgs:
            if m.get("id") == int_id:
                return [int_id]
    except ValueError:
        pass

    lower_val = str_val.lower()
    for m in mfgs:
        m_name = str(m.get("Name", "")).strip()
        if m_name.lower() == lower_val:
            return [m["id"]]
    return None


# Default node budgets for get_bom_tree when the caller passes no max_nodes.
# A single SSE event above ~1 MiB aborts conforming clients, so the tree must be
# bounded; callers can raise max_nodes for a compact payload.
_DEFAULT_MAX_NODES_FULL = 400
_DEFAULT_MAX_NODES_COMPACT = 2000

# Baserow's maximum rows per page. Used as the candidate-pool size when a
# search also applies a category/lifecycle filter that is evaluated locally.
_SEARCH_CANDIDATE_CAP = 200


class _DefaultQuantity(float):
    """Sentinel float subclass to distinguish default quantity 1.0 from an explicitly provided quantity."""
    pass


_DEFAULT_QUANTITY = _DefaultQuantity(1.0)


class NodeCounter:
    """Tracks node count and truncation state during BOM tree projection."""
    def __init__(self, max_nodes: int):
        self.max_nodes = max_nodes
        self.count = 0
        self.truncated = False

    def can_add(self) -> bool:
        if self.max_nodes <= 0:
            return True
        if self.count < self.max_nodes:
            return True
        self.truncated = True
        return False

    def add(self):
        self.count += 1


def _enrich_and_project_node(
    client: Any,
    node: Dict[str, Any],
    depth: int,
    max_depth: int,
    compact: bool,
    counter: NodeCounter,
    bom_map: Dict[int, Dict[str, Any]],
    items_with_instructions: Set[int],
    inst_cache: Dict[int, bool],
    visited: Set[int]
) -> Optional[Dict[str, Any]]:
    if not counter.can_add():
        return None

    counter.add()
    node_id = node.get("id")

    is_bb = _check_is_blackbox(node, bom_map)
    is_pk = _check_is_purchase_kit(node, bom_map)
    raw_children = node.get("children", [])
    has_children = bool(raw_children) and isinstance(raw_children, list) and len(raw_children) > 0
    has_inst = _check_has_instructions(client, node_id, items_with_instructions, inst_cache)

    processed_children = []
    if depth < max_depth and has_children:
        curr_visited = visited | {node_id} if node_id is not None else visited
        for child in raw_children:
            child_id = child.get("id")
            if child_id is not None and child_id in visited:
                continue
            if counter.can_add():
                child_proj = _enrich_and_project_node(
                    client,
                    child,
                    depth + 1,
                    max_depth,
                    compact,
                    counter,
                    bom_map,
                    items_with_instructions,
                    inst_cache,
                    curr_visited
                )
                if child_proj is not None:
                    processed_children.append(child_proj)
            else:
                counter.truncated = True
                break
    elif has_children and depth >= max_depth and counter.max_nodes > 0:
        counter.truncated = True

    if compact:
        name = node.get("name")
        desc = node.get("description")
        if (not name or not desc) and node_id in bom_map:
            m_name, m_desc = _extract_name_desc(bom_map[node_id])
            name = name or m_name
            desc = desc or m_desc
        name = name or desc or ""
        desc = desc or name or ""

        state = node.get("state")
        if not state and node_id in bom_map:
            state = _extract_lifecycle_state(bom_map[node_id])
        if not state:
            state = "Unknown"

        qty = node.get("quantity")
        if qty is None:
            qty = 1

        proj = {
            "id": node_id,
            "part_number": node.get("part_number") or (bom_map.get(node_id, {}).get("Part Number", "") if node_id else ""),
            "name": name,
            "description": desc,
            "state": state,
            "quantity": qty,
            "blackbox": is_bb,
            "purchase_kit": is_pk,
            "has_children": has_children,
            "has_instructions": has_inst,
            "children": processed_children
        }
        return proj
    else:
        proj = dict(node)
        if "problems_count" in proj:
            proj["problems_count"] = None
        proj["blackbox"] = is_bb
        proj["purchase_kit"] = is_pk
        proj["has_children"] = has_children
        proj["has_instructions"] = has_inst
        proj["children"] = processed_children
        return proj



def create_mcp_server(client: Optional[BaserowClient] = None) -> MCPServer:
    """
    Creates and configures the ERA ERP MCPServer with all tools, resources, and prompts.
    """
    if client is None:
        client = BaserowClient()

    server = MCPServer(
        name="ERA-ERP-MCP",
        instructions=(
            "ERA BaseRow ERP MCP Server. Interact with manufacturing Bills of Materials, the part "
            "catalog, Work Instructions (WIs), tolling quantities, BOM equilibrium balance, and "
            "inventory requirements.\n"
            "Conventions:\n"
            "- Part numbers look like '<2-digit category prefix>-<5 digits>' (e.g. '40-00000'); "
            "prefixes run 10..99 (10 Raw Material, 20 Mechanical COTS, 30 Mechanical Custom, "
            "40 Electrical COTS, 50 Electrical Custom, 55 Assemblies & Kits, 60 Software, "
            "70 Packaging & Labeling, 80 Products, 90 Tooling & Fixtures, 99 Prototype).\n"
            "- Tools that take 'part_number_or_id' accept a Part Number, a Full PN with revision "
            "(e.g. '40-00000 Rev.A'), or the numeric row ID. The same Part Number can exist on "
            "several rows at different revisions: these are distinct items, so prefer the ID or "
            "Full PN when revisions matter.\n"
            "- An item's 'Category' is a read-only formula derived from the Part Number prefix; it "
            "cannot be set directly. Its 'State' is a link to the lifecycle-state table.\n"
            "- On success a tool returns JSON. On failure it returns {\"error\": \"...\"} and never "
            "raises. Check for the 'error' key before using a result."
        )
    )

    # =========================================================================
    # TOOLS - ITEM & CATALOG MANAGEMENT
    # =========================================================================

    @server.tool()
    def search_items(query: str = "", category: str = "", lifecycle_state: str = "", limit: int = 50) -> str:
        """
        Search for items/parts in the ERA ERP database by query string, category name, or lifecycle state.

        Args:
            query: Keyword for a full-text search across the item text fields (Part Number, Item description, External Part Number, Notes). A query shorter than 3 characters uses a local substring match on Part Number / name / description instead.
            category: Optional category filter matching as a case-insensitive substring of the category name (e.g. 'Electrical COTS', 'Mechanical COTS', 'Assemblies & Kits').
            lifecycle_state: Optional lifecycle state filter matching as a case-insensitive substring (e.g. 'Production Use', 'Engineerig Use').
            limit: Maximum number of items to return (default 50).
        """
        try:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                limit = 50
            if limit <= 0:
                return json.dumps({"count": 0, "items": []}, indent=2)

            if query and len(query) >= 3:
                # When a category/lifecycle filter is also applied, scan the full candidate
                # page (Baserow's 200-row page cap) before filtering, otherwise a small
                # `limit` starves matches that fall outside the first `limit` rows and the
                # tool silently under-reports (e.g. limit=5 returned 3 of 24 real matches).
                fetch_limit = _SEARCH_CANDIDATE_CAP if (category or lifecycle_state) else limit
                items = client.search_items(query, limit=fetch_limit)
            else:
                items = client.get_items()

            results = []
            for it in items:
                # Category filter
                cat_val = it.get("Category")
                cat_name = cat_val.get("value", "") if isinstance(cat_val, dict) else str(cat_val or "")
                if category and category.lower() not in cat_name.lower():
                    continue

                # Lifecycle state filter
                state_name = _extract_lifecycle_state(it)
                if lifecycle_state and lifecycle_state.lower() not in state_name.lower():
                    continue

                # Text filter if short query
                name, desc = _extract_name_desc(it)
                if query and len(query) < 3:
                    text_blob = f"{it.get('Part Number', '')} {name or ''} {desc or ''}".lower()
                    if query.lower() not in text_blob:
                        continue

                results.append({
                    "id": it.get("id"),
                    "part_number": it.get("Part Number"),
                    "revision": it.get("Revision"),
                    "full_pn": it.get("Full PN"),
                    "name": name,
                    "description": desc,
                    "category": cat_name,
                    "lifecycle_state": state_name,
                    "blackbox": it.get("Blackbox", False),
                    "purchase_kit": bool(it.get("Purchase Kit", False) or it.get("purchase_kit", False)),
                    "price_per_unit": it.get("Price per unit") or it.get("Price"),
                    "external_pn": it.get("External PN") or it.get("External Part Number"),
                    "manufacturer": it.get("Manufacturer")
                })
                if len(results) >= limit:
                    break

            return json.dumps({"count": len(results), "items": results}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to search items: {str(e)}"})

    @server.tool()
    def get_item_details(part_number_or_id: str) -> str:
        """
        Get complete metadata and relationship details for a specific item/part by Part Number (e.g. '40-00000'), Full PN (e.g. '40-00000 Rev.A'), or Baserow Row ID.
        Exact Full PN or numeric ID is unambiguous, while a bare Part Number picks the most current revision (annotating _ambiguous_matches when multiple revisions exist).

        Purchase Kits (`purchase_kit`):
        Includes `purchase_kit: bool` indicating whether this item is a purchase kit. Purchase kits are
        ordered as a single purchased unit rather than ordering their sub-components individually. When a kit
        is received into inventory, its children increment as untracked stock at their assembly quantities.
        Consequently, children of a purchase kit legitimately have no unit price (not a data gap).

        Important note on `child_components_count`:
        `child_components_count` reports the raw count of direct assembly graph edges (all immediate child
        relationship rows in the database assembly table). It is NOT the BOM tree depth-1 count and does NOT
        reflect whether those children are subassemblies or terminal components. An item with 18 child edges
        may actually be composed of complex multi-tier subassemblies that contain further children. Do NOT
        assume `child_components_count` is a list of flat leaf parts. To inspect the true hierarchical
        assembly tree, always use `get_bom_tree`.

        Args:
            part_number_or_id: The Part Number (e.g. '40-00000'), Full PN ('40-00000 Rev.A'), or numeric row ID of the item. Exact Full PN / numeric ID is unambiguous; a bare Part Number picks the most current revision.
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found in BOM catalog."})
            
            # Enrich with where-used summary & WI summary
            item_id = item.get("id")
            parents = client.get_graph_parents(item_id) if hasattr(client, "get_graph_parents") else []
            children = client.get_graph_children(item_id) if hasattr(client, "get_graph_children") else []
            
            name, desc = _extract_name_desc(item)
            cat_val = item.get("Category")
            cat_name = cat_val.get("value", "") if isinstance(cat_val, dict) else str(cat_val or "")
            summary = {
                "id": item.get("id"),
                "part_number": item.get("Part Number"),
                "revision": item.get("Revision"),
                "full_pn": item.get("Full PN"),
                "name": name,
                "description": desc,
                "category": cat_name,
                "lifecycle_state": _extract_lifecycle_state(item),
                "blackbox": item.get("Blackbox", False),
                "purchase_kit": bool(item.get("Purchase Kit", False) or item.get("purchase_kit", False)),
                "price_per_unit": item.get("Price per unit") or item.get("Price"),
                "lot_size": item.get("Lot Size"),
                "nre_cost": item.get("NRE Cost"),
                "external_pn": item.get("External PN") or item.get("External Part Number"),
                "manufacturer": item.get("Manufacturer"),
                "supplier": item.get("Supplier"),
                "source_url": item.get("Source URL") or item.get("Source Link"),
                "notes": item.get("Notes"),
                "child_components_count": len(children),
                "child_components_description": (
                    "Raw count of direct assembly table edges (immediate child relations). "
                    "Not the BOM tree depth-1 count; use get_bom_tree for hierarchy."
                ),
                "used_in_assemblies_count": len(parents),
                "has_photos": bool(item.get("Image") or item.get("Photos") or item.get("Images")),
                "has_datasheets": bool(item.get("Datasheet") or item.get("Datasheets"))
            }
            return json.dumps(summary, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get item details: {str(e)}"})

    @server.tool()
    def create_item(
        part_number: str,
        name: str,
        category: str = "",
        description: str = "",
        lifecycle_state: str = "Engineering Use",
        price_per_unit: Optional[float] = None,
        external_pn: str = "",
        manufacturer: str = "",
        blackbox: bool = False
    ) -> str:
        """
        Create a new item/component in the ERA ERP catalog.

        Args:
            part_number: Unique part number in '<prefix>-<5 digits>' format (e.g., '40-00000').
            name: Human-readable component name.
            category: Ignored. An item's Category is a read-only formula derived from the Part Number prefix and cannot be set; it is accepted here only for backwards compatibility. Choose the prefix via part_number instead.
            description: Optional technical description.
            lifecycle_state: Initial state, one of the values returned by list_item_lifecycle_states (currently: Production Use, Engineerig Use, Unknown, Finish Stock (Use Up), EOL, Do Not Use (Discard)); defaults to 'Engineering Use'. Unknown values are rejected.
            price_per_unit: Unit price (USD).
            external_pn: Manufacturer or vendor part number.
            manufacturer: Manufacturer name or ID (link_row).
            blackbox: Whether this assembly should be treated as an indivisible blackbox in BOM explosions.
        """
        try:
            item_desc = description.strip() if description else name.strip()
            payload: Dict[str, Any] = {
                "Part Number": part_number.strip(),
                "Item description": item_desc,
                "Blackbox": bool(blackbox)
            }
            if lifecycle_state:
                state_name = lifecycle_state.strip()
                if state_name.lower() == "engineering use":
                    state_name = "Engineerig Use"
                state_id = client.get_state_id(state_name) if hasattr(client, "get_state_id") else []
                states_map = getattr(client, "states_map", {}) or {}
                matched_key = next((k for k in states_map.keys() if k.lower() == state_name.lower()), None)
                if not state_id and not matched_key:
                    return json.dumps({
                        "error": f"Invalid lifecycle_state '{lifecycle_state}'. Must be one of the values returned by list_item_lifecycle_states."
                    })
                payload["State"] = state_id if state_id else (matched_key or state_name)
            if price_per_unit is not None:
                payload["Price per unit"] = float(price_per_unit)
            if external_pn:
                payload["External Part Number"] = external_pn.strip()
            if manufacturer:
                resolved_mfg = _resolve_manufacturer(client, manufacturer)
                if not resolved_mfg:
                    return json.dumps({
                        "error": f"Could not resolve manufacturer '{manufacturer}'. 'Manufacturer' is a link_row field requiring a valid manufacturer name or ID."
                    })
                payload["Manufacturer"] = resolved_mfg

            created = client.create_bom_item(payload)
            return json.dumps({
                "message": f"Successfully created item '{part_number}'",
                "item": created
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to create item: {str(e)}"})

    @server.tool()
    def update_item(
        part_number_or_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        price_per_unit: Optional[float] = None,
        external_pn: Optional[str] = None,
        manufacturer: Optional[str] = None,
        blackbox: Optional[bool] = None,
        notes: Optional[str] = None
    ) -> str:
        """
        Update fields of an existing item in the ERA ERP catalog.
        Exact Full PN or numeric ID is unambiguous, while a bare Part Number picks the most current revision (annotating _ambiguous_matches when multiple revisions exist).

        Args:
            part_number_or_id: Part Number, Full PN, or Row ID of the item to update. Exact Full PN / numeric ID is unambiguous; a bare Part Number picks the most current revision.
            name: New name / item description (or None to keep current).
            description: New technical description (or None to keep current).
            category: New category name (or None to keep current).
            lifecycle_state: New lifecycle state, one of the values returned by list_item_lifecycle_states (unknown values rejected; or None to keep current).
            price_per_unit: New unit price (or None to keep current).
            external_pn: New external part number (or None to keep current).
            manufacturer: New manufacturer name or ID (link_row; or None to keep current).
            blackbox: New blackbox flag (or None to keep current).
            notes: Engineering notes (or None to keep current).
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found."})
            
            item_id = item["id"]
            payload: Dict[str, Any] = {}
            if description is not None:
                payload["Item description"] = description
            elif name is not None:
                payload["Item description"] = name
            if lifecycle_state is not None:
                state_name = lifecycle_state.strip()
                if state_name.lower() == "engineering use":
                    state_name = "Engineerig Use"
                state_id = client.get_state_id(state_name) if hasattr(client, "get_state_id") else []
                states_map = getattr(client, "states_map", {}) or {}
                matched_key = next((k for k in states_map.keys() if k.lower() == state_name.lower()), None)
                if not state_id and not matched_key:
                    return json.dumps({
                        "error": f"Invalid lifecycle_state '{lifecycle_state}'. Must be one of the values returned by list_item_lifecycle_states."
                    })
                payload["State"] = state_id if state_id else (matched_key or state_name)
            if price_per_unit is not None:
                payload["Price per unit"] = float(price_per_unit)
            if external_pn is not None:
                payload["External Part Number"] = external_pn
            if manufacturer is not None:
                if manufacturer == "":
                    payload["Manufacturer"] = []
                else:
                    resolved_mfg = _resolve_manufacturer(client, manufacturer)
                    if not resolved_mfg:
                        return json.dumps({
                            "error": f"Could not resolve manufacturer '{manufacturer}'. 'Manufacturer' is a link_row field requiring a valid manufacturer name or ID."
                        })
                    payload["Manufacturer"] = resolved_mfg
            if blackbox is not None:
                payload["Blackbox"] = bool(blackbox)
            if notes is not None:
                payload["Notes"] = notes

            if not payload:
                return json.dumps({"message": "No fields provided to update.", "item": item})

            updated = client.update_item(item_id, payload)
            return json.dumps({
                "message": f"Successfully updated item #{item_id} ({item.get('Part Number')})",
                "updated_fields": list(payload.keys()),
                "item": updated
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to update item: {str(e)}"})

    # =========================================================================
    # TOOLS - BOM HIERARCHY & WHERE-USED
    # =========================================================================

    @server.tool()
    def get_bom_tree(
        part_number_or_id: str = "",
        max_depth: int = 10,
        compact: bool = False,
        max_nodes: int = 0
    ) -> str:
        """
        Retrieve the multi-tier nested Bill of Materials (BOM) assembly hierarchy for an assembly or top-level assemblies.

        Hierarchy & Enrichment rules:
        - Returns the assembly hierarchy tree.
        - Only nodes with `has_children: true` are assemblies. Nodes with `has_children: false` are terminal leaf components/parts.
        - Each node in both full and compact mode is enriched with:
          - `blackbox: bool`: True if the assembly is a sealed or purchased unit that hides internal BOM explosion.
          - `purchase_kit: bool`: True if this item is a purchase kit. A purchase kit is ordered as one unit for procurement, while its children arrive and increment in inventory as untracked stock.
          - `has_children: bool`: True if this item contains sub-components or subassemblies (i.e. is an assembly).
          - `has_instructions: bool`: True if standard operating Work Instructions exist for this assembly.

        Args:
            part_number_or_id: Optional Part Number or ID of the root assembly. If empty, returns top-level trees.
            max_depth: Maximum hierarchy depth to traverse (default 10).
            compact: When true, omits heavy per-node metadata (edge_id, uom_id, search_helper, pcb_symbol, parent_id, image/datasheet fields) and returns only core fields (part_number, name, description, state, quantity, blackbox, purchase_kit, has_children, has_instructions, children).
            max_nodes: When > 0, caps total emitted nodes across the tree to prevent payload truncation. The root result will include `"truncated": true` and `"node_count": <n>`. Never silently truncates.
        """
        try:
            tree = client.get_bom_tree()
            bom_map, items_with_instructions = _get_tree_enrichment_context(client)
            inst_cache: Dict[int, bool] = {}
            # Transport safety: a single SSE event above ~1 MiB makes conforming clients
            # abort the stream, so an unbounded full-metadata tree is not deliverable.
            # When the caller passes no max_nodes, apply a safe budget and report the
            # truncation instead of silently dropping data (the historical `[:10]` root
            # slice, which contradicted the "never silently truncates" contract).
            effective_max_nodes = max_nodes if max_nodes > 0 else (
                _DEFAULT_MAX_NODES_COMPACT if compact else _DEFAULT_MAX_NODES_FULL
            )
            counter = NodeCounter(effective_max_nodes)

            if not part_number_or_id:
                emitted_trees = []
                for root in tree:
                    if counter.can_add():
                        p_root = _enrich_and_project_node(
                            client, root, 0, max_depth, compact, counter,
                            bom_map, items_with_instructions, inst_cache, set()
                        )
                        if p_root is not None:
                            emitted_trees.append(p_root)
                    else:
                        counter.truncated = True
                        break

                result: Dict[str, Any] = {
                    "root_count": len(tree),
                    "roots_returned": len(emitted_trees),
                    "bom_tree": emitted_trees
                }
                # Report truncation honestly. The historical `emitted_trees[:10]` cap
                # silently dropped every root past the tenth while the docstring
                # promised it "never silently truncates". Use max_nodes to bound the
                # payload deliberately.
                if max_nodes > 0 or counter.truncated:
                    result["truncated"] = counter.truncated
                    result["node_count"] = counter.count
                return json.dumps(result, indent=2)

            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            target_id = target["id"]
            if target_id not in bom_map:
                bom_map[target_id] = target

            def find_subtree(nodes):
                for n in nodes:
                    if n.get("id") == target_id:
                        return n
                    sub = find_subtree(n.get("children", []))
                    if sub:
                        return sub
                return None

            subtree = find_subtree(tree)
            if not subtree:
                # Build localized tree from graph children
                children = client.get_graph_children(target_id) if hasattr(client, "get_graph_children") else []
                name, desc = _extract_name_desc(target)
                subtree = {
                    "id": target_id,
                    "part_number": target.get("Part Number"),
                    "revision": target.get("Revision", ""),
                    "name": name,
                    "description": desc,
                    "purchase_kit": bool(target.get("Purchase Kit", False) or target.get("purchase_kit", False)),
                    "blackbox": bool(target.get("Blackbox", False)),
                    "children": children
                }

            proj = _enrich_and_project_node(
                client, subtree, 0, max_depth, compact, counter,
                bom_map, items_with_instructions, inst_cache, set()
            )
            if proj is None:
                proj = {}

            if max_nodes > 0:
                proj["truncated"] = counter.truncated
                proj["node_count"] = counter.count

            return json.dumps(proj, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get BOM tree: {str(e)}"})

    @server.tool()
    def find_assemblies_missing_instructions(part_number_or_id: str = "", max_depth: int = 10) -> str:
        """
        Traverse the tree of assembly children under the specified root (or all top-level assemblies)
        down to the furthest assemblies, and list all assemblies that are non-blackbox, have children,
        and lack work instructions.

        Blackbox Rule:
        - If an item is marked as a blackbox (blackbox=True), it represents a sealed or purchased unit.
        - Blackbox items are excluded from the result list.
        - Crucially, the subtrees of blackbox items are NOT traversed (a blackbox hides its internal structure).

        Assembly & Instruction Rule:
        - Only items with `has_children: true` are assemblies. Terminal/leaf parts (`has_children: false`) are ignored.
        - Only assemblies that do NOT have work instructions (`has_instructions: false`) are returned.
        - Each matching assembly is returned with: part_number, name, revision, id, and depth.

        Args:
            part_number_or_id: Optional Part Number or Row ID of the root assembly. If empty, traverses all top-level assemblies.
            max_depth: Maximum hierarchy depth to traverse (default 10).
        """
        try:
            tree = client.get_bom_tree()
            bom_map, items_with_instructions = _get_tree_enrichment_context(client)
            inst_cache: Dict[int, bool] = {}

            target = None
            if part_number_or_id:
                target = _find_item_by_pn_or_id(client, part_number_or_id)
                if not target:
                    return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

                target_id = target["id"]

                def find_subtree(nodes):
                    for n in nodes:
                        if n.get("id") == target_id:
                            return n
                        sub = find_subtree(n.get("children", []))
                        if sub:
                            return sub
                    return None

                root_node = find_subtree(tree)
                if not root_node:
                    children = client.get_graph_children(target_id) if hasattr(client, "get_graph_children") else []
                    name, desc = _extract_name_desc(target)
                    root_node = {
                        "id": target_id,
                        "part_number": target.get("Part Number"),
                        "revision": target.get("Revision", ""),
                        "name": name,
                        "description": desc,
                        "children": children
                    }
                roots = [root_node]
            else:
                roots = tree

            missing_assemblies: List[Dict[str, Any]] = []
            seen_assembly_ids: Set[Any] = set()

            def traverse(node: Dict[str, Any], depth: int, branch_visited: Set[int]):
                node_id = node.get("id")

                # Blackbox check:
                # "Blackbox items are excluded and their subtrees are NOT traversed (a blackbox hides its internals)."
                is_bb = _check_is_blackbox(node, bom_map)
                if is_bb:
                    return

                raw_children = node.get("children", [])
                has_children = bool(raw_children) and isinstance(raw_children, list) and len(raw_children) > 0
                has_inst = _check_has_instructions(client, node_id, items_with_instructions, inst_cache)

                # Assembly check:
                # "assemblies that are non-blackbox and have children but no work instructions"
                if has_children and not has_inst:
                    dedup_key = node_id if node_id is not None else node.get("part_number")
                    if dedup_key not in seen_assembly_ids:
                        seen_assembly_ids.add(dedup_key)
                        name = node.get("name")
                        if not name:
                            name, _ = _extract_name_desc(node)
                        if not name and node_id in bom_map:
                            name, _ = _extract_name_desc(bom_map[node_id])
                        
                        rev = node.get("revision")
                        if rev is None and node_id in bom_map:
                            rev = bom_map[node_id].get("Revision", "")

                        missing_assemblies.append({
                            "part_number": node.get("part_number") or (bom_map.get(node_id, {}).get("Part Number", "") if node_id else ""),
                            "name": name or "",
                            "revision": str(rev or ""),
                            "id": node_id,
                            "depth": depth
                        })

                # Traverse children if depth < max_depth
                if depth < max_depth and has_children:
                    curr_branch = branch_visited | {node_id} if node_id is not None else branch_visited
                    for child in raw_children:
                        cid = child.get("id")
                        if cid is not None and cid in branch_visited:
                            continue
                        traverse(child, depth + 1, curr_branch)

            for r in roots:
                traverse(r, depth=0, branch_visited=set())

            return json.dumps({
                "root": target.get("Part Number") if target else "ALL",
                "count": len(missing_assemblies),
                "assemblies": missing_assemblies
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to find assemblies missing instructions: {str(e)}"})

    @server.tool()
    def get_where_used(part_number_or_id: str) -> str:
        """
        Find all parent assemblies that use or contain this specific component (Where-Used Analysis).

        Args:
            part_number_or_id: Part Number or Row ID of the child component.
        """
        try:
            item = _find_item_by_pn_or_id(client, part_number_or_id)
            if not item:
                return json.dumps({"error": f"Item '{part_number_or_id}' not found."})

            item_id = item["id"]
            parents = client.get_graph_parents(item_id) if hasattr(client, "get_graph_parents") else []
            name, _ = _extract_name_desc(item)
            return json.dumps({
                "component": {
                    "id": item_id,
                    "part_number": item.get("Part Number"),
                    "name": name
                },
                "used_in_count": len(parents),
                "parent_assemblies": parents
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get parent assemblies: {str(e)}"})

    @server.tool()
    def create_bom_edge(
        parent_part_number_or_id: str,
        child_part_number_or_id: str,
        quantity: float = _DEFAULT_QUANTITY,
        length: float = 0.0,
        pcb_symbol: str = "",
        uom_id: str = ""
    ) -> str:
        """
        Create, update, or return an existing assembly BOM edge between a parent assembly and a child component.

        Identity & Revision Resolution:
        - Parent and child items are resolved via _find_item_by_pn_or_id. Exact Full PN or numeric ID is
          unambiguous, while a bare Part Number resolves to the most current revision (annotating
          _ambiguous_matches when multiple revisions exist).

        Edge Creation & Validation Rules:
        - Refuses self-referencing edges where parent and child are the same item.
        - Refuses edges where the child is already an ancestor of the parent (cycle guard), stating which item is the ancestor.
        - If an edge already exists for this (parent, child) pair, does not create a second edge: returns
          the existing edge_id with action 'existing', unless quantity was passed explicitly (in which case
          it updates the existing edge and reports action 'updated').

        Args:
            parent_part_number_or_id: Part Number, Full PN, or Row ID of the parent assembly.
            child_part_number_or_id: Part Number, Full PN, or Row ID of the child component.
            quantity: Quantity of the child item in the parent assembly (default 1.0).
            length: Measurement/length value for bulk/raw items (default 0.0).
            pcb_symbol: PCB reference designator(s) (e.g. 'R1, R2' or 'N/A').
            uom_id: Unit of Measure name, symbol, or ID (e.g. 'mm', 'pcs', 'cm').
        """
        try:
            parent_item = _find_item_by_pn_or_id(client, parent_part_number_or_id)
            if not parent_item:
                return json.dumps({
                    "ok": False,
                    "error": f"Parent item '{parent_part_number_or_id}' not found in BOM catalog.",
                    "message": f"Parent item '{parent_part_number_or_id}' not found in BOM catalog."
                }, indent=2)

            child_item = _find_item_by_pn_or_id(client, child_part_number_or_id)
            if not child_item:
                return json.dumps({
                    "ok": False,
                    "error": f"Child item '{child_part_number_or_id}' not found in BOM catalog.",
                    "message": f"Child item '{child_part_number_or_id}' not found in BOM catalog."
                }, indent=2)

            parent_id = parent_item["id"]
            child_id = child_item["id"]

            p_name, _ = _extract_name_desc(parent_item)
            c_name, _ = _extract_name_desc(child_item)

            parent_info: Dict[str, Any] = {
                "part_number": parent_item.get("Part Number", ""),
                "name": p_name or ""
            }
            if "_ambiguous_matches" in parent_item:
                parent_info["_ambiguous_matches"] = parent_item["_ambiguous_matches"]

            child_info: Dict[str, Any] = {
                "part_number": child_item.get("Part Number", ""),
                "name": c_name or ""
            }
            if "_ambiguous_matches" in child_item:
                child_info["_ambiguous_matches"] = child_item["_ambiguous_matches"]

            # 1. Refuse when parent == child
            if parent_id == child_id:
                return json.dumps({
                    "ok": False,
                    "error": f"Cannot create self-referencing BOM edge: parent and child are the same item '{parent_info['part_number']}' (#{parent_id}).",
                    "message": f"Cannot create self-referencing BOM edge: parent and child are the same item '{parent_info['part_number']}' (#{parent_id})."
                }, indent=2)

            try:
                qty_float = float(quantity)
            except (ValueError, TypeError):
                return json.dumps({
                    "ok": False,
                    "error": f"Invalid quantity '{quantity}'. Must be a valid number.",
                    "message": f"Invalid quantity '{quantity}'. Must be a valid number."
                }, indent=2)

            try:
                length_float = float(length) if length is not None and str(length).strip() != "" else 0.0
            except (ValueError, TypeError):
                length_float = 0.0

            # 2. Fetch existing assembly edges
            assembly_rows = []
            if hasattr(client, "_get_all_rows") and hasattr(client, "table_assembly"):
                try:
                    res = client._get_all_rows(client.table_assembly)
                    if isinstance(res, list):
                        assembly_rows = res
                except Exception as e:
                    logger.debug(f"Could not load assembly rows: {e}")

            # 3. Cycle guard: Refuse when child is already an ancestor of parent
            parents_of = defaultdict(list)
            for edge in assembly_rows:
                p = _extract_relation_id(edge.get("Item"))
                c = _extract_relation_id(edge.get("Contains"))
                if p is not None and c is not None:
                    parents_of[c].append(p)

            queue = [parent_id]
            visited = {parent_id}
            is_ancestor = False

            while queue:
                curr = queue.pop(0)
                for p in parents_of.get(curr, []):
                    if p == child_id:
                        is_ancestor = True
                        break
                    if p not in visited:
                        visited.add(p)
                        queue.append(p)
                if is_ancestor:
                    break

            if is_ancestor:
                return json.dumps({
                    "ok": False,
                    "error": f"Cannot create BOM edge: child item '{child_info['part_number']}' (#{child_id}) is already an ancestor of parent '{parent_info['part_number']}' (#{parent_id}) (cycle detected).",
                    "message": f"Cannot create BOM edge: child item '{child_info['part_number']}' (#{child_id}) is already an ancestor of parent '{parent_info['part_number']}' (#{parent_id}) (cycle detected)."
                }, indent=2)

            # 4. Check offline UoM resolution
            resolved_uom_id = None
            if uom_id:
                uom_info = BaserowClient.uom_info_offline(uom_id)
                resolved_uom_id = uom_info.get("id")
                if resolved_uom_id is None:
                    try:
                        resolved_uom_id = int(uom_id)
                    except (ValueError, TypeError):
                        pass
            elif length_float > 0 and child_item:
                child_uom = BaserowClient.resolve_edge_uom_offline({}, child_item)
                if child_uom and child_uom.get("id"):
                    resolved_uom_id = child_uom.get("id")

            # 5. Check if edge already exists
            existing_edge = None
            for edge in assembly_rows:
                p = _extract_relation_id(edge.get("Item"))
                c = _extract_relation_id(edge.get("Contains"))
                if p == parent_id and c == child_id:
                    existing_edge = edge
                    break

            if existing_edge is not None:
                existing_edge_id = existing_edge.get("id")
                q_raw = existing_edge.get("Amount of Times")
                if q_raw is None or q_raw == "":
                    q_raw = existing_edge.get("Quantity", 1.0)
                try:
                    existing_qty = float(q_raw)
                except (ValueError, TypeError):
                    existing_qty = 1.0

                l_raw = existing_edge.get("Measurement")
                try:
                    existing_len = float(l_raw) if l_raw is not None and str(l_raw).strip() != "" else 0.0
                except (ValueError, TypeError):
                    existing_len = 0.0

                explicit_quantity = not isinstance(quantity, _DefaultQuantity)
                if not explicit_quantity:
                    return json.dumps({
                        "ok": True,
                        "action": "existing",
                        "edge_id": existing_edge_id,
                        "parent": parent_info,
                        "child": child_info,
                        "quantity": existing_qty,
                        "length": existing_len,
                        "message": f"BOM edge already exists between parent '{parent_info['part_number']}' and child '{child_info['part_number']}' with edge_id #{existing_edge_id}."
                    }, indent=2)
                else:
                    # Update existing edge
                    update_kwargs: Dict[str, Any] = {"quantity": qty_float}
                    if length_float > 0:
                        update_kwargs["length"] = length_float
                    if pcb_symbol:
                        update_kwargs["pcb_symbol"] = pcb_symbol
                    if resolved_uom_id is not None:
                        update_kwargs["uom_id"] = resolved_uom_id

                    client.update_assembly(existing_edge_id, **update_kwargs)
                    return json.dumps({
                        "ok": True,
                        "action": "updated",
                        "edge_id": existing_edge_id,
                        "parent": parent_info,
                        "child": child_info,
                        "quantity": qty_float,
                        "length": length_float if length_float > 0 else existing_len,
                        "message": f"Updated existing assembly edge #{existing_edge_id} between '{parent_info['part_number']}' and '{child_info['part_number']}' with quantity {qty_float}."
                    }, indent=2)

            # 6. Create new edge
            symbol_val = pcb_symbol if pcb_symbol else "N/A"
            created_res = client.create_assembly(
                parent_id=parent_id,
                child_id=child_id,
                quantity=qty_float,
                length=length_float,
                pcb_symbol=symbol_val,
                uom_id=resolved_uom_id
            )
            new_edge_id = created_res.get("id") if isinstance(created_res, dict) else created_res

            return json.dumps({
                "ok": True,
                "action": "created",
                "edge_id": new_edge_id,
                "parent": parent_info,
                "child": child_info,
                "quantity": qty_float,
                "length": length_float,
                "message": f"Successfully created BOM edge #{new_edge_id} from '{parent_info['part_number']}' to '{child_info['part_number']}'."
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Failed to create BOM edge: {str(e)}",
                "message": f"Failed to create BOM edge: {str(e)}"
            }, indent=2)

    @server.tool()
    def delete_bom_edge(edge_id: str) -> str:
        """
        Delete an assembly BOM edge from the database.

        Args:
            edge_id: The Row ID of the assembly edge to delete.
        """
        try:
            clean_id = str(edge_id).strip()
            try:
                int_edge_id = int(clean_id)
            except (ValueError, TypeError):
                return json.dumps({
                    "ok": False,
                    "error": f"Invalid edge_id '{edge_id}'. Must be a valid integer ID.",
                    "message": f"Invalid edge_id '{edge_id}'. Must be a valid integer ID."
                }, indent=2)

            assembly_rows = []
            if hasattr(client, "_get_all_rows") and hasattr(client, "table_assembly"):
                try:
                    res = client._get_all_rows(client.table_assembly)
                    if isinstance(res, list):
                        assembly_rows = res
                except Exception as e:
                    logger.debug(f"Could not load assembly rows: {e}")

            edge_row = None
            for r in assembly_rows:
                if r.get("id") == int_edge_id or str(r.get("id")) == clean_id:
                    edge_row = r
                    break

            if not edge_row:
                return json.dumps({
                    "ok": False,
                    "error": f"Assembly edge #{edge_id} not found.",
                    "message": f"Assembly edge #{edge_id} not found."
                }, indent=2)

            pid = _extract_relation_id(edge_row.get("Item"))
            cid = _extract_relation_id(edge_row.get("Contains"))

            parent_item = _find_item_by_pn_or_id(client, str(pid)) if pid else None
            child_item = _find_item_by_pn_or_id(client, str(cid)) if cid else None

            p_name, _ = _extract_name_desc(parent_item) if parent_item else (None, None)
            c_name, _ = _extract_name_desc(child_item) if child_item else (None, None)

            parent_info: Dict[str, Any] = {
                "part_number": (parent_item.get("Part Number") if parent_item else "") or (f"ID-{pid}" if pid else ""),
                "name": p_name or ""
            }
            child_info: Dict[str, Any] = {
                "part_number": (child_item.get("Part Number") if child_item else "") or (f"ID-{cid}" if cid else ""),
                "name": c_name or ""
            }

            client.delete_assembly(int_edge_id)

            return json.dumps({
                "ok": True,
                "action": "deleted",
                "edge_id": int_edge_id,
                "parent": parent_info,
                "child": child_info,
                "message": f"Successfully deleted assembly edge #{int_edge_id} ({parent_info['part_number']} -> {child_info['part_number']})."
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Failed to delete BOM edge #{edge_id}: {str(e)}",
                "message": f"Failed to delete BOM edge #{edge_id}: {str(e)}"
            }, indent=2)

    # =========================================================================
    # TOOLS - BOM EQUILIBRIUM & QUALITY PROBLEM SCANNER
    # =========================================================================

    @server.tool()
    def scan_bom_duplicates(
        part_number_or_id: str = "",
        apply: bool = False
    ) -> str:
        """
        Scan BOM relations for multi-edge duplicate relations, placement splits, and distinct measurements.
        Optionally apply patches to combine duplicates/placement splits while keeping distinct measurements untouched.

        Args:
            part_number_or_id: Part Number or Row ID of the assembly to scan. If empty, scans all relations.
            apply: When True, merges true_duplicate and placement_split groups by patching the lowest edge ID and deleting others, then re-fetching to verify. Never modifies distinct_measure groups.
        """
        try:
            from collections import defaultdict

            assembly_rows = client._get_all_rows(client.table_assembly)
            bom_rows = client._get_all_rows(client.table_bom)
            bom_map = {r["id"]: r for r in bom_rows}

            target = None
            if part_number_or_id:
                clean_id = str(part_number_or_id).strip()
                if clean_id.isdigit():
                    target = bom_map.get(int(clean_id))
                if not target:
                    target = _find_item_by_pn_or_id(client, part_number_or_id)

                if not target:
                    return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

                target_id = target["id"]
                subtree_parent_ids = set()

                def collect_subtree(curr_id):
                    if curr_id in subtree_parent_ids:
                        return
                    subtree_parent_ids.add(curr_id)
                    for edge in assembly_rows:
                        p_id = _extract_relation_id(edge.get("Item"))
                        c_id = _extract_relation_id(edge.get("Contains"))
                        if p_id == curr_id and c_id:
                            collect_subtree(c_id)

                collect_subtree(target_id)
                assembly_rows = [
                    e for e in assembly_rows
                    if _extract_relation_id(e.get("Item")) in subtree_parent_ids
                ]

            by_pair = defaultdict(list)
            for edge in assembly_rows:
                pid = _extract_relation_id(edge.get("Item"))
                cid = _extract_relation_id(edge.get("Contains"))
                if pid and cid:
                    by_pair[(pid, cid)].append(edge)

            multi_edge_pairs = {pair: edges for pair, edges in by_pair.items() if len(edges) > 1}

            raw_groups = []
            for (pid, cid), edge_list in multi_edge_pairs.items():
                p_part = bom_map.get(pid, {})
                c_part = bom_map.get(cid, {})
                p_pn = p_part.get("Part Number") or str(pid)
                c_pn = c_part.get("Part Number") or str(cid)

                edges_info = []
                converted_values = set()
                designators_set = set()
                sum_qty = 0

                for e in edge_list:
                    uom_info = None
                    if hasattr(client, "resolve_edge_uom"):
                        try:
                            res_uom = client.resolve_edge_uom(e, c_part)
                            if isinstance(res_uom, dict):
                                uom_info = res_uom
                        except Exception:
                            pass
                    if not uom_info:
                        try:
                            res_uom = BaserowClient.resolve_edge_uom(client, e, c_part)
                            if isinstance(res_uom, dict):
                                uom_info = res_uom
                        except Exception:
                            pass
                    if not uom_info:
                        # No live client available: resolve from the static UoM table.
                        # Never construct a real BaserowClient() here -- it would bypass
                        # the injected client and issue live HTTP that stalls on retry
                        # backoff whenever the caller passes a mock/fake.
                        try:
                            uom_info = BaserowClient.resolve_edge_uom_offline(e, c_part)
                        except Exception:
                            uom_info = {"multiplier": 1.0, "is_count": True, "symbol": "pcs"}

                    try:
                        mult = float(uom_info.get("multiplier", 1.0))
                    except (ValueError, TypeError):
                        mult = 1.0
                    is_count = bool(uom_info.get("is_count", True))
                    uom_sym = str(uom_info.get("symbol") or "pcs")

                    qty_raw = e.get("Amount of Times")
                    if qty_raw is None or qty_raw == "":
                        qty_raw = e.get("Quantity", 1)
                    try:
                        amount = float(qty_raw) if (qty_raw is not None and str(qty_raw).strip() != "") else 1.0
                        if amount.is_integer():
                            amount = int(amount)
                    except (ValueError, TypeError):
                        amount = 1

                    meas_raw = e.get("Measurement")
                    try:
                        meas = float(meas_raw) if (meas_raw is not None and str(meas_raw).strip() != "") else 0.0
                    except (ValueError, TypeError):
                        meas = 0.0

                    conv = 0.0 if is_count else round(meas * mult, 6)
                    converted_values.add(conv)

                    pcb_sym = str(e.get("PCB Symbol") or "").strip()
                    if pcb_sym and pcb_sym.upper() != "N/A":
                        for p in pcb_sym.split(","):
                            cleaned = p.strip()
                            if cleaned and cleaned.upper() != "N/A":
                                designators_set.add(cleaned)

                    sum_qty += amount
                    edges_info.append({
                        "id": e["id"],
                        "amount": amount,
                        "measurement": meas,
                        "uom": uom_sym,
                        "pcb_symbol": pcb_sym
                    })

                designators_list = sorted(list(designators_set))

                if len(converted_values) > 1:
                    classification = "distinct_measure"
                    action = "keep_separate"
                elif len(designators_list) > 0:
                    classification = "placement_split"
                    action = "merge"
                else:
                    classification = "true_duplicate"
                    action = "merge"

                raw_groups.append({
                    "parent_pn": p_pn,
                    "child_pn": c_pn,
                    "edges": edges_info,
                    "sum_qty": sum_qty,
                    "designators": designators_list,
                    "classification": classification,
                    "action": action,
                    "_pid": pid,
                    "_cid": cid
                })

            raw_groups.sort(key=lambda g: (g["parent_pn"], g["child_pn"]))

            verified_list = []
            if apply:
                for g in raw_groups:
                    if g["classification"] == "distinct_measure":
                        continue

                    pid = g["_pid"]
                    cid = g["_cid"]
                    pre_sum = g["sum_qty"]
                    lowest_edge_id = min(e["id"] for e in g["edges"])
                    other_edge_ids = [e["id"] for e in g["edges"] if e["id"] != lowest_edge_id]
                    comma_designators = ", ".join(g["designators"]) if g["designators"] else "N/A"

                    try:
                        client.update_assembly(lowest_edge_id, quantity=pre_sum, pcb_symbol=comma_designators)
                        for eid in other_edge_ids:
                            client.delete_assembly(eid)
                        g["action"] = "merged"
                    except Exception as exc:
                        verified_list.append({
                            "parent_pn": g["parent_pn"],
                            "child_pn": g["child_pn"],
                            "surviving_edge_id": lowest_edge_id,
                            "deleted_edge_ids": other_edge_ids,
                            "pre_sum_qty": pre_sum,
                            "post_sum_qty": None,
                            "merged_group_gone": False,
                            "quantity_unchanged": False,
                            "status": "failed",
                            "error": str(exc)
                        })

                # Re-fetch relation table and re-run scan verification
                refetched_rows = client._get_all_rows(client.table_assembly)
                for g in raw_groups:
                    if g["classification"] == "distinct_measure":
                        continue
                    if any(v["parent_pn"] == g["parent_pn"] and v["child_pn"] == g["child_pn"] and v["status"] == "failed" for v in verified_list):
                        continue

                    pid = g["_pid"]
                    cid = g["_cid"]
                    pre_sum = g["sum_qty"]
                    lowest_edge_id = min(e["id"] for e in g["edges"])
                    other_edge_ids = [e["id"] for e in g["edges"] if e["id"] != lowest_edge_id]

                    remaining = [
                        e for e in refetched_rows
                        if _extract_relation_id(e.get("Item")) == pid and _extract_relation_id(e.get("Contains")) == cid
                    ]
                    post_sum = 0
                    for e in remaining:
                        q = e.get("Amount of Times")
                        if q is None or q == "":
                            q = e.get("Quantity", 1)
                        try:
                            post_sum += float(q)
                        except (ValueError, TypeError):
                            post_sum += 1.0

                    if post_sum.is_integer():
                        post_sum_val = int(post_sum)
                    else:
                        post_sum_val = post_sum

                    group_gone = (len(remaining) == 1 and remaining[0]["id"] == lowest_edge_id)
                    qty_unchanged = (float(pre_sum) == float(post_sum))

                    if group_gone and qty_unchanged:
                        verified_list.append({
                            "parent_pn": g["parent_pn"],
                            "child_pn": g["child_pn"],
                            "surviving_edge_id": lowest_edge_id,
                            "deleted_edge_ids": other_edge_ids,
                            "pre_sum_qty": pre_sum,
                            "post_sum_qty": post_sum_val,
                            "merged_group_gone": True,
                            "quantity_unchanged": True,
                            "status": "verified"
                        })
                    else:
                        verified_list.append({
                            "parent_pn": g["parent_pn"],
                            "child_pn": g["child_pn"],
                            "surviving_edge_id": lowest_edge_id,
                            "deleted_edge_ids": other_edge_ids,
                            "pre_sum_qty": pre_sum,
                            "post_sum_qty": post_sum_val,
                            "merged_group_gone": group_gone,
                            "quantity_unchanged": qty_unchanged,
                            "status": "failed",
                            "error": f"Post-verification mismatch: group_gone={group_gone}, qty_unchanged={qty_unchanged}"
                        })

            final_groups = []
            for g in raw_groups:
                final_groups.append({
                    "parent_pn": g["parent_pn"],
                    "child_pn": g["child_pn"],
                    "edges": g["edges"],
                    "sum_qty": g["sum_qty"],
                    "designators": g["designators"],
                    "classification": g["classification"],
                    "action": g["action"]
                })

            totals = {
                "true_duplicate": sum(1 for g in final_groups if g["classification"] == "true_duplicate"),
                "placement_split": sum(1 for g in final_groups if g["classification"] == "placement_split"),
                "distinct_measure": sum(1 for g in final_groups if g["classification"] == "distinct_measure"),
                "total": len(final_groups)
            }

            result = {
                "totals": totals,
                "groups": final_groups
            }
            if apply:
                result["verified"] = verified_list

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to scan BOM duplicates: {str(e)}"})

    @server.tool()
    def audit_bom_balance(part_number_or_id: str) -> str:
        """
        Audit the mathematical BOM equilibrium / balance for an assembly: compares declared BOM child
        quantities against the tolling quantities consumed across all Work Instruction (WI) steps.

        Identity & Revision Resolution:
        - Full PN = Part Number + ' Rev.' + Revision is the unique item identity; a bare Part Number can
          exist on several rows at different revisions as distinct items.
        - Exact Full PN or numeric ID is unambiguous; a bare Part Number picks the most current revision
          by lifecycle state (annotating _ambiguous_matches when multiple revisions exist).

        Toll Resolution Order:
        - A step's toll entry is matched to the parent's BOM child by edge_id, then by item_id, then by
          Part Number; anything matching none of these is reported in discrepancies with reason 'orphan_toll_entry'.

        Semantics & Return Fields:
        - required: summed 'Amount of Times' from the BOM across the non-blackbox subtree.
        - tolled: sum of Toll Map entries with toll: true over the set's steps (supports all stored formats).
        - variance: tolled - required (0 is balanced).
        - bom_equilibrium_balanced: True iff every instruction set is balanced and at least one set exists.
        - discrepancies: Genuine quantity mismatches (status 'OVER_TOLLED' or 'UNDER_TOLLED') and orphan toll
          entries. Each entry carries: part_id, part_number, revision, full_pn, required_bom_qty,
          tolled_wi_qty, variance, status.
        - stale_revision_references: Toll entries resolving to a different revision row than the parent's
          BOM child. Each entry has: parent, bom_child, tolled_row (all Full PN), part_number, quantity,
          step_number. This is a data inconsistency (toll map authored against an older revision) reported
          for cleanup and does NOT make the set unbalanced.
        - includes per-step has_photo reporting.

        Args:
            part_number_or_id: Part Number, Full PN, or Row ID of the assembly to audit. Exact Full PN /
                numeric ID is unambiguous; a bare Part Number picks the most current revision.
        """
        try:
            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            pid = target["id"]
            bom_rows = client._get_all_rows(client.table_bom)
            assembly_rows = client._get_all_rows(client.table_assembly)
            instruction_rows = client._get_all_rows(client.table_instructions)
            
            bom_map = {r["id"]: r for r in bom_rows}

            # Map assembly relations (parent -> children) and edge_id -> child row
            parent_to_children = {}
            edge_to_child = {}
            for edge in assembly_rows:
                child_link = edge.get("Contains")
                parent_link = edge.get("Item")
                cid = None
                p_val = None
                if child_link:
                    cid = child_link[0]["id"] if isinstance(child_link, list) and child_link else (child_link.get("id") if isinstance(child_link, dict) else child_link)
                if parent_link:
                    p_val = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                if edge.get("id") is not None and cid is not None:
                    try:
                        edge_to_child[int(edge["id"])] = int(cid)
                    except (ValueError, TypeError):
                        pass
                if p_val and cid:
                    qty = edge.get("Amount of Times")
                    if qty is None or qty == "":
                        qty = edge.get("Quantity", 1)
                    try:
                        qty = float(qty) if qty is not None else 1.0
                    except (ValueError, TypeError):
                        qty = 1.0
                    parent_to_children.setdefault(p_val, []).append({"child_id": cid, "quantity": qty})

            # Map instructions
            parent_to_instruction_sets = {}
            for row in instruction_rows:
                parent_link = row.get("Parent Item")
                if parent_link:
                    parent_item_id = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                    if parent_item_id:
                        s_raw = row.get("Set Index")
                        try:
                            s_idx = int(float(s_raw)) if s_raw is not None and str(s_raw).strip() != "" else 1
                        except (ValueError, TypeError):
                            s_idx = 1
                        parent_to_instruction_sets.setdefault(parent_item_id, {}).setdefault(s_idx, []).append(row)

            # Calculate required totals
            items_with_instructions = set(parent_to_instruction_sets.keys())
            required_totals = {}

            def traverse(current_id, current_multiplier, visited):
                if current_id in visited:
                    return
                rels = parent_to_children.get(current_id, [])
                for rel in rels:
                    cid = rel["child_id"]
                    qty = rel["quantity"] * current_multiplier
                    child_part = bom_map.get(cid, {})
                    is_blackbox = bool(child_part.get("Blackbox", False))
                    has_inst = cid in items_with_instructions
                    child_has_children = bool(parent_to_children.get(cid))
                    if child_has_children and not is_blackbox and not has_inst:
                        traverse(cid, qty, visited | {current_id})
                    else:
                        required_totals[cid] = required_totals.get(cid, 0) + qty

            traverse(pid, 1, set())

            # Index parent's BOM children by Part Number for revision matching
            pn_to_bom_children = defaultdict(list)
            for cid in required_totals.keys():
                c_part = bom_map.get(cid) or (client.get_item(cid) if hasattr(client, "get_item") else {})
                c_pn = c_part.get("Part Number")
                if c_pn:
                    pn_to_bom_children[str(c_pn).strip().lower()].append(cid)
            for k in pn_to_bom_children:
                pn_to_bom_children[k].sort(
                    key=lambda cid: _lifecycle_state_rank(
                        _extract_lifecycle_state(bom_map.get(cid) or {})
                    )
                )

            # Pre-compute parent Full PN
            p_pn = target.get("Part Number", "")
            p_rev = target.get("Revision") or ""
            parent_full_pn = target.get("Full PN") or (f"{p_pn} Rev.{p_rev}" if p_rev else p_pn)

            sets_dict = parent_to_instruction_sets.get(pid, {})
            num_sets = len(sets_dict)

            audit_sets = []
            if num_sets > 0:
                for s_idx, set_steps in sorted(sets_dict.items(), key=lambda x: x[0]):
                    instructed_totals = {}
                    orphan_totals = {}
                    stale_references = []
                    steps_detail = []
                    has_missing_photos = False

                    # Sort steps by Step Order
                    set_steps.sort(key=lambda x: int(float(x.get("Step Order") or 0)))

                    for s in set_steps:
                        photos = s.get("Photo") or s.get("Photos") or []
                        has_photo = bool(photos) and len(photos) > 0
                        if not has_photo:
                            has_missing_photos = True

                        step_ord = s.get("Step Order")
                        try:
                            step_num = int(float(step_ord)) if step_ord is not None and str(step_ord).strip() != "" else None
                        except (ValueError, TypeError):
                            step_num = step_ord

                        toll_map_str = s.get("Toll Map")
                        toll_items = []
                        if toll_map_str:
                            for entry in parse_toll_map(toll_map_str):
                                is_toll = entry.get("toll", True)
                                if not is_toll:
                                    continue
                                raw_item_id = entry.get("item_id")
                                edge_id = entry.get("edge_id")
                                q_num = float(entry.get("qty", 1.0))

                                # 1. Resolve each toll entry to the parent's actual BOM child in order:
                                # a. edge_id (when present) -> that BOM edge's child row
                                resolved_cid = None
                                if edge_id is not None:
                                    try:
                                        edge_child = edge_to_child.get(int(edge_id))
                                        if edge_child in required_totals:
                                            resolved_cid = edge_child
                                    except (ValueError, TypeError):
                                        pass

                                # b. else item_id if that row IS one of the parent's BOM children
                                if resolved_cid is None and raw_item_id is not None:
                                    try:
                                        iid = int(raw_item_id)
                                        if iid in required_totals:
                                            resolved_cid = iid
                                    except (ValueError, TypeError):
                                        pass

                                # c. else match by Part Number against the parent's BOM children
                                if resolved_cid is None and raw_item_id is not None:
                                    try:
                                        iid = int(raw_item_id)
                                        raw_part = bom_map.get(iid) or (client.get_item(iid) if hasattr(client, "get_item") else {})
                                        raw_pn = str(raw_part.get("Part Number", "")).strip().lower()
                                        if raw_pn and raw_pn in pn_to_bom_children:
                                            resolved_cid = pn_to_bom_children[raw_pn][0]
                                    except (ValueError, TypeError):
                                        pass

                                # Record toll step detail
                                toll_items.append({"part_id": raw_item_id, "quantity": q_num})

                                # 2. Aggregate quantity onto resolved BOM child or track orphan
                                if resolved_cid is not None:
                                    instructed_totals[resolved_cid] = instructed_totals.get(resolved_cid, 0) + q_num
                                    # 3. Emit stale revision reference if resolved row differs from tolled row
                                    if raw_item_id is not None and int(raw_item_id) != resolved_cid:
                                        bom_child_part = bom_map.get(resolved_cid) or (client.get_item(resolved_cid) if hasattr(client, "get_item") else {})
                                        bom_child_pn = bom_child_part.get("Part Number", "")
                                        bom_child_rev = bom_child_part.get("Revision") or ""
                                        bom_child_full = bom_child_part.get("Full PN") or (f"{bom_child_pn} Rev.{bom_child_rev}" if bom_child_rev else bom_child_pn)

                                        tolled_part = bom_map.get(int(raw_item_id)) or (client.get_item(int(raw_item_id)) if hasattr(client, "get_item") else {})
                                        tolled_pn = tolled_part.get("Part Number", "")
                                        tolled_rev = tolled_part.get("Revision") or ""
                                        tolled_full = tolled_part.get("Full PN") or (f"{tolled_pn} Rev.{tolled_rev}" if tolled_rev else tolled_pn)

                                        stale_references.append({
                                            "parent": parent_full_pn,
                                            "bom_child": bom_child_full,
                                            "tolled_row": tolled_full,
                                            "part_number": bom_child_pn or tolled_pn,
                                            "quantity": q_num,
                                            "step_number": step_num
                                        })
                                else:
                                    # 4. Genuine orphan toll entry
                                    if raw_item_id is not None:
                                        orphan_id = int(raw_item_id)
                                        orphan_totals[orphan_id] = orphan_totals.get(orphan_id, 0) + q_num

                        step_title_val = s.get("Action", "")

                        steps_detail.append({
                            "step_id": s.get("id"),
                            "step_number": step_num,
                            "title": step_title_val,
                            "has_photo": has_photo,
                            "tolled_items": toll_items
                        })

                    # Compare required vs instructed
                    component_discrepancies = []
                    is_set_balanced = True

                    # Check BOM requirements
                    for cid in sorted(required_totals.keys()):
                        req_q = required_totals.get(cid, 0)
                        inst_q = instructed_totals.get(cid, 0)
                        c_part = bom_map.get(cid, {})
                        c_pn = c_part.get("Part Number", f"ID-{cid}")
                        # A part number can exist on more than one row (different revisions),
                        # and those rows are distinct items with independent balances. Always
                        # report the revision too, or two rows sharing a PN read as contradictions.
                        c_rev = c_part.get("Revision") or ""
                        c_full_pn = c_part.get("Full PN") or (f"{c_pn} Rev.{c_rev}" if c_rev else c_pn)
                        
                        variance = round(inst_q - req_q, 4)
                        if abs(variance) > 0.0001:
                            is_set_balanced = False
                            status = "OVER_TOLLED" if variance > 0 else "UNDER_TOLLED"
                            component_discrepancies.append({
                                "part_id": cid,
                                "part_number": c_pn,
                                "revision": c_rev,
                                "full_pn": c_full_pn,
                                "required_bom_qty": req_q,
                                "tolled_wi_qty": inst_q,
                                "variance": variance,
                                "status": status
                            })

                    # Check orphan toll entries
                    for orphan_id in sorted(orphan_totals.keys()):
                        is_set_balanced = False
                        o_part = bom_map.get(orphan_id, {}) or (client.get_item(orphan_id) if hasattr(client, "get_item") else {})
                        o_pn = o_part.get("Part Number", f"ID-{orphan_id}")
                        o_rev = o_part.get("Revision") or ""
                        o_full_pn = o_part.get("Full PN") or (f"{o_pn} Rev.{o_rev}" if o_rev else o_pn)
                        o_qty = orphan_totals[orphan_id]
                        component_discrepancies.append({
                            "part_id": orphan_id,
                            "part_number": o_pn,
                            "revision": o_rev,
                            "full_pn": o_full_pn,
                            "required_bom_qty": 0,
                            "tolled_wi_qty": o_qty,
                            "variance": round(o_qty, 4),
                            "status": "OVER_TOLLED",
                            "reason": "orphan_toll_entry"
                        })

                    audit_sets.append({
                        "set_index": s_idx,
                        "step_count": len(set_steps),
                        "has_missing_photos": has_missing_photos,
                        "is_balanced": is_set_balanced,
                        "discrepancies": component_discrepancies,
                        "stale_revision_references": stale_references,
                        "steps": steps_detail
                    })

            overall_balanced = (num_sets > 0) and all(s["is_balanced"] for s in audit_sets)
            all_discrepancies = []
            all_stale_references = []
            for s in audit_sets:
                all_discrepancies.extend(s["discrepancies"])
                all_stale_references.extend(s["stale_revision_references"])

            audit_target_name, _ = _extract_name_desc(target)
            result = {
                "assembly": {
                    "id": pid,
                    "part_number": target.get("Part Number"),
                    "name": audit_target_name
                },
                "bom_equilibrium_balanced": overall_balanced,
                "instruction_sets_count": num_sets,
                "discrepancies": all_discrepancies,
                "stale_revision_references": all_stale_references,
                "sets": audit_sets
            }
            if not overall_balanced:
                if num_sets == 0:
                    result["reason"] = "no_instruction_sets"
                else:
                    result["reason"] = "unbalanced_instruction_sets"

            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to audit BOM balance: {str(e)}"})

    # =========================================================================
    # TOOLS - WORK INSTRUCTIONS (WI) & TOLLING
    # =========================================================================

    @server.tool()
    def get_work_instructions(part_number_or_id: str, set_index: int = 0) -> str:
        """
        Retrieve step-by-step Work Instructions (WIs) and tolling mappings for an assembly.

        Args:
            part_number_or_id: Part Number or Row ID of the parent assembly.
            set_index: Instruction set index (default 0). If 0 and only set 1+ exists, falls back to the first available set.
        """
        try:
            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            parent_id = target["id"]
            sets = client.get_instruction_sets_for_item(parent_id)
            effective_set = set_index
            if sets and set_index == 0 and not any(s.get("set_index") == 0 for s in sets):
                effective_set = sets[0].get("set_index", 0)
            details = client.get_instruction_set_details(parent_id, effective_set)
            wi_target_name, _ = _extract_name_desc(target)
            
            return json.dumps({
                "assembly": {
                    "id": parent_id,
                    "part_number": target.get("Part Number"),
                    "name": wi_target_name
                },
                "available_sets": sets,
                "current_set_index": effective_set,
                "steps": details
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get work instructions: {str(e)}"})

    @server.tool()
    def create_or_update_wi_step(
        assembly_pn_or_id: str,
        step_number: int,
        instruction_text: str,
        step_title: str = "",
        set_index: int = 0,
        tolling_items: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Create or update a Work Instruction (WI) step for an assembly item.
        Parameter mappings: step_number maps to 'Step Order', step_title maps to 'Action', instruction_text maps to 'Description', set_index maps to 'Set Index'.

        Args:
            assembly_pn_or_id: Part Number or Row ID of the parent assembly.
            step_number: Step sequence number (written to 'Step Order').
            instruction_text: Step markdown or descriptive instruction text (written to 'Description').
            step_title: Short step summary/action (written to 'Action', e.g. 'Mount PCB onto Chassis').
            set_index: Instruction set index (written to 'Set Index', default 0).
            tolling_items: Optional list of dicts specifying parts tolled in this step. Accepts either canonical [{'edge_id':..., 'item_id':..., 'qty':..., 'length':..., 'toll': True}] or legacy [{'id':..., 'quantity':..., 'toll': True}].
        """
        try:
            target = _find_item_by_pn_or_id(client, assembly_pn_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{assembly_pn_or_id}' not found."})

            parent_id = target["id"]
            
            sets = client.get_instruction_sets_for_item(parent_id) if hasattr(client, "get_instruction_sets_for_item") else []
            effective_set = set_index
            if sets and set_index == 0 and not any(s.get("set_index") == 0 for s in sets):
                effective_set = sets[0].get("set_index", 1)

            # Find existing step for this set and step_number
            existing_details = client.get_instruction_set_details(parent_id, effective_set)
            if isinstance(existing_details, dict):
                existing_steps = existing_details.get("steps", [])
            elif isinstance(existing_details, list):
                existing_steps = existing_details
            else:
                existing_steps = []

            matched_step = None
            for s in existing_steps:
                s_order = s.get("step_order")
                if s_order is None or s_order == "":
                    s_order = s.get("Step Order")
                try:
                    if s_order is not None and int(s_order) == int(step_number):
                        matched_step = s
                        break
                except (ValueError, TypeError):
                    if str(s_order) == str(step_number):
                        matched_step = s
                        break

            payload: Dict[str, Any] = {
                "Parent Item": [parent_id],
                "Step Order": step_number,
                "Description": instruction_text,
                "Set Index": effective_set
            }
            if step_title:
                payload["Action"] = step_title
            if tolling_items is not None:
                payload["Toll Map"] = json.dumps(tolling_items)

            if matched_step:
                step_id = matched_step["id"]
                updated = client.update_instruction(step_id, payload)
                return json.dumps({
                    "message": f"Updated Step #{step_number} (ID: {step_id}) for {target.get('Part Number')}",
                    "step": updated
                }, indent=2)
            else:
                created = client.create_instruction(payload)
                return json.dumps({
                    "message": f"Created Step #{step_number} for {target.get('Part Number')}",
                    "step": created
                }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to create/update WI step: {str(e)}"})

    # =========================================================================
    # TOOLS - INVENTORY & STOCK REQUIREMENTS
    # =========================================================================

    @server.tool()
    def get_inventory_summary(part_number_or_id: str = "", target_build_qty: float = 1.0) -> str:
        """
        Calculate inventory requirements and component demand for building target quantity of an assembly.
        Reads 'Amount of Times' from assembly relations. Blackbox items stop the explosion: the blackbox
        item itself is reported in required parts, but its internal children are not exploded.

        Component Demand vs. Procurement (Purchase Kits):
        - Returns the raw component demand (every terminal child, kits exploded into their children).
        - Kit children (`purchase_kit` items exploded into their sub-parts) are expected to have no unit price;
          a $0 / 0 unit price on a kit child is by design and is NOT a data-quality problem.
        - For procurement, the purchase kit lines themselves are what get ordered (not the individual children).
          When a kit is received, its child components increment in inventory as untracked stock at their
          assembly amount.
        - To view items grouped by kit for purchasing, inspect the `purchase_kit` flag on items/BOM nodes
          or refer to the generated XLSX inventory report (`inventory_report.py`), which collapses kit children
          into their parent kit lines.

        Args:
            part_number_or_id: Part Number or Row ID of the assembly to build.
            target_build_qty: Target quantity of assemblies to produce (default 1.0).
        """
        try:
            if not part_number_or_id:
                # Return general top level items summary
                top_items = client.get_top_level_items(limit=20)
                return json.dumps({
                    "summary": "Top-level production assemblies available for build calculation",
                    "assemblies": top_items
                }, indent=2)

            target = _find_item_by_pn_or_id(client, part_number_or_id)
            if not target:
                return json.dumps({"error": f"Assembly '{part_number_or_id}' not found."})

            try:
                target_build_qty = float(target_build_qty)
            except (ValueError, TypeError):
                return json.dumps({"error": "target_build_qty must be a number."})
            if target_build_qty <= 0:
                return json.dumps({
                    "error": f"target_build_qty must be greater than 0 (got {target_build_qty:g})."
                })

            item_id = target["id"]

            # Compute requirements
            bom_rows = client._get_all_rows(client.table_bom)
            assembly_rows = client._get_all_rows(client.table_assembly)
            bom_map = {r["id"]: r for r in bom_rows}

            parent_to_children = {}
            for edge in assembly_rows:
                child_link = edge.get("Contains")
                parent_link = edge.get("Item")
                cid = child_link[0]["id"] if isinstance(child_link, list) and child_link else (child_link.get("id") if isinstance(child_link, dict) else child_link)
                pid = parent_link[0]["id"] if isinstance(parent_link, list) and parent_link else (parent_link.get("id") if isinstance(parent_link, dict) else parent_link)
                if pid and cid:
                    qty = edge.get("Amount of Times")
                    if qty is None or qty == "":
                        qty = edge.get("Quantity", 1)
                    try:
                        qty = float(qty) if qty is not None else 1.0
                    except (ValueError, TypeError):
                        qty = 1.0
                    parent_to_children.setdefault(pid, []).append({"child_id": cid, "quantity": qty})

            flat_requirements = {}

            def explode(current_id, current_qty):
                rels = parent_to_children.get(current_id, [])
                if not rels:
                    flat_requirements[current_id] = flat_requirements.get(current_id, 0) + current_qty
                    return

                part = bom_map.get(current_id, {})
                if bool(part.get("Blackbox", False)):
                    flat_requirements[current_id] = flat_requirements.get(current_id, 0) + current_qty
                    return

                for rel in rels:
                    explode(rel["child_id"], rel["quantity"] * current_qty)

            explode(item_id, target_build_qty)

            # Group flat requirements by Part Number to aggregate across revisions
            pn_groups = defaultdict(list)
            for cid, qty in flat_requirements.items():
                c_part = bom_map.get(cid, {})
                pn = c_part.get("Part Number")
                key = str(pn).strip() if pn else f"ID-{cid}"
                pn_groups[key].append((cid, qty, c_part))

            exploded_list = []
            total_est_cost = 0.0
            for pn_key, entries in pn_groups.items():
                sorted_entries = sorted(
                    entries,
                    key=lambda e: _lifecycle_state_rank(_extract_lifecycle_state(e[2]))
                )
                rep_cid, _, rep_part = sorted_entries[0]
                total_qty = sum(e[1] for e in entries)

                p_unit = rep_part.get("Price per unit") or rep_part.get("Price") or 0.0
                try:
                    p_unit = float(p_unit)
                except (ValueError, TypeError):
                    p_unit = 0.0
                subtotal = p_unit * total_qty
                total_est_cost += subtotal

                rep_name, _ = _extract_name_desc(rep_part)
                line = {
                    "part_id": rep_cid,
                    "part_number": rep_part.get("Part Number"),
                    "name": rep_name,
                    "category": rep_part.get("Category"),
                    "required_quantity": total_qty,
                    "unit_price": p_unit,
                    "subtotal_cost": round(subtotal, 4)
                }
                if len(entries) > 1:
                    collapsed = []
                    for e in sorted_entries:
                        fpn = e[2].get("Full PN") or (f"{e[2].get('Part Number')} Rev.{e[2].get('Revision')}" if e[2].get("Revision") else e[2].get("Part Number"))
                        if fpn and fpn not in collapsed:
                            collapsed.append(fpn)
                    line["collapsed_revisions"] = collapsed

                exploded_list.append(line)

            inv_target_name, _ = _extract_name_desc(target)
            return json.dumps({
                "assembly": {
                    "id": item_id,
                    "part_number": target.get("Part Number"),
                    "name": inv_target_name,
                    "target_build_qty": target_build_qty
                },
                "total_unique_terminal_parts": len(exploded_list),
                "total_estimated_unit_bom_cost": round(total_est_cost, 2),
                "required_parts": exploded_list
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to compute inventory summary: {str(e)}"})

    # =========================================================================
    # TOOLS - REFERENCE DATA & METADATA
    # =========================================================================

    @server.tool()
    def list_pn_categories() -> str:
        """
        List all defined Part Number (PN) categories. Returns a mapping of 2-digit category prefix to {name, color}.
        """
        try:
            rules = client.rules if hasattr(client, "rules") else []
            return json.dumps({"categories": rules}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list PN categories: {str(e)}"})

    @server.tool()
    def list_item_lifecycle_states() -> str:
        """
        List the authoritative item lifecycle states from the database. Note that 'Engineerig Use' is the literal stored value (database spelling).
        """
        try:
            states = client.states_map if hasattr(client, "states_map") and client.states_map else {}
            return json.dumps({"lifecycle_states": states}, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list lifecycle states: {str(e)}"})

    @server.tool()
    def list_manufacturers_and_suppliers() -> str:
        """
        List all registered manufacturers and suppliers in the directory.
        """
        try:
            mfgs = client.get_manufacturers() if hasattr(client, "get_manufacturers") else []
            sups = client.get_suppliers() if hasattr(client, "get_suppliers") else []
            return json.dumps({
                "manufacturers_count": len(mfgs),
                "manufacturers": mfgs,
                "suppliers_count": len(sups),
                "suppliers": sups
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list manufacturers and suppliers: {str(e)}"})

    # =========================================================================
    # RESOURCES
    # =========================================================================

    @server.resource("era://items/{part_number}")
    def item_resource(part_number: str) -> str:
        """Provides direct JSON metadata for an item by Part Number."""
        return get_item_details(part_number)

    @server.resource("era://bom/{part_number}")
    def bom_resource(part_number: str) -> str:
        """Provides direct JSON BOM hierarchy tree for an assembly."""
        return get_bom_tree(part_number)

    @server.resource("era://wi/{part_number}")
    def wi_resource(part_number: str) -> str:
        """Provides direct JSON Work Instructions for an assembly."""
        return get_work_instructions(part_number)

    @server.resource("era://inventory/{part_number}")
    def inventory_resource(part_number: str) -> str:
        """Provides direct JSON inventory requirement explosion for an assembly."""
        return get_inventory_summary(part_number)

    @server.resource("era://categories")
    def categories_resource() -> str:
        """Provides list of PN category configurations."""
        return list_pn_categories()

    @server.resource("era://states")
    def states_resource() -> str:
        """Provides list of item lifecycle states."""
        return list_item_lifecycle_states()

    # =========================================================================
    # PROMPTS
    # =========================================================================

    @server.prompt()
    def audit_bom_balance(part_number: str) -> str:
        """
        Interactive audit prompt to verify BOM equilibrium and diagnose tolling discrepancies for an assembly.
        """
        return (
            f"Please conduct an in-depth BOM balance audit for assembly '{part_number}'.\n"
            f"1. Use the `audit_bom_balance` tool to inspect child components and Work Instruction tolling.\n"
            f"2. Identify any over-tolled or under-tolled parts.\n"
            f"3. Verify whether all instruction steps include required assembly photos.\n"
            f"4. Recommend specific step modifications to restore full BOM equilibrium."
        )

    @server.prompt()
    def create_assembly_wi(part_number: str) -> str:
        """
        Prompt template to guide authoring standard operating Work Instructions for an assembly.
        """
        return (
            f"Please assist in creating or refining Work Instructions for assembly '{part_number}'.\n"
            f"1. Call `get_bom_tree` or `get_item_details` to understand all sub-components and fasteners.\n"
            f"2. Draft logical, step-by-step assembly instructions covering prep, mechanical mounting, wiring/routing, and QA test.\n"
            f"3. Allocate the appropriate tolling quantities per step using `create_or_update_wi_step`.\n"
            f"4. Run `audit_bom_balance` to guarantee zero component leakage."
        )

    return server


# =============================================================================
# RUNNER HELPERS
# =============================================================================

def create_mcp_sse_app(
    server: MCPServer,
    host: str = "127.0.0.1",
    auth_token: Optional[str] = None,
    enable_dns_rebinding_protection: bool = False
) -> Starlette:
    """
    Creates and configures the Starlette SSE application with authentication middleware.
    """
    token = auth_token if auth_token is not None else os.getenv("MCP_AUTH_TOKEN", "")
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=enable_dns_rebinding_protection)
    starlette_app = server.sse_app(
        host=host,
        transport_security=sec
    )
    if token and token.strip():
        starlette_app.add_middleware(MCPAuthMiddleware, token=token.strip())
        logger.info("MCP SSE Server authentication ENABLED (Token configured).")
    else:
        logger.info("MCP SSE Server authentication DISABLED (No MCP_AUTH_TOKEN set).")
    return starlette_app


def create_mcp_app(
    server: MCPServer,
    host: str = "127.0.0.1",
    auth_token: Optional[str] = None,
    enable_dns_rebinding_protection: bool = False,
    jwks_url: Optional[str] = None,
    resource_url: Optional[str] = None
) -> Starlette:
    """
    Creates a unified Starlette application hosting both SSE and StreamableHTTP transports.
    Also hosts the OAuth protected resource metadata and health endpoints.
    """
    token = auth_token if auth_token is not None else os.getenv("MCP_AUTH_TOKEN", "")
    sec = TransportSecuritySettings(enable_dns_rebinding_protection=enable_dns_rebinding_protection)

    # Configure Auth Settings for SDK
    if jwks_url and resource_url:
        issuer_url = jwks_url.rsplit("/.well-known", 1)[0]
        from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
        server.settings.auth = AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_url,
            validate_token_resource=True,
            client_registration_options=ClientRegistrationOptions(enabled=False)
        )
        server._token_verifier = ERATokenVerifier(token, jwks_url, resource_url)

    sse = server.sse_app(host=host, transport_security=sec)
    streamable = server.streamable_http_app(streamable_http_path="/mcp", transport_security=sec, host=host)

    from starlette.routing import Mount, Route
    from starlette.responses import PlainTextResponse

    async def health(request):
        return PlainTextResponse("OK")

    # Merge routes rather than nesting Mount("/") twice: the first mount would
    # otherwise capture every path and /mcp would never be reached.
    sse_paths = {getattr(r, "path", None) for r in sse.routes}
    merged_routes = list(sse.routes)
    for r in streamable.routes:
        if getattr(r, "path", None) not in sse_paths:
            merged_routes.append(r)
    merged_routes.append(Route("/health", health))
    


    import contextlib

    @contextlib.asynccontextmanager
    async def unified_lifespan(app):
        # The streamable app needs its session-manager lifespan; the SSE app has none.
        async with streamable.router.lifespan_context(streamable):
            yield

    unified_app = Starlette(routes=merged_routes, lifespan=unified_lifespan)

    # Flattening the routes into a new Starlette app drops the middleware that
    # sse_app() installed -- notably the SDK's AuthenticationMiddleware, which is
    # what populates scope["user"]. Without it the SDK's RequireAuthMiddleware
    # rejects every request with 401 "Authentication required", even when a
    # valid token is presented.
    # Re-apply them, preserving outer->inner order (add_middleware prepends).
    for m in reversed(sse.user_middleware):
        unified_app.add_middleware(m.cls, **m.kwargs)

    metadata_url = None
    if resource_url:
        from mcp.server.auth.routes import build_resource_metadata_url
        metadata_url = build_resource_metadata_url(resource_url)

    unified_app.add_middleware(MCPAuthMiddleware, token=token, resource_metadata_url=metadata_url)
    
    from starlette.middleware.cors import CORSMiddleware
    unified_app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_methods=["GET", "POST", "OPTIONS", "HEAD", "DELETE"],
        allow_headers=["*"],
        expose_headers=["WWW-Authenticate", "Mcp-Session-Id", "Content-Type"],
        max_age=86400,
    )
    return unified_app


def run_mcp_stdio(client: Optional[BaserowClient] = None) -> None:
    """Runs the MCP server over standard input/output (stdio transport)."""
    server = create_mcp_server(client)
    server.run(transport="stdio")


def run_mcp_sse(
    host: str = "127.0.0.1",
    port: int = 8001,
    client: Optional[BaserowClient] = None,
    auth_token: Optional[str] = None
) -> None:
    """Runs the unified MCP server (SSE and StreamableHTTP) with authentication support."""
    import uvicorn
    server = create_mcp_server(client)
    
    jwks_url = os.getenv("OAUTH_ISSUER_URL")
    if jwks_url:
        jwks_url = f"{jwks_url.rstrip('/')}/.well-known/jwks.json"
    resource_url = os.getenv("MCP_RESOURCE_URL", f"https://{host}:{port}")

    app = create_mcp_app(
        server, 
        host=host, 
        auth_token=auth_token,
        jwks_url=jwks_url,
        resource_url=resource_url
    )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=server.settings.log_level.lower(),
    )
    uvicorn_server = uvicorn.Server(config)
    asyncio.run(uvicorn_server.serve())


def start_mcp_background(
    host: str = "127.0.0.1",
    port: int = 8001,
    client: Optional[BaserowClient] = None,
    auth_token: Optional[str] = None
) -> threading.Thread:
    """
    Starts the unified MCP server in a background daemon thread.
    Returns the started Thread object.
    """
    def _runner():
        run_mcp_sse(host=host, port=port, client=client, auth_token=auth_token)

    thread = threading.Thread(
        target=_runner,
        name="ERA-MCP-Server-Thread",
        daemon=True
    )
    thread.start()
    logger.info(f"ERA MCP Server (SSE+StreamableHTTP) started in background on http://{host}:{port}")
    return thread
