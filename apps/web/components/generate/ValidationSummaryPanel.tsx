"use client";

import React from "react";
import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { buildResultReviewItems } from "@/lib/generation-result-utils";
import type { ResultArtifactPayload } from "@/lib/api-client";
import styles from "./generate.module.css";

type ValidationSummaryPanelProps = {
  payload: ResultArtifactPayload | null | undefined;
};

const statusLabels = {
  pass: "좋음",
  warn: "확인 필요",
  fail: "수정 필요"
} as const;

export function ValidationSummaryPanel({ payload }: ValidationSummaryPanelProps) {
  const items = buildResultReviewItems(payload);
  if (items.length === 0) {
    return null;
  }

  return (
    <section className={styles.validationPanel} aria-label="생성 결과 검수">
      <div className={styles.validationHeader}>
        <Info size={18} aria-hidden="true" />
        <div>
          <h2>생성 결과 검수</h2>
          <p>완성된 이미지를 쓰기 전에 확인하면 좋은 부분이에요.</p>
        </div>
      </div>

      <div className={styles.validationGrid}>
        {items.map((item) => {
          const Icon = item.status === "pass" ? CheckCircle2 : item.status === "warn" ? Info : AlertTriangle;
          return (
            <article className={styles.validationItem} data-validation-status={item.status} key={item.id}>
              <span className={styles.validationIcon}>
                <Icon size={17} aria-hidden="true" />
              </span>
              <div>
                <h3>{item.label}</h3>
                <p>{item.message}</p>
              </div>
              <strong>{statusLabels[item.status]}</strong>
            </article>
          );
        })}
      </div>
    </section>
  );
}
