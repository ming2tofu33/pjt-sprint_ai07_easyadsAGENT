import type { ReactNode } from "react";
import clsx from "clsx";
import styles from "./generate.module.css";

type ChoiceChipProps = {
  selected?: boolean;
  disabled?: boolean;
  children: ReactNode;
  onClick?: () => void;
  ariaLabel?: string;
};

export function ChoiceChip({ selected = false, disabled = false, children, onClick, ariaLabel }: ChoiceChipProps) {
  return (
    <button
      type="button"
      className={clsx(styles.chip, selected && styles.chipSelected)}
      aria-pressed={selected}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
