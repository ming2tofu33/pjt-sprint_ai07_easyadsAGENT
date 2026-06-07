export type CreativeTone = "strawberry" | "mint" | "cream" | "sunny" | "peach";

export type MockCreative = {
  id: string;
  title: string;
  subtitle: string;
  format: string;
  imageUrl?: string | null;
  date?: string;
  tone: CreativeTone;
  badge?: string;
  status?: "saved" | "generating" | "favorite" | "draft";
  progress?: number;
  channel?: string;
  fileName?: string;
  fileType?: "PNG" | "JPG";
  storage?: string;
  savedAt?: string;
  tags?: string[];
  savedCount?: number;
  styleProfile?: {
    colors: string[];
    layout: string;
    copySpace: string;
    mood: string;
    bestUse: string;
  };
};

export const referenceCreatives: MockCreative[] = [
  {
    id: "ref-strawberry-poster",
    title: "감성 카페 신메뉴 포스터",
    subtitle: "봄을 닮은 한 잔, 딸기라떼 출시",
    format: "포스터",
    tone: "strawberry",
    badge: "감성 카페",
    tags: ["카페", "신메뉴", "인스타 피드", "감성적인", "크림톤"],
    savedCount: 124,
    styleProfile: {
      colors: ["#FFF1E8", "#FFD0C6", "#F69A8F", "#E16054", "#6D4937"],
      layout: "상품을 중앙에 배치하고 넓은 여백으로 시선을 자연스럽게 집중시켜요.",
      copySpace: "우측 또는 상단에 여백을 두고 카피를 깔끔하게 배치해요.",
      mood: "감성적이고 따뜻한 카페 무드로 신메뉴와 시즌 메뉴에 잘 어울려요.",
      bestUse: "인스타 피드 1:1, 신메뉴 출시, 시즌 한정 메뉴, 음료/디저트 광고"
    }
  },
  {
    id: "ref-review-banner",
    title: "리뷰 이벤트 배너",
    subtitle: "부드러운 색감과 여백이 살아있는 광고 스타일",
    format: "배너",
    tone: "mint",
    badge: "리뷰 이벤트",
    tags: ["리뷰", "이벤트", "배너", "깔끔한", "민트톤"],
    savedCount: 88,
    styleProfile: {
      colors: ["#E8FBF5", "#BCEBE2", "#69D1B8", "#FFF8ED", "#334B45"],
      layout: "텍스트와 혜택 정보를 분리해 한눈에 읽히는 카드형 구성이에요.",
      copySpace: "좌측 상단에 이벤트 카피, 하단에 참여 조건을 두기 좋아요.",
      mood: "신뢰감 있고 산뜻한 분위기로 리뷰 이벤트나 재방문 유도에 적합해요.",
      bestUse: "배너, 리뷰 이벤트, 쿠폰 안내, 재방문 프로모션"
    }
  },
  {
    id: "ref-sale-story",
    title: "인스타 스토리",
    subtitle: "여름 시즌 할인 소식을 한눈에 보여주는 시안",
    format: "스토리",
    tone: "sunny",
    badge: "SUMMER SALE",
    tags: ["스토리", "할인", "여름", "강조형", "옐로우"],
    savedCount: 76,
    styleProfile: {
      colors: ["#FFF1B8", "#FFD05A", "#FFAD3D", "#FFFFFF", "#3F3221"],
      layout: "세로 화면에서 핵심 할인 문구를 크게 배치해 즉시 주목시키는 구조예요.",
      copySpace: "중앙 상단에는 혜택, 하단에는 날짜와 조건을 배치하기 좋아요.",
      mood: "밝고 경쾌한 할인 행사 무드로 빠른 반응을 만들기 좋아요.",
      bestUse: "인스타 스토리 9:16, 할인 이벤트, 시즌 세일, 당일 프로모션"
    }
  },
  {
    id: "ref-spring-sale",
    title: "시즌 할인 포스터",
    subtitle: "봄 시즌 할인 프로모션",
    format: "포스터",
    tone: "peach",
    badge: "SPRING SALE",
    tags: ["포스터", "시즌", "할인", "복숭아톤", "따뜻한"],
    savedCount: 102,
    styleProfile: {
      colors: ["#FFF0EA", "#FFD8D1", "#FFB3A7", "#E87E6E", "#68433B"],
      layout: "메인 오브젝트와 프로모션 문구를 균형 있게 배치한 포스터형 구성이에요.",
      copySpace: "좌측 또는 상단에 큰 제목, 하단에 세부 혜택을 넣기 좋아요.",
      mood: "따뜻하고 부드러운 계절감이 있어 봄 시즌 행사에 잘 맞아요.",
      bestUse: "포스터 4:5, 시즌 할인, 신상품 소개, 매장 안내"
    }
  }
];

