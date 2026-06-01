"use client";

import {
  ArrowRight,
  Briefcase,
  CheckCircle2,
  Home,
  ImagePlus,
  MessageCircle,
  Package,
  Palette,
  Plus,
  Search,
  Sparkles,
  Store,
  Upload,
  User,
  Utensils
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref, type BrandKitStep as BrandKitFlowStage } from "@/lib/brand-kit-navigation";
import {
  brandKitMeta,
  brandKitPhrases,
  brandKitProducts,
  brandKitTone,
  readBrandKitDraft,
  saveBrandKit,
  writeBrandKitDraft,
  type BrandKitInput
} from "@/lib/brand-kit-storage";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { StepHeader } from "./StepHeader";
import styles from "./generate.module.css";

type BrandKitFlowStepProps = {
  step: BrandKitFlowStage;
};

const businessTypes = [
  { label: "카페", icon: Store },
  { label: "음식점", icon: Utensils },
  { label: "뷰티샵", icon: Sparkles },
  { label: "꽃집", icon: Palette },
  { label: "학원", icon: Briefcase },
  { label: "기타", icon: Plus }
];

const toneOptions = ["감성적인", "고급스러운", "귀여운", "깔끔한", "트렌디한", "따뜻한"];
const phraseOptions = ["예약은 DM 주세요", "신메뉴 출시", "매일 한정 수량", "오늘만 할인", "감사합니다"];
const productOptions = ["딸기라떼", "바닐라라떼", "크림라떼", "아메리카노"];
const colorOptions = ["#FFD7C9", "#FFE4B5", "#BCEBE2", "#C8B8FF", "#111111"];

