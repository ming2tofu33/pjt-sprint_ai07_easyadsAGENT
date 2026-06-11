import React from "react";
import { useRouter } from "next/navigation";
import styles from "./generate.module.css";

export function ThreadLimitModal() {
  const router = useRouter();

  return (
    <div className={styles.threadLimitOverlay}>
      <div className={styles.threadLimitModal} role="dialog" aria-modal="true" aria-labelledby="thread-limit-text">
        <div className={styles.threadLimitEmoji} aria-hidden="true">⚠️</div>
        <p className={styles.threadLimitText} id="thread-limit-text">
          작업은 최대 3개까지만 만들 수 있어요.<br />
          새 작업을 시작하려면 기존 작업 하나를 삭제해주세요.
        </p>
        <button
          type="button"
          className={styles.threadLimitButton}
          onClick={() => router.push("/")}
        >
          홈으로 이동
        </button>
      </div>
    </div>
  );
}
