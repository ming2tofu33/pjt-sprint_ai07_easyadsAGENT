import type { User } from "@supabase/supabase-js";

export type AppUserProfile = {
  id: string;
  email: string;
  displayName: string;
  loginMethod: string;
  avatarUrl: string | null;
};

function stringMetadataValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

export function getDisplayNameFromUser(user: Pick<User, "email" | "user_metadata">): string {
  return (
    stringMetadataValue(user.user_metadata?.full_name) ??
    stringMetadataValue(user.user_metadata?.name) ??
    stringMetadataValue(user.user_metadata?.preferred_username) ??
    user.email?.split("@")[0] ??
    "로그인 사용자"
  );
}

export function getLoginMethodFromUser(user: Pick<User, "app_metadata" | "identities">): string {
  const provider =
    stringMetadataValue(user.app_metadata?.provider) ??
    stringMetadataValue(user.identities?.[0]?.provider);

  if (provider === "google") {
    return "Google 계정";
  }

  return "Google 계정 확인 필요";
}

export function buildAppUserProfile(user: User | null): AppUserProfile | null {
  if (!user) {
    return null;
  }

  return {
    id: user.id,
    email: user.email ?? "이메일 확인 전",
    displayName: getDisplayNameFromUser(user),
    loginMethod: getLoginMethodFromUser(user),
    avatarUrl: stringMetadataValue(user.user_metadata?.avatar_url) ?? stringMetadataValue(user.user_metadata?.picture)
  };
}
