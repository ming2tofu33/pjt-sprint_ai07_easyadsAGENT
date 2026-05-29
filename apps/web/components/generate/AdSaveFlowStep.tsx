"use client";

import {
  Bookmark,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  ImageDown,
  Instagram,
  Link,
  MessageCircle,
  MoreHorizontal,
  Share2,
  Sparkles
} from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { buildAdHref, type AdSaveStep } from "@/lib/ad-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { getAdCreativeById, resultCreatives, type MockCreative } from "@/lib/mock-dashboard-data";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type AdSaveFlowStepProps = {
  creativeId: string;
  step: AdSaveStep;
};

const channels = [
  { id: "feed", label: "인스타 피드", ratio: "1:1", icon: Instagram },
  { id: "story", label: "인스타 스토리", ratio: "9:16", icon: Instagram },
  { id: "poster", label: "포스터", ratio: "4:5", icon: ImageDown },
  { id: "flyer", label: "전단지", ratio: "A4", icon: ImageDown },
  { id: "kakao", label: "카카오톡 채널", ratio: "1.91:1", icon: MessageCircle },
  { id: "blog", label: "블로그 썸네일", ratio: "4:3", icon: ImageDown }
];

const formats = [
  { id: "PNG", label: "PNG", helper: "고화질 추천" },
  { id: "JPG", label: "JPG", helper: "용량이 작아요" }
] as const;

