"use client";

import { ArrowLeft, AlertTriangle, Briefcase, ChevronRight, Home, LogIn, LogOut, Mail, MapPin, Search, Sparkles, Store, Trash2, User } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { buildLoginHref } from "@/lib/auth-navigation";
import { buildBrandKitHref } from "@/lib/brand-kit-navigation";
import { brandKitFromServerResponse, brandKitMeta, brandKitProducts, brandKitTone, readSavedBrandKit, type StoredBrandKit } from "@/lib/brand-kit-storage";
import { getCurrentBrandKit } from "@/lib/api-client";
import { buildDashboardHref } from "@/lib/dashboard-navigation";
import { buildMyHref } from "@/lib/my-navigation";
import { goBackOrPush } from "@/lib/navigation-history";
import { deleteCurrentAccount } from "@/lib/account-delete";
import { getCurrentAppUserProfile, signOutAppUser } from "@/lib/user-auth-client";
import type { AppUserProfile } from "@/lib/user-profile";
import styles from "./generate.module.css";

type AccountAuthState = "loading" | "guest" | "signedIn";

export function AccountInfoStep() {
  const router = useRouter();
  const [brandKit, setBrandKit] = useState<StoredBrandKit | null>(null);
  const [userProfile, setUserProfile] = useState<AppUserProfile | null>(null);
  const [authState, setAuthState] = useState<AccountAuthState>("loading");
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [accountActionMessage, setAccountActionMessage] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;
    setBrandKit(readSavedBrandKit());
    void getCurrentAppUserProfile().then((profile) => {
      if (!isActive) {
        return;
      }
      setUserProfile(profile);
      setAuthState(profile ? "signedIn" : "guest");
      if (!profile) {
        return;
      }
      // Server brand kit wins over the local fallback for signed-in users.
      void getCurrentBrandKit({ userId: profile.id })
        .then((payload) => {
          if (!isActive) {
            return;
          }
          const serverBrandKit = brandKitFromServerResponse(payload);
          if (serverBrandKit) {
            setBrandKit(serverBrandKit);
          }
        })
        .catch(() => {
          // Keep the local fallback already set above.
        });
    });

    return () => {
      isActive = false;
    };
  }, []);

  async function handleSignOut() {
    setAccountActionMessage(null);
    setIsSigningOut(true);
    await signOutAppUser();
    setUserProfile(null);
    setAuthState("guest");
    setIsSigningOut(false);
    router.replace(buildMyHref());
    router.refresh();
  }

  async function handleDeleteAccount() {
    if (!userProfile || isDeletingAccount) {
      return;
    }

    const confirmed = window.confirm("계정을 삭제하면 로그인 정보와 프로필이 삭제됩니다. 계속할까요?");
    if (!confirmed) {
      return;
    }

    setAccountActionMessage(null);
    setIsDeletingAccount(true);
    const result = await deleteCurrentAccount();

    if (!result.success) {
      setIsDeletingAccount(false);
      setAccountActionMessage(result.message);
      return;
    }

    await signOutAppUser().catch(() => {
      // The server already removed the user; this only clears local session state.
    });
    setUserProfile(null);
    setAuthState("guest");
    setIsDeletingAccount(false);
    router.replace(buildMyHref());
    router.refresh();
  }

  const isBusy = authState === "loading" || isSigningOut || isDeletingAccount;
  const accountName = authState === "loading" ? "계정 확인 중" : userProfile?.displayName ?? "Google 로그인 필요";
  const accountEmail = authState === "loading" ? "로그인 상태를 확인하고 있어요." : userProfile?.email ?? "Google 계정으로 로그인하면 표시됩니다.";
  const loginMethod = authState === "loading" ? "확인 중" : userProfile?.loginMethod ?? "Google 계정 로그인 전";

  return (
    <>
      <header className={styles.stepHeader}>
        <button aria-label="뒤로" type="button" onClick={() => goBackOrPush(router, buildMyHref())}>
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
            <dd>{accountName}</dd>
          </div>
          <div>
            <dt>
              <Mail size={17} aria-hidden="true" />
              이메일
            </dt>
            <dd>{accountEmail}</dd>
          </div>
          <div>
            <dt>연결 계정</dt>
            <dd>{loginMethod}</dd>
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

      <button className={styles.myLinkedBrandCard} type="button" onClick={() => router.push(buildBrandKitHref(brandKit ? "complete" : "start"))}>
        <Store size={24} aria-hidden="true" />
        <strong>
          {brandKit?.businessName ?? "브랜드 파일 연결 전"}
          <small>
            {brandKit ? `${brandKitTone(brandKit)} · 대표 상품: ${brandKitProducts(brandKit)} · ${brandKitMeta(brandKit)}` : "가게 정보를 입력하면 여기에 표시됩니다."}
          </small>
        </strong>
        <ChevronRight size={18} aria-hidden="true" />
      </button>

      {accountActionMessage ? (
        <p className={styles.accountActionNotice} role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          {accountActionMessage}
        </p>
      ) : null}

      <div className={styles.myStackedActions}>
        {authState === "signedIn" ? (
          <button className={styles.secondaryButton} disabled={isBusy} type="button" onClick={handleSignOut}>
            <LogOut size={17} aria-hidden="true" />
            {isSigningOut ? "로그아웃 중" : "로그아웃"}
          </button>
        ) : (
          <button className={styles.secondaryButton} disabled={isBusy} type="button" onClick={() => router.push(buildLoginHref(buildMyHref("account")))}>
            <LogIn size={17} aria-hidden="true" />
            {authState === "loading" ? "계정 확인 중" : "Google 계정으로 로그인"}
          </button>
        )}
        <button className={styles.secondaryButton} type="button" onClick={() => router.push(buildBrandKitHref("info"))}>
          브랜드 파일 수정
        </button>
        {authState === "signedIn" ? (
          <button className={styles.secondaryButton} data-danger="true" disabled={isBusy} type="button" onClick={handleDeleteAccount}>
            <Trash2 size={17} aria-hidden="true" />
            {isDeletingAccount ? "계정 삭제 중" : "계정 삭제"}
          </button>
        ) : null}
      </div>

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
        <button data-active="true" type="button" onClick={() => router.push(buildMyHref())}>
          <User size={18} aria-hidden="true" />
          마이페이지
        </button>
      </nav>
    </>
  );
}
