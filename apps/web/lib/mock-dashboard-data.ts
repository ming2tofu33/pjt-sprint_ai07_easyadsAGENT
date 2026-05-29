export type CreativeTone = "strawberry" | "mint" | "cream" | "sunny" | "peach";

export type MockCreative = {
  id: string;
  title: string;
  subtitle: string;
  format: string;
  date?: string;
  tone: CreativeTone;
  badge?: string;
};

export const referenceCreatives: MockCreative[] = [
  {
    id: "ref-strawberry-poster",
    title: "감성 카페 신메뉴 포스터",
    subtitle: "봄을 닮은 한 잔, 딸기라떼 출시",
    format: "포스터",
    tone: "strawberry",
    badge: "감성 카페"
  },
  {
    id: "ref-review-banner",
    title: "리뷰 이벤트 배너",
    subtitle: "부드러운 색감과 여백이 살아있는 광고 스타일",
    format: "배너",
    tone: "mint",
    badge: "리뷰 이벤트"
  },
  {
    id: "ref-sale-story",
    title: "인스타 스토리",
    subtitle: "여름 시즌 할인 소식을 한눈에 보여주는 시안",
    format: "스토리",
    tone: "sunny",
    badge: "SUMMER SALE"
  },
  {
    id: "ref-spring-sale",
    title: "시즌 할인 포스터",
    subtitle: "봄 시즌 할인 프로모션",
    format: "포스터",
    tone: "peach",
    badge: "SPRING SALE"
  }
];

export const recentCreatives: MockCreative[] = [
  {
    id: "recent-strawberry",
    title: "딸기라떼 신메뉴 광고",
    subtitle: "인스타 피드 (1:1)",
    format: "인스타 피드",
    date: "2024.05.29",
    tone: "strawberry"
  },
  {
    id: "recent-cafe-sale",
    title: "카페 할인 이벤트",
    subtitle: "인스타 스토리 (9:16)",
    format: "인스타 스토리",
    date: "2024.05.25",
    tone: "cream"
  },
  {
    id: "recent-summer",
    title: "여름 시즌 포스터",
    subtitle: "포스터 (4:5)",
    format: "포스터",
    date: "2024.05.20",
    tone: "mint"
  }
];

export const resultCreatives: MockCreative[] = [
  {
    id: "result-1",
    title: "봄을 닮은 한 잔",
    subtitle: "오늘 저녁, 따뜻한 딸기라떼 한 잔",
    format: "1:1",
    tone: "strawberry"
  },
  {
    id: "result-2",
    title: "New Strawberry Latte",
    subtitle: "상큼한 신메뉴 출시",
    format: "1:1",
    tone: "peach"
  },
  {
    id: "result-3",
    title: "딸기 한가득 오늘의 신메뉴",
    subtitle: "매일 한정 수량",
    format: "4:5",
    tone: "cream"
  },
  {
    id: "result-4",
    title: "STRAWBERRY LATTE",
    subtitle: "부드럽고 산뜻한 시즌 메뉴",
    format: "1:1",
    tone: "mint"
  }
];

export const brandFacts = {
  name: "도민 카페",
  status: "사용 중",
  meta: "카페 · 성수동 감성 상권 · @domin_cafe",
  tone: "감성적인, 따뜻한",
  colors: ["#D7B48B", "#FFD7C9", "#D8A29B"],
  products: "딸기라떼, 바닐라라떼, 크림라떼",
  phrases: "신메뉴 출시, 매일 한정 수량, 예약은 DM"
};
