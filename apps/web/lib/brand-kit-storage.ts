export type BrandKitStatus = "draft" | "saved";

export type StoredBrandKit = {
  businessName: string;
  businessType: string;
  region: string;
  sns: string;
  logoFileName: string;
  logoDataUrl: string;
  tones: string[];
  colors: string[];
  phrases: string[];
  products: string[];
  status: BrandKitStatus;
  updatedAt: string;
};

export type BrandKitInput = Omit<StoredBrandKit, "status" | "updatedAt" | "logoFileName" | "logoDataUrl"> & {
  logoFileName?: string;
  logoDataUrl?: string;
};

export const BRAND_KIT_STORAGE_KEY = "easyads_brand_kit_v1";

const EMPTY_BRAND_KIT: BrandKitInput = {
  businessName: "",
  businessType: "",
  region: "",
  sns: "",
  logoFileName: "",
  logoDataUrl: "",
  tones: [],
  colors: [],
  phrases: [],
  products: []
};

function cleanText(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function cleanList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(cleanText).filter(Boolean) : [];
}

function normalizeBrandKit(value: Partial<StoredBrandKit> | null | undefined): StoredBrandKit {
  return {
    businessName: cleanText(value?.businessName),
    businessType: cleanText(value?.businessType),
    region: cleanText(value?.region),
    sns: cleanText(value?.sns),
    logoFileName: cleanText(value?.logoFileName),
    logoDataUrl: cleanText(value?.logoDataUrl),
    tones: cleanList(value?.tones),
    colors: cleanList(value?.colors),
    phrases: cleanList(value?.phrases),
    products: cleanList(value?.products),
    status: value?.status === "saved" ? "saved" : "draft",
    updatedAt: cleanText(value?.updatedAt)
  };
}

function writeBrandKit(input: BrandKitInput, status: BrandKitStatus): StoredBrandKit {
  const next = normalizeBrandKit({
    ...input,
    status,
    updatedAt: new Date().toISOString()
  });
  try {
    window.localStorage.setItem(BRAND_KIT_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // The active form still reflects the user's input even if storage is blocked.
  }
  return next;
}

export function createEmptyBrandKitDraft(): StoredBrandKit {
  return normalizeBrandKit({ ...EMPTY_BRAND_KIT, status: "draft" });
}

export function readBrandKit(): StoredBrandKit | null {
  try {
    const raw = window.localStorage.getItem(BRAND_KIT_STORAGE_KEY);
    return raw ? normalizeBrandKit(JSON.parse(raw) as Partial<StoredBrandKit>) : null;
  } catch {
    return null;
  }
}

export function readBrandKitDraft(): StoredBrandKit {
  return readBrandKit() ?? createEmptyBrandKitDraft();
}

export function readSavedBrandKit(): StoredBrandKit | null {
  const brandKit = readBrandKit();
  return brandKit?.status === "saved" ? brandKit : null;
}

export function writeBrandKitDraft(input: BrandKitInput): StoredBrandKit {
  return writeBrandKit(input, "draft");
}

export function saveBrandKit(input: BrandKitInput): StoredBrandKit {
  return writeBrandKit(input, "saved");
}

/**
 * Maps a server `/api/brand-kits/current` payload into the local StoredBrandKit
 * shape. Returns null when the user has no server-side brand kit. Tolerant of
 * receiving either the wrapped response ({ has_brand_kit, brand_kit }) or the
 * bare brand_kit object.
 */
export function brandKitFromServerResponse(payload: unknown): StoredBrandKit | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const root = payload as Record<string, unknown>;
  if (root.has_brand_kit === false) {
    return null;
  }
  const source = (root.brand_kit ?? root) as Record<string, unknown> | null;
  if (!source || typeof source !== "object") {
    return null;
  }

  const storeName = cleanText(source.store_name);
  const businessType = cleanText(source.business_type);
  if (!storeName && !businessType) {
    return null;
  }

  const logo = (source.logo_asset ?? null) as Record<string, unknown> | null;
  const products = Array.isArray(source.representative_products)
    ? (source.representative_products as Array<Record<string, unknown>>)
        .map((item) => cleanText(item?.name))
        .filter(Boolean)
    : [];

  return normalizeBrandKit({
    businessName: storeName,
    businessType,
    region: cleanText(source.region_text),
    sns: cleanText(source.sns_handle),
    logoFileName: cleanText(logo?.file_name ?? logo?.fileName),
    logoDataUrl: cleanText(logo?.url ?? logo?.signed_url ?? logo?.signedUrl),
    tones: cleanList(source.brand_tones),
    colors: cleanList(source.brand_colors),
    phrases: cleanList(source.frequent_phrases),
    products,
    status: "saved",
    updatedAt: cleanText(source.updated_at)
  });
}

export function brandKitMeta(brandKit: StoredBrandKit): string {
  return [brandKit.businessType, brandKit.region, brandKit.sns].filter(Boolean).join(" · ") || "가게 정보 저장됨";
}

export function brandKitTone(brandKit: StoredBrandKit): string {
  return brandKit.tones.length > 0 ? brandKit.tones.join(", ") : "브랜드 톤 선택 전";
}

export function brandKitProducts(brandKit: StoredBrandKit): string {
  return brandKit.products.length > 0 ? brandKit.products.join(", ") : "대표 상품 선택 전";
}

export function brandKitPhrases(brandKit: StoredBrandKit): string {
  return brandKit.phrases.length > 0 ? brandKit.phrases.join(", ") : "자주 쓰는 문구 선택 전";
}
