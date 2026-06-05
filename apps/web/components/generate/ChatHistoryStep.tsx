"use client";

import { Clock, MessageCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { listChatThreads, type ChatThreadResponse } from "@/lib/api-client";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type ChatHistoryStepProps = {
  onBack: () => void;
  onGoHome: () => void;
  onSelectThread: (threadId: string) => void;
};

export function ChatHistoryStep({ onBack, onGoHome, onSelectThread }: ChatHistoryStepProps) {
  const [threads, setThreads] = useState<ChatThreadResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;
    listChatThreads({ limit: 50 })
      .then((res) => {
        if (isActive) {
          setThreads(res.threads);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isActive) setLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, []);

  return (
    <>
      <StepHeader title="이전 대화 기록" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onGoHome} />
      <div className={styles.recentAdsList}>
        {loading ? (
          <p className={styles.helperText}>기록을 불러오는 중...</p>
        ) : threads.length === 0 ? (
          <div className={styles.emptyState}>
            <MessageCircle size={32} strokeWidth={1.5} />
            <p>이전 대화 기록이 없어요.</p>
          </div>
        ) : (
          threads.map((thread) => (
            <button
              key={thread.thread_id}
              className={styles.recentAdItem}
              onClick={() => onSelectThread(thread.thread_id)}
            >
              <div className={styles.recentAdInfo}>
                <span className={styles.recentAdTitle}>{thread.title || "새로운 대화"}</span>
                <span className={styles.recentAdMeta}>
                  <Clock size={12} />
                  {new Date(thread.last_message_at || thread.updated_at).toLocaleDateString()}
                </span>
              </div>
            </button>
          ))
        )}
      </div>
    </>
  );
}
