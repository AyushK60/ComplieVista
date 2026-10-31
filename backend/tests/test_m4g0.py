"""M4 G0 stabilization tests — audit findings F01..F05 (F01/F02/F04 are browser-E2E;
this module covers the backend-verifiable subset F03 + F05)."""
import io
import zipfile

from app.services.graphs import MAX_NODES, _capped


def test_f03_cap_reports_endpoint_drops_in_truncation_flag():
    """Audit F03: an edge dropped by the node cap must set truncated.edges."""
    nodes = [{"id": f"n{i}", "kind": "x"} for i in range(MAX_NODES + 1)]
    edges = [{"source": "n0", "target": f"n{MAX_NODES}"}]  # target beyond the cap
    kept_nodes, kept_edges, trunc = _capped(nodes, edges)
    assert len(kept_nodes) == MAX_NODES
    assert kept_edges == [], "edge to a dropped node must be removed (CV-02 invariant)"
    assert trunc["nodes"] is True
    assert trunc["edges"] is True, "endpoint-filtered drops must set the edges flag"
    assert trunc["edges_omitted_endpoint_filter"] == 1
    assert trunc["edges_omitted_total"] == 1


def test_f03_cap_flag_set_by_edge_cap_also(monkeypatch):
    from app.services import graphs
    monkeypatch.setattr(graphs, "MAX_EDGES", 5)
    nodes = [{"id": f"n{i}", "kind": "x"} for i in range(10)]
    edges = [{"source": f"n{i}", "target": f"n{i + 1}"} for i in range(10)]
    _, kept_edges, trunc = _capped(nodes, edges)
    assert len(kept_edges) == 5
    assert trunc["edges"] is True
    assert trunc["edges_omitted_by_cap"] == 4      # valid edges beyond the cap
    assert trunc["edges_omitted_endpoint_filter"] == 1  # n9 -> n10 (missing node)
    assert trunc["edges_omitted_total"] == 5


def test_f03_no_omission_no_flag():
    nodes = [{"id": f"n{i}", "kind": "x"} for i in range(10)]
    edges = [{"source": "n0", "target": "n1"}]
    _, kept_edges, trunc = _capped(nodes, edges)
    assert len(kept_edges) == 1
    assert trunc["edges"] is False and trunc["nodes"] is False
    assert trunc["edges_omitted_total"] == 0


def _chunked_post(client, url, body: bytes, content_type: str):
    """POST with a streamed (chunked) body: no Content-Length header is sent."""
    def gen():
        chunk = 64 * 1024
        for i in range(0, len(body), chunk):
            yield body[i:i + chunk]

    return client.post(url, content=gen(), headers={"Content-Type": content_type})


def test_f05_chunked_multipart_over_cap_rejected_413(client):
    """Audit F05: a chunked multipart body exceeding the total cap must be
    rejected at the ASGI stream level, before form parsing completes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("pad.bin", b"\0" * (33 * 1024 * 1024))  # > 32 MB request cap
    boundary = "cvtestbound"
    part = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="pad.zip"\r\nContent-Type: application/zip\r\n\r\n').encode()
    body = part + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    r = _chunked_post(client, "/api/v1/sources", body,
                      f"multipart/form-data; boundary={boundary}")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_f05_chunked_github_body_over_cap_rejected_413(client):
    big = b'{"url": "https://github.com/' + b"a" * (2 * 1024 * 1024) + b'/repo"}'
    r = _chunked_post(client, "/api/v1/imports/github", big, "application/json")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_f05_chunked_paste_over_cap_rejected_413(client):
    body = (b'{"kind": "paste", "language": "python", "filename": "x.py", '
            b'"content": "' + b"x" * (2 * 1024 * 1024) + b'"}')
    r = _chunked_post(client, "/api/v1/sources", body, "application/json")
    assert r.status_code == 413


def test_f05_normal_sized_chunked_requests_still_work(client):
    body = b'{"kind": "paste", "language": "python", "filename": "ok.py", "content": "x = 1\\n"}'
    r = _chunked_post(client, "/api/v1/sources", body, "application/json")
    assert r.status_code == 200
    assert r.json()["file_count"] == 1
