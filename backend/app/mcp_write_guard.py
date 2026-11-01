"""
mcp_write_guard.py
Dry-run, audit-log and revert support for the ERA MCP write tools.

Every MCP write tool runs inside a WriteScope. The MCP server talks to Baserow through a
GuardedClient that proxies the real BaserowClient. Inside a scope, each write method call
(update_item, create_assembly, update_instruction, ...) is either:
- recorded and NOT executed (dry_run=True): the tool still runs end to end, so its response
  shows what it would have done, and the scope returns the planned writes with a
  before/after diff; or
- executed and recorded with its before values: the records are appended to an
  append-only JSONL audit log under one change_id, which revert_change can undo.
"""

import os
import json
import uuid
import logging
import functools
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# method name -> (client attribute holding the table id, operation kind)
WRITE_METHODS: Dict[str, tuple] = {
    "create_bom_item": ("table_bom", "create"),
    "update_item": ("table_bom", "update"),
    "delete_item": ("table_bom", "delete"),
    "create_assembly": ("table_assembly", "create"),
    "update_assembly": ("table_assembly", "update"),
    "delete_assembly": ("table_assembly", "delete"),
    "create_instruction": ("table_instructions", "create"),
    "update_instruction": ("table_instructions", "update"),
    "delete_instruction_step": ("table_instructions", "delete"),
    "create_manufacturer": ("table_manufacturers", "create"),
    "update_manufacturer": ("table_manufacturers", "update"),
    "delete_manufacturer": ("table_manufacturers", "delete"),
    "create_supplier": ("table_suppliers", "create"),
    "update_supplier": ("table_suppliers", "update"),
    "delete_supplier": ("table_suppliers", "delete"),
    "create_contact": ("table_contacts", "create"),
    "update_contact": ("table_contacts", "update"),
    "delete_contact": ("table_contacts", "delete"),
    "add_revision": ("table_bom", "revision"),
    "upload_file": (None, "upload"),
    "upload_file_via_url": (None, "upload"),
}

# update_assembly takes keyword arguments rather than a field payload.
_ASSEMBLY_KWARG_FIELDS = {
    "quantity": "Amount of Times",
    "length": "Measurement",
    "pcb_symbol": "PCB Symbol",
    "parent_id": "Item",
    "child_id": "Contains",
    "uom_id": "Measurement UoM",
}

_current_scope: contextvars.ContextVar = contextvars.ContextVar("era_mcp_write_scope", default=None)


def audit_log_path() -> Optional[str]:
    """Audit log location: $ERA_AUDIT_LOG, else audit_log.jsonl in the backups volume. 'off' disables it."""
    configured = os.getenv("ERA_AUDIT_LOG", "").strip()
    if configured.lower() in ("off", "none", "0", "false"):
        return None
    if configured:
        return configured
    from app.backup_manager import get_backups_dir
    return os.path.join(get_backups_dir(), "audit_log.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_writable(value: Any) -> Any:
    """
    Converts a value read from Baserow into the shape Baserow accepts on write:
    link rows -> [ids], files -> [{"name", "visible_name"}], single select -> option id.
    """
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict) and "name" in v and ("mime_type" in v or "visible_name" in v):
                out.append({"name": v["name"], "visible_name": v.get("visible_name")})
            elif isinstance(v, dict) and "id" in v:
                out.append(v["id"])
            else:
                out.append(v)
        return out
    if isinstance(value, dict) and "id" in value and "value" in value:
        return value["id"]
    return value


def _changed_fields(method: str, args: tuple, kwargs: dict) -> Optional[Dict[str, Any]]:
    """The field payload an update call writes, or None when it is not a plain field update."""
    if method == "update_assembly":
        names = ["edge_id", "quantity", "length", "pcb_symbol", "parent_id", "child_id", "uom_id"]
        bound = dict(zip(names, args))
        bound.update(kwargs)
        out = {}
        for k, field in _ASSEMBLY_KWARG_FIELDS.items():
            v = bound.get(k)
            if v is not None:
                out[field] = v
        return out
    payload = args[1] if len(args) > 1 else kwargs.get("data")
    return dict(payload) if isinstance(payload, dict) else None


class WriteScope:
    """Collects the writes of one MCP tool call."""

    def __init__(self, tool: str, args: Dict[str, Any], dry_run: bool):
        self.tool = tool
        self.args = args
        self.dry_run = dry_run
        self.change_id = f"chg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.writes: List[Dict[str, Any]] = []
        self._fake_ids = 0

    def next_fake_id(self) -> str:
        self._fake_ids += 1
        return f"dry_run_new_{self._fake_ids}"


