import type { ReactNode } from "react";
import Icon, { IconName } from "./Icon";

/** A calm, useful empty state: what is missing, and the next step. */
export default function EmptyState({ icon = "compass", title, children, action }:
  { icon?: IconName; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="emptystate">
      <div className="es-art"><Icon name={icon} size={26} /></div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