export function getReferenceCreativeById(id: string): MockCreative | undefined {
  return referenceCreatives.find((creative) => creative.id === id);
}

export function getSimilarReferenceCreatives(id: string): MockCreative[] {
  const selected = getReferenceCreativeById(id) ?? referenceCreatives[0];
  return referenceCreatives
    .filter((creative) => creative.id !== selected.id)
    .sort((first, second) => {
      const firstToneMatch = first.tone === selected.tone ? -1 : 0;
      const secondToneMatch = second.tone === selected.tone ? -1 : 0;
      return firstToneMatch - secondToneMatch;
    });
}

export const recentCreatives: MockCreative[] = [
  {
    id: "recent-strawberry",
    title: "딸기라떼 신메뉴 광고",
    subtitle: "인스타 피드 (1:1)",
    format: "인스타 피드",
    date: "2024.05.29",
    tone: "strawberry",
    status: "saved",
    channel: "인스타 피드",
    fileName: "strawberry_latte_ad_01.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 14:30",
    tags: ["카페", "딸기라떼", "신메뉴"]
  },
  {
    id: "recent-cafe-sale",
    title: "카페 할인 이벤트",
    subtitle: "인스타 스토리 (9:16)",
    format: "인스타 스토리",
    date: "2024.05.25",
    tone: "cream",
    status: "saved",
    channel: "인스타 스토리",
    fileName: "cafe_sale_story_01.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.25 11:20",
    tags: ["카페", "할인", "스토리"]
  },
  {
    id: "recent-summer",
    title: "여름 시즌 포스터",
    subtitle: "포스터 (4:5)",
    format: "포스터",
    date: "2024.05.20",
    tone: "mint",
    status: "generating",
    progress: 68,
    channel: "포스터",
    fileName: "summer_season_poster.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.20 18:05",
    tags: ["여름", "시즌", "포스터"]
  }
];

export const resultCreatives: MockCreative[] = [
  {
    id: "result-1",
    title: "봄을 닮은 한 잔",
    subtitle: "오늘 저녁, 따뜻한 딸기라떼 한 잔",
    format: "1:1",
    tone: "strawberry",
    status: "saved",
    channel: "인스타 피드",
    fileName: "strawberry_latte_ad_01.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 14:30",
    tags: ["카페", "딸기라떼", "신메뉴", "인스타 피드"]
  },
  {
    id: "result-2",
    title: "New Strawberry Latte",
    subtitle: "상큼한 신메뉴 출시",
    format: "1:1",
    tone: "peach",
    status: "saved",
    channel: "인스타 피드",
    fileName: "strawberry_latte_ad_02.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 14:31",
    tags: ["카페", "영문", "신메뉴"]
  },
  {
    id: "result-3",
    title: "딸기 한가득 오늘의 신메뉴",
    subtitle: "매일 한정 수량",
    format: "4:5",
    tone: "cream",
    status: "favorite",
    channel: "포스터",
    fileName: "strawberry_latte_poster.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 14:32",
    tags: ["한정 수량", "포스터", "크림톤"]
  },
  {
    id: "result-4",
    title: "STRAWBERRY LATTE",
    subtitle: "부드럽고 산뜻한 시즌 메뉴",
    format: "1:1",
    tone: "mint",
    status: "saved",
    channel: "인스타 피드",
    fileName: "strawberry_latte_mint.png",
    fileType: "JPG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 14:33",
    tags: ["시즌 메뉴", "민트톤", "피드"]
  }
];

