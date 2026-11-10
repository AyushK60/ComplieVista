import { beforeEach, describe, expect, it } from "vitest";
import { clearRecent, loadRecent, recentUrl, recordRecent } from "./recent";

function stubStorage(initial: Record<string, string> = {}, throws = false) {
  const m = new Map(Object.entries(initial));
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: (k: string) => { if (throws) throw new Error("blocked"); return m.get(k) ?? null; },
    setItem: (k: string, v: string) => { if (throws) throw new Error("blocked"); m.set(k, v); },
    removeItem: (k: string) => { m.delete(k); },
  } as unknown as Storage;
}
const base = { title: "t", language: "c", project: "p1" };

describe("recent sessions", () => {
  beforeEach(() => stubStorage());

  it("records, de-duplicates by snapshot and keeps newest first", () => {
    recordRecent({ ...base, snapshot: "s1" });
    recordRecent({ ...base, snapshot: "s2" });
    recordRecent({ ...base, snapshot: "s1", analysis: "a1" });
    const r = loadRecent();
    expect(r.map((x) => x.snapshot)).toEqual(["s1", "s2"]);
    expect(r[0].analysis).toBe("a1");
  });

  it("keeps at most 12 entries", () => {
    for (let i = 0; i < 20; i++) recordRecent({ ...base, snapshot: `s${i}` });
    expect(loadRecent()).toHaveLength(12);
    expect(loadRecent()[0].snapshot).toBe("s19");
  });

  it("survives corrupted or blocked storage", () => {
    stubStorage({ "cv.recent.v1": "{not json" });
    expect(loadRecent()).toEqual([]);
    stubStorage({}, true);
    expect(() => recordRecent({ ...base, snapshot: "s" })).not.toThrow();
    expect(loadRecent()).toEqual([]);
  });

  it("clears and builds a reopen URL with only the known parameters", () => {
    recordRecent({ ...base, snapshot: "s1", analysis: "a", execution: "e", target: "t" });
    expect(recentUrl(loadRecent()[0])).toBe("/workspace?project=p1&snapshot=s1&target=t&analysis=a&execution=e");
    clearRecent();
    expect(loadRecent()).toEqual([]);
  });
});
