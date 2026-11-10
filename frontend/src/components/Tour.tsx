import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button, Icon } from "../ui";

const KEY = "cv.tour.v1";

type Step = { selector: string; title: string; body: string };

const STEPS: Step[] = [
  { selector: ".sourcedock", title: "1. Your program",
    body: "This is the exact source that was analyzed. Click any line and the other views follow it." },
  { selector: ".obs-toolrow", title: "2. Stages and views",
    body: "Walk the compilation journey stage by stage, or switch to the recorded run and the optimization lab. Press [ and ] to step through stages." },
  { selector: ".obs-right, .obs-right-rail", title: "3. The inspector",
    body: "Select anything on the canvas and the inspector explains what it is, which line produced it and the recorded evidence. Press I to show or hide it." },
  { selector: ".theater-controls, .obs-actions", title: "4. Run and replay",
    body: "Run the program once in a sandbox, then replay it event by event. Space plays or pauses, and the arrow keys step." },
];

function seen(): boolean {
  try { return localStorage.getItem(KEY) === "done"; } catch { return true; }
}
function markSeen() {
  try { localStorage.setItem(KEY, "done"); } catch { /* ignore */ }
}

/** First-run tour: offered once (never auto-opens over the page), restartable from the palette. */
export default function Tour({ ready }: { ready: boolean }) {
  const [offer, setOffer] = useState(false);
  const [active, setActive] = useState(false);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const popRef = useRef<HTMLDivElement | null>(null);

  // offer once, a moment after a program is on screen; never in automated browsers
  useEffect(() => {
    if (!ready || seen() || navigator.webdriver) return;
    const t = setTimeout(() => setOffer(true), 1200);
    return () => clearTimeout(t);
  }, [ready]);

  useEffect(() => {
    const start = () => { setOffer(false); setI(0); setActive(true); };
    window.addEventListener("cv:tour", start);
    return () => window.removeEventListener("cv:tour", start);
  }, []);

  const steps = STEPS.filter((s) => !active || document.querySelector(s.selector));
  const step = steps[Math.min(i, steps.length - 1)];

  const measure = useCallback(() => {
    if (!active || !step) return;
    const el = document.querySelector(step.selector);
    setRect(el ? el.getBoundingClientRect() : null);
  }, [active, step]);
  useLayoutEffect(() => {
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);
  useEffect(() => { if (active) popRef.current?.focus(); }, [active, i]);

  const finish = () => { markSeen(); setActive(false); setOffer(false); };

  if (offer && !active) {
    return (
      <div className="tour-offer" role="region" aria-label="Guided tour offer">
        <span>New here? A 30-second tour shows where things are.</span>
        <Button variant="primary" size="sm" onClick={() => { setI(0); setActive(true); setOffer(false); }}>Show me</Button>
        <Button variant="ghost" size="sm" onClick={finish}>No thanks</Button>
      </div>
    );
  }
  if (!active || !step) return null;

  const last = i >= steps.length - 1;
  // place the card beside the target, clamped to the viewport
  const W = 320;
  const vw = window.innerWidth, vh = window.innerHeight;
  let left = rect ? rect.right + 16 : vw / 2 - W / 2;
  let top = rect ? rect.top + 12 : vh / 3;
  if (rect && left + W > vw - 12) left = Math.max(12, rect.left + 16);
  if (rect && rect.right + 16 + W > vw - 12 && rect.height > 160) top = Math.min(vh - 220, rect.top + 60);
  if (rect && rect.top > vh - 240) top = vh - 240;
  top = Math.max(12, Math.min(top, vh - 200));
  left = Math.max(12, Math.min(left, vw - W - 12));

  return (
    <>
      {rect && <div className="tour-hole" style={{ top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }} aria-hidden />}
      <div className="tour-card" role="dialog" aria-label="Guided tour" tabIndex={-1} ref={popRef}
           style={{ top, left, width: W }}
           onKeyDown={(e) => {
             if (e.key === "Escape") finish();
             else if (e.key === "ArrowRight") { if (!last) setI(i + 1); }
             else if (e.key === "ArrowLeft") { setI(Math.max(0, i - 1)); }
           }}>
        <div className="tour-h"><strong>{step.title}</strong>
          <button className="iconbtn" aria-label="Close tour" onClick={finish}><Icon name="close" size={13} /></button></div>
        <p>{step.body}</p>
        <div className="tour-f">
          <span className="tour-dots" aria-label={`Step ${i + 1} of ${steps.length}`}>
            {steps.map((_, k) => <i key={k} className={k === i ? "on" : ""} />)}
          </span>
          <span className="spacer" />
          {i > 0 && <Button variant="ghost" size="sm" onClick={() => setI(i - 1)}>Back</Button>}
          {last
            ? <Button variant="primary" size="sm" onClick={finish}>Done</Button>
            : <Button variant="primary" size="sm" onClick={() => setI(i + 1)}>Next</Button>}
        </div>
      </div>
    </>
  );
}
