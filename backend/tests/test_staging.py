"""Staging bridge tests (ADR-0001): hashing, attacks, atomicity, cleanup, timings."""
import os
import time

import pytest

from app.services import staging
from app.services.staging import StagingError, cleanup_job, snapshot_tree, validate_relative_path, windows_to_wsl_path


@pytest.fixture()
def source_tree(tmp_path):
    src = tmp_path / "src"
    (src / "sub dir").mkdir(parents=True)
    (src / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (src / "sub dir" / "naïve file.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
    return src


def test_snapshot_happy_path_with_spaces_and_nonascii(source_tree, tmp_path):
    root = tmp_path / "jobs"
    m = snapshot_tree(source_tree, "job_ok_1", dest_root=root)
    assert m["file_count"] == 2
    assert (root / "job_ok_1" / "src" / "sub dir" / "naïve file.c").is_file()
    assert len(m["combined_sha256"]) == 64
    assert all(len(f["sha256"]) == 64 for f in m["files"])
    assert not list(root.glob("*.tmp")), "temp staging tree must be renamed away"


def test_snapshot_repeatable_combined_hash(source_tree, tmp_path):
    root = tmp_path / "jobs"
    m1 = snapshot_tree(source_tree, "job_a", dest_root=root)
    m2 = snapshot_tree(source_tree, "job_b", dest_root=root)
    assert m1["combined_sha256"] == m2["combined_sha256"]


def test_rejects_traversal_and_odd_paths():
    for bad in ("../escape.txt", "a/../../etc/passwd", "/etc/passwd", "C:\\boot.ini",
                "a\\b.txt", "a/../b.txt", "", "./x", "x\x00y"):
        with pytest.raises(StagingError):
            validate_relative_path(bad)


def test_rejects_symlink(source_tree, tmp_path):
    (source_tree / "link.txt").symlink_to("/etc/hostname")
    with pytest.raises(StagingError):
        snapshot_tree(source_tree, "job_lnk", dest_root=tmp_path / "jobs")


def test_rejects_oversized_file(source_tree, tmp_path):
    big = source_tree / "big.bin"
    big.write_bytes(b"x" * 1024)
    with pytest.raises(StagingError):
        snapshot_tree(source_tree, "job_big", dest_root=tmp_path / "jobs", max_file_bytes=512)


def test_rejects_bad_job_id_and_missing_source(tmp_path):
    with pytest.raises(StagingError):
        snapshot_tree(tmp_path / "nope", "job_x", dest_root=tmp_path / "jobs")
    with pytest.raises(StagingError):
        snapshot_tree(tmp_path, "../evil", dest_root=tmp_path / "jobs")


def test_cleanup_job(source_tree, tmp_path):
    root = tmp_path / "jobs"
    snapshot_tree(source_tree, "job_del", dest_root=root)
    assert cleanup_job("job_del", dest_root=root) is True
    assert not (root / "job_del").exists()
    assert cleanup_job("job_del", dest_root=root) is False


def test_windows_to_wsl_path_mapping():
    assert windows_to_wsl_path("E:\\ComplieVista\\demos") == __import__("pathlib").Path("/mnt/e/ComplieVista/demos")
    assert str(windows_to_wsl_path("e:\\ComplieVista")) == "/mnt/e/ComplieVista"
    for bad in ("relative/path", "E:", "C:relative\\x"):
        with pytest.raises(StagingError):
            windows_to_wsl_path(bad)


def test_measured_cross_os_copy_timing(tmp_path):
    """Real measured /mnt/e -> ext4 timing vs native read; printed for evidence, no fake numbers."""
    mnt_src = staging.windows_to_wsl_path("E:\\ComplieVista\\demos\\m0")
    if not mnt_src.is_dir():
        pytest.skip("repo not under /mnt/e in this environment")
    t0 = time.perf_counter()
    m = snapshot_tree(mnt_src, f"perf_{int(time.time())}", dest_root=tmp_path / "jobs")
    staged_ms = int((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    n = sum(len(f.read_bytes()) for f in mnt_src.iterdir() if f.is_file())
    direct_ms = int((time.perf_counter() - t0) * 1000)
    print(f"\nMEASURED staging copy of {m['file_count']} files ({m['total_bytes']} B): "
          f"{staged_ms} ms; direct /mnt/e read of same bytes: {direct_ms} ms")
    assert staged_ms >= 0 and direct_ms >= 0 and n == m["total_bytes"]
