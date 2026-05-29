import type { ReactNode } from "react";
import clsx from "clsx";
import styles from "./generate.module.css";

type ChoiceChipProps = {
  selected?: boolean;
  children: ReactNode;
  onClick?: () => void;
  ariaLabel?: string;
};

export function ChoiceChip({ selected = false, children, onClick, ariaLabel }: ChoiceChipProps) {
  return (
    <button
      type="button"
      className={clsx(styles.chip, selected && styles.chipSelected)}
      aria-pressed={selected}
      aria-label={ariaLabel}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
