"""Pure helpers for execution records: framed-stream parsing, symbol/address resolution
and capped reads. No Docker, no database, no module state — unit-testable on their own.
Re-exported from app.services.execution for existing callers."""
from __future__ import annotations

import base64
import json
from pathlib import Path


def parse_framed_stream(data: bytes) -> dict:
    """Parse the M8-G0 protected trace channel (harness stdout frames).

    Returns per-channel record lists plus integrity verdict. Integrity is
    CONSISTENT only when: a meta frame exists, it is the LAST frame, no foreign
    frames appeared, the stdout cap was not hit, and the meta's authoritative
    event count equals the number of trace frames received. Anything else is
    SUSPECT and never silently promoted (F-M7-01)."""
    res: dict = {"trace": [], "memory": [], "process": [], "stdout": b"",
                 "meta": None, "meta_last": False, "foreign": 0,
                 "integrity": "SUSPECT"}
    lines = data.splitlines()
    for i, raw in enumerate(lines):
        try:
            fr = json.loads(raw)
            ch = fr.get("c")
        except (ValueError, UnicodeDecodeError):
            res["foreign"] += 1
            continue
        try:
            if ch == "t":
                res["trace"].append(
                    json.dumps(fr["j"], separators=(",", ":")).encode())
            elif ch == "m":
                res["memory"].append(
                    json.dumps(fr["j"], separators=(",", ":")).encode())
            elif ch == "p":
                res["process"].append(
                    json.dumps(fr["j"], separators=(",", ":")).encode())
            elif ch == "out":
                res["stdout"] = base64.b64decode(fr["j"]["b64"], validate=True)
            elif ch == "meta":
                res["meta"] = fr.get("j") if isinstance(fr.get("j"), dict) else fr
                res["meta_last"] = i == len(lines) - 1
            else:
                res["foreign"] += 1
        except (KeyError, TypeError, ValueError):
            res["foreign"] += 1
    meta = res["meta"] or {}
    counts_ok = isinstance(meta.get("events"), int) and \
        meta["events"] == len(res["trace"])
    if (res["meta"] is not None and res["meta_last"] and res["foreign"] == 0
            and counts_ok):
        res["integrity"] = "CONSISTENT"
    return res


def _parse_symbols(symbols_txt: Path) -> list[tuple[int, int, str]]:
    """nm -S lines: ADDR SIZE type name → [(start, end, name)] for functions."""
    out = []
    for line in symbols_txt.read_text("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] in ("t", "T"):
            try:
                start = int(parts[0], 16)
                size = int(parts[1], 16)
                out.append((start, start + size, parts[3].strip()))
            except (ValueError, IndexError):
                continue
    return out


def _is_event_line(raw: bytes) -> bool:
    """A C-shim trace EVENT line: everything except the meta/trace_meta records."""
    try:
        rec = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return False
    return rec.get("kind") not in ("meta", "trace_meta")


def _resolve_c_addr(raw: bytes, symbols: list[tuple[int, int, str]]) -> bytes:
    try:
        rec = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    addr = rec.get("addr")
    if addr is None:
        return raw
    for start, end, name in symbols:
        if start <= addr < end:
            rec["fn"] = name
            break
    else:
        rec["fn"] = f"0x{addr:x}"
    return json.dumps(rec).encode()


def _meta_flags(meta_payloads: list[dict]) -> dict:
    """In-band truncation markers written by the shim/harness (trusted: they are
    emitted by the pinned container code, not by user source)."""
    return {
        "trace": any(p.get("truncated") is True for p in meta_payloads),
        "stdout": any(p.get("stdout_truncated") is True for p in meta_payloads),
        "stderr": any(p.get("stderr_truncated") is True for p in meta_payloads),
    }


def _read_capped(path: Path, cap: int) -> tuple[bytes, bool]:
    """Read at most `cap` bytes from a container-written file. Container output is
    untrusted: the orchestrator never trusts a file's size (M4QA-02/03)."""
    if not path.is_file():
        return b"", False
    with path.open("rb") as f:
        data = f.read(cap + 1)
    return data[:cap], len(data) > cap
