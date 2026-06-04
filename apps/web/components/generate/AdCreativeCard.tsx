"use client";

import { Bookmark } from "lucide-react";
import Image from "next/image";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type AdCreativeCardProps = {
  creative: MockCreative;
  index?: number;
  compact?: boolean;
  showPlaceholderArt?: boolean;
  openLabel?: string;
  openText?: string;
  onSave?: () => void;
  onOpen?: () => void;
};

export function AdCreativeCard({ creative, index, compact = false, showPlaceholderArt = true, openLabel, openText, onSave, onOpen }: AdCreativeCardProps) {
  const hasImage = Boolean(creative.imageUrl);

  return (
    <article className={styles.adCreativeCard} data-tone={creative.tone} data-compact={compact}>
      {typeof index === "number" ? <strong className={styles.adCreativeNumber}>{index + 1}</strong> : null}
      {onSave ? (
        <button aria-label={`${creative.title} 저장`} className={styles.adCreativeSaveButton} type="button" onClick={onSave}>
          <Bookmark size={15} aria-hidden="true" />
        </button>
      ) : null}
      <div className={styles.adCreativeVisual} data-has-image={hasImage ? "true" : undefined} aria-hidden="true">
        {creative.imageUrl ? (
          <Image
            alt=""
            className={styles.adCreativeImage}
            fill
            sizes={compact ? "96px" : "160px"}
            src={creative.imageUrl}
            unoptimized
          />
        ) : showPlaceholderArt ? (
          <>
            <span className={styles.adCreativeCup} />
            <span className={styles.adCreativeFruit} />
          </>
        ) : (
          <span className={styles.adCreativeImageMissing}>이미지 준비 중</span>
        )}
      </div>
      <div className={styles.adCreativeCopy}>
        {creative.badge ? <em>{creative.badge}</em> : null}
        <h2>{creative.title}</h2>
        <p>{creative.subtitle}</p>
        {onOpen ? (
          <button aria-label={openLabel ?? `${creative.title} 상세 보기`} className={styles.adCreativeActionButton} type="button" onClick={onOpen}>
            {openText ?? "상세 보기"}
          </button>
        ) : null}
      </div>
    </article>
  );
}
