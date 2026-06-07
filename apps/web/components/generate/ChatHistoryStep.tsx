"use client";

import { Clock, MessageCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { listChatThreads, type ChatThreadResponse } from "@/lib/api-client";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";
import { workspaceLoadErrorMessage } from "./workspace-errors";

type ChatHistoryStepProps = {
  onBack: () => void;
  onGoHome: () => void;
  onSelectThread: (threadId: string) => void;
};

const statusLabelByThreadStatus: Record<string, string> = {
  draft: "브리프 작성 중",
  generating: "생성 중",
  completed: "생성 완료",
  failed: "생성 실패",
  archived: "보관됨"
};

export function ChatHistoryStep({ onBack, onGoHome, onSelectThread }: ChatHistoryStepProps) {
  const [threads, setThreads] = useState<ChatThreadResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadThreads = useCallback((isActive: () => boolean = () => true) => {
    setLoading(true);
    setLoadError(null);
    listChatThreads({ limit: 50 })
      .then((res) => {
        if (!isActive()) {
          return;
        }
        setThreads(res.threads);
      })
      .catch((error) => {
        if (!isActive()) {
          return;
        }
        setThreads([]);
        setLoadError(workspaceLoadErrorMessage(error));
      })
      .finally(() => {
        if (isActive()) {
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    let isActive = true;
    loadThreads(() => isActive);
    return () => {
      isActive = false;
    };
  }, [loadThreads]);

  return (
    <>
      <StepHeader title="이전 대화 기록" canGoBack backLabel="이전 화면" onBack={onBack} onHome={onGoHome} />
      <div className={styles.workspaceSection}>
        {loading ? (
          <p className={styles.workspaceEmptyText}>기록을 불러오는 중입니다.</p>
        ) : loadError ? (
          <div className={styles.workspaceEmptyCard} role="alert">
            <MessageCircle size={32} strokeWidth={1.5} />
            <strong>이전 대화 기록을 불러오지 못했어요</strong>
            <p>{loadError}</p>
            <button className={styles.workspaceAction} type="button" onClick={() => loadThreads()}>
              다시 불러오기
            </button>
          </div>
        ) : threads.length === 0 ? (
          <div className={styles.workspaceEmptyCard}>
            <MessageCircle size={32} strokeWidth={1.5} />
            <strong>이전 대화 기록이 없어요</strong>
            <p>스튜디오에서 새 작업을 만들면 여기에 표시돼요.</p>
          </div>
        ) : (
          <div className={styles.workspaceList}>
            {threads.map((thread) => (
              <button
                key={thread.thread_id}
                className={styles.workspaceCard}
                type="button"
                onClick={() => onSelectThread(thread.thread_id)}
              >
                <span className={styles.workspaceOpenButton}>
                  <span className={styles.workspaceThumb} data-status={thread.status}>
                    <MessageCircle size={22} aria-hidden="true" />
                  </span>
                  <span>
                    <strong>{thread.title || "새로운 대화"}</strong>
                    <p>{statusLabelByThreadStatus[thread.status] ?? "작업 중"}</p>
                    <small>
                      <Clock size={12} aria-hidden="true" />
                      {new Date(thread.last_message_at || thread.updated_at).toLocaleDateString()}
                    </small>
                  </span>
                </span>
                <span className={styles.workspaceAction}>열기</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
