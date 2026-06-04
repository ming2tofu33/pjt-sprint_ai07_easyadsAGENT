import type { LucideIcon } from "lucide-react";
import styles from "./generate.module.css";

type BriefRowProps = {
  icon: LucideIcon;
  label: string;
  value: string;
};

export function BriefRow({ icon: Icon, label, value }: BriefRowProps) {
  return (
    <div className={styles.briefRow}>
      <Icon size={17} strokeWidth={2.3} aria-hidden="true" />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
