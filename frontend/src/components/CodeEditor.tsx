import { useEffect, useRef } from "react";
import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import { python } from "@codemirror/lang-python";
import { cpp } from "@codemirror/lang-cpp";

/**
 * Code editor for pasted source (CodeMirror 6): line numbers, syntax highlighting, undo,
 * indentation, bracket matching. Loaded lazily so the editor never weighs on first paint.
 * It only edits text - nothing is executed or analyzed until the user clicks.
 *
 * Presentation: the editor is an ink plate in both themes and uses the same code colours as
 * every other code surface (identifiers sky, keywords violet, numbers apricot, strings mint).
 */
const highlight = HighlightStyle.define([
  { tag: [t.keyword, t.controlKeyword, t.definitionKeyword, t.moduleKeyword, t.operatorKeyword], color: "var(--violet-l)" },
  { tag: [t.number, t.bool, t.null, t.atom], color: "var(--apricot-l)" },
  { tag: [t.string, t.special(t.string)], color: "var(--mint-l)" },
  { tag: [t.comment, t.lineComment, t.blockComment], color: "var(--c-ink-3)", fontStyle: "italic" },
  { tag: [t.variableName, t.propertyName, t.function(t.variableName), t.definition(t.variableName)], color: "var(--sky-l)" },
  { tag: [t.typeName, t.className, t.namespace], color: "var(--sky-l)" },
  { tag: [t.operator, t.punctuation, t.bracket], color: "var(--c-ink-2)" },
]);

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
          syntaxHighlighting(highlight),
          EditorView.contentAttributes.of({ "aria-label": ariaLabel, spellcheck: "false" }),
          EditorView.updateListener.of((u) => { if (u.docChanged) onChangeRef.current(u.state.doc.toString()); }),
          EditorView.theme({
            "&": { fontSize: "13px", maxHeight: "420px", border: "1px solid var(--line-strong)", borderRadius: "4px", backgroundColor: "var(--canvas)", color: "var(--c-ink)" },
            ".cm-scroller": { fontFamily: "var(--font-mono)", minHeight: "260px" },
            ".cm-content": { caretColor: "var(--sel)" },
            ".cm-cursor": { borderLeftColor: "var(--sel)" },
            ".cm-gutters": { backgroundColor: "var(--canvas)", color: "var(--c-ink-3)", border: "0" },
            ".cm-activeLine": { backgroundColor: "rgba(233, 239, 241, 0.05)" },
            ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--c-ink)" },
            ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "var(--sel-dim)" },
            "&.cm-focused": { outline: "2px solid var(--accent-text)", outlineOffset: "1px" },
          }, { dark: true }),
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
