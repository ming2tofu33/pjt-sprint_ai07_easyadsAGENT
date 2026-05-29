"use client";

import {
  ArrowLeft,
  ArrowRight,
  Bell,
  Briefcase,
  Camera,
  CircleAlert,
  FileImage,
  FolderOpen,
  Home,
  Image as ImageIcon,
  MessageCircle,
  Pencil,
  RotateCcw,
  Search,
  SearchX,
  Sparkles,
  UploadCloud,
  User
} from "lucide-react";
import { useRouter } from "next/navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import type { ExceptionStateKind } from "@/lib/exception-state-navigation";
import { exceptionStateContent } from "@/lib/mock-dashboard-data";
import styles from "./generate.module.css";

type ExceptionStateStepProps = {
  kind: ExceptionStateKind;
};

const modeIconById = {
  reference: ImageIcon,
  photo: Camera,
  chat: MessageCircle
};

export function ExceptionStateStep({ kind }: ExceptionStateStepProps) {
  const router = useRouter();
  const content = exceptionStateContent[kind];
  const hasBottomTabs = kind === "searchEmpty" || kind === "archiveEmpty";

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function openReference() {
    router.push(buildDashboardHref("reference"));
  }

  function openStudio() {
    router.push(buildDashboardHref("studio"));
  }

  function openAds() {
    router.push(buildDashboardHref("ads"));
  }

  function openMy() {
    router.push(buildDashboardHref("my"));
  }

  function renderTopBar() {
    if (kind === "archiveEmpty") {
      return (
        <header className={styles.exceptionTopBar}>
          <button aria-label="알림" type="button">
            <Bell size={19} aria-hidden="true" />
          </button>
          <h1>{content.surfaceTitle}</h1>
          <button aria-label="검색" type="button">
            <Search size={19} aria-hidden="true" />
          </button>
        </header>
      );
    }

    return (
      <header className={styles.exceptionTopBar}>
        <button aria-label="이전 화면" type="button" onClick={kind === "searchEmpty" ? openReference : kind === "uploadFailed" ? () => router.push(buildDashboardHref("photo")) : () => router.push(buildDashboardHref("chat", "generating"))}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>{content.surfaceTitle}</h1>
        {kind === "searchEmpty" ? (
          <button aria-label="검색" type="button">
            <Search size={19} aria-hidden="true" />
          </button>
        ) : (
          <span />
        )}
      </header>
    );
  }

  return (
    <section className={styles.exceptionScreen} data-kind={kind}>
      {renderTopBar()}

      {kind === "searchEmpty" ? (
        <label className={styles.exceptionSearchField}>
          <Search size={17} aria-hidden="true" />
          <input aria-label="레퍼런스 검색어" readOnly value={exceptionStateContent.searchEmpty.query} />
          <SearchX size={16} aria-hidden="true" />
        </label>
      ) : null}

      <section className={styles.exceptionHero} data-tone={content.tone}>
        <div className={styles.exceptionIllustration} aria-hidden="true">
          {kind === "searchEmpty" ? <SearchX size={54} /> : null}
          {kind === "archiveEmpty" ? <FolderOpen size={56} /> : null}
          {kind === "uploadFailed" ? <UploadCloud size={56} /> : null}
          {kind === "generationFailed" ? <CircleAlert size={56} /> : null}
        </div>
        <h2>{content.title}</h2>
        <p>{content.description}</p>
      </section>

      {kind === "searchEmpty" ? (
        <>
          <h2 className={styles.exceptionSectionTitle}>추천 검색어</h2>
          <div className={styles.exceptionChipGrid}>
            {exceptionStateContent.searchEmpty.suggestions.map((suggestion) => (
              <button key={suggestion} type="button">
                {suggestion}
              </button>
            ))}
          </div>
          <button className={styles.primaryButton} type="button" onClick={openReference}>
            전체 레퍼런스 보기 <ArrowRight size={18} aria-hidden="true" />
          </button>
        </>
      ) : null}

      {kind === "archiveEmpty" ? (
        <section className={styles.exceptionActionList} aria-label="광고 만들기 시작 방식">
          {exceptionStateContent.archiveEmpty.actions.map((action) => {
            const Icon = modeIconById[action.id as keyof typeof modeIconById];
            const target = action.id === "reference" ? "reference" : action.id === "photo" ? "photo" : "chat";
            return (
              <button key={action.id} type="button" onClick={() => router.push(buildDashboardHref(target))}>
                <span data-tone={action.id}>
                  <Icon size={22} aria-hidden="true" />
                </span>
                <strong>
                  {action.label}
                  <small>{action.description}</small>
                </strong>
                <ArrowRight size={18} aria-hidden="true" />
              </button>
            );
          })}
        </section>
      ) : null}

      {kind === "uploadFailed" ? (
        <>
          <section className={styles.exceptionInfoCard} aria-label="업로드 조건">
            {exceptionStateContent.uploadFailed.requirements.map((item) => (
              <article key={item.label}>
                <FileImage size={18} aria-hidden="true" />
                <strong>
                  {item.label}
                  <small>{item.value}</small>
                </strong>
              </article>
            ))}
          </section>
          <p className={styles.exceptionTip}>
            <Sparkles size={17} aria-hidden="true" />
            {exceptionStateContent.uploadFailed.tip}
          </p>
          <div className={styles.exceptionFooter}>
            <button className={styles.primaryButton} type="button" onClick={() => router.push(buildDashboardHref("photo"))}>
              다시 업로드하기 <RotateCcw size={18} aria-hidden="true" />
            </button>
            <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildDashboardHref("chat"))}>
              대화로 시작하기 <MessageCircle size={17} aria-hidden="true" />
            </button>
          </div>
        </>
      ) : null}

      {kind === "generationFailed" ? (
        <>
          <section className={styles.exceptionBriefCard}>
            <h2>저장된 브리프 요약</h2>
            <dl>
              {exceptionStateContent.generationFailed.briefRows.map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </section>
          <div className={styles.exceptionFooter}>
            <button className={styles.primaryButton} type="button" onClick={() => router.push(buildDashboardHref("chat", "generating"))}>
              다시 생성하기 <RotateCcw size={18} aria-hidden="true" />
            </button>
            <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildDashboardHref("chat"))}>
              브리프 수정하기 <Pencil size={17} aria-hidden="true" />
            </button>
            <button className={styles.exceptionTextButton} type="button" onClick={openAds}>
              내 광고 보관함 보기 <ArrowRight size={17} aria-hidden="true" />
            </button>
          </div>
        </>
      ) : null}

      {hasBottomTabs ? (
        <nav className={styles.bottomTabs} aria-label="하단 메뉴">
          <button type="button" onClick={goHome}>
            <Home size={18} aria-hidden="true" />
            홈
          </button>
          <button data-active={kind === "searchEmpty" ? "true" : undefined} type="button" onClick={openReference}>
            <Search size={18} aria-hidden="true" />
            레퍼런스
          </button>
          <button type="button" onClick={openStudio}>
            <Sparkles size={18} aria-hidden="true" />
            스튜디오
          </button>
          <button data-active={kind === "archiveEmpty" ? "true" : undefined} type="button" onClick={openAds}>
            <Briefcase size={18} aria-hidden="true" />
            보관함
          </button>
          <button type="button" onClick={openMy}>
            <User size={18} aria-hidden="true" />
            마이페이지
          </button>
        </nav>
      ) : null}
    </section>
  );
}
