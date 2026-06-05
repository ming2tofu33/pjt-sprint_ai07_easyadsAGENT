export type AccountDeleteResult =
  | { success: true }
  | {
      success: false;
      errorCode: string;
      message: string;
    };

type AccountDeletePayload = {
  success?: boolean;
  error_code?: string;
  message?: string;
};

export function getAccountDeleteErrorMessage(errorCode: string | undefined, fallback?: string): string {
  if (errorCode === "not_authenticated") {
    return "로그인 상태를 확인하지 못했어요. 다시 로그인한 뒤 시도해주세요.";
  }
  if (errorCode === "account_delete_not_configured") {
    return "계정 삭제 설정이 아직 연결되지 않았어요. 서버 환경변수를 확인해주세요.";
  }
  if (errorCode === "auth_not_configured") {
    return "로그인 설정이 아직 연결되지 않았어요. 개발 서버를 다시 실행해 주세요.";
  }
  if (errorCode === "profile_delete_failed" || errorCode === "auth_delete_failed") {
    return "계정 삭제 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.";
  }
  return fallback || "계정 삭제에 실패했어요. 잠시 후 다시 시도해주세요.";
}

export async function deleteCurrentAccount(fetchImpl: typeof fetch = fetch): Promise<AccountDeleteResult> {
  const response = await fetchImpl("/api/account/delete", {
    method: "DELETE",
    headers: { accept: "application/json" }
  });
  const payload = (await response.json().catch(() => ({}))) as AccountDeletePayload;

  if (!response.ok || payload.success === false) {
    const errorCode = payload.error_code || "account_delete_failed";
    return {
      success: false,
      errorCode,
      message: getAccountDeleteErrorMessage(errorCode, payload.message)
    };
  }

  return { success: true };
}
