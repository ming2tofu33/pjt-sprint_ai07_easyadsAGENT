import type { ReactNode } from "react";
import styles from "./generate.module.css";

export function MobileShell({ children }: { children: ReactNode }) {
  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="개떡찰떡 모바일 화면">
        <div className={styles.statusBar} aria-hidden="true">
          <span>9:41</span>
          <span className={styles.signal}>● ● ●</span>
        </div>
        <div className={styles.body}>{children}</div>
      </section>
    </main>
  );
}
