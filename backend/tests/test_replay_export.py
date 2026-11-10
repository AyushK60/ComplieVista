"""Stage C: self-contained replay export, built from REAL recorded executions."""
import json
import re
import time

PY = ("def sq(n):\n    return n * n\n\n"
      "if __name__ == '__main__':\n    t = 0\n    for i in range(3):\n"
      "        t += sq(i)\n    print('total', t)\n")
C = ('#include <stdio.h>\nstatic int sq(int n){return n*n;}\n'
     'int main(void){printf("%d\\n", sq(7));return 0;}\n')


def _run(client, language, filename, content):
    r = client.post("/api/v1/sources", json={"kind": "paste", "language": language,
                                              "filename": filename, "content": content}).json()
    t = client.get(f"/api/v1/projects/{r['project_id']}/targets").json()[0]
    eid = client.post("/api/v1/executions", json={
        "snapshot_id": r["snapshot_id"], "target_id": t["target_id"]}).json()["execution_id"]
    for _ in range(240):
        j = client.get(f"/api/v1/executions/{eid}").json()
        if j["status"] in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BLOCKED"):
            return j
        time.sleep(0.5)
    return j


def _data(html: str) -> dict:
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert m
    return json.loads(m.group(1))


def test_python_replay_is_self_contained_and_faithful(client):
    j = _run(client, "python", "t.py", PY)
    assert j["status"] == "COMPLETED", j.get("error_code")
    r = client.get(f"/api/v1/executions/{j['id']}/replay.html")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    html = r.text
    # self-contained: no external fetches of any kind
    assert not re.search(r'(src|href)\s*=\s*["\']https?:', html)
    assert "default-src 'none'" in html
    d = _data(html)
    assert d["source"] == PY
    assert d["output"]["stdout"].strip() == "total 5"        # 0+1+4
    assert d["execution"]["exit_code"] == 0
    # embedded events equal the API's events, in order
    api, after = [], 0
    while True:
        pg = client.get(f"/api/v1/executions/{j['id']}/events?after={after}&limit=500").json()
        api += [(e["seq"], e["kind"]) for e in pg["events"] if e["kind"] not in ("meta", "trace_meta")]
        if not pg["events"]:
            break
        after = pg["next_after"]
    assert [(e["seq"], e["kind"]) for e in d["events"]] == api
    assert d["has_line_events"] and any(e["kind"] == "line" and e["payload"]["line"] == 7
                                         for e in d["events"])


def test_c_replay_states_function_level_limitation(client):
    j = _run(client, "c", "t.c", C)
    assert j["status"] == "COMPLETED", j.get("error_code")
    d = _data(client.get(f"/api/v1/executions/{j['id']}/replay.html").text)
    assert d["has_line_events"] is False
    assert {e["kind"] for e in d["events"]} <= {"call", "return", "exit"}
    assert d["output"]["stdout"].strip() == "49"


def test_script_breakout_in_source_is_neutralised(client):
    evil = "if __name__ == '__main__':\n    print('</script><script>alert(1)</script>')\n"
    j = _run(client, "python", "evil.py", evil)
    html = client.get(f"/api/v1/executions/{j['id']}/replay.html").text
    assert "</script><script>alert" not in html
    assert _data(html)["source"] == evil


def test_unknown_execution_404(client):
    assert client.get("/api/v1/executions/nope/replay.html").status_code == 404
