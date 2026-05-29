"use client";

import { ArrowLeft, ArrowRight, Check, Info, RotateCcw, TriangleAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { buildAdHref } from "@/lib/ad-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { resultCreatives } from "@/lib/mock-dashboard-data";
import { buildNotificationHref } from "@/lib/notification-navigation";
import styles from "./generate.module.css";

type NotificationDetailStepProps = {
  variant: "complete" | "failed";
};

const completeRows = [
  ["광고 목적", "신메뉴 출시"],
  ["상품 / 서비스", "딸기라떼"],
  ["분위기", "감성적인 카페 무드"],
  ["사용 채널", "인스타 피드 1:1"],
  ["생성 수량", "4개 시안"]
];

const failedRows = [
  ["광고 목적", "신메뉴 출시"],
  ["상품 / 서비스", "딸기라떼"],
  ["분위기", "감성적인 카페 무드"],
  ["사용 채널", "인스타 피드 1:1"],
  ["이미지 방향", "크림톤 배경, 중앙 상품 배치"]
];

export function NotificationDetailStep({ variant }: NotificationDetailStepProps) {
  const router = useRouter();
  const isComplete = variant === "complete";
  const rows = isComplete ? completeRows : failedRows;

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildNotificationHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>알림 상세</h1>
        <span />
      </header>

      <section className={styles.notificationDetailHero} data-variant={variant}>
        <span>{isComplete ? <Check size={34} aria-hidden="true" /> : <TriangleAlert size={34} aria-hidden="true" />}</span>
        <h2>{isComplete ? "광고 시안이 완성됐어요!" : "광고 생성에 실패했어요"}</h2>
        <p>{isComplete ? "딸기라떼 신메뉴 광고" : "일시적인 문제로 광고 시안을 만들지 못했어요."}</p>
      </section>

      <section className={styles.notificationBriefCard}>
        <h2>{isComplete ? "광고 브리프" : "저장된 브리프"}</h2>
        <dl>
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      {isComplete ? (
        <section className={styles.notificationPreviewStrip} aria-label="완성된 시안 미리보기">
          {resultCreatives.map((creative) => (
            <span data-tone={creative.tone} key={creative.id}>
              {creative.title}
            </span>
          ))}
        </section>
      ) : null}

      <button
        className={styles.primaryButton}
        type="button"
        onClick={() => router.push(isComplete ? buildAdHref("result-1") : buildDashboardHref("chat", "generating"))}
      >
        {isComplete ? "결과 확인하기" : "다시 생성하기"}
        {isComplete ? <ArrowRight size={18} aria-hidden="true" /> : <RotateCcw size={18} aria-hidden="true" />}
      </button>

      <div className={styles.notificationActionRow}>
        <button type="button" onClick={() => router.push(isComplete ? buildDashboardHref("ads") : buildDashboardHref("chat"))}>
          {isComplete ? "내 광고 보관함 보기" : "브리프 수정하기"}
        </button>
        <button type="button" onClick={() => router.push(isComplete ? buildDashboardHref("reference") : buildDashboardHref("ads"))}>
          {isComplete ? "비슷한 스타일 더 보기" : "내 광고 보관함 보기"}
        </button>
      </div>

      <p className={styles.notificationInfoBox} data-variant={variant}>
        <Info size={16} aria-hidden="true" />
        {isComplete ? "생성된 광고는 내 광고 보관함에 자동 저장됐어요." : "실패한 생성은 생성 횟수에서 차감되지 않아요."}
      </p>
    </>
  );
}
