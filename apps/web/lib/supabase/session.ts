"use client";

import type { Session } from "@supabase/supabase-js";

export type RequestHeaders = Record<string, string>;

export type SupabaseAuthorizationOptions = {
  allowAnonymous?: boolean;
  forceRefresh?: boolean;
};

export class SupabaseGuestSessionError extends Error {
  constructor(message = "게스트 작업 공간을 준비하지 못했어요. 잠시 후 다시 시도해주세요.") {
    super(message);
    this.name = "SupabaseGuestSessionError";
  }
}

function sessionToken(session: Session | null | undefined): string | null {
  const token = session?.access_token;
  return typeof token === "string" && token.trim() ? token : null;
}

let anonymousSignInPromise: Promise<string> | null = null;

function clearAnonymousSignInPromiseAfterCurrentTick(promise: Promise<string>) {
  setTimeout(() => {
    if (anonymousSignInPromise === promise) {
      anonymousSignInPromise = null;
    }
  }, 0);
}

async function createAnonymousAccessToken(supabase: ReturnType<typeof import("./browser").createSupabaseBrowserClient>) {
  if (!supabase || typeof supabase.auth.signInAnonymously !== "function") {
    throw new SupabaseGuestSessionError();
  }

  const result = await supabase.auth.signInAnonymously({
    options: {
      data: {
        account_type: "guest",
        source: "easyads_web"
      }
    }
  });

  if (!result) {
    throw new SupabaseGuestSessionError();
  }

  const { data, error } = result;

  if (error) {
    throw new SupabaseGuestSessionError();
  }

  const guestToken = sessionToken(data.session);
  if (!guestToken) {
    throw new SupabaseGuestSessionError();
  }
  return guestToken;
}

async function refreshAccessToken(
  supabase: ReturnType<typeof import("./browser").createSupabaseBrowserClient>
): Promise<string | null> {
  if (!supabase || typeof supabase.auth.refreshSession !== "function") {
    return null;
  }
  const result = await supabase.auth.refreshSession();
  if (!result || result.error) {
    return null;
  }
  return sessionToken(result.data.session);
}

export async function getSupabaseAccessToken(options: SupabaseAuthorizationOptions = {}): Promise<string | null> {
  if (typeof window === "undefined") {
    return null;
  }

  const { createSupabaseBrowserClient } = await import("./browser");
  const supabase = createSupabaseBrowserClient();
  if (!supabase) {
    return null;
  }

  if (options.forceRefresh) {
    const refreshedToken = await refreshAccessToken(supabase);
    if (refreshedToken) {
      return refreshedToken;
    }
    if (options.allowAnonymous === false) {
      return null;
    }
  }

  const {
    data: { session }
  } = await supabase.auth.getSession();
  const currentToken = sessionToken(session);
  if (currentToken) {
    return currentToken;
  }

  if (options.allowAnonymous === false) {
    return null;
  }

  const signInPromise =
    anonymousSignInPromise ?? (anonymousSignInPromise = createAnonymousAccessToken(supabase));

  try {
    return await signInPromise;
  } finally {
    clearAnonymousSignInPromiseAfterCurrentTick(signInPromise);
  }
}

export async function getSupabaseAuthorizationHeader(
  options: SupabaseAuthorizationOptions = {}
): Promise<RequestHeaders> {
  const token = await getSupabaseAccessToken(options);
  return token ? { authorization: `Bearer ${token}` } : {};
}
