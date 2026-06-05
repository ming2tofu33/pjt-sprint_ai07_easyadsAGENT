import Link from "next/link";
import { Home, Sparkles } from "lucide-react";
import { getSafeAuthRedirectPath } from "@/lib/auth-navigation";
import styles from "./login.module.css";
import { LoginClient } from "./LoginClient";

type LoginPageProps = {
  searchParams?: {
    next?: string | string[];
    error?: string | string[];
  };
};

function firstSearchValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function authErrorMessage(error: string | undefined): string | null {
  if (!error) {
    return null;
  }

  if (error === "missing_env") {
    return "로그인 환경변수가 아직 설정되지 않았어요.";
  }

  if (error === "missing_code") {
    return "로그인 응답을 확인할 수 없어요. 다시 시도해 주세요.";
  }

  if (error === "auth_failed") {
    return "Google 로그인 연결이 완료되지 않았어요. 다시 시도해 주세요.";
  }

  return "로그인을 다시 시도해 주세요.";
}

export default function LoginPage({ searchParams }: LoginPageProps) {
  const nextPath = getSafeAuthRedirectPath(firstSearchValue(searchParams?.next));
  const errorMessage = authErrorMessage(firstSearchValue(searchParams?.error));

  return (
    <main className={styles.page}>
      <section className={styles.phone} aria-label="로그인">
        <div className={styles.body}>
          <header className={styles.header}>
            <div>
              <p className={styles.eyebrow}>LOGIN</p>
              <h1>로그인</h1>
            </div>
            <Link className={styles.ghostLink} href="/" aria-label="홈으로 이동">
              <Home size={18} aria-hidden="true" />
            </Link>
          </header>

          <section className={styles.hero}>
            <span className={styles.heroIcon} aria-hidden="true">
              <Sparkles size={28} />
            </span>
            <h2>Google 계정으로 광고 작업을 이어가세요.</h2>
            <p>로그인하면 만든 결과와 브랜드 정보를 같은 계정에서 이어서 관리할 수 있어요.</p>
          </section>

          {errorMessage ? <p className={styles.errorText}>{errorMessage}</p> : null}

          <LoginClient nextPath={nextPath} />
        </div>
      </section>
    </main>
  );
}
