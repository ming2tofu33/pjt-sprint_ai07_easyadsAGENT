import { ChevronLeft, Home, MessageCircle } from "lucide-react";
import styles from "./generate.module.css";

type StepHeaderProps = {
  title: string;
  canGoBack?: boolean;
  onBack?: () => void;
  backLabel?: string;
  onHome?: () => void;
  onHistory?: () => void;
};

export function StepHeader({ title, canGoBack = false, onBack, backLabel = "이전 단계", onHome, onHistory }: StepHeaderProps) {
  return (
    <header className={styles.topNav}>
      {canGoBack ? (
        <button className={styles.iconButton} type="button" aria-label={backLabel} onClick={onBack}>
          <ChevronLeft size={22} strokeWidth={2.4} aria-hidden="true" />
        </button>
      ) : (
        <span />
      )}
      <h1 className={styles.title}>{title}</h1>
      {onHome ? (
        <button className={styles.iconButton} type="button" aria-label="홈으로" onClick={onHome}>
          <Home size={20} strokeWidth={2.4} aria-hidden="true" />
        </button>
      ) : onHistory ? (
        <button className={styles.iconButton} type="button" aria-label="이전 대화" onClick={onHistory}>
          <MessageCircle size={20} strokeWidth={2.4} aria-hidden="true" />
        </button>
      ) : (
        <span />
      )}
    </header>
  );
}
