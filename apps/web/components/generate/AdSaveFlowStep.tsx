"use client";

import {
  Bookmark,
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
import Image from "next/image";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { buildAdHref, type AdSaveStep } from "@/lib/ad-navigation";
import { archiveItemToCreative } from "@/lib/archive-creative";
import { getArchiveItem } from "@/lib/api-client";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { readGeneratedCreatives } from "@/lib/generated-creative-storage";
import { getAdCreativeById, resultCreatives, type MockCreative } from "@/lib/mock-dashboard-data";
import { MascotImage } from "./MascotImage";
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
  const staticCreative = getAdCreativeById(creativeId);
  const [sessionCreative, setSessionCreative] = useState<MockCreative | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [channel, setChannel] = useState("feed");
  const [fileType, setFileType] = useState<"PNG" | "JPG">("PNG");
  const [storage, setStorage] = useState("archive");
  const [downloadFeedback, setDownloadFeedback] = useState<string | null>(null);
  const creative = staticCreative ?? sessionCreative;

  useEffect(() => {
    let isActive = true;
    const generatedCreative = readGeneratedCreatives().find((item) => item.id === creativeId) ?? null;
    setSessionCreative(generatedCreative);

    if (staticCreative || generatedCreative) {
      setSessionChecked(true);
      return () => {
        isActive = false;
      };
    }

    setSessionChecked(false);
    void getArchiveItem(creativeId)
      .then((item) => {
        if (!isActive) {
          return;
        }

        setSessionCreative(archiveItemToCreative(item));
      })
      .catch(() => {
        if (isActive) {
          setSessionCreative(null);
        }
      })
      .finally(() => {
        if (isActive) {
          setSessionChecked(true);
        }
      });

    return () => {
      isActive = false;
    };
  }, [creativeId, staticCreative]);

  useEffect(() => {
    if (creative?.fileType) {
      setFileType(creative.fileType);
    }
  }, [creative?.fileType]);

  if (!creative) {
    return (
      <>
        <StepHeader title="찰떡 광고 시안" canGoBack onBack={() => router.push(buildDashboardHref("ads"))} onHome={goHome} />
        <section className={styles.emptyResultPanel} aria-label="보관함 항목 없음">
          <MascotImage role="archiveBox" decorative className={styles.emptyMascot} />
          <strong>{!sessionChecked ? "보관함 항목을 불러오는 중이에요" : "보관함에서 이 항목을 찾지 못했어요"}</strong>
          <p>
            {creativeId.startsWith("generated-")
              ? "이 브라우저에 임시 보관된 실제 생성 결과가 삭제됐거나 다른 브라우저에서 만든 항목일 수 있어요."
              : "보관함으로 돌아가 다시 확인해주세요."}
          </p>
        </section>
      </>
    );
  }
  const activeCreative = creative;
  const isGeneratedCreative =
    Boolean(activeCreative.imageUrl) &&
    (activeCreative.id.startsWith("generated-") || activeCreative.storage === "내 광고 보관함");

  function goBack() {
    if (step === "detail") {
      router.push(buildDashboardHref("ads"));
      return;
    }

    router.push(buildAdHref(activeCreative.id, step === "saved" ? "save" : "detail"));
  }

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function goArchive() {
    router.push(buildDashboardHref("ads"));
  }

  function showMockDownloadFeedback() {
    setDownloadFeedback("실제 파일 저장 연결 후 다운로드가 활성화돼요.");
  }

  if (isGeneratedCreative) {
    return (
      <>
        <div className={styles.adDetailTopNav}>
          <button aria-label="보관함으로" type="button" onClick={goArchive}>
            <ChevronLeft size={22} aria-hidden="true" />
          </button>
          <h1>생성 이미지 보기</h1>
          <span />
        </div>

        <section className={styles.generatedImageViewer} aria-label={`${activeCreative.title} 생성 이미지`}>
          <AdPreview creative={activeCreative} showCaption={false} />
        </section>

        <section className={styles.generatedImageSummary} aria-label="생성 이미지 정보">
          <div className={styles.generatedSummaryHeader}>
            <MascotImage role="downloadFile" decorative className={styles.generatedSummaryMascot} />
            <span>실제 생성</span>
          </div>
          <h2>{activeCreative.title}</h2>
          <p>생성된 이미지만 확인하고 다운로드할 수 있어요.</p>
          <dl>
            <div><dt>형식</dt><dd>{activeCreative.fileType ?? "PNG"}</dd></div>
            <div><dt>채널</dt><dd>{activeCreative.channel ?? activeCreative.format}</dd></div>
            <div><dt>저장 위치</dt><dd>{activeCreative.storage ?? "보관함"}</dd></div>
          </dl>
        </section>

        <div className={styles.stepFooter}>
          <button className={styles.primaryButton} type="button" onClick={showMockDownloadFeedback}>
            <Download size={18} aria-hidden="true" />
            이미지 다운로드
          </button>
          {downloadFeedback ? (
            <p className={styles.downloadMockNotice} role="status">
              {downloadFeedback}
            </p>
          ) : null}
          <button className={styles.secondaryButton} type="button" onClick={goArchive}>
            보관함으로 돌아가기
          </button>
        </div>
      </>
    );
  }

  if (step === "save") {
    return (
      <>
        <StepHeader title="광고 저장하기" canGoBack onBack={goBack} onHome={goHome} />

        <h2 className={styles.sectionTitle}>어디에 사용할까요?</h2>
        <div className={styles.saveHelperCard}>
          <MascotImage role="downloadFile" decorative className={styles.saveFlowMascot} />
          <p>채널에 맞게 이미지 크기와 여백을 자동으로 맞춰드려요.</p>
        </div>
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
          <button className={styles.primaryButton} type="button" onClick={() => router.push(buildAdHref(activeCreative.id, "saved"))}>
            <Download size={18} aria-hidden="true" />
            이미지 저장하기
          </button>
        </div>
      </>
    );
  }

  if (step === "saved") {
    const fileName = activeCreative.fileName ?? `${activeCreative.id}.${fileType.toLowerCase()}`;
    return (
      <>
        <section className={styles.savedCompleteHero}>
          <MascotImage role="saveGift" decorative className={styles.savedMascot} />
          <h1>광고 이미지가 저장됐어요!</h1>
          <p>바로 사용하거나, 보관함에서 다시 확인할 수 있어요.</p>
        </section>

        <section className={styles.savedFileCard} aria-label="저장된 광고 정보">
          <AdPreview creative={activeCreative} compact />
          <dl>
            <div><dt>파일명</dt><dd>{fileName}</dd></div>
            <div><dt>크기</dt><dd>{activeCreative.channel ?? "인스타 피드"} ({activeCreative.format})</dd></div>
            <div><dt>형식</dt><dd>{fileType}</dd></div>
            <div><dt>저장 위치</dt><dd>{storage === "archive" ? "내 광고 보관함" : "기기 저장"}</dd></div>
            <div><dt>저장일</dt><dd>{activeCreative.savedAt ?? "2024.05.29 14:30"}</dd></div>
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
          <button type="button" onClick={() => router.push(buildAdHref(activeCreative.id))}>
            같은 스타일로 더 만들기 <ChevronRight size={17} aria-hidden="true" />
          </button>
          <button type="button" onClick={() => router.push(buildAdHref(activeCreative.id, "save"))}>
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

      <section className={styles.adDetailPreview} aria-label={`${activeCreative.title} 상세 시안`}>
        <span className={styles.adCountBadge}>1 / 4</span>
        <button aria-label={`${activeCreative.title} 북마크`} type="button">
          <Bookmark size={19} aria-hidden="true" />
        </button>
        <AdPreview creative={activeCreative} />
      </section>

      <div className={styles.adThumbStrip} aria-label="시안 썸네일">
        {resultCreatives.map((item, index) => (
          <button data-active={item.id === activeCreative.id ? "true" : undefined} key={item.id} type="button" onClick={() => router.push(buildAdHref(item.id))}>
            <span data-tone={item.tone} />
            <small>{index + 1}</small>
          </button>
        ))}
      </div>

      <section className={styles.adDetailMeta}>
        <div className={styles.inlineTags}>
          {(activeCreative.tags ?? ["카페", "딸기라떼", "신메뉴"]).slice(0, 4).map((tag) => (
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
        <button className={styles.primaryButton} type="button" onClick={() => router.push(buildAdHref(activeCreative.id, "save"))}>
          <Download size={18} aria-hidden="true" />
          이 시안 저장하기
        </button>
      </div>
    </>
  );
}

function AdPreview({ creative, compact = false, showCaption = true }: { creative: MockCreative; compact?: boolean; showCaption?: boolean }) {
  const hasImageFile = Boolean(creative.imageUrl);
  const [imageFailed, setImageFailed] = useState(false);
  const shouldShowImage = hasImageFile && !imageFailed;

  useEffect(() => {
    setImageFailed(false);
  }, [creative.imageUrl]);

  return (
    <div className={styles.adPreviewArt} data-compact={compact ? "true" : undefined} data-has-image={hasImageFile ? "true" : undefined} data-tone={creative.tone}>
      {shouldShowImage ? (
        <Image
          alt=""
          className={styles.adPreviewImage}
          fill
          sizes={compact ? "180px" : "340px"}
          src={creative.imageUrl!}
          unoptimized
          onError={() => setImageFailed(true)}
        />
      ) : null}
      {hasImageFile && imageFailed ? (
        <div className={styles.adPreviewImageFallback}>
          <ImageDown size={22} aria-hidden="true" />
          <strong>이미지를 불러올 수 없어요</strong>
          <small>생성 파일 경로나 임시 보관 상태를 확인해주세요.</small>
        </div>
      ) : null}
      {showCaption ? (
        <div className={hasImageFile ? styles.adPreviewCaption : undefined}>
          <strong>{creative.title}</strong>
          <small>{creative.subtitle}</small>
        </div>
      ) : null}
      {hasImageFile ? null : <span aria-hidden="true" />}
    </div>
  );
}
