"use client";

import {
  ArrowLeft,
  Briefcase,
  Check,
  Home,
  Minus,
  Search,
  Sparkles,
  User,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildMyHref } from "@/lib/my-navigation";
import { goBackOrPush } from "@/lib/navigation-history";
import styles from "./generate.module.css";

type PlanFeatureValue = boolean | "partial" | string;

type PlanFeature = {
  label: string;
  free: PlanFeatureValue;
  economic: PlanFeatureValue;
  premium: PlanFeatureValue;
};

const PLAN_FEATURES: PlanFeature[] = [
  {
    label: "AI 엔진",
    free: "로컬 AI (Gemma)",
    economic: "로컬 AI + OpenAI 혼합",
    premium: "OpenAI 고품질 모델",
  },
  {
    label: "카피 후보 수",
    free: "최대 2개",
    economic: "최대 3개",
    premium: "최대 5개",
  },
  {
    label: "최종 광고 검증",
    free: false,
    economic: "partial",
    premium: true,
  },
  {
    label: "배경 이미지 비전 검증",
    free: false,
    economic: false,
    premium: true,
  },
  {
    label: "API 비용",
    free: "없음",
    economic: "소량 발생",
    premium: "발생",
  },
];

function FeatureValue({ value }: { value: PlanFeatureValue }) {
  if (value === true) {
    return <Check size={16} className={styles.planFeatureCheck} aria-label="지원" />;
  }
  if (value === false) {
    return <X size={16} className={styles.planFeatureX} aria-label="미지원" />;
  }
  if (value === "partial") {
    return <Minus size={16} className={styles.planFeaturePartial} aria-label="부분 지원" />;
  }
  return <span>{value}</span>;
}

export function PlanInfoStep() {
  const router = useRouter();

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => goBackOrPush(router, buildMyHref("settings"))}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>요금제 안내</h1>
      </header>

      <div className={styles.planInfoContainer}>
        <p className={styles.planInfoDesc}>
          요금제에 따라 사용되는 AI 엔진과 기능 범위가 달라져요.
        </p>

        <div className={styles.planInfoCards}>
          <article className={styles.planInfoCard} data-plan="free">
            <div className={styles.planInfoCardHeader}>
              <strong>Free</strong>
              <span>무료</span>
            </div>
            <p>로컬 AI(Gemma)만 사용해 API 비용 없이 광고 카피를 생성해요. 기본적인 카피 생성에 적합해요.</p>
          </article>

          <article className={styles.planInfoCard} data-plan="economic">
            <div className={styles.planInfoCardHeader}>
              <strong>Economic</strong>
              <span>경제형</span>
            </div>
            <p>주요 카피 생성 노드에 OpenAI API를 활용해 품질을 높여요. 비용을 최소화하면서 더 나은 결과를 원할 때 적합해요.</p>
          </article>

          <article className={styles.planInfoCard} data-plan="premium">
            <div className={styles.planInfoCardHeader}>
              <strong>Premium</strong>
              <span>프리미엄</span>
            </div>
            <p>거의 모든 노드에 OpenAI 고품질 모델을 사용해요. 이미지 비전 분석과 배경 검증까지 지원해 최고 품질의 결과물을 만들어요.</p>
          </article>
        </div>

        <section className={styles.planInfoTable}>
          <h2>기능 비교</h2>
          <div className={styles.planInfoTableHead}>
            <span />
            <span>Free</span>
            <span>Economic</span>
            <span>Premium</span>
          </div>
          {PLAN_FEATURES.map((feature) => (
            <div key={feature.label} className={styles.planInfoTableRow}>
              <span>{feature.label}</span>
              <span><FeatureValue value={feature.free} /></span>
              <span><FeatureValue value={feature.economic} /></span>
              <span><FeatureValue value={feature.premium} /></span>
            </div>
          ))}
        </section>

        <p className={styles.planInfoNote}>
          * 요금제 변경은 별도 문의가 필요해요. 설정 &gt; 문의하기를 이용해주세요.
        </p>
      </div>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}>
          <Search size={18} aria-hidden="true" />
          찾기
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("studio"))}>
          <Sparkles size={18} aria-hidden="true" />
          스튜디오
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("ads"))}>
          <Briefcase size={18} aria-hidden="true" />
          보관함
        </button>
        <button data-active="true" type="button" onClick={() => router.push(buildDashboardHref("my"))}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