class GuardedClient:
    """Proxy over BaserowClient that routes write methods through the active WriteScope."""

    def __init__(self, real: Any):
        object.__setattr__(self, "_real", real)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._real, name)
        if name in WRITE_METHODS and callable(attr):
            return functools.partial(self._guarded_call, name, attr)
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._real, name, value)

    def _table(self, method: str) -> Optional[str]:
        table_attr = WRITE_METHODS[method][0]
        return str(getattr(self._real, table_attr, "")) if table_attr else None

    def _snapshot(self, table: Optional[str], row_id: Any) -> Optional[Dict[str, Any]]:
        if table is None or row_id is None or str(row_id).startswith("dry_run_"):
            return None
        try:
            row = self._real.get_row(table, row_id)
            return row if isinstance(row, dict) else None
        except Exception as e:
            logger.debug(f"Could not snapshot row {row_id} of table {table}: {e}")
            return None

    def _guarded_call(self, method: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        scope: Optional[WriteScope] = _current_scope.get()
        if scope is None:
            return func(*args, **kwargs)

        table = self._table(method)
        kind = WRITE_METHODS[method][1]
        record: Dict[str, Any] = {"method": method, "kind": kind, "table": table}

        if kind == "update":
            row_id = args[0] if args else kwargs.get("item_id") or kwargs.get("step_id") or kwargs.get("edge_id")
            after = _changed_fields(method, args, kwargs) or {}
            before_row = self._snapshot(table, row_id)
            record.update({
                "row_id": row_id,
                "after": after,
                "before": {k: before_row.get(k) for k in after} if before_row is not None else None,
            })
            if scope.dry_run:
                scope.writes.append(record)
                merged = dict(before_row or {"id": row_id})
                merged.update(after)
                merged["_dry_run"] = True
                return merged
        elif kind == "delete":
            row_id = args[0] if args else next(iter(kwargs.values()), None)
            record.update({"row_id": row_id, "before": self._snapshot(table, row_id)})
            if scope.dry_run:
                scope.writes.append(record)
                return True
        elif kind == "create":
            record["after"] = args[0] if args and isinstance(args[0], dict) else {
                "args": list(args), **kwargs
            }
            if scope.dry_run:
                fake_id = scope.next_fake_id()
                record["row_id"] = fake_id
                scope.writes.append(record)
                created = dict(record["after"]) if isinstance(record["after"], dict) else {}
                created.update({"id": fake_id, "_dry_run": True})
                return created
        elif kind == "upload":
            label = args[0] if args else kwargs.get("filename") or kwargs.get("file_url")
            record["after"] = {"source": label}
            if scope.dry_run:
                scope.writes.append(record)
                visible = str(label).rstrip("/").split("/")[-1] or "file"
                return {"name": f"dry_run_{visible}", "visible_name": visible, "size": None,
                        "mime_type": None, "_dry_run": True}
        elif kind == "revision":
            item_id = args[0] if args else kwargs.get("item_id")
            old_state = kwargs.get("old_state", args[1] if len(args) > 1 else "EOL")
            try:
                plan = self._real.plan_revision(item_id)
            except Exception as e:
                if scope.dry_run:
                    raise
                logger.warning(f"Could not plan revision of row {item_id} for the audit log: {e}")
                plan = {}
            plan = plan if isinstance(plan, dict) else {}
            record.update({
                "row_id": item_id,
                "old_state": old_state,
                "old_state_before": to_writable(plan.get("old_state_value")),
                "repointed_edge_ids": plan.get("repointed_edge_ids", []),
            })
            if scope.dry_run:
                record["new_revision"] = plan.get("next_revision")
                scope.writes.append(record)
                return {
                    "id": scope.next_fake_id(),
                    "Part Number": plan.get("part_number"),
                    "Revision": plan.get("next_revision"),
                    "Full PN": f"{plan.get('part_number')} Rev.{plan.get('next_revision')}",
                    "edges_repointed": len(plan.get("repointed_edge_ids", [])),
                    "children_copied": len(plan.get("copied_child_edge_ids", [])),
                    "_dry_run": True,
                }

        result = func(*args, **kwargs)
        if kind in ("create", "revision") and isinstance(result, dict):
            record["new_row_id"] = result.get("id")
        if kind == "upload" and isinstance(result, dict):
            record["after"]["name"] = result.get("name")
        scope.writes.append(record)
        return result


def _append_audit(entry: Dict[str, Any]) -> bool:
    path = audit_log_path()
    if not path:
        return False
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        return True
    except Exception as e:
        logger.error(f"Could not append to MCP audit log '{path}': {e}")
        return False


def read_audit_log() -> List[Dict[str, Any]]:
    path = audit_log_path()
    if not path or not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _diff(write: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, JSON-safe description of one write for tool responses."""
    out = {k: write[k] for k in ("method", "kind", "table", "row_id", "new_row_id", "new_revision") if k in write}
    before = write.get("before")
    after = write.get("after")
    if write.get("kind") == "update" and isinstance(after, dict):
        out["changes"] = {
            k: {"before": (before or {}).get(k) if before is not None else "<unknown>", "after": v}
            for k, v in after.items()
        }
    elif write.get("kind") == "delete":
        out["before"] = before
    elif after is not None:
        out["after"] = after
    if write.get("kind") == "revision":
        out["repointed_edge_ids"] = write.get("repointed_edge_ids", [])
    return out


def _loggable(value: Any) -> Any:
    """Keep audit entries small: long strings (e.g. file_base64) are replaced by their length."""
    if isinstance(value, str) and len(value) > 2000:
        return f"<{len(value)} characters omitted>"
    return value


def write_tool(tool_name: str):
    """
    Decorator for MCP write tools. The tool must declare `dry_run: bool = False`.
    The wrapped function keeps its signature (via functools.wraps) for MCP schema generation.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            dry_run = bool(kwargs.get("dry_run", False))
            scope = WriteScope(tool_name, {k: _loggable(v) for k, v in kwargs.items() if k != "dry_run"}, dry_run)
            token = _current_scope.set(scope)
            try:
                raw = fn(*args, **kwargs)
            finally:
                _current_scope.reset(token)
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                return raw

            if dry_run:
                return json.dumps({
                    "dry_run": True,
                    "message": "Dry run: nothing was written. 'would_write' lists the writes this call would make.",
                    "would_write": [_diff(w) for w in scope.writes],
                    "result_preview": parsed,
                }, indent=2, default=str)

            if not scope.writes:
                return raw
            entry = {
                "change_id": scope.change_id,
                "timestamp": _now(),
                "tool": tool_name,
                "args": scope.args,
                "writes": scope.writes,
            }
            logged = _append_audit(entry)
            if isinstance(parsed, dict):
                if logged:
                    parsed["change_id"] = scope.change_id
                parsed["writes_count"] = len(scope.writes)
                return json.dumps(parsed, indent=2, default=str)
            return raw
        return wrapper
    return decorator


def summarize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "change_id": entry.get("change_id"),
        "timestamp": entry.get("timestamp"),
        "tool": entry.get("tool"),
        "args": entry.get("args"),
        "reverted_by": entry.get("reverted_by"),
        "writes": [_diff(w) for w in entry.get("writes", [])],
    }


def revert_entry(real_client: Any, entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Undoes the writes of one audit entry in reverse order, using the raw client (not logged as
    guarded writes). Updates restore their before values, creates delete the created row and
    revisions are unwound. Deletes and uploads cannot be undone and are reported as skipped.
    """
    reverted: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for w in reversed(entry.get("writes", [])):
        kind = w.get("kind")
        table = w.get("table")
        try:
            if kind == "update":
                before = w.get("before")
                if before is None:
                    skipped.append({**_diff(w), "reason": "before values were not captured"})
                    continue
                payload = {k: to_writable(v) for k, v in before.items()}
                real_client.patch_row(table, w["row_id"], payload)
                reverted.append({"method": w["method"], "row_id": w["row_id"], "restored": list(payload)})
            elif kind == "create":
                new_id = w.get("new_row_id")
                if new_id is None:
                    skipped.append({**_diff(w), "reason": "created row id unknown"})
                    continue
                real_client.delete_row(table, new_id)
                reverted.append({"method": w["method"], "deleted_row_id": new_id})
            elif kind == "revision":
                old_id = w["row_id"]
                new_id = w.get("new_row_id")
                for edge_id in w.get("repointed_edge_ids", []):
                    real_client.patch_row(real_client.table_assembly, edge_id, {"Contains": [old_id]})
                if new_id is not None:
                    for edge in real_client._get_all_rows(real_client.table_assembly):
                        parents = edge.get("Item") or []
                        if any((p.get("id") if isinstance(p, dict) else p) == new_id for p in parents):
                            real_client.delete_row(real_client.table_assembly, edge["id"])
                    real_client.delete_row(table, new_id)
                if w.get("old_state_before") is not None:
                    real_client.patch_row(table, old_id, {"State": w["old_state_before"]})
                reverted.append({"method": "add_revision", "old_row_id": old_id, "deleted_revision_row_id": new_id})
            elif kind == "upload":
                skipped.append({**_diff(w), "reason": "uploaded user-files are left in storage; detaching them is covered by the item update"})
            else:
                skipped.append({**_diff(w), "reason": f"'{kind}' writes cannot be undone; restore from a backup"})
        except Exception as e:
            skipped.append({**_diff(w), "reason": f"revert failed: {e}"})
    return {"reverted": reverted, "skipped": skipped}


def mark_reverted(change_id: str, revert_change_id: str, result: Dict[str, Any]) -> None:
    _append_audit({
        "change_id": revert_change_id,
        "timestamp": _now(),
        "tool": "revert_change",
        "args": {"change_id": change_id},
        "reverts": change_id,
        "result": result,
        "writes": [],
    })