export function BrandKitFlowStep({ step }: BrandKitFlowStepProps) {
  const router = useRouter();
  const initialBrandKit = readBrandKitDraft();
  const [brandKitStatus, setBrandKitStatus] = useState(initialBrandKit.status);
  const [businessName, setBusinessName] = useState(initialBrandKit.businessName);
  const [businessType, setBusinessType] = useState(initialBrandKit.businessType);
  const [region, setRegion] = useState(initialBrandKit.region);
  const [sns, setSns] = useState(initialBrandKit.sns);
  const [tones, setTones] = useState<string[]>(initialBrandKit.tones);
  const [colors, setColors] = useState<string[]>(initialBrandKit.colors);
  const [phrases, setPhrases] = useState<string[]>(initialBrandKit.phrases);
  const [products, setProducts] = useState<string[]>(initialBrandKit.products);
  const canContinueInfo = Boolean(businessName.trim() && businessType);

  function goBack() {
    if (step === "start") {
      router.push(buildDashboardHref("my"));
      return;
    }

    router.push(buildBrandKitHref(step === "complete" ? "tone" : step === "tone" ? "info" : "start"));
  }

  function goHome() {
    router.push(buildDashboardHref("home"));
  }

  function toggleValue(value: string, values: string[], setValues: (nextValues: string[]) => void) {
    setValues(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  }

  function currentBrandKitInput(): BrandKitInput {
    return {
      businessName,
      businessType,
      region,
      sns,
      tones,
      colors,
      phrases,
      products
    };
  }

  function continueToTone() {
    const next = writeBrandKitDraft(currentBrandKitInput());
    setBrandKitStatus(next.status);
    router.push(buildBrandKitHref("tone"));
  }

  function completeBrandKit() {
    const next = saveBrandKit(currentBrandKitInput());
    setBrandKitStatus(next.status);
    router.push(buildBrandKitHref("complete"));
  }

  if (step === "info") {
    return (
      <>
        <StepHeader title="가게 정보를 알려주세요" canGoBack onBack={goBack} onHome={goHome} />

        <p className={styles.brandFlowIntro}>입력한 정보는 AI가 광고를 이해하는 데 활용돼요.</p>

        <label className={styles.brandInputField}>
          <span>가게 이름 *</span>
          <input aria-label="가게 이름" value={businessName} placeholder="예) 도민 카페" onChange={(event) => setBusinessName(event.target.value)} />
        </label>

        <h2 className={styles.sectionTitle}>업종 *</h2>
        <div className={styles.brandTypeGrid}>
          {businessTypes.map(({ label, icon: Icon }) => (
            <button data-active={businessType === label ? "true" : undefined} key={label} type="button" onClick={() => setBusinessType(label)}>
              <Icon size={16} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>

        <label className={styles.brandInputField}>
          <span>지역 / 상권</span>
          <input aria-label="지역 또는 상권" value={region} placeholder="예) 성수동 감성 상권" onChange={(event) => setRegion(event.target.value)} />
        </label>

        <label className={styles.brandInputField}>
          <span>SNS 계정</span>
          <input aria-label="SNS 계정" value={sns} placeholder="예) @domin_cafe" onChange={(event) => setSns(event.target.value)} />
        </label>

        <button className={styles.logoUploadCard} type="button">
          <Upload size={22} aria-hidden="true" />
          <strong>로고 이미지 추가</strong>
          <small>JPG, PNG 최대 5MB</small>
        </button>

        <BrandFlowFooter current={2} tone="purple">
          <button className={styles.primaryButton} disabled={!canContinueInfo} type="button" onClick={continueToTone}>
            다음 <ArrowRight size={18} aria-hidden="true" />
          </button>
        </BrandFlowFooter>
      </>
    );
  }

  if (step === "tone") {
    return (
      <>
        <StepHeader title="우리 가게는 어떤 느낌인가요?" canGoBack onBack={goBack} onHome={goHome} />
        <p className={styles.brandFlowIntro}>선택한 정보는 광고 스타일 제안에 반영돼요.</p>

        <h2 className={styles.sectionTitle}>브랜드 톤</h2>
        <div className={styles.brandChipWrap}>
          {toneOptions.map((tone) => (
            <button data-active={tones.includes(tone) ? "true" : undefined} key={tone} type="button" onClick={() => toggleValue(tone, tones, setTones)}>
              <Sparkles size={15} aria-hidden="true" />
              {tone}
            </button>
          ))}
        </div>

        <h2 className={styles.sectionTitle}>브랜드 컬러</h2>
        <div className={styles.brandColorRow} aria-label="브랜드 컬러">
          {colorOptions.map((color) => (
            <button aria-label={`${color} 색상`} data-active={colors.includes(color) ? "true" : undefined} key={color} style={{ background: color }} type="button" onClick={() => toggleValue(color, colors, setColors)} />
          ))}
          <button aria-label="컬러 직접 선택" type="button">
            <Plus size={18} aria-hidden="true" />
          </button>
        </div>

        <h2 className={styles.sectionTitle}>자주 쓰는 문구</h2>
        <div className={styles.brandChipWrap}>
          {phraseOptions.map((phrase) => (
            <button data-active={phrases.includes(phrase) ? "true" : undefined} key={phrase} type="button" onClick={() => toggleValue(phrase, phrases, setPhrases)}>
              <MessageCircle size={15} aria-hidden="true" />
              {phrase}
            </button>
          ))}
          <button type="button">
            <Plus size={15} aria-hidden="true" />
            직접 추가하기
          </button>
        </div>

        <h2 className={styles.sectionTitle}>대표 상품</h2>
        <div className={styles.brandChipWrap}>
          {productOptions.map((product) => (
            <button data-active={products.includes(product) ? "true" : undefined} key={product} type="button" onClick={() => toggleValue(product, products, setProducts)}>
              <Package size={15} aria-hidden="true" />
              {product}
            </button>
          ))}
          <button type="button">
            <Plus size={15} aria-hidden="true" />
            상품 추가
          </button>
        </div>

        <BrandFlowFooter current={3} tone="mint">
          <button className={styles.primaryButton} disabled={!canContinueInfo} type="button" onClick={completeBrandKit}>
            저장하기 <ArrowRight size={18} aria-hidden="true" />
          </button>
        </BrandFlowFooter>
      </>
    );
  }

  if (step === "complete") {
    if (brandKitStatus !== "saved") {
      return (
        <>
          <StepHeader title="브랜드 키트" canGoBack onBack={goBack} onHome={goHome} />
          <section className={styles.brandCompleteHero}>
            <Store size={42} aria-hidden="true" />
            <h1>브랜드 키트가 아직 저장되지 않았어요</h1>
            <p>가게 정보를 입력하고 저장하면 홈과 마이페이지에 바로 반영됩니다.</p>
          </section>

          <BrandFlowFooter current={1} tone="lime">
            <button className={styles.primaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
              브랜드 키트 만들기 <ArrowRight size={18} aria-hidden="true" />
            </button>
          </BrandFlowFooter>
        </>
      );
    }

    return (
      <>
        <StepHeader title="브랜드 키트" canGoBack onBack={goBack} onHome={goHome} />
        <section className={styles.brandCompleteHero}>
          <CheckCircle2 size={42} aria-hidden="true" />
          <h1>브랜드 키트가 저장됐어요</h1>
          <p>현재는 이 브라우저 안에서만 확인되는 임시 브랜드 키트예요.</p>
        </section>

        <section className={styles.brandSummaryCard}>
          <div className={styles.brandIdentity}>
            <span>
              <Store size={28} aria-hidden="true" />
            </span>
            <div>
              <strong>{businessName}</strong>
              <small>{businessType}</small>
              <p>{brandKitMeta({ ...currentBrandKitInput(), status: "saved", updatedAt: "" })}</p>
            </div>
          </div>
          <dl className={styles.brandFacts}>
            <div><dt>브랜드 톤</dt><dd>{brandKitTone({ ...currentBrandKitInput(), status: "saved", updatedAt: "" })}</dd></div>
            <div>
              <dt>브랜드 컬러</dt>
              <dd>{colors.slice(0, 4).map((color) => <span key={color} style={{ background: color }} />)}</dd>
            </div>
            <div><dt>자주 쓰는 문구</dt><dd>{brandKitPhrases({ ...currentBrandKitInput(), status: "saved", updatedAt: "" })}</dd></div>
            <div><dt>대표 상품</dt><dd>{brandKitProducts({ ...currentBrandKitInput(), status: "saved", updatedAt: "" })}</dd></div>
          </dl>
        </section>

        <p className={styles.styleNotice}>
          <Sparkles size={17} aria-hidden="true" />
          브랜드 키트 저장 API가 연결되면 “이번 주말 이벤트 광고 만들어줘” 같은 요청에 자동 반영됩니다.
        </p>

        <BrandFlowFooter current={4} tone="coral">
          <button className={styles.primaryButton} type="button" onClick={() => router.push(buildDashboardHref("studio"))}>
            광고 만들기 <Sparkles size={18} aria-hidden="true" />
          </button>
          <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
            브랜드 키트 수정하기
          </button>
        </BrandFlowFooter>
      </>
    );
  }

  return (
    <>
      <StepHeader title="브랜드 키트" canGoBack onBack={goBack} onHome={goHome} />

      <section className={styles.brandStartHero}>
        <div>
          <h1>우리 가게 정보를 저장해두면,</h1>
          <p>지금은 샘플 입력 화면으로 먼저 흐름을 확인할 수 있어요.</p>
        </div>
        <span aria-hidden="true">
          <Store size={42} />
        </span>
      </section>

      <section className={styles.brandInfoCard}>
        <h2>저장할 수 있는 정보</h2>
        <ul>
          <li><Store size={17} aria-hidden="true" /> 가게 이름, 업종, 지역</li>
          <li><ImagePlus size={17} aria-hidden="true" /> 로고, 브랜드 컬러</li>
          <li><MessageCircle size={17} aria-hidden="true" /> 브랜드 톤, 자주 쓰는 문구</li>
          <li><Package size={17} aria-hidden="true" /> 대표 상품, 영업시간</li>
        </ul>
      </section>

      <BrandFlowFooter current={1} tone="lime">
        <button className={styles.primaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
          브랜드 키트 만들기 <ArrowRight size={18} aria-hidden="true" />
        </button>
      </BrandFlowFooter>

      <nav className={styles.bottomTabs} aria-label="하단 메뉴">
        <button type="button" onClick={() => router.push(buildDashboardHref("home"))}>
          <Home size={18} aria-hidden="true" />
          홈
        </button>
        <button type="button" onClick={() => router.push(buildDashboardHref("reference"))}>
          <Search size={18} aria-hidden="true" />
          레퍼런스
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

function BrandFlowFooter({ children, current, tone }: { children: ReactNode; current: number; tone: "lime" | "purple" | "mint" | "coral" }) {
  return (
    <div className={styles.stepFooter}>
      {children}
      <div className={styles.brandFlowProgress} data-tone={tone} aria-label={`브랜드 키트 ${current}/4 단계`}>
        {[1, 2, 3, 4].map((item) => (
          <span data-active={item <= current ? "true" : undefined} key={item} />
        ))}
      </div>
    </div>
  );
}