export function AdSaveFlowStep({ creativeId, step }: AdSaveFlowStepProps) {
  const router = useRouter();
  const creative = getAdCreativeById(creativeId) ?? resultCreatives[0];
  const [channel, setChannel] = useState("feed");
  const [fileType, setFileType] = useState<"PNG" | "JPG">(creative.fileType ?? "PNG");
  const [storage, setStorage] = useState("archive");

  function goBack() {
    if (step === "detail") {
      router.push(buildDashboardHref("ads"));
      return;
    }

    router.push(buildAdHref(creative.id, step === "saved" ? "save" : "detail"));
  }

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function goArchive() {
    router.push(buildDashboardHref("ads"));
  }

  if (step === "save") {
    return (
      <>
        <StepHeader title="광고 저장하기" canGoBack onBack={goBack} onHome={goHome} />

        <h2 className={styles.sectionTitle}>어디에 사용할까요?</h2>
        <p className={styles.saveHelper}>채널에 맞게 이미지 크기와 여백을 자동으로 맞춰드려요.</p>
        <div className={styles.saveChannelGrid}>
          {channels.map(({ id, label, ratio, icon: Icon }) => (
            <button data-active={channel === id ? "true" : undefined} key={id} type="button" onClick={() => setChannel(id)}>
              <span>{label}</span>
              <small>{ratio}</small>
              <Icon size={18} aria-hidden="true" />
            </button>
          ))}
        </div>

        <h2 className={styles.sectionTitle}>파일 형식</h2>
        <div className={styles.saveOptionGrid}>
          {formats.map((format) => (
            <button data-active={fileType === format.id ? "true" : undefined} key={format.id} type="button" onClick={() => setFileType(format.id)}>
              <span>
                <strong>{format.label}</strong>
                <small>{format.helper}</small>
              </span>
              {fileType === format.id ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
            </button>
          ))}
        </div>

        <h2 className={styles.sectionTitle}>저장 위치</h2>
        <div className={styles.saveOptionGrid}>
          <button data-active={storage === "archive" ? "true" : undefined} type="button" onClick={() => setStorage("archive")}>
            <span>
              <strong>내 광고 보관함</strong>
              <small>서비스 안에서 다시 활용</small>
            </span>
            {storage === "archive" ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
          </button>
          <button data-active={storage === "device" ? "true" : undefined} type="button" onClick={() => setStorage("device")}>
            <span>
              <strong>기기에 저장</strong>
              <small>이미지 파일로 저장</small>
            </span>
            {storage === "device" ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
          </button>
        </div>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={() => router.push(buildAdHref(creative.id, "saved"))}>
            <Download size={18} aria-hidden="true" />
            이미지 저장하기
          </button>
        </div>
      </>
    );
  }

  if (step === "saved") {
    const fileName = creative.fileName ?? `${creative.id}.${fileType.toLowerCase()}`;
    return (
      <>
        <section className={styles.savedCompleteHero}>
          <span>
            <Check size={34} aria-hidden="true" />
          </span>
          <h1>광고 이미지가 저장됐어요!</h1>
          <p>바로 사용하거나, 보관함에서 다시 확인할 수 있어요.</p>
        </section>

        <section className={styles.savedFileCard} aria-label="저장된 광고 정보">
          <AdPreview creative={creative} compact />
          <dl>
            <div><dt>파일명</dt><dd>{fileName}</dd></div>
            <div><dt>크기</dt><dd>{creative.channel ?? "인스타 피드"} ({creative.format})</dd></div>
            <div><dt>형식</dt><dd>{fileType}</dd></div>
            <div><dt>저장 위치</dt><dd>{storage === "archive" ? "내 광고 보관함" : "기기 저장"}</dd></div>
            <div><dt>저장일</dt><dd>{creative.savedAt ?? "2024.05.29 14:30"}</dd></div>
          </dl>
        </section>

        <div className={styles.savedActionGrid}>
          <button type="button">
            <Download size={18} aria-hidden="true" />
            이미지 저장
          </button>
          <button type="button">
            <Link size={18} aria-hidden="true" />
            링크 복사
          </button>
          <button type="button">
            <Share2 size={18} aria-hidden="true" />
            공유하기
          </button>
        </div>

        <section className={styles.nextUseCard}>
          <h2>다음에 활용해보세요</h2>
          <button type="button" onClick={() => router.push(buildAdHref(creative.id))}>
            같은 스타일로 더 만들기 <ChevronRight size={17} aria-hidden="true" />
          </button>
          <button type="button" onClick={() => router.push(buildAdHref(creative.id, "save"))}>
            스토리용으로 만들기 (9:16) <ChevronRight size={17} aria-hidden="true" />
          </button>
        </section>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={goArchive}>
            내 광고 보관함 보기
          </button>
          <button className={styles.textButton} type="button" onClick={goHome}>
            홈으로 돌아가기
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className={styles.adDetailTopNav}>
        <button aria-label="보관함으로" type="button" onClick={goBack}>
          <ChevronLeft size={22} aria-hidden="true" />
        </button>
        <h1>찰떡 광고 시안</h1>
        <button aria-label="더보기" type="button">
          <MoreHorizontal size={22} aria-hidden="true" />
        </button>
      </div>

      <section className={styles.adDetailPreview} aria-label={`${creative.title} 상세 시안`}>
        <span className={styles.adCountBadge}>1 / 4</span>
        <button aria-label={`${creative.title} 북마크`} type="button">
          <Bookmark size={19} aria-hidden="true" />
        </button>
        <AdPreview creative={creative} />
      </section>

      <div className={styles.adThumbStrip} aria-label="시안 썸네일">
        {resultCreatives.map((item, index) => (
          <button data-active={item.id === creative.id ? "true" : undefined} key={item.id} type="button" onClick={() => router.push(buildAdHref(item.id))}>
            <span data-tone={item.tone} />
            <small>{index + 1}</small>
          </button>
        ))}
      </div>

      <section className={styles.adDetailMeta}>
        <div className={styles.inlineTags}>
          {(creative.tags ?? ["카페", "딸기라떼", "신메뉴"]).slice(0, 4).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <p>
          <Sparkles size={16} aria-hidden="true" />
          크림톤 배경, 딸기라떼를 중앙에 크게 배치하고 우측 여백에 카피 배치
        </p>
      </section>

      <h2 className={styles.sectionTitle}>빠른 수정</h2>
      <div className={styles.editActionGrid} aria-label="빠른 수정 요청">
        {["문구 수정", "비슷하게 더 만들기", "다른 비율로 만들기"].map((action) => (
          <button key={action} type="button">
            {action}
          </button>
        ))}
      </div>

      <div className={styles.stepFooter}>
        <button className={styles.primaryButton} type="button" onClick={() => router.push(buildAdHref(creative.id, "save"))}>
          <Download size={18} aria-hidden="true" />
          이 시안 저장하기
        </button>
      </div>
    </>
  );
}

function AdPreview({ creative, compact = false }: { creative: MockCreative; compact?: boolean }) {
  return (
    <div className={styles.adPreviewArt} data-compact={compact ? "true" : undefined} data-tone={creative.tone}>
      <div>
        <strong>{creative.title}</strong>
        <small>{creative.subtitle}</small>
      </div>
      <span aria-hidden="true" />
    </div>
  );
}
