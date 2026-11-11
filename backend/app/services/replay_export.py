"""Self-contained replay export (Stage C).

``build_replay_html(store, execution_id)`` returns ONE html file that replays a recorded
execution with no backend, no network and no external assets: the real source, the real
recorded events (call / line / return / exception / exit), the real captured output and
the provenance of the run are embedded as JSON; a small vanilla-JS player renders them.

Honesty rules (project contract): the file replays a *recording* - it never runs code and
never invents events. Python traces carry line events; the C trace only records function
call/return, and the player says so instead of faking line stepping. Output is the final
captured stdout/stderr, not time-aligned to steps. Truncation flags are shown.
"""
from __future__ import annotations

import hashlib
import html
import json
from typing import Any

MAX_EVENTS = 5000
MAX_OUTPUT = 60_000
FORMAT_VERSION = 1


def collect_replay_data(store, execution_id: str) -> dict[str, Any] | None:
    job = store.query_one("SELECT * FROM executions WHERE id=?", (execution_id,))
    if not job:
        return None
    src_row = store.query_one(
        "SELECT content_sha256 FROM source_files WHERE snapshot_id=? AND rel_path=?",
        (job["snapshot_id"], job["primary_file"]))
    source = store.get_artifact(src_row["content_sha256"]).decode("utf-8", "replace") \
        if src_row else ""
    rows = store.query(
        "SELECT seq, kind, payload_json FROM execution_events WHERE execution_id=?"
        " ORDER BY seq LIMIT ?", (execution_id, MAX_EVENTS))
    events = [{"seq": r["seq"], "kind": r["kind"], "payload": json.loads(r["payload_json"])}
              for r in rows if r["kind"] not in ("meta", "trace_meta")]
    out: dict[str, Any] = {"stdout": None, "stderr": None, "output_truncated": False}
    for key, col in (("stdout", "stdout_sha256"), ("stderr", "stderr_sha256")):
        if job[col]:
            data = store.get_artifact(job[col])
            out[key] = data[:MAX_OUTPUT].decode("utf-8", "replace")
            out["output_truncated"] = out["output_truncated"] or len(data) > MAX_OUTPUT
    return {
        "format": "compilevista-replay", "version": FORMAT_VERSION,
        "execution": {
            "id": execution_id, "language": job["language"], "file": job["primary_file"],
            "status": job["status"], "exit_code": job["exit_code"],
            "duration_ms": job["duration_ms"], "created_utc": job["created_utc"],
            "image_id": job["image_id"], "binary_sha256": job["binary_sha256"],
            "events_total": job["events_count"],
            "events_embedded": len(events),
            "events_truncated": bool(job["events_truncated"]) or
            (job["events_count"] or 0) > len(events),
        },
        "source": source,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "events": events,
        "output": out,
        "has_line_events": any(e["kind"] == "line" for e in events),
    }


