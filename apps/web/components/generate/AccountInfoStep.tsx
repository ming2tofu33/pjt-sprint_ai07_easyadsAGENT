"use client";

import { ArrowLeft, Briefcase, ChevronRight, Home, Mail, MapPin, Search, Sparkles, Store, User } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { brandKitMeta, brandKitProducts, brandKitTone, readSavedBrandKit, type StoredBrandKit } from "@/lib/brand-kit-storage";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { myProfile } from "@/lib/mock-dashboard-data";
import { buildMyHref } from "@/lib/my-navigation";
import styles from "./generate.module.css";

export function AccountInfoStep() {
  const router = useRouter();
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);

  useEffect(() => {
    setBrandKit(readSavedBrandKit());
  }, []);

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => router.push(buildMyHref())}>
          <ArrowLeft size={20} aria-hidden="true" />
        </button>
        <h1>계정 및 가게 정보</h1>
        <span />
      </header>

      <section className={styles.myInfoCard}>
        <h2>계정 정보</h2>
        <dl>
          <div>
            <dt>
              <User size={17} aria-hidden="true" />
              이름
            </dt>
            <dd>{myProfile.ownerName}</dd>
          </div>
          <div>
            <dt>
              <Mail size={17} aria-hidden="true" />
              이메일
            </dt>
            <dd>{myProfile.email}</dd>
          </div>
          <div>
            <dt>로그인 방식</dt>
            <dd>{myProfile.loginMethod}</dd>
          </div>
        </dl>
      </section>

      <section className={styles.myInfoCard}>
        <h2>가게 정보</h2>
        <dl>
          <div>
            <dt>
              <Store size={17} aria-hidden="true" />
              가게 이름
            </dt>
            <dd>{brandKit?.businessName ?? "등록 전"}</dd>
          </div>
          <div>
            <dt>업종</dt>
            <dd>{brandKit?.businessType ?? "등록 전"}</dd>
          </div>
          <div>
            <dt>
              <MapPin size={17} aria-hidden="true" />
              지역 / 상권
            </dt>
            <dd>{brandKit?.region || "등록 전"}</dd>
          </div>
          <div>
            <dt>SNS 계정</dt>
            <dd>{brandKit?.sns || "등록 전"}</dd>
          </div>
        </dl>
      </section>

      <button className={styles.myLinkedBrandCard} type="button" onClick={() => router.push(buildBrandKitHref(brandKit ? "complete" : "info"))}>
        <Store size={24} aria-hidden="true" />
        <strong>
          {brandKit?.businessName ?? "브랜드 키트 연결 전"}
          <small>
            {brandKit ? `${brandKitTone(brandKit)} · 대표 상품: ${brandKitProducts(brandKit)} · ${brandKitMeta(brandKit)}` : "가게 정보를 입력하면 여기에 표시됩니다."}
          </small>
        </strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      <div className={styles.myStackedActions}>
        <button className={styles.secondaryButton} type="button">
          계정 정보 수정
        </button>
        <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
          브랜드 키트 수정
        </button>
      </div>

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
        <button data-active="true" type="button" onClick={() => router.push(buildMyHref())}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
