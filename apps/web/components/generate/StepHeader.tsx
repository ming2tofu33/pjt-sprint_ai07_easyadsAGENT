import { ChevronLeft } from "lucide-react";
import styles from "./generate.module.css";

type StepHeaderProps = {
  title: string;
  canGoBack?: boolean;
  onBack?: () => void;
};

export function StepHeader({ title, canGoBack = false, onBack }: StepHeaderProps) {
  return (
    <header className={styles.topNav}>
      {canGoBack ? (
        <button className={styles.iconButton} type="button" aria-label="이전 단계" onClick={onBack}>
          <ChevronLeft size={22} strokeWidth={2.4} />
        </button>
      ) : (
        <span />
      )}
      <h1 className={styles.title}>{title}</h1>
      <span />
    </header>
  );
}
