"""Stage 1-B/Stage 1-F hostile archive security tests (zip slip, symlinks, bombs, collisions)."""
import io
import zipfile

import pytest

from app.services.archive import ArchiveError, extract_tar_gz, extract_zip


def zbuild(entries, mode_flags=None):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, (name, data) in enumerate(entries.items()):
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_DEFLATED
            if mode_flags and name in mode_flags:
                zi.create_system = 3
                zi.external_attr = mode_flags[name] << 16
            zf.writestr(zi, data)
    return buf.getvalue()


def test_zip_slip_traversal_rejected():
    res = extract_zip(zbuild({"good.py": b"x=1\n", "../evil.txt": b"pwned"}))
    assert "good.py" in res.files and "../evil.txt" not in res.files
    assert any(r["reason_code"] == "PATH_TRAVERSAL" for r in res.rejected)


def test_zip_absolute_and_drive_and_backslash_rejected():
    res = extract_zip(zbuild({"/etc/passwd.py": b"a", "C:/evil.py": b"b", "a\\b.py": b"c",
                              "ok.py": b"d"}))
    codes = {r["reason_code"] for r in res.rejected}
    assert "PATH_ABSOLUTE" in codes and "PATH_DRIVE_PREFIX" in codes
    assert "PATH_BACKSLASH" in codes
    assert set(res.files) == {"ok.py"}


def test_zip_symlink_entry_rejected():
    res = extract_zip(zbuild({"link.py": b"target", "ok.py": b"x=1\n"},
                             mode_flags={"link.py": 0o120777}))
    assert any(r["reason_code"] == "NON_REGULAR_ENTRY" for r in res.rejected)
    assert "link.py" not in res.files


def _set_encrypted_flag(data: bytes) -> bytes:
    """Flip the 'encrypted' bit in local + central headers of a zip built by zipfile
    (zipfile does not let us write flag_bits directly for writestr entries)."""
    out = bytearray(data)
    i = 0
    while True:
        i = out.find(b"PK\x03\x04", i)          # local file header: flags at +6
        if i < 0:
            break
        out[i + 6] |= 0x01
        i += 4
    i = 0
    while True:
        i = out.find(b"PK\x01\x02", i)          # central directory: flags at +8
        if i < 0:
            break
        out[i + 8] |= 0x01
        i += 4
    return bytes(out)


def test_zip_encrypted_entry_rejected():
    raw = zbuild({"secret.py": b"x=1"})
    res = extract_zip(_set_encrypted_flag(raw))
    assert any(r["reason_code"] == "ENCRYPTED_ENTRY" for r in res.rejected)
    assert res.files == {}


def test_zip_ratio_bomb_rejected():
    big = b"0" * (30 * 1024 * 1024)  # compresses to ~30KB → ratio >> 100
    with pytest.raises(ArchiveError) as ei:
        extract_zip(zbuild({"zeros.txt": big}))
    assert ei.value.code in ("BOMB_RATIO", "EXPANSION_CAP")


def test_zip_nested_archive_and_binary_rejected():
    inner = zbuild({"x.py": b"y=2\n"})
    res = extract_zip(zbuild({"inner.zip": inner, "blob.py": b"\x00\x01binary",
                              "app.exe": b"MZ...", "ok.py": b"z=3\n"}))
    codes = {r["reason_code"] for r in res.rejected}
    assert "ARCHIVE_OR_BINARY_SUFFIX" in codes and "BINARY_NOT_SOURCE" in codes
    assert set(res.files) == {"ok.py"}


def test_zip_case_and_unicode_collision_rejected():
    nfc = "caf\u00e9.py"
    nfd = "cafe\u0301.py"
    res = extract_zip(zbuild({"A.py": b"1", "a.py": b"2", nfc: b"3", nfd: b"4"}))
    # A.py and NFC café survive; a.py and NFD café are recorded collisions.
    assert len(res.files) == 2
    assert sum(1 for r in res.rejected if r["reason_code"] == "COLLISION") == 2


def test_zip_too_deep_rejected():
    deep = "/".join(["d"] * 13) + ".py"
    res = extract_zip(zbuild({deep: b"x=1\n", "ok.py": b"x=1\n"}))
    assert any(r["reason_code"] == "PATH_TOO_DEEP" for r in res.rejected)


def test_tar_gz_symlink_and_traversal_rejected():
    import tarfile
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        import io as _io
        ti = tarfile.TarInfo("repo-abc/../../evil.py")
        ti.size = 4
        tf.addfile(ti, _io.BytesIO(b"x=1\n"))
        ln = tarfile.TarInfo("repo-abc/link.py")
        ln.type = tarfile.SYMTYPE
        ln.linkname = "/etc/passwd"
        tf.addfile(ln)
        ok = tarfile.TarInfo("repo-abc/ok.py")
        ok.size = 4
        tf.addfile(ok, _io.BytesIO(b"x=1\n"))
    res = extract_tar_gz(buf.getvalue())
    assert set(res.files) == {"ok.py"}
    codes = {r["reason_code"] for r in res.rejected}
    assert "PATH_TRAVERSAL" in codes and "NON_REGULAR_ENTRY" in codes


def test_tar_gz_strips_common_prefix():
    import tarfile, io as _io
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in (("repo-sha123/src/a.py", b"a=1\n"), ("repo-sha123/b.c", b"int x;\n")):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tf.addfile(ti, _io.BytesIO(data))
    res = extract_tar_gz(buf.getvalue())
    assert set(res.files) == {"src/a.py", "b.c"}


def test_malformed_archive_typed_error():
    with pytest.raises(ArchiveError) as ei:
        extract_zip(b"not a zip at all")
    assert ei.value.code == "MALFORMED_ARCHIVE"
