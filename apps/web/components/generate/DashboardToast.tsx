"use client";

import { CheckCircle2 } from "lucide-react";
import styles from "./generate.module.css";

type DashboardToastProps = {
  message: string | null;
};

export function DashboardToast({ message }: DashboardToastProps) {
  if (!message) {
    return null;
  }

  return (
    <div className={styles.dashboardToast} role="status" aria-live="polite">
      <CheckCircle2 size={17} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
