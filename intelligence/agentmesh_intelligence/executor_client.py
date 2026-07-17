"""Client for the Rust execution & edge layer.

When ``AGENTMESH_EXECUTOR_URL`` is set (and ``httpx`` is installed) the heavy
compute is delegated to the Rust service over HTTP. Otherwise — and on any
network error — it falls back to a pure-Python mirror that implements the exact
same semantics, so the intelligence layer runs standalone and offline. The
fallback also lets the unit tests exercise the whole pipeline without a running
Rust binary.
"""

from __future__ import annotations

import ast
import os
from typing import Any


class ExecutorClient:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or os.environ.get("AGENTMESH_EXECUTOR_URL", "")
        self._httpx = None
        if self.url:
            try:
                import httpx  # type: ignore

                self._httpx = httpx
            except ImportError:
                self._httpx = None

    @property
    def remote(self) -> bool:
        return bool(self.url and self._httpx)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.remote:
            return None
        try:
            async with self._httpx.AsyncClient(timeout=5.0) as client:  # type: ignore
                r = await client.post(self.url.rstrip("/") + path, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception:
            return None  # fall back to local

    async def tokenize(self, text: str) -> dict[str, Any]:
        remote = await self._post("/v1/tokenize", {"text": text})
        if remote is not None:
            return remote
        toks = _local_tokenize(text)
        return {"tokens": toks, "count": len(toks)}

    async def eval(self, expr: str, vars: dict[str, float] | None = None) -> dict[str, Any]:
        vars = vars or {}
        remote = await self._post("/v1/eval", {"expr": expr, "vars": vars})
        if remote is not None:
            return remote
        try:
            value, is_bool = _local_eval(expr, vars)
            return {"ok": True, "value": value, "is_bool": is_bool}
        except Exception as e:
            return {"ok": False, "value": 0.0, "is_bool": False, "error": str(e)}

    async def csv(self, csv: str, op: str, column: str) -> dict[str, Any]:
        remote = await self._post("/v1/csv", {"csv": csv, "op": op, "column": column})
        if remote is not None:
            return remote
        try:
            rows, result = _local_csv(csv, op, column)
            return {"ok": True, "rows": rows, "result": result}
        except Exception as e:
            return {"ok": False, "rows": 0, "result": 0.0, "error": str(e)}


# ---- pure-Python mirrors of the Rust ops (offline fallback) ----------------


def _local_tokenize(text: str) -> list[str]:
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isalpha():
            j = i
            while j < n and text[j].isalpha():
                j += 1
            word = text[i:j]
            out.extend(word[k : k + 4] for k in range(0, len(word), 4))
            i = j
        elif c.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            out.append(text[i:j])
            i = j
        elif c.isspace():
            j = i
            while j < n and text[j].isspace():
                j += 1
            i = j
        else:
            out.append(c)
            i += 1
    return out


_ALLOWED_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Mod: lambda a, b: a % b,
}
_ALLOWED_CMP = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Gt: lambda a, b: a > b,
    ast.Lt: lambda a, b: a < b,
    ast.GtE: lambda a, b: a >= b,
    ast.LtE: lambda a, b: a <= b,
}


def _local_eval(expr: str, vars: dict[str, float]) -> tuple[float, bool]:
    if len(expr) > 4096:
        raise ValueError("expression too long")
    tree = ast.parse(expr, mode="eval").body
    val = _eval_node(tree, vars)
    return (1.0 if val is True else 0.0 if val is False else float(val), isinstance(val, bool))


def _eval_node(node: ast.AST, vars: dict[str, float]) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool)):
            return node.value
        raise ValueError("unsupported constant")
    if isinstance(node, ast.Name):
        if node.id == "true":
            return True
        if node.id == "false":
            return False
        if node.id in vars:
            return vars[node.id]
        raise ValueError(f"unknown variable '{node.id}'")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        a = _eval_node(node.left, vars)
        b = _eval_node(node.right, vars)
        if type(node.op) in (ast.Div, ast.Mod) and b == 0:
            raise ValueError("division by zero")
        return _ALLOWED_BINOPS[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp):
        v = _eval_node(node.operand, vars)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
        if isinstance(node.op, ast.Not):
            return not v
    if isinstance(node, ast.BoolOp):
        vals = [_eval_node(v, vars) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(vals)
        return any(vals)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        a = _eval_node(node.left, vars)
        b = _eval_node(node.comparators[0], vars)
        op = type(node.ops[0])
        if op in _ALLOWED_CMP:
            return _ALLOWED_CMP[op](a, b)
    raise ValueError("unsupported expression")


def _local_csv(csv: str, op: str, column: str) -> tuple[int, float]:
    lines = [ln for ln in csv.splitlines()]
    if not lines:
        raise ValueError("empty csv")
    header = _parse_line(lines[0])
    try:
        idx = [c.strip() for c in header].index(column)
    except ValueError:
        raise ValueError(f"column '{column}' not found")
    rows = 0
    nums: list[float] = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        rows += 1
        fields = _parse_line(ln)
        if idx < len(fields):
            try:
                nums.append(float(fields[idx].strip()))
            except ValueError:
                pass
    if op == "sum":
        result = sum(nums)
    elif op == "mean":
        result = sum(nums) / len(nums) if nums else 0.0
    elif op == "count":
        result = float(rows)
    elif op == "max":
        result = max(nums) if nums else 0.0
    elif op == "min":
        result = min(nums) if nums else 0.0
    else:
        raise ValueError(f"unknown op '{op}'")
    return rows, result


def _parse_line(line: str) -> list[str]:
    out: list[str] = []
    field: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                field.append('"')
                i += 1
            else:
                in_quotes = not in_quotes
        elif c == "," and not in_quotes:
            out.append("".join(field))
            field = []
        else:
            field.append(c)
        i += 1
    out.append("".join(field))
    return out
