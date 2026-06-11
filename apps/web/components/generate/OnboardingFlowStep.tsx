"use client";

import {
  ArrowRight,
  Camera,
  ChevronRight,
  HelpCircle,
  Image as ImageIcon,
  MessageCircle,
  Palette,
  Store,
  WandSparkles
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { onboardingSlides } from "@/lib/mock-dashboard-data";
import { ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE } from "@/lib/onboarding-completion";
import type { OnboardingStep } from "@/lib/onboarding-navigation";
import styles from "./generate.module.css";

const stepOrder: OnboardingStep[] = ["intro", "modes", "brief", "start"];

const modes = [
  {
    title: "샘플 보고 만들기",
    description: "마음에 드는 광고 스타일을 고르면 AI가 내 가게 광고에 맞게 바꿔줘요.",
    icon: ImageIcon,
    tone: "lime",
    href: buildDashboardHref("reference")
  },
  {
    title: "내 사진으로 만들기",
    description: "상품 사진이나 매장 사진을 올리면 AI가 광고 방향을 제안해요.",
    icon: Camera,
    tone: "purple",
    href: buildDashboardHref("photo")
  },
  {
    title: "대화로 시작하기",
    description: "사진이 없어도 괜찮아요. 원하는 광고를 편하게 적어보세요.",
    icon: MessageCircle,
    tone: "mint",
    href: buildDashboardHref("chat")
  }
];

const copyOptions = ["프리미엄 딸기라떼, 봄 한정 출시", "봄을 닮은 한 잔, 딸기라떼 출시", "오늘만 더 달콤하게, 신메뉴 딸기라떼"];

const modeActionHrefs = modes.map(({ href }) => href);
const finalActionHrefs = [buildDashboardHref("studio"), buildBrandKitHref(), buildDashboardHref("home")];

export function OnboardingFlowStep() {
  const router = useRouter();
  const [currentIndex, setCurrentIndex] = useState(0);
  const activeStep = stepOrder[currentIndex];
  const isFinal = activeStep === "start";

  useEffect(() => {
    const hrefs = new Set([...modeActionHrefs, ...finalActionHrefs]);
    hrefs.forEach((href) => router.prefetch(href));
  }, [router]);

  function handleNext() {
    setCurrentIndex((index) => Math.min(index + 1, stepOrder.length - 1));
  }

  function completeOnboarding(href: string) {
    try {
      window.localStorage.setItem(ONBOARDING_COMPLETED_STORAGE_KEY, ONBOARDING_COMPLETED_VALUE);
    } catch {
      // Navigation should still continue if storage is unavailable.
    }

    router.push(href);
  }

  function renderSlide(step: OnboardingStep) {
    const slide = onboardingSlides[step];
    const isActive = step === activeStep;
    const inactiveTabIndex = isActive ? undefined : -1;

    return (
      <article aria-hidden={!isActive} className={styles.onboardingSlide} data-step={step} key={step}>
        <div className={styles.onboardingHero}>
          <h1>{slide.title}</h1>
          <p>{slide.description}</p>
        </div>

        {step === "intro" ? (
          <>
            <div className={styles.onboardingIllustration} aria-hidden="true">
              <span />
              <i />
            </div>
            <section className={styles.onboardingFeatureCard} aria-label="앱 핵심 기능">
              {onboardingSlides.intro.features.map((feature, index) => {
                const icons = [MessageCircle, HelpCircle, ImageIcon];
                const Icon = icons[index];
                return (
                  <article key={feature.title}>
                    <span data-tone={index}>
                      <Icon size={20} aria-hidden="true" />
                    </span>
                    <strong>
                      {feature.title}
                      <small>{feature.description}</small>
                    </strong>
                  </article>
                );
              })}
            </section>
          </>
        ) : null}

        {step === "modes" ? (
          <section className={styles.onboardingModeList} aria-label="시작 방식">
            {modes.map(({ title, description, icon: Icon, tone, href }) => (
              <button
                className={styles.onboardingModeCard}
                data-tone={tone}
                key={title}
                tabIndex={inactiveTabIndex}
                type="button"
                onClick={() => {
                  if (isActive) {
                    completeOnboarding(href);
                  }
                }}
              >
                <span>
                  <Icon size={26} aria-hidden="true" />
                </span>
                <strong>
                  {title}
                  <small>{description}</small>
                </strong>
                <ChevronRight size={19} aria-hidden="true" />
              </button>
            ))}
          </section>
        ) : null}

        {step === "brief" ? (
          <section className={styles.onboardingChatDemo} aria-label="AI 브리프 예시">
            <article>
              <span>AI</span>
              <p>어떤 분위기의 광고를 원하시나요?</p>
            </article>
            <div className={styles.onboardingMoodChips}>
              {["감성적인", "상큼한", "고급스러운", "깔끔한"].map((label) => (
                <span key={label}>{label}</span>
              ))}
            </div>
            <p className={styles.onboardingUserBubble}>고급스럽고 차분한 느낌이요!</p>
            <article>
              <span>AI</span>
              <p>좋아요. 문구는 이렇게 제안드려요.</p>
            </article>
            <div className={styles.onboardingCopyCards}>
              {copyOptions.map((copy, index) => (
                <span data-active={index === 0 ? "true" : undefined} key={copy}>
                  <b>{index + 1}</b>
                  {copy}
                </span>
              ))}
            </div>
            <div className={styles.onboardingInputPreview}>
              직접 입력도 가능해요
              <Palette size={15} aria-hidden="true" />
            </div>
          </section>
        ) : null}

        {step === "start" ? (
          <section className={styles.onboardingFinalActions} aria-label="시작할 작업 선택">
            <button
              tabIndex={inactiveTabIndex}
              type="button"
              onClick={() => {
                if (isActive) {
                  completeOnboarding(buildDashboardHref("studio"));
                }
              }}
            >
              <span data-tone="ad">
                <WandSparkles size={30} aria-hidden="true" />
              </span>
              <strong>
                바로 광고 만들기
                <small>샘플, 사진, 대화 중 원하는 방식으로 지금 바로 시작해요.</small>
              </strong>
              <ArrowRight size={20} aria-hidden="true" />
            </button>
            <button
              tabIndex={inactiveTabIndex}
              type="button"
              onClick={() => {
                if (isActive) {
                  completeOnboarding(buildBrandKitHref());
                }
              }}
            >
              <span data-tone="brand">
                <Store size={30} aria-hidden="true" />
              </span>
              <strong>
                브랜드 파일 만들기
                <small>가게 이름, 로고, 자주 쓰는 문구를 저장하면 다음 광고가 쉬워져요.</small>
              </strong>
              <ArrowRight size={20} aria-hidden="true" />
            </button>
          </section>
        ) : null}
      </article>
    );
  }

  return (
    <section className={styles.onboardingScreen} data-step={activeStep}>
      <div className={styles.onboardingViewport}>
        <div className={styles.onboardingTrack} style={{ transform: `translateX(-${currentIndex * 100}%)` }}>
          {stepOrder.map((item) => renderSlide(item))}
        </div>
      </div>

      <div className={styles.onboardingFooter}>
        <div className={styles.onboardingDots} aria-label={`온보딩 ${currentIndex + 1}/4 단계`}>
          {stepOrder.map((item, index) => (
            <button
              aria-current={item === activeStep ? "step" : undefined}
              aria-label={`온보딩 ${index + 1}단계로 이동`}
              data-active={item === activeStep ? "true" : undefined}
              key={item}
              type="button"
              onClick={() => setCurrentIndex(index)}
            >
              {index + 1}
            </button>
          ))}
        </div>

        {isFinal ? (
          <button className={styles.onboardingSkipButton} type="button" onClick={() => completeOnboarding(buildDashboardHref("home"))}>
            나중에 할게요
          </button>
        ) : (
          <>
            <button className={styles.primaryButton} type="button" onClick={handleNext}>
              다음 <ArrowRight size={18} aria-hidden="true" />
            </button>
            <button className={styles.onboardingSkipButton} type="button" onClick={() => completeOnboarding(buildDashboardHref("home"))}>
              건너뛰기
            </button>
          </>
        )}
      </div>
    </section>
  );
}