def _json_for_script(data: dict[str, Any]) -> str:
    # Safe to embed inside <script type="application/json">: neutralise tag/comment closers.
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def build_replay_html(store, execution_id: str) -> bytes | None:
    data = collect_replay_data(store, execution_id)
    if data is None:
        return None
    title = html.escape(f"CompileVista replay - {data['execution']['file']}")
    page = _TEMPLATE.replace("{{TITLE}}", title).replace("{{DATA}}", _json_for_script(data))
    return page.encode("utf-8")


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>{{TITLE}}</title>
<style>
:root{--bg:#fff;--fg:#1b1f24;--mut:#59636e;--line:#d0d7de;--pane:#f6f8fa;--hi:#fff1b8;--acc:#0b5fff}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--mut:#9aa4af;--line:#30363d;--pane:#161b22;--hi:#4a3d00;--acc:#58a6ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}
header{padding:12px 16px;border-bottom:1px solid var(--line)}h1{font-size:16px;margin:0 0 4px}
.meta{color:var(--mut);font-size:12px;display:flex;flex-wrap:wrap;gap:4px 14px}
.note{margin:8px 16px 0;padding:8px 10px;border:1px solid var(--line);background:var(--pane);border-radius:6px;font-size:12px;color:var(--mut)}
.bar{display:flex;gap:8px;align-items:center;padding:10px 16px;flex-wrap:wrap}
button{font:inherit;padding:4px 10px;border:1px solid var(--line);background:var(--pane);color:var(--fg);border-radius:6px;cursor:pointer}
button:focus-visible,input:focus-visible,.ev:focus-visible{outline:2px solid var(--acc)}
input[type=range]{flex:1;min-width:140px}
main{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:12px;padding:0 16px 16px}
@media (max-width:820px){main{grid-template-columns:1fr}}
section{border:1px solid var(--line);border-radius:6px;overflow:hidden;min-width:0}
section>h2{margin:0;padding:6px 10px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);background:var(--pane);border-bottom:1px solid var(--line)}
.body{max-height:340px;overflow:auto}
pre,code{font:12.5px/1.5 ui-monospace,Consolas,monospace}
.src div{display:flex;white-space:pre}.src .n{flex:none;width:44px;text-align:right;padding-right:10px;color:var(--mut);user-select:none}
.src .cur{background:var(--hi)}
.ev{padding:2px 10px;cursor:pointer;white-space:nowrap;border-bottom:1px solid transparent}.ev.cur{background:var(--hi)}
.kv{padding:6px 10px;font-family:ui-monospace,Consolas,monospace;font-size:12px;white-space:pre-wrap;word-break:break-word}
.stack div{padding:2px 10px;font-family:ui-monospace,Consolas,monospace;font-size:12px}
#status{padding:0 16px;color:var(--mut);font-size:13px;min-height:1.5em}
</style></head><body>
<header><h1 id="h"></h1><div class="meta" id="meta"></div></header>
<div class="note" id="note"></div>
<div class="bar"><button id="first" aria-label="First step">&#9198;</button><button id="prev" aria-label="Previous step">&#9664;</button>
<button id="play" aria-label="Play">&#9654; Play</button><button id="next" aria-label="Next step">&#9654;</button>
<button id="last" aria-label="Last step">&#9197;</button>
<input id="slider" type="range" min="0" value="0" aria-label="Step"><span id="pos"></span></div>
<div id="status" role="status" aria-live="polite"></div>
<main><div>
<section><h2 id="srch">Source</h2><div class="body src" id="src"></div></section>
<section style="margin-top:12px"><h2>Output (final capture, not time-aligned)</h2><div class="body"><div class="kv" id="out"></div></div></section>
</div><div>
<section><h2>Call stack</h2><div class="body stack" id="stack" style="max-height:140px"></div></section>
<section style="margin-top:12px"><h2>Values at this step</h2><div class="body" style="max-height:160px"><div class="kv" id="vals"></div></div></section>
<section style="margin-top:12px"><h2>Recorded events</h2><div class="body" id="evs" role="listbox" aria-label="Recorded events"></div></section>
</div></main>
<script id="data" type="application/json">{{DATA}}</script>
<script>
(function(){
var D=JSON.parse(document.getElementById('data').textContent),X=D.execution,E=D.events,$=function(i){return document.getElementById(i)};
var cur=0,timer=null,lines=D.source.split('\n');
$('h').textContent='Replay of '+X.file+' ('+X.language+')';
function m(t){var s=document.createElement('span');s.textContent=t;$('meta').appendChild(s)}
m('exit code '+X.exit_code);m('status '+X.status);if(X.duration_ms!=null)m(X.duration_ms+' ms');
m(X.events_embedded+' events');m('execution '+X.id.slice(0,12));m('source sha256 '+D.source_sha256.slice(0,12));
if(X.image_id)m('image '+String(X.image_id).replace('sha256:','').slice(0,12));
var notes=['This is a recording of one run in a restricted container. It does not execute code and cannot rewind a live process.'];
if(!D.has_line_events)notes.push('This trace records function calls and returns only (no per-line events), so the source cannot be highlighted line by line.');
if(X.events_truncated)notes.push('The recording hit its event cap: the first '+X.events_embedded+' events are included and later events were not recorded, so the end of the run is not shown.');
if(D.output.output_truncated)notes.push('Captured output was truncated.');
$('note').textContent=notes.join(' ');
var src=$('src');lines.forEach(function(t,i){var d=document.createElement('div');d.id='L'+(i+1);var n=document.createElement('span');n.className='n';n.textContent=i+1;var c=document.createElement('span');c.textContent=t||' ';d.appendChild(n);d.appendChild(c);src.appendChild(d)});
var o=D.output,ot='';if(o.stdout)ot+=o.stdout;if(o.stderr)ot+=(ot?'\n':'')+'[stderr]\n'+o.stderr;$('out').textContent=ot||'(no output captured)';
var evs=$('evs');
function label(e){var p=e.payload;if(e.kind==='line')return 'line '+p.line+'  '+p.fn;if(e.kind==='call')return 'call '+p.fn+(p.line!=null&&p.line>0?' (line '+p.line+')':'');
if(e.kind==='return')return 'return '+p.fn;if(e.kind==='exception')return 'exception '+(p.exc||'');if(e.kind==='exit')return 'exit '+p.exit_code;return e.kind}
E.forEach(function(e,i){var d=document.createElement('div');d.className='ev';d.tabIndex=0;d.setAttribute('role','option');d.textContent=(i+1)+'. '+label(e);d.onclick=function(){go(i)};
d.onkeydown=function(k){if(k.key==='Enter'||k.key===' '){k.preventDefault();go(i)}};evs.appendChild(d)});
$('slider').max=Math.max(E.length-1,0);
function vals(p){if(!p||!p.locals)return null;return Object.keys(p.locals).map(function(k){var v=p.locals[k];return k+' = '+(v.repr!=null?v.repr:v.type+(v.len!=null?' (len '+v.len+')':''))+(v.type?'   : '+v.type:'')}).join('\n')}
function render(){
 if(!E.length){$('status').textContent='No events were recorded for this run.';$('pos').textContent='0 / 0';return}
 var e=E[cur],stack=[],lastVals=null,i;
 for(i=0;i<=cur;i++){var k=E[i];if(k.kind==='call')stack.push(k.payload.fn);else if(k.kind==='return'&&stack.length)stack.pop();
  if(k.kind==='call'||k.kind==='line'){var v=vals(k.payload);if(v)lastVals={t:v,at:i}}}
 var s=$('stack');s.textContent='';(stack.length?stack.slice().reverse():['(empty)']).forEach(function(f,j){var d=document.createElement('div');d.textContent=(j===0&&stack.length?'> ':'  ')+f;s.appendChild(d)});
 var vv=vals(e.payload);$('vals').textContent=vv||(lastVals?'(not recorded at this step; last recorded at step '+(lastVals.at+1)+')\n'+lastVals.t:'(no values recorded for this run)');
 Array.prototype.forEach.call(document.querySelectorAll('.src .cur'),function(n){n.classList.remove('cur')});
 var ln=(e.kind==='line'||(e.kind==='call'&&e.payload.line>0))?e.payload.line:(e.kind==='return'&&e.payload.line>0?e.payload.line:0);
 if(ln&&$('L'+ln)){var r=$('L'+ln);r.classList.add('cur');var b=src.parentNode;if(r.offsetTop<b.scrollTop||r.offsetTop>b.scrollTop+b.clientHeight-30)b.scrollTop=Math.max(r.offsetTop-80,0)}
 Array.prototype.forEach.call(evs.children,function(n,j){n.classList.toggle('cur',j===cur);n.setAttribute('aria-selected',j===cur)});
 evs.children[cur].scrollIntoView({block:'nearest'});
 $('slider').value=cur;$('pos').textContent=(cur+1)+' / '+E.length;$('status').textContent='Step '+(cur+1)+': '+label(e);
}
function go(i){cur=Math.max(0,Math.min(E.length-1,i));render()}
function stop(){if(timer){clearInterval(timer);timer=null;$('play').innerHTML='&#9654; Play'}}
$('first').onclick=function(){stop();go(0)};$('prev').onclick=function(){stop();go(cur-1)};
$('next').onclick=function(){stop();go(cur+1)};$('last').onclick=function(){stop();go(E.length-1)};
$('slider').oninput=function(){stop();go(+this.value)};
$('play').onclick=function(){if(timer){stop();return}if(cur>=E.length-1)cur=0;$('play').textContent='Pause';timer=setInterval(function(){if(cur>=E.length-1){stop();return}go(cur+1)},300)};
document.addEventListener('keydown',function(k){if(k.target.tagName==='INPUT')return;if(k.key==='ArrowRight'){stop();go(cur+1)}else if(k.key==='ArrowLeft'){stop();go(cur-1)}});
render();
})();
</script></body></html>
"""
