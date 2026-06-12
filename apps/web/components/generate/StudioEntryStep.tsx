"use client";

import { ChevronLeft, Clock, Home, Image as ImageIcon, Lightbulb, MessageCircle, Plus, Search, Sparkles, Trash2, Upload, User } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { archiveChatThread, listChatThreads, type ChatThreadResponse } from "@/lib/api-client";
import styles from "./generate.module.css";
import { workspaceLoadErrorMessage } from "./workspace-errors";

type StudioEntryStepProps = {
  onGoHome: () => void;
  onOpenChat: () => void;
  onOpenPhoto: () => void;
  onOpenReference: () => void;
  onOpenRecentAds: () => void;
  onOpenBrandKit: () => void;
  onOpenThread: (threadId: string) => void;
};

const statusLabelByThreadStatus: Record<string, string> = {
  draft: "브리프 작성 중",
  generating: "생성 중",
  completed: "생성 완료",
  failed: "생성 실패",
  archived: "보관됨"
};
const RECENT_WORKSPACE_LIMIT = 5;

function formatThreadDate(value: string | null | undefined): string {
  if (!value) {
    return "최근 작업";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "최근 작업";
  }
  return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}

export function StudioEntryStep({
  onGoHome,
  onOpenChat,
  onOpenPhoto,
  onOpenReference,
  onOpenRecentAds,
  onOpenBrandKit,
  onOpenThread
}: StudioEntryStepProps) {
  const [threads, setThreads] = useState<ChatThreadResponse[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [threadLoadError, setThreadLoadError] = useState<string | null>(null);
  const [threadToDelete, setThreadToDelete] = useState<ChatThreadResponse | null>(null);
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadThreads = useCallback((isActive: () => boolean = () => true) => {
    setIsLoadingThreads(true);
    setThreadLoadError(null);
    listChatThreads({ limit: RECENT_WORKSPACE_LIMIT, includeTotal: false })
      .then((response) => {
        if (!isActive()) {
          return;
        }
        setThreads(response.threads);
      })
      .catch((error) => {
        if (isActive()) {
          setThreads([]);
          setThreadLoadError(workspaceLoadErrorMessage(error));
        }
      })
      .finally(() => {
        if (isActive()) {
          setIsLoadingThreads(false);
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

  const handleConfirmDelete = async () => {
    if (!threadToDelete) {
      return;
    }
    setDeletingThreadId(threadToDelete.thread_id);
    setDeleteError(null);
    try {
      await archiveChatThread(threadToDelete.thread_id);
      setThreads((currentThreads) => currentThreads.filter((thread) => thread.thread_id !== threadToDelete.thread_id));
      setThreadToDelete(null);
    } catch {
      setDeleteError("작업방을 삭제하지 못했어요. 생성 중인 작업이라면 완료된 뒤 다시 시도해주세요.");
    } finally {
      setDeletingThreadId(null);
    }
  };

  return (
    <>
      <header className={styles.studioTopNav}>
        <button aria-label="홈으로" type="button" onClick={onGoHome}>
          <ChevronLeft size={22} aria-hidden="true" />
        </button>
        <h1>스튜디오</h1>
        <span />
      </header>

      <section className={styles.workspaceHero}>
        <div>
          <span>내 광고 작업방</span>
          <h2>만들던 광고를 이어가세요</h2>
          <p>대화, 브리프, 생성 상태가 작업방별로 저장돼요.</p>
        </div>
        <button type="button" onClick={onOpenChat}>
          <Plus size={17} aria-hidden="true" />
          새 작업
        </button>
      </section>

      <section className={styles.workspaceSection} aria-label="광고 작업방 목록">
        <div className={styles.workspaceSectionHeader}>
          <h2>최근 작업방</h2>
          <small>{threads.length > 0 ? `${threads.length}개` : "새 작업을 시작해보세요"}</small>
        </div>
        {isLoadingThreads ? (
          <p className={styles.workspaceEmptyText}>작업방을 불러오는 중입니다.</p>
        ) : threadLoadError ? (
          <div className={styles.workspaceEmptyCard} role="alert">
            <MessageCircle size={28} strokeWidth={1.7} aria-hidden="true" />
            <strong>작업방을 불러오지 못했어요</strong>
            <p>{threadLoadError}</p>
            <button className={styles.workspaceAction} type="button" onClick={() => loadThreads()}>
              다시 불러오기
            </button>
          </div>
        ) : threads.length === 0 ? (
          <div className={styles.workspaceEmptyCard}>
            <MessageCircle size={28} strokeWidth={1.7} aria-hidden="true" />
            <strong>아직 이어갈 작업방이 없어요</strong>
            <p>아래에서 새 광고 작업을 만들면 여기에 표시돼요.</p>
          </div>
        ) : (
          <div className={styles.workspaceList}>
            {threads.slice(0, RECENT_WORKSPACE_LIMIT).map((thread) => {
              const statusLabel = statusLabelByThreadStatus[thread.status] ?? "작업 중";
              return (
                <div key={thread.thread_id} className={styles.workspaceCard}>
                  <button className={styles.workspaceOpenButton} type="button" onClick={() => onOpenThread(thread.thread_id)}>
                    <span className={styles.workspaceThumb} data-status={thread.status}>
                      {thread.has_final_output ? <ImageIcon size={22} aria-hidden="true" /> : <MessageCircle size={22} aria-hidden="true" />}
                    </span>
                    <div>
                      <strong>{thread.title || "새 광고 작업"}</strong>
                      <p>
                        {statusLabel} · {thread.has_final_output ? "결과 저장됨" : thread.active_job_id ? "AI 작업 중" : "이어갈 수 있어요"}
                      </p>
                      <small>
                        <Clock size={12} aria-hidden="true" />
                        {formatThreadDate(thread.last_message_at || thread.updated_at)}
                      </small>
                    </div>
                  </button>
                  <span className={styles.workspaceActions}>
                    <button className={styles.workspaceAction} type="button" onClick={() => onOpenThread(thread.thread_id)}>
                      {thread.status === "completed" ? "보기" : "이어하기"}
                    </button>
                    <button
                      aria-label={`${thread.title || "새 광고 작업"} 작업방 삭제`}
                      className={styles.workspaceDeleteButton}
                      data-busy={deletingThreadId === thread.thread_id ? "true" : undefined}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setDeleteError(null);
                        setThreadToDelete(thread);
                      }}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                    </button>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className={styles.studioIntro}>
        <h2>어떻게 시작할까요?</h2>
        <p>원하는 방식을 선택하면 AI가 도와드릴게요.</p>
      </section>

      <div className={styles.studioOptionList}>
        <button className={styles.studioOptionCard} type="button" onClick={onOpenReference}>
          <span className={styles.optionThumb} data-kind="reference">
            <ImageIcon size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>샘플 보고 만들기</strong>
            <p>마음에 드는 광고 스타일을 골라 내 광고로 바꿔요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>

        <button className={styles.studioOptionCard} type="button" onClick={onOpenPhoto}>
          <span className={styles.optionThumb} data-kind="photo">
            <Upload size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>내 사진으로 만들기</strong>
            <p>상품 사진이나 매장 사진을 올리면 AI가 광고 방향을 제안해요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>

        <button className={styles.studioOptionCard} type="button" onClick={onOpenChat}>
          <span className={styles.optionThumb} data-kind="chat">
            <MessageCircle size={26} aria-hidden="true" />
          </span>
          <div>
            <strong>대화로 시작하기</strong>
            <p>이미지 없어도 괜찮아요. 대충 말해도 AI가 질문하며 브리프를 완성해요.</p>
          </div>
          <span className={styles.optionArrow}>→</span>
        </button>
      </div>

      <p className={styles.studioTip}>
        <Lightbulb size={17} aria-hidden="true" />
        <span>어떤 방식이든 AI가 광고 브리프를 만들고 찰떡같은 광고 이미지를 제안해드려요.</span>
      </p>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={onGoHome}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={onOpenReference}>
          <Search size={18} aria-hidden="true" />
          찾기
        </button>
        <button data-active="true" type="button">
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button type="button" onClick={onOpenRecentAds}>
          <ImageIcon size={18} aria-hidden="true" />
          보관함
        </button>
        <button type="button" onClick={onOpenBrandKit}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>

      {threadToDelete ? (
        <div className={styles.workspaceDeleteDialogBackdrop} role="presentation" onClick={() => deletingThreadId ? undefined : setThreadToDelete(null)}>
          <section
            aria-labelledby="workspace-delete-title"
            aria-modal="true"
            className={styles.workspaceDeleteDialog}
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div>
              <span className={styles.workspaceDeleteIcon}>
                <Trash2 size={18} aria-hidden="true" />
              </span>
              <h2 id="workspace-delete-title">이 작업방을 삭제할까요?</h2>
              <p>대화와 진행 상태가 최근 작업방에서 사라져요. 완성된 이미지는 보관함에 남아요.</p>
            </div>
            <strong>{threadToDelete.title || "새 광고 작업"}</strong>
            {deleteError ? <p className={styles.workspaceDeleteError}>{deleteError}</p> : null}
            <div className={styles.workspaceDeleteDialogActions}>
              <button disabled={Boolean(deletingThreadId)} type="button" onClick={() => setThreadToDelete(null)}>
                취소
              </button>
              <button data-danger="true" disabled={Boolean(deletingThreadId)} type="button" onClick={handleConfirmDelete}>
                {deletingThreadId ? "삭제 중" : "삭제"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
