import { useEffect, useRef } from "react";
import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";

/**
 * Code editor for pasted source (CodeMirror 6): line numbers, syntax highlighting, undo,
 * indentation, bracket matching. Loaded lazily so the editor never weighs on first paint.
 * It only edits text — nothing is executed or analyzed until the user clicks.
 */
export default function CodeEditor({ value, onChange, language, ariaLabel }: {
  value: string; onChange: (v: string) => void; language: string; ariaLabel: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    if (!host.current) return;
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          basicSetup,
          language === "python" ? python() : cpp(),
          EditorView.contentAttributes.of({ "aria-label": ariaLabel, spellcheck: "false" }),
          EditorView.updateListener.of((u) => { if (u.docChanged) onChangeRef.current(u.state.doc.toString()); }),
          EditorView.theme({
            "&": { fontSize: "13px", maxHeight: "420px", border: "1px solid var(--line, #d0d7de)", borderRadius: "6px" },
            ".cm-scroller": { fontFamily: "'JetBrains Mono', ui-monospace, Consolas, monospace", minHeight: "260px" },
            "&.cm-focused": { outline: "2px solid var(--accent, #0b5fff)" },
          }),
        ],
      }),
    });
    view.current = v;
    return () => { v.destroy(); view.current = null; };
    // the editor is rebuilt only when the language changes; text flows in via the effect below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  // keep the editor in sync when the parent replaces the text (e.g. a different sample)
  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  return <div ref={host} className="cm-host" />;
}
