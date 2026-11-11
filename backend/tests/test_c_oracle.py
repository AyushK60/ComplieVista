"""Independent Clang oracle tests: re-run the real toolchain, compare to the manifest.

These call clang/objdump again and compare against evidence/m0/c/manifest.json -
the manifest is never compared with itself. Fixture paths are absolute because
clang -E and -dump-tokens embed the path they were given, and the proof script
used absolute paths.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from toolchains.c.proof import parse_dump_tokens  # noqa: E402  (same parser, independent run)

FIXTURE = str(REPO / "demos" / "m0" / "c_fixture.c")
SYNTAX = str(REPO / "demos" / "m0" / "c_syntax_error.c")


def manifest():
    return json.loads(open(REPO / "evidence/m0/c/manifest.json").read())


def clang(argv):
    return subprocess.run(["clang", *argv], capture_output=True, timeout=120)


def test_preprocess_artifact_reproduces_byte_identical():
    m = manifest()
    st = next(s for s in m["stages"] if s["stage"] == "preprocess")
    fresh = clang(["-E", FIXTURE])
    assert fresh.returncode == 0
    assert hashlib.sha256(fresh.stdout).hexdigest() == st["invocation_stdout_sha256"]


def test_token_count_matches_fresh_clang_dump():
    m = manifest()
    st = next(s for s in m["stages"] if s["stage"] == "tokens")
    fresh = clang(["-fsyntax-only", "-Xclang", "-dump-tokens", FIXTURE])
    dump = (fresh.stdout or fresh.stderr).decode("utf-8", "replace")
    toks = parse_dump_tokens(dump)
    assert len(toks) == st["counts"]["tokens"] > 0


def test_ir_functions_present_and_match_manifest():
    m = manifest()
    st = next(s for s in m["stages"] if s["stage"] == "ir")
    fresh = clang(["-S", "-emit-llvm", "-g", "-O0", "-o", "-", FIXTURE])
    ir = fresh.stdout.decode("utf-8", "replace")
    funcs = re.findall(r"^define\s+(?:[^@]*@)([\w.$-]+)", ir, re.M)
    assert len(funcs) == st["counts"]["functions"] == 2
    assert "scale_and_adjust" in funcs and "main" in funcs


def test_syntax_diagnostic_verbatim():
    m = manifest()
    st = next(s for s in m["stages"] if s["stage"] == "diagnostics_syntax")
    fresh = clang(["-fsyntax-only", SYNTAX])
    assert fresh.returncode != 0
    err = fresh.stderr.decode("utf-8", "replace")
    assert "expected ';'" in err and st["availability"] == "AVAILABLE"
    # verbatim tail match (collection-time prefix contains the same absolute path)
    tail = st["diagnostic_verbatim"].split("c_syntax_error.c:", 1)[-1]
    assert tail in err


def test_no_execution_evidence_leak():
    """The object stage must exist as analysis, but no linked executable is committed."""
    m = manifest()
    assert any(s["stage"] == "object" for s in m["stages"])
    committed = [p for p in (REPO / "evidence/m0/c").rglob("*") if p.is_file()]
    assert not [p for p in committed if p.suffix in (".out", ".exe")], "no executables in evidence"