export const archivedCreatives: MockCreative[] = [
  ...resultCreatives,
  ...recentCreatives.filter((creative) => !resultCreatives.some((result) => result.id === creative.id)),
  {
    id: "archive-bakery",
    title: "베이커리 신제품",
    subtitle: "포스터 · 2024.05.29",
    format: "포스터",
    date: "2024.05.29",
    tone: "peach",
    status: "draft",
    channel: "포스터",
    fileName: "bakery_new_menu.png",
    fileType: "PNG",
    storage: "내 광고 보관함",
    savedAt: "2024.05.29 09:45",
    tags: ["베이커리", "신제품", "포스터"]
  }
];

export function getAdCreativeById(id: string): MockCreative | undefined {
  return archivedCreatives.find((creative) => creative.id === id);
}

export const myActivitySummary = {
  generatedAds: 12,
  savedAds: 8,
  activeJobs: 1,
  remainingCredits: 5,
  monthlyLimit: 20,
  usedCredits: 12,
  usagePercent: 60
};

export const usageHistory = [
  {
    id: "usage-strawberry",
    title: "딸기라떼 신메뉴 광고",
    createdAt: "2024.05.29 14:32",
    count: "1회 사용",
    tone: "strawberry" as CreativeTone
  },
  {
    id: "usage-cafe-sale",
    title: "카페 할인 이벤트",
    createdAt: "2024.05.28 11:10",
    count: "1회 사용",
    tone: "mint" as CreativeTone
  },
  {
    id: "usage-summer",
    title: "여름 시즌 포스터",
    createdAt: "2024.05.27 16:45",
    count: "1회 사용",
    tone: "sunny" as CreativeTone
  }
];

export const appSettings = [
  { id: "notifications", label: "알림 설정", value: "ON" },
  { id: "complete-alert", label: "생성 완료 알림", value: "ON" },
  { id: "promo-alert", label: "프로모션 알림", value: "OFF" },
  { id: "save-format", label: "기본 저장 형식", value: "PNG" },
  { id: "default-channel", label: "기본 사용 채널", value: "인스타 피드 1:1" },
  { id: "image-quality", label: "기본 이미지 품질", value: "고화질" },
  { id: "push-permission", label: "푸시 알림 허용", value: "ON" }
];

export const onboardingSlides = {
  intro: {
    title: "개떡처럼 말해도, 찰떡같이 광고로.",
    description: "디자인을 몰라도 괜찮아요. AI가 질문하고 제안하면서 광고 이미지를 만들 준비를 도와드려요.",
    features: [
      { title: "대충 말해도 OK", description: "원하는 광고를 편하게 말해요" },
      { title: "AI가 필요한 정보를 질문", description: "빠진 정보를 AI가 물어봐요" },
      { title: "찰떡 광고 이미지로 완성", description: "완성된 광고를 바로 활용해요" }
    ]
  },
  modes: {
    title: "원하는 방식으로 시작하세요",
    description: "가지고 있는 자료에 따라 가장 편한 방법을 선택할 수 있어요."
  },
  brief: {
    title: "AI가 질문하고 제안해 브리프를 완성해요",
    description: "업종, 상품, 목적, 문구, 분위기, 채널을 대화와 선택지로 자연스럽게 채워요."
  },
  start: {
    title: "이제 첫 찰떡 광고를 만들어볼까요?",
    description: "바로 시작해도 되고, 우리 가게 정보를 먼저 저장해도 좋아요."
  }
};

