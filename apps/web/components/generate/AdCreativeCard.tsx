"use client";

import { Bookmark } from "lucide-react";
import Image from "next/image";
import { shouldUseNextImageOptimization } from "@/lib/image-optimization";
import type { MockCreative } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type AdCreativeCardProps = {
  creative: MockCreative;
  index?: number;
  compact?: boolean;
  savePlacement?: "overlay" | "copy";
  showPlaceholderArt?: boolean;
  openOnImage?: boolean;
  openLabel?: string;
  openText?: string;
  onSave?: () => void;
  onOpen?: () => void;
};

export function AdCreativeCard({
  creative,
  index,
  compact = false,
  savePlacement = "overlay",
  showPlaceholderArt = true,
  openOnImage = false,
  openLabel,
  openText,
  onSave,
  onOpen
}: AdCreativeCardProps) {
  const hasImage = Boolean(creative.imageUrl);
  const visualContent = creative.imageUrl ? (
    <Image
      alt=""
      className={styles.adCreativeImage}
      fill
      sizes={compact ? "96px" : openOnImage ? "190px" : "160px"}
      src={creative.imageUrl}
      unoptimized={!shouldUseNextImageOptimization(creative.imageUrl)}
    />
  ) : showPlaceholderArt ? (
    <>
      <span className={styles.adCreativeCup} />
      <span className={styles.adCreativeFruit} />
    </>
  ) : (
    <span className={styles.adCreativeImageMissing}>이미지 준비 중</span>
  );
  const saveButton = onSave ? (
    <button
      aria-label={`${creative.title} 저장`}
      className={styles.adCreativeSaveButton}
      data-placement={savePlacement}
      type="button"
      onClick={onSave}
    >
      <Bookmark size={savePlacement === "copy" ? 18 : 15} aria-hidden="true" />
    </button>
  ) : null;
  const shouldShowCopyHeader = Boolean(creative.badge || (saveButton && savePlacement === "copy"));

  return (
    <article className={styles.adCreativeCard} data-tone={creative.tone} data-compact={compact} data-gallery={openOnImage ? "true" : undefined}>
      {typeof index === "number" ? <strong className={styles.adCreativeNumber}>{index + 1}</strong> : null}
      {savePlacement === "overlay" ? saveButton : null}
      {onOpen && openOnImage ? (
        <button
          aria-label={openLabel ?? `${creative.title} 상세 보기`}
          className={styles.adCreativeVisual}
          data-has-image={hasImage ? "true" : undefined}
          type="button"
          onClick={onOpen}
        >
          {visualContent}
        </button>
      ) : (
        <div className={styles.adCreativeVisual} data-has-image={hasImage ? "true" : undefined} aria-hidden="true">
          {visualContent}
        </div>
      )}
      <div className={styles.adCreativeCopy}>
        {shouldShowCopyHeader ? (
          <div className={styles.adCreativeCopyHeader}>
            {creative.badge ? <em>{creative.badge}</em> : <span aria-hidden="true" />}
            {savePlacement === "copy" ? saveButton : null}
          </div>
        ) : null}
        <h2>{creative.title}</h2>
        <p>{creative.subtitle}</p>
        {onOpen && !openOnImage ? (
          <button aria-label={openLabel ?? `${creative.title} 상세 보기`} className={styles.adCreativeActionButton} type="button" onClick={onOpen}>
            {openText ?? "상세 보기"}
          </button>
        ) : null}
      </div>
    </article>
  );
}
