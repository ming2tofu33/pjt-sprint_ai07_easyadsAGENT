"use client";

import { LoaderCircle, Sparkles } from "lucide-react";
import React, { useEffect, useState } from "react";
import type { WaitingStatusCopy } from "@/lib/generation-waiting-copy";
import { waitingMessageAt } from "@/lib/generation-waiting-copy";
import styles from "./generate.module.css";

type WaitingStatusCardProps = {
  copy: WaitingStatusCopy;
  compact?: boolean;
  className?: string;
  intervalMs?: number;
};

export function WaitingStatusCard({
  copy,
  compact = false,
  className,
  intervalMs = 2600
}: WaitingStatusCardProps) {
  const [tick, setTick] = useState(0);
  const waitingMessage = waitingMessageAt(copy.loop, tick);
  const cardClassName = [
    styles.waitingStatusCard,
    compact ? styles.waitingStatusCardCompact : "",
    className ?? ""
  ]
    .filter(Boolean)
    .join(" ");

  useEffect(() => {
    setTick(0);
    const intervalId = window.setInterval(() => {
      setTick((currentTick) => currentTick + 1);
    }, intervalMs);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [copy.statusKey, intervalMs]);

  return (
    <section
      aria-label="작업 대기 상태"
      aria-live="polite"
      className={cardClassName}
      data-compact={compact}
      data-status-key={copy.statusKey}
    >
      <span className={styles.waitingStatusIcon} aria-hidden="true">
        <Sparkles size={18} />
        <LoaderCircle size={15} />
      </span>
      <div className={styles.waitingStatusText}>
        <span className={styles.waitingStatusEyebrow}>{copy.eyebrow}</span>
        <strong>{copy.title}</strong>
        <p>{copy.description}</p>
        {waitingMessage ? <small>{waitingMessage}</small> : null}
      </div>
    </section>
  );
}