export const exceptionStateContent = {
  searchEmpty: {
    surfaceTitle: "샘플 검색",
    title: "검색 결과가 없어요",
    description: "다른 키워드로 다시 찾아보세요. 다양한 스타일의 광고를 추천해드릴게요!",
    query: "빈티지 카페 포스터",
    tone: "lime",
    suggestions: ["카페", "신메뉴", "할인 이벤트", "인스타 스토리", "감성", "포스터", "여름 시즌", "베이커리"]
  },
  archiveEmpty: {
    surfaceTitle: "내 찰떡 광고",
    title: "아직 만든 광고가 없어요",
    description: "첫 찰떡 광고를 만들어볼까요? 어떤 방법으로 시작할지 선택해보세요.",
    tone: "purple",
    actions: [
      { id: "reference", label: "샘플 보고 만들기", description: "마음에 드는 광고 스타일을 골라 만들어요" },
      { id: "photo", label: "내 사진으로 만들기", description: "우리 가게 사진으로 광고를 만들어요" },
      { id: "chat", label: "대화로 시작하기", description: "말로 설명하면 AI가 브리프를 제안해요" }
    ]
  },
  uploadFailed: {
    surfaceTitle: "사진 업로드",
    title: "사진을 업로드하지 못했어요",
    description: "파일 형식이나 용량을 확인해주세요.",
    tone: "mint",
    requirements: [
      { label: "지원 형식", value: "JPG, PNG, WEBP" },
      { label: "최대 용량", value: "10MB 이하" }
    ],
    tip: "이미지가 너무 크면 업로드가 안 될 수 있어요. 용량을 줄이거나 다른 사진을 선택해주세요."
  },
  generationFailed: {
    surfaceTitle: "광고 생성",
    title: "광고 생성에 실패했어요",
    description: "일시적인 문제로 시안을 만들지 못했어요. 브리프는 저장되어 있으니 다시 시도할 수 있어요.",
    tone: "coral",
    briefRows: [
      ["업종", "카페"],
      ["제품/서비스", "딸기라떼"],
      ["광고 목적", "신메뉴 출시"],
      ["채널", "인스타 피드 (1:1)"]
    ]
  }
};

export type MockNotificationType = "complete" | "progress" | "failed" | "brand";

export type MockNotification = {
  id: string;
  type: MockNotificationType;
  title: string;
  subtitle: string;
  time: string;
  ctaLabel: string;
  target: "complete" | "generating" | "failed" | "brand-kit";
  progress?: number;
  creativeId?: string;
};

export const mockNotifications: MockNotification[] = [
  {
    id: "notice-complete",
    type: "complete",
    title: "찰떡 광고 시안이 완성됐어요",
    subtitle: "딸기라떼 신메뉴 광고",
    time: "방금 전",
    ctaLabel: "결과 확인하기",
    target: "complete",
    creativeId: "result-1"
  },
  {
    id: "notice-progress",
    type: "progress",
    title: "광고 생성 중이에요",
    subtitle: "카페 할인 이벤트",
    time: "2분 전",
    ctaLabel: "진행 상황 보기",
    target: "generating",
    progress: 68
  },
  {
    id: "notice-failed",
    type: "failed",
    title: "광고 생성에 실패했어요",
    subtitle: "리뷰 이벤트 포스터",
    time: "3분 전",
    ctaLabel: "다시 시도",
    target: "failed"
  },
  {
    id: "notice-brand",
    type: "brand",
    title: "브랜드 파일이 저장됐어요",
    subtitle: "저장된 브랜드 파일 정보가 다음 광고에 적용돼요.",
    time: "10분 전",
    ctaLabel: "브랜드 파일 보기",
    target: "brand-kit"
  }
];

export const notificationSettings = [
  {
    id: "generation-complete",
    label: "생성 완료 알림",
    description: "광고가 완성되면 알려드려요.",
    enabled: true
  },
  {
    id: "generation-failed",
    label: "생성 실패 알림",
    description: "생성 실패 시 원인과 대안을 알려드려요.",
    enabled: true
  },
  {
    id: "save-complete",
    label: "저장 완료 알림",
    description: "광고를 저장하면 알려드려요.",
    enabled: true
  },
  {
    id: "brand-kit",
    label: "브랜드 파일 알림",
    description: "브랜드 파일 변경/저장 시 알려드려요.",
    enabled: true
  },
  {
    id: "reference",
    label: "추천 샘플 알림",
    description: "새로운 스타일을 추천해드려요.",
    enabled: false
  },
  {
    id: "promotion",
    label: "프로모션 알림",
    description: "이벤트 및 혜택 정보를 알려드려요.",
    enabled: false
  }
];

export const notificationChannels = [
  { id: "in-app", label: "앱 내 알림", enabled: true },
  { id: "push", label: "푸시 알림", enabled: true },
  { id: "email", label: "이메일 알림", enabled: false }
];
