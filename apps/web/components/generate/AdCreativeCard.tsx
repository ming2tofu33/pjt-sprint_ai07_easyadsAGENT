"use client";

import { Bookmark } from "lucide-react";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type AdCreativeCardProps = {
  creative: MockCreative;
  index?: number;
  compact?: boolean;
  onSave?: () => void;
};

export function AdCreativeCard({ creative, index, compact = false, onSave }: AdCreativeCardProps) {
  return (
    <article className={styles.adCreativeCard} data-tone={creative.tone} data-compact={compact}>
      {typeof index === "number" ? <strong className={styles.adCreativeNumber}>{index + 1}</strong> : null}
      <button aria-label={`${creative.title} 저장`} className={styles.adCreativeSaveButton} type="button" onClick={onSave}>
        <Bookmark size={15} aria-hidden="true" />
      </button>
      <div className={styles.adCreativeVisual} aria-hidden="true">
        <span className={styles.adCreativeCup} />
        <span className={styles.adCreativeFruit} />
      </div>
      <div className={styles.adCreativeCopy}>
        {creative.badge ? <em>{creative.badge}</em> : null}
        <h2>{creative.title}</h2>
        <p>{creative.subtitle}</p>
      </div>
    </article>
  );
}
