"use client";

import {
  ArrowRight,
  Briefcase,
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
import NextImage from "next/image";
import type { ChangeEvent, ReactNode } from "react";
import { useRef, useState } from "react";
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
  type BrandKitInput,
  type StoredBrandKit
} from "@/lib/brand-kit-storage";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { MascotImage } from "./MascotImage";
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
const productOptions = ["대표 메뉴", "시그니처 상품", "예약 서비스", "이벤트 혜택"];
const colorOptions = ["#FFD7C9", "#FFE4B5", "#BCEBE2", "#C8B8FF", "#111111"];
const acceptedLogoMimeTypes = new Set(["image/jpeg", "image/png"]);
const maxLogoFileSize = 5 * 1024 * 1024;

export function BrandKitFlowStep({ step }: BrandKitFlowStepProps) {
  const router = useRouter();
  const logoInputRef = useRef<HTMLInputElement | null>(null);
  const initialBrandKit = readBrandKitDraft();
  const [brandKitStatus, setBrandKitStatus] = useState(initialBrandKit.status);
  const [businessName, setBusinessName] = useState(initialBrandKit.businessName);
  const [businessType, setBusinessType] = useState(initialBrandKit.businessType);
  const [region, setRegion] = useState(initialBrandKit.region);
  const [sns, setSns] = useState(initialBrandKit.sns);
  const [logoFileName, setLogoFileName] = useState(initialBrandKit.logoFileName);
  const [logoDataUrl, setLogoDataUrl] = useState(initialBrandKit.logoDataUrl);
  const [logoErrorMessage, setLogoErrorMessage] = useState("");
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
      logoFileName,
      logoDataUrl,
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

  async function handleLogoChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const file = input.files?.[0] ?? null;
    if (!file) {
      return;
    }

    try {
      if (!acceptedLogoMimeTypes.has(file.type)) {
        setLogoErrorMessage("JPG, PNG 형식의 로고 이미지만 사용할 수 있어요.");
        return;
      }
      if (file.size > maxLogoFileSize) {
        setLogoErrorMessage("로고 이미지는 최대 5MB까지 사용할 수 있어요.");
        return;
      }

      const nextLogoDataUrl = await createLogoPreviewDataUrl(file);
      setLogoFileName(file.name);
      setLogoDataUrl(nextLogoDataUrl);
      setLogoErrorMessage("");
    } catch {
      setLogoErrorMessage("로고 이미지를 불러오지 못했어요. 다른 파일을 선택해주세요.");
    } finally {
      input.value = "";
    }
  }

  if (step === "info") {
    return (
      <>
        <StepHeader title="가게 정보를 알려주세요" canGoBack onBack={goBack} onHome={goHome} />

        <section className={styles.brandFlowIntroCard}>
          <MascotImage role="cloudUpload" decorative className={styles.brandFlowMiniMascot} />
          <p>입력한 정보는 AI가 광고를 이해하는 데 활용돼요.</p>
        </section>

        <label className={styles.brandInputField}>
          <span>가게 이름 *</span>
          <input aria-label="가게 이름" value={businessName} placeholder="가게 이름을 입력하세요" onChange={(event) => setBusinessName(event.target.value)} />
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
          <input aria-label="SNS 계정" value={sns} placeholder="SNS 계정을 입력하세요" onChange={(event) => setSns(event.target.value)} />
        </label>

        <input ref={logoInputRef} accept="image/jpeg,image/png" className={styles.logoFileInput} type="file" onChange={handleLogoChange} />
        <button className={styles.logoUploadCard} data-has-logo={logoDataUrl ? "true" : undefined} type="button" onClick={() => logoInputRef.current?.click()}>
          {logoDataUrl ? (
            <span className={styles.logoPreviewFrame}>
              <NextImage alt="" fill sizes="56px" src={logoDataUrl} unoptimized />
            </span>
          ) : (
            <Upload size={22} aria-hidden="true" />
          )}
          <strong>{logoFileName ? "로고 이미지 선택됨" : "로고 이미지 추가"}</strong>
          <small>{logoFileName || "JPG, PNG 최대 5MB"}</small>
        </button>
        {logoErrorMessage ? (
          <p className={styles.brandInlineError} role="alert">
            {logoErrorMessage}
          </p>
        ) : null}

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
        <section className={styles.brandFlowIntroCard}>
          <MascotImage role="checkPaper" decorative className={styles.brandFlowMiniMascot} />
          <p>선택한 정보는 광고 스타일 제안에 반영돼요.</p>
        </section>

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
          <StepHeader title="브랜드 파일" canGoBack onBack={goBack} onHome={goHome} />
          <section className={styles.brandCompleteHero}>
            <MascotImage role="brandSettings" decorative className={styles.brandHeroMascot} />
            <h1>브랜드 파일이 아직 저장되지 않았어요</h1>
            <p>가게 정보를 입력하고 저장하면 홈과 마이페이지에 바로 반영됩니다.</p>
          </section>

          <BrandFlowFooter current={1} tone="lime">
            <button className={styles.primaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
              브랜드 파일 만들기 <ArrowRight size={18} aria-hidden="true" />
            </button>
          </BrandFlowFooter>
        </>
      );
    }

    const savedBrandKitPreview: StoredBrandKit = {
      ...currentBrandKitInput(),
      logoFileName,
      logoDataUrl,
      status: "saved",
      updatedAt: ""
    };

    return (
      <>
        <StepHeader title="브랜드 파일" canGoBack onBack={goBack} onHome={goHome} />
        <section className={styles.brandCompleteHero}>
          <MascotImage role="brandShield" decorative className={styles.brandHeroMascot} />
          <h1>브랜드 파일이 저장됐어요</h1>
          <p>현재는 이 브라우저 안에서만 확인되는 임시 브랜드 파일이에요.</p>
        </section>

        <section className={styles.brandSummaryCard}>
          <div className={styles.brandIdentity}>
            <span>
              {logoDataUrl ? <NextImage alt="" height={56} src={logoDataUrl} width={56} unoptimized /> : <Store size={28} aria-hidden="true" />}
            </span>
            <div>
              <strong>{businessName}</strong>
              <small>{businessType}</small>
              <p>{brandKitMeta(savedBrandKitPreview)}</p>
            </div>
          </div>
          <dl className={styles.brandFacts}>
            <div><dt>브랜드 톤</dt><dd>{brandKitTone(savedBrandKitPreview)}</dd></div>
            <div>
              <dt>브랜드 컬러</dt>
              <dd>{colors.slice(0, 4).map((color) => <span key={color} style={{ background: color }} />)}</dd>
            </div>
            <div><dt>자주 쓰는 문구</dt><dd>{brandKitPhrases(savedBrandKitPreview)}</dd></div>
            <div><dt>대표 상품</dt><dd>{brandKitProducts(savedBrandKitPreview)}</dd></div>
          </dl>
        </section>

        <p className={styles.styleNotice}>
          <Sparkles size={17} aria-hidden="true" />
          브랜드 파일이 저장되면 “이번 주말 이벤트 광고 만들어줘” 같은 요청에 자동으로 참고돼요.
        </p>

        <BrandFlowFooter current={4} tone="coral">
          <button className={styles.primaryButton} type="button" onClick={() => router.push(buildDashboardHref("studio"))}>
            광고 만들기 <Sparkles size={18} aria-hidden="true" />
          </button>
          <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
            브랜드 파일 수정하기
          </button>
        </BrandFlowFooter>
      </>
    );
  }

  return (
    <>
      <StepHeader title="브랜드 파일" canGoBack onBack={goBack} onHome={goHome} />

      <section className={styles.brandStartHero}>
        <div>
          <h1>우리 가게 정보를 저장해두면,</h1>
          <p>빠르고 정확한 광고 이미지 생성에 도움이 돼요</p>
        </div>
        <MascotImage role="brandShield" decorative className={styles.brandStartMascot} />
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
          브랜드 파일 만들기 <ArrowRight size={18} aria-hidden="true" />
        </button>
      </BrandFlowFooter>

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

function createLogoPreviewDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("logo-read-failed"));
    reader.onload = () => {
      const source = typeof reader.result === "string" ? reader.result : "";
      if (!source) {
        reject(new Error("logo-empty"));
        return;
      }

      const image = new window.Image();
      image.onerror = () => resolve(source);
      image.onload = () => {
        const sourceWidth = image.naturalWidth || image.width;
        const sourceHeight = image.naturalHeight || image.height;
        const maxSide = 320;
        const scale = Math.min(1, maxSide / Math.max(sourceWidth, sourceHeight));
        const width = Math.max(1, Math.round(sourceWidth * scale));
        const height = Math.max(1, Math.round(sourceHeight * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        if (!context) {
          resolve(source);
          return;
        }

        context.clearRect(0, 0, width, height);
        context.drawImage(image, 0, 0, width, height);
        resolve(canvas.toDataURL("image/png"));
      };
      image.src = source;
    };
    reader.readAsDataURL(file);
  });
}

function BrandFlowFooter({ children, current, tone }: { children: ReactNode; current: number; tone: "lime" | "purple" | "mint" | "coral" }) {
  return (
    <div className={styles.stepFooter}>
      {children}
      <div className={styles.brandFlowProgress} data-tone={tone} aria-label={`브랜드 파일 ${current}/4 단계`}>
        {[1, 2, 3, 4].map((item) => (
          <span data-active={item <= current ? "true" : undefined} key={item} />
        ))}
      </div>
    </div>
  );
}
