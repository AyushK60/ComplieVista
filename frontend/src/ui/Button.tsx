import type { ButtonHTMLAttributes, ReactNode } from "react";
import Icon, { IconName } from "./Icon";

export type ButtonVariant = "primary" | "secondary" | "run" | "ghost";

/** The one button. Variants map to the .btn classes so spacing/states stay in CSS. */
export default function Button({ variant = "secondary", icon, size, className = "", children, ...rest }:
  { variant?: ButtonVariant; icon?: IconName; size?: "sm" | "md" | "lg"; children?: ReactNode } &
  ButtonHTMLAttributes<HTMLButtonElement>) {
  const cls = ["btn", variant === "secondary" ? "" : variant, size === "lg" ? "big" : size === "sm" ? "sm" : "", className]
    .filter(Boolean).join(" ");
  return (
    <button type="button" className={cls} {...rest}>
      {icon && <Icon name={icon} size={size === "sm" ? 14 : 16} />}
      {children}
    </button>
  );
}
