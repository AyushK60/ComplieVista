import type { ReactNode } from "react";

/** The one surface: optional header with title and right-side actions. */
export default function Panel({ title, actions, children, className = "", ...rest }:
  { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string } &
  Omit<React.HTMLAttributes<HTMLDivElement>, "title">) {
  return (
    <div className={`panel ${className}`} {...rest}>
      {(title || actions) && (
        <div className="panel-h">{title}<span className="spacer" />{actions}</div>
      )}
      {children}
    </div>
  );
}
